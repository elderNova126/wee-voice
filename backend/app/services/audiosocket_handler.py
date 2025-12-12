"""
Asterisk AudioSocket Handler

Uses threading instead of asyncio for immediate frame sending.
This matches what works in the standalone server.
"""
import asyncio
import socket
import struct
import threading
import time
import logging
import audioop
import uuid as uuid_lib
from typing import Optional
from datetime import datetime
from queue import Queue, Empty

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
from app.services.agent_service import FrenchVoiceAgentService
from app.api.websocket import auto_summarize_call

logger = logging.getLogger(__name__)

MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

FRAME_SIZE = 320  # 160 samples * 2 bytes = 20ms at 8kHz
SILENCE_FRAME = b'\x00' * FRAME_SIZE


class AudioSocketSession:
    """Handles AudioSocket connection using threads (not asyncio)"""
    
    def __init__(self, conn: socket.socket, addr):
        self.conn = conn
        self.addr = addr
        self.call_uuid = None
        self.call = None
        self.agent = None
        self.agent_service = None
        self.is_running = False
        self.db = None
        self.ai_audio_queue = Queue()
        self.ai_ready = threading.Event()
        
    def handle(self):
        """Main handler - runs in thread"""
        logger.info(f"AudioSocket connection from {self.addr}")
        
        try:
            self.is_running = True
            self.conn.settimeout(60)
            
            # Start sender thread IMMEDIATELY
            sender_thread = threading.Thread(target=self._send_loop, daemon=True)
            sender_thread.start()
            
            # Read UUID
            self._read_uuid()
            if not self.call_uuid:
                logger.error("No UUID received")
                return
            
            logger.info(f"Call UUID: {self.call_uuid}")
            
            # Setup call with AI (this takes time)
            if not self._setup_call():
                return
            
            # Signal AI is ready
            self.ai_ready.set()
            
            # Start AI audio task
            ai_thread = threading.Thread(target=self._ai_audio_loop, daemon=True)
            ai_thread.start()
            
            # Main receive loop
            self._receive_loop()
            
        except Exception as e:
            logger.error(f"AudioSocket error: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    def _send_loop(self):
        """Send audio frames to Asterisk"""
        frames_sent = 0
        try:
            while self.is_running:
                # Get AI audio if available, otherwise send silence
                try:
                    audio_data = self.ai_audio_queue.get_nowait()
                except Empty:
                    audio_data = SILENCE_FRAME
                
                # Send frame
                header = struct.pack('>BH', MSG_AUDIO, len(audio_data))
                self.conn.sendall(header + audio_data)
                frames_sent += 1
                
                if frames_sent == 1:
                    logger.info("First audio frame sent to Asterisk")
                
                time.sleep(0.02)  # 20ms = 50fps
                
        except Exception as e:
            if self.is_running:
                logger.error(f"Send loop error: {e}")
        
        logger.info(f"Send loop ended, sent {frames_sent} frames")
    
    def _receive_loop(self):
        """Receive audio from Asterisk"""
        frames_received = 0
        try:
            while self.is_running:
                # Read header
                header = self._read_exact(3)
                if not header:
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                # Read payload
                payload = self._read_exact(payload_len) if payload_len > 0 else b''
                if payload_len > 0 and not payload:
                    break
                
                if msg_type == MSG_AUDIO:
                    frames_received += 1
                    if frames_received == 1:
                        logger.info("First audio frame from Asterisk")
                    self._process_audio(payload)
                elif msg_type == MSG_HANGUP:
                    logger.info("Hangup received")
                    break
                elif msg_type == MSG_ERROR:
                    logger.error(f"Error from Asterisk")
                    break
                    
        except socket.timeout:
            logger.info("Receive timeout")
        except Exception as e:
            if self.is_running:
                logger.error(f"Receive error: {e}")
        
        logger.info(f"Receive loop ended, got {frames_received} frames")
    
    def _read_exact(self, n: int) -> Optional[bytes]:
        """Read exactly n bytes"""
        data = b''
        while len(data) < n:
            try:
                chunk = self.conn.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except:
                return None
        return data
    
    def _read_uuid(self):
        """Read UUID packet"""
        try:
            header = self._read_exact(3)
            if not header:
                self.call_uuid = str(uuid_lib.uuid4())
                return
            
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            if msg_type == MSG_UUID and payload_len > 0:
                uuid_bytes = self._read_exact(payload_len)
                if uuid_bytes:
                    try:
                        self.call_uuid = uuid_bytes.decode('ascii').strip()
                        if len(self.call_uuid) == 36:
                            return
                    except:
                        pass
            
            self.call_uuid = str(uuid_lib.uuid4())
        except:
            self.call_uuid = str(uuid_lib.uuid4())
    
    def _setup_call(self) -> bool:
        """Setup call record and AI"""
        self.db = SessionLocal()
        try:
            # Find agent
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None)
            ).first()
            
            if phone and phone.agent_id:
                self.agent = self.db.query(VoiceAgent).filter(
                    VoiceAgent.id == phone.agent_id
                ).first()
            
            if not self.agent:
                self.agent = self.db.query(VoiceAgent).first()
            
            if not self.agent:
                logger.error("No agent found")
                return False
            
            # Create call record
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone="unknown",
                caller_name="Caller",
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"audiosocket_{self.call_uuid}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            logger.info(f"Created call {self.call.id}")
            
            # Initialize AI
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            
            # Run async start_session in a new event loop
            loop = asyncio.new_event_loop()
            try:
                success = loop.run_until_complete(self.agent_service.start_session())
            finally:
                loop.close()
            
            if not success:
                logger.error("Failed to start Gemini")
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            logger.info(f"Call {self.call.id} ready")
            return True
            
        except Exception as e:
            logger.error(f"Setup error: {e}", exc_info=True)
            return False
    
    def _process_audio(self, audio_8k: bytes):
        """Process incoming audio from Asterisk, send to AI"""
        if not self.agent_service or not self.ai_ready.is_set():
            return
        if len(audio_8k) < 2:
            return
        
        try:
            # Ensure even bytes
            if len(audio_8k) % 2:
                audio_8k = audio_8k[:-1]
            
            # Upsample 8kHz -> 16kHz
            audio_16k, _ = audioop.ratecv(audio_8k, 2, 1, 8000, 16000, None)
            
            # Send to AI (async call in sync context)
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.agent_service.send_audio(audio_16k))
            finally:
                loop.close()
        except:
            pass
    
    def _ai_audio_loop(self):
        """Receive audio from AI and queue for sending"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def receive():
                async for audio_24k in self.agent_service.receive_audio():
                    if not self.is_running:
                        break
                    if not audio_24k or len(audio_24k) < 2:
                        continue
                    
                    # Ensure even bytes
                    if len(audio_24k) % 2:
                        audio_24k = audio_24k[:-1]
                    
                    # Downsample 24kHz -> 8kHz
                    audio_8k, _ = audioop.ratecv(audio_24k, 2, 1, 24000, 8000, None)
                    
                    # Queue for sender
                    self.ai_audio_queue.put(audio_8k)
            
            loop.run_until_complete(receive())
        except Exception as e:
            if self.is_running:
                logger.error(f"AI audio error: {e}")
    
    def _cleanup(self):
        """Cleanup resources"""
        logger.info(f"Cleaning up {self.call_uuid}")
        self.is_running = False
        
        # End AI session
        if self.agent_service:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.agent_service.end_session())
                loop.close()
            except:
                pass
        
        # Update call record
        if self.call and self.db:
            try:
                self.db.refresh(self.call)
                self.call.ended_at = datetime.utcnow()
                self.call.calculate_duration_and_cost()
                self.call.status = CallStatus.SUMMARIZING
                self.db.commit()
                
                # Summarize async
                call_id = self.call.id
                def summarize():
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(auto_summarize_call(call_id))
                    loop.close()
                threading.Thread(target=summarize, daemon=True).start()
            except:
                pass
            finally:
                self.db.close()
        
        # Close socket
        try:
            self.conn.close()
        except:
            pass


class AudioSocketServer:
    """TCP server using threads (not asyncio)"""
    
    def __init__(self, host='0.0.0.0', port=9092):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
    
    async def start(self):
        """Start the server"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        logger.info(f"AudioSocket server on {self.host}:{self.port}")
        print(f"[AudioSocket] Starting AudioSocket server...")
        print(f"[AudioSocket] ✅ AudioSocket server started on port {self.port}")
        
        # Accept connections in a thread
        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()
    
    def _accept_loop(self):
        """Accept connections"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                # Handle each connection in a new thread
                handler = threading.Thread(
                    target=self._handle_connection,
                    args=(conn, addr),
                    daemon=True
                )
                handler.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")
    
    def _handle_connection(self, conn, addr):
        """Handle a connection"""
        session = AudioSocketSession(conn, addr)
        session.handle()
    
    async def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


audiosocket_server = AudioSocketServer()
