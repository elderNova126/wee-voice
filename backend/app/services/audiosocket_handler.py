"""
Asterisk AudioSocket Handler

IMPORTANT: Asterisk expects audio frames IMMEDIATELY after connection.
We must send silence/keepalive while waiting for AI to initialize.
"""
import asyncio
import logging
import struct
import audioop
import uuid as uuid_lib
from typing import Optional
from datetime import datetime

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

# 160 samples at 8kHz = 20ms of audio (standard frame size)
FRAME_SIZE = 320  # 160 samples * 2 bytes per sample
SILENCE_FRAME = b'\x00' * FRAME_SIZE


class AudioSocketSession:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.call_uuid = None
        self.call = None
        self.agent = None
        self.agent_service = None
        self.is_running = False
        self.db = None
        self.audio_send_task = None
        self.keepalive_task = None
        self.ai_ready = asyncio.Event()
        self._write_lock = asyncio.Lock()
        
    async def handle(self):
        addr = self.writer.get_extra_info('peername')
        logger.info(f"AudioSocket connection from {addr}")
        
        try:
            self.is_running = True
            
            # Start keepalive IMMEDIATELY to prevent Asterisk timeout
            self.keepalive_task = asyncio.create_task(self._keepalive_loop())
            
            # Now read UUID
            await self._read_uuid()
            
            if not self.call_uuid:
                logger.error("No UUID")
                return
            
            logger.info(f"Call UUID: {self.call_uuid}")
            
            # Setup call (this starts Gemini)
            if not await self._setup_call():
                return
            
            # Signal that AI is ready - stop keepalive, start real audio
            self.ai_ready.set()
            
            # Main audio receive loop
            await self._audio_receive_loop()
                    
        except Exception as e:
            logger.error(f"AudioSocket error: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _keepalive_loop(self):
        """Send silence frames to keep Asterisk happy while AI initializes"""
        logger.info("Keepalive started - sending silence to Asterisk")
        frames_sent = 0
        try:
            while self.is_running and not self.ai_ready.is_set():
                await self._send_frame(SILENCE_FRAME)
                frames_sent += 1
                # Send at ~50fps (20ms per frame)
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Keepalive error: {e}")
        logger.info(f"Keepalive ended after {frames_sent} silence frames")
    
    async def _send_frame(self, audio_data: bytes):
        """Send a single audio frame to Asterisk"""
        try:
            async with self._write_lock:
                header = struct.pack('>BH', MSG_AUDIO, len(audio_data))
                self.writer.write(header + audio_data)
                await self.writer.drain()
        except Exception as e:
            logger.error(f"Send frame error: {e}")
            self.is_running = False
    
    async def _read_uuid(self):
        """Read UUID from first packet"""
        try:
            # Read header (3 bytes)
            header = await asyncio.wait_for(self._read_exact(3), timeout=5.0)
            if not header or len(header) < 3:
                self.call_uuid = str(uuid_lib.uuid4())
                return
            
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            logger.info(f"UUID header: type=0x{msg_type:02x}, len={payload_len}")
            
            if msg_type == MSG_UUID and payload_len > 0:
                uuid_bytes = await asyncio.wait_for(
                    self._read_exact(payload_len), 
                    timeout=5.0
                )
                if uuid_bytes:
                    # Try to decode as ASCII
                    try:
                        self.call_uuid = uuid_bytes.decode('ascii').strip('\x00').strip()
                        # Validate format
                        if len(self.call_uuid) == 36 and self.call_uuid.count('-') == 4:
                            logger.info(f"Valid UUID received: {self.call_uuid}")
                            return
                    except:
                        pass
                    
                    logger.warning(f"Invalid UUID format, generating new")
            
            self.call_uuid = str(uuid_lib.uuid4())
            logger.info(f"Generated UUID: {self.call_uuid}")
                
        except Exception as e:
            logger.error(f"UUID read error: {e}")
            self.call_uuid = str(uuid_lib.uuid4())
    
    async def _read_exact(self, n: int) -> Optional[bytes]:
        """Read exactly n bytes from the socket"""
        data = b''
        remaining = n
        while remaining > 0:
            try:
                chunk = await self.reader.read(remaining)
                if not chunk:
                    return None
                data += chunk
                remaining -= len(chunk)
            except Exception:
                return None
        return data

    async def _setup_call(self) -> bool:
        """Setup call record and initialize AI agent"""
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
            
            # Initialize Gemini
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            if not await self.agent_service.start_session():
                logger.error("Failed to start Gemini")
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            # Start audio send task (real AI audio)
            self.audio_send_task = asyncio.create_task(self._audio_send_loop())
            
            logger.info(f"Call {self.call.id} ready")
            return True
            
        except Exception as e:
            logger.error(f"Setup error: {e}", exc_info=True)
            if self.db:
                self.db.rollback()
            return False

    async def _audio_receive_loop(self):
        """Receive audio from Asterisk and send to Gemini"""
        logger.info("Audio receive loop started")
        packets = 0
        try:
            while self.is_running:
                # Read header
                header = await self._read_exact(3)
                if not header:
                    logger.info(f"Connection closed after {packets} packets")
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                # Read payload
                if payload_len > 0:
                    payload = await self._read_exact(payload_len)
                    if not payload:
                        break
                else:
                    payload = b''
                
                if msg_type == MSG_AUDIO:
                    packets += 1
                    if packets == 1:
                        logger.info("First audio from Asterisk received")
                    await self._process_audio(payload)
                elif msg_type == MSG_HANGUP:
                    logger.info(f"Hangup received after {packets} packets")
                    break
                elif msg_type == MSG_ERROR:
                    logger.error(f"Error from Asterisk: {payload}")
                    break
                    
        except Exception as e:
            logger.error(f"Receive loop error: {e}", exc_info=True)
        logger.info(f"Receive loop ended, total: {packets} packets")

    async def _process_audio(self, audio_8k: bytes):
        """Process incoming 8kHz audio from Asterisk, send to Gemini"""
        if not self.agent_service or len(audio_8k) < 2:
            return
        try:
            # Ensure even bytes
            if len(audio_8k) % 2:
                audio_8k = audio_8k[:-1]
            if not audio_8k:
                return
            
            # Upsample 8kHz -> 16kHz
            audio_16k, _ = audioop.ratecv(audio_8k, 2, 1, 8000, 16000, None)
            await self.agent_service.send_audio(audio_16k)
        except Exception as e:
            logger.error(f"Process audio error: {e}")

    async def _audio_send_loop(self):
        """Send AI audio from Gemini to Asterisk"""
        logger.info("Audio send loop started")
        packets = 0
        try:
            async for audio_24k in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                if not audio_24k or len(audio_24k) < 2:
                    continue
                
                # Ensure even bytes
                if len(audio_24k) % 2:
                    audio_24k = audio_24k[:-1]
                if not audio_24k:
                    continue
                
                # Downsample 24kHz -> 8kHz
                audio_8k, _ = audioop.ratecv(audio_24k, 2, 1, 24000, 8000, None)
                
                await self._send_frame(audio_8k)
                packets += 1
                if packets == 1:
                    logger.info("First AI audio sent to Asterisk")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Send loop error: {e}", exc_info=True)
        logger.info(f"Send loop ended, total: {packets} packets")

    async def _cleanup(self):
        """Clean up resources"""
        logger.info(f"Cleaning up call {self.call_uuid}")
        self.is_running = False
        
        # Cancel keepalive
        if self.keepalive_task and not self.keepalive_task.done():
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except:
                pass
        
        # Cancel send task
        if self.audio_send_task and not self.audio_send_task.done():
            self.audio_send_task.cancel()
            try:
                await self.audio_send_task
            except:
                pass
        
        # End AI session
        if self.agent_service:
            try:
                await self.agent_service.end_session()
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
                asyncio.create_task(auto_summarize_call(self.call.id))
            except:
                pass
            finally:
                try:
                    self.db.close()
                except:
                    pass
        
        # Close socket
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass
        
        logger.info("Cleanup complete")


class AudioSocketServer:
    def __init__(self, host='0.0.0.0', port=9092):
        self.host = host
        self.port = port
        self.server = None
    
    async def start(self):
        self.server = await asyncio.start_server(
            self._handle_connection, 
            self.host, 
            self.port
        )
        logger.info(f"AudioSocket server on {self.host}:{self.port}")
        print(f"[AudioSocket] Starting AudioSocket server...")
        print(f"[AudioSocket] ✅ AudioSocket server started on port {self.port}")
        asyncio.create_task(self._serve())
    
    async def _serve(self):
        try:
            async with self.server:
                await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def _handle_connection(self, reader, writer):
        session = AudioSocketSession(reader, writer)
        await session.handle()


audiosocket_server = AudioSocketServer()
