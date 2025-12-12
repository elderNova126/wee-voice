"""
Asterisk AudioSocket Handler
Receives audio from Asterisk via TCP socket and bridges to Gemini AI

AudioSocket Protocol:
- Port: TCP 9092 (configurable)
- Audio: 16-bit signed linear PCM, 8kHz mono
- Packets: 3-byte header + payload
  - Byte 0: Type (0x01 = UUID, 0x10 = Audio, 0x00 = Hangup)
  - Bytes 1-2: Payload length (big-endian)
  - Remaining: Payload data
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

# AudioSocket message types
MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF


class AudioSocketSession:
    """Handles a single AudioSocket connection from Asterisk"""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.call_uuid: Optional[str] = None
        self.call: Optional[Call] = None
        self.agent: Optional[VoiceAgent] = None
        self.agent_service: Optional[FrenchVoiceAgentService] = None
        self.is_running = False
        self.db: Optional[Session] = None
        self.audio_send_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()
        
    async def handle(self):
        """Main handler for AudioSocket connection"""
        addr = self.writer.get_extra_info('peername')
        logger.info(f"AudioSocket connection from {addr}")
        
        try:
            self.is_running = True
            
            # Read first packet (UUID)
            await self._read_uuid()
            
            if not self.call_uuid:
                logger.error("No UUID received, closing connection")
                return
            
            logger.info(f"Call UUID: {self.call_uuid}")
            
            # Set up call
            if not await self._setup_call():
                logger.error("Failed to setup call")
                return
            
            # Main audio receive loop
            await self._audio_receive_loop()
                    
        except asyncio.CancelledError:
            logger.info("Session cancelled")
        except Exception as e:
            logger.error(f"AudioSocket error: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _read_uuid(self):
        """Read UUID from first packet"""
        try:
            # Read 3-byte header - use readexactly to ensure we get all 3 bytes
            header = await asyncio.wait_for(self.reader.readexactly(3), timeout=5.0)
            
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            logger.info(f"Header: type=0x{msg_type:02x}, len={payload_len}")
            
            if msg_type == MSG_UUID and payload_len > 0:
                # Read UUID payload - use readexactly to get all bytes
                uuid_bytes = await asyncio.wait_for(
                    self.reader.readexactly(payload_len), 
                    timeout=5.0
                )
                logger.info(f"UUID bytes ({len(uuid_bytes)}): {uuid_bytes}")
                
                # Decode UUID - should be plain ASCII
                try:
                    self.call_uuid = uuid_bytes.decode('ascii').strip('\x00').strip()
                except:
                    self.call_uuid = uuid_bytes.decode('utf-8', errors='ignore').strip('\x00').strip()
                
                # Validate UUID format (should be like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
                if len(self.call_uuid) == 36 and self.call_uuid.count('-') == 4:
                    logger.info(f"Valid UUID: {self.call_uuid}")
                else:
                    logger.warning(f"Non-standard UUID format: {self.call_uuid}")
                    # Generate a proper UUID if the received one is garbage
                    if not all(c in '0123456789abcdef-' for c in self.call_uuid.lower()):
                        self.call_uuid = str(uuid_lib.uuid4())
                        logger.info(f"Generated new UUID: {self.call_uuid}")
            else:
                self.call_uuid = str(uuid_lib.uuid4())
                logger.info(f"No UUID packet, generated: {self.call_uuid}")
                
        except asyncio.TimeoutError:
            logger.error("Timeout reading UUID")
            self.call_uuid = str(uuid_lib.uuid4())
        except Exception as e:
            logger.error(f"Error reading UUID: {e}")
            self.call_uuid = str(uuid_lib.uuid4())

    async def _setup_call(self) -> bool:
        """Set up call record and AI agent"""
        self.db = SessionLocal()
        try:
            # Find agent from phone number or use first available
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
            
            # Create call record with clean session_id
            session_id = f"audiosocket_{self.call_uuid}"
            
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone="unknown",
                caller_name="Caller",
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=session_id,
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            logger.info(f"Created call {self.call.id} with session {session_id}")
            
            # Start Gemini agent
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            if not await self.agent_service.start_session():
                logger.error("Failed to start Gemini")
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            # Start background task to send AI audio to Asterisk
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
        logger.info("Audio receive loop STARTED")
        packets_received = 0
        try:
            while self.is_running:
                # Read header with timeout - use readexactly
                try:
                    header = await asyncio.wait_for(
                        self.reader.readexactly(3),
                        timeout=60.0  # 60 second timeout
                    )
                except asyncio.IncompleteReadError:
                    logger.info(f"Connection closed after {packets_received} packets")
                    break
                except asyncio.TimeoutError:
                    logger.info(f"Receive timeout after {packets_received} packets")
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                # Read payload - use readexactly
                if payload_len > 0:
                    try:
                        payload = await asyncio.wait_for(
                            self.reader.readexactly(payload_len),
                            timeout=5.0
                        )
                    except asyncio.IncompleteReadError:
                        logger.warning(f"Incomplete payload after {packets_received} packets")
                        break
                else:
                    payload = b''
                
                # Handle message types
                if msg_type == MSG_AUDIO:
                    packets_received += 1
                    if packets_received % 100 == 1:
                        logger.info(f"Audio packets from Asterisk: {packets_received}")
                    await self._process_incoming_audio(payload)
                elif msg_type == MSG_HANGUP:
                    logger.info(f"Hangup after {packets_received} packets")
                    break
                elif msg_type == MSG_ERROR:
                    logger.error(f"Error from Asterisk: {payload}")
                    break
                    
        except Exception as e:
            logger.error(f"Receive loop error: {e}", exc_info=True)
        logger.info(f"Audio receive loop ENDED, total: {packets_received}")

    async def _process_incoming_audio(self, audio_8k: bytes):
        """Process incoming 8kHz audio from Asterisk"""
        if not self.agent_service or not audio_8k:
            return
        try:
            # Ensure even number of bytes (16-bit samples)
            if len(audio_8k) % 2 != 0:
                audio_8k = audio_8k[:-1]
            if len(audio_8k) == 0:
                return
            
            # Upsample 8kHz -> 16kHz for Gemini
            audio_16k, _ = audioop.ratecv(audio_8k, 2, 1, 8000, 16000, None)
            await self.agent_service.send_audio(audio_16k)
        except Exception as e:
            logger.error(f"Audio process error: {e}")

    async def _audio_send_loop(self):
        """Send AI audio from Gemini to Asterisk"""
        logger.info("Audio send loop STARTED")
        packets_sent = 0
        try:
            async for audio_24k in self.agent_service.receive_audio():
                if not self.is_running:
                    logger.info("Audio send loop: is_running=False, stopping")
                    break
                if not audio_24k or len(audio_24k) == 0:
                    continue
                
                # Ensure even bytes
                if len(audio_24k) % 2 != 0:
                    audio_24k = audio_24k[:-1]
                if len(audio_24k) == 0:
                    continue
                
                # Downsample 24kHz -> 8kHz for Asterisk
                audio_8k, _ = audioop.ratecv(audio_24k, 2, 1, 24000, 8000, None)
                
                # Send to Asterisk
                await self._send_audio_packet(audio_8k)
                packets_sent += 1
                if packets_sent % 100 == 1:
                    logger.info(f"Audio packets sent to Asterisk: {packets_sent}")
                
        except asyncio.CancelledError:
            logger.info(f"Audio send loop cancelled after {packets_sent} packets")
        except Exception as e:
            logger.error(f"Send loop error after {packets_sent} packets: {e}", exc_info=True)
        logger.info(f"Audio send loop ENDED, total packets: {packets_sent}")

    async def _send_audio_packet(self, audio_data: bytes):
        """Send audio packet to Asterisk"""
        try:
            async with self._write_lock:
                header = struct.pack('>BH', MSG_AUDIO, len(audio_data))
                self.writer.write(header + audio_data)
                await self.writer.drain()
        except ConnectionResetError:
            logger.warning("Connection reset while sending audio")
            self.is_running = False
        except BrokenPipeError:
            logger.warning("Broken pipe while sending audio")
            self.is_running = False
        except Exception as e:
            logger.error(f"Send error: {e}", exc_info=True)
            self.is_running = False

    async def _cleanup(self):
        """Clean up resources"""
        logger.info(f"Cleaning up call {self.call_uuid}")
        self.is_running = False
        
        # Cancel send task
        if self.audio_send_task and not self.audio_send_task.done():
            self.audio_send_task.cancel()
            try:
                await asyncio.wait_for(self.audio_send_task, timeout=2.0)
            except:
                pass
        
        # End AI session
        if self.agent_service:
            try:
                await self.agent_service.end_session()
            except Exception as e:
                logger.error(f"Error ending AI session: {e}")
        
        # Update call record
        if self.call and self.db:
            try:
                self.db.refresh(self.call)
                self.call.ended_at = datetime.utcnow()
                self.call.calculate_duration_and_cost()
                self.call.status = CallStatus.SUMMARIZING
                self.db.commit()
                
                # Trigger summarization
                call_id = self.call.id
                asyncio.create_task(auto_summarize_call(call_id))
                logger.info(f"Call {call_id} ended, summarizing")
            except Exception as e:
                logger.error(f"Error updating call: {e}")
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
    """TCP server for AudioSocket connections"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 9092):
        self.host = host
        self.port = port
        self.server = None
        self._sessions = set()
    
    async def start(self):
        """Start the AudioSocket server"""
        try:
            self.server = await asyncio.start_server(
                self._handle_connection,
                self.host,
                self.port
            )
            addr = self.server.sockets[0].getsockname()
            logger.info(f"AudioSocket server listening on {addr[0]}:{addr[1]}")
            
            # Start serving in background
            asyncio.create_task(self._serve())
            
        except Exception as e:
            logger.error(f"Failed to start AudioSocket server: {e}")
            raise
    
    async def _serve(self):
        """Run the server"""
        try:
            async with self.server:
                await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Server error: {e}")
    
    async def stop(self):
        """Stop the AudioSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("AudioSocket server stopped")
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a new AudioSocket connection"""
        session = AudioSocketSession(reader, writer)
        self._sessions.add(session)
        try:
            await session.handle()
        finally:
            self._sessions.discard(session)


# Global server instance
audiosocket_server = AudioSocketServer()
