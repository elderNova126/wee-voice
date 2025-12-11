"""
Asterisk AudioSocket Handler
Receives audio from Asterisk via TCP socket and bridges to Gemini AI

AudioSocket Protocol:
- Port: TCP 9092 (configurable)
- Audio: 16-bit signed linear PCM, 8kHz mono
- Packets: 3-byte header + audio data
  - Byte 0: Type (0x01 = UUID, 0x10 = Audio, 0x00 = Hangup)
  - Bytes 1-2: Payload length (big-endian)
  - Remaining: Payload data
"""
import asyncio
import logging
import struct
from typing import Optional, Dict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
from app.services.agent_service import FrenchVoiceAgentService
from app.api.websocket import call_monitor_manager, auto_summarize_call

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
        self.audio_task: Optional[asyncio.Task] = None
        
    async def handle(self):
        """Main handler for AudioSocket connection"""
        addr = self.writer.get_extra_info('peername')
        logger.info(f"📞 AudioSocket connection from {addr}")
        
        try:
            self.is_running = True
            
            while self.is_running:
                # Read message header (3 bytes)
                header = await self.reader.read(3)
                if len(header) < 3:
                    logger.info("Connection closed (incomplete header)")
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                # Read payload
                payload = b''
                if payload_len > 0:
                    payload = await self.reader.read(payload_len)
                    if len(payload) < payload_len:
                        logger.warning("Incomplete payload received")
                        break
                
                # Handle message
                if msg_type == MSG_UUID:
                    await self._handle_uuid(payload)
                elif msg_type == MSG_AUDIO:
                    await self._handle_audio(payload)
                elif msg_type == MSG_HANGUP:
                    logger.info(f"📞 Hangup received for {self.call_uuid}")
                    break
                elif msg_type == MSG_ERROR:
                    error_msg = payload.decode('utf-8', errors='ignore')
                    logger.error(f"AudioSocket error: {error_msg}")
                    break
                    
        except asyncio.CancelledError:
            logger.info("AudioSocket session cancelled")
        except Exception as e:
            logger.error(f"AudioSocket error: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _handle_uuid(self, payload: bytes):
        """Handle UUID message - call setup"""
        self.call_uuid = payload.decode('utf-8').strip()
        logger.info(f"📞 AudioSocket call UUID: {self.call_uuid}")
        
        # Look up call in database or create new one
        self.db = SessionLocal()
        try:
            # UUID format from Asterisk: "1733928187.0" (epoch.sequence)
            # Or custom format: "caller_number:called_number:agent_id"
            parts = self.call_uuid.split(':')
            
            if len(parts) >= 3:
                # Custom format with call info
                caller_number = parts[0]
                called_number = parts[1]
                agent_id = int(parts[2]) if parts[2].isdigit() else None
            else:
                # Standard Asterisk UUID - we need to look up the agent
                caller_number = "unknown"
                called_number = "unknown" 
                agent_id = None
            
            # Find agent
            if agent_id:
                self.agent = self.db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
            
            if not self.agent:
                # Try to find phone number with agent assigned
                phone = self.db.query(PhoneNumber).filter(
                    PhoneNumber.agent_id.isnot(None)
                ).first()
                if phone and phone.agent_id:
                    self.agent = self.db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
                    called_number = phone.phone_number
            
            if not self.agent:
                # Use default/first agent
                self.agent = self.db.query(VoiceAgent).first()
            
            if not self.agent:
                logger.error("No agent found for AudioSocket call")
                await self._send_hangup()
                return
            
            # Create call record
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone=caller_number,
                caller_name=caller_number,
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"audiosocket_{self.call_uuid}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            logger.info(f"✅ Created call record: ID={self.call.id} for agent {self.agent.id}")
            
            # Initialize Gemini agent
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            success = await self.agent_service.start_session()
            
            if not success:
                logger.error("Failed to start Gemini session")
                await self._send_hangup()
                return
            
            # Update call status
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            # Start audio output task (Gemini -> Asterisk)
            self.audio_task = asyncio.create_task(self._send_audio_to_asterisk())
            
            logger.info(f"✅ AudioSocket session started for call {self.call.id}")
            
        except Exception as e:
            logger.error(f"Error setting up AudioSocket call: {e}", exc_info=True)
            if self.db:
                self.db.rollback()
    
    async def _handle_audio(self, payload: bytes):
        """Handle audio from Asterisk -> send to Gemini"""
        if not self.agent_service:
            return
        
        try:
            # Audio is 16-bit signed linear PCM, 8kHz mono
            # Gemini expects 16kHz, so we need to upsample
            import audioop
            
            # Upsample from 8kHz to 16kHz
            upsampled = audioop.ratecv(payload, 2, 1, 8000, 16000, None)[0]
            
            # Send to Gemini
            await self.agent_service.send_audio(upsampled)
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
    
    async def _send_audio_to_asterisk(self):
        """Send audio from Gemini -> Asterisk"""
        try:
            import audioop
            
            async for audio_data in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                
                # Audio from Gemini is 24kHz, downsample to 8kHz for Asterisk
                downsampled = audioop.ratecv(audio_data, 2, 1, 24000, 8000, None)[0]
                
                # Send via AudioSocket protocol
                await self._send_audio(downsampled)
                
        except asyncio.CancelledError:
            logger.debug("Audio send task cancelled")
        except Exception as e:
            logger.error(f"Error sending audio to Asterisk: {e}", exc_info=True)
    
    async def _send_audio(self, audio_data: bytes):
        """Send audio packet to Asterisk"""
        try:
            # Build AudioSocket audio message
            header = struct.pack('>BH', MSG_AUDIO, len(audio_data))
            self.writer.write(header + audio_data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error writing audio: {e}")
            self.is_running = False
    
    async def _send_hangup(self):
        """Send hangup to Asterisk"""
        try:
            header = struct.pack('>BH', MSG_HANGUP, 0)
            self.writer.write(header)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending hangup: {e}")
    
    async def _cleanup(self):
        """Cleanup session resources"""
        self.is_running = False
        
        # Cancel audio task
        if self.audio_task and not self.audio_task.done():
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                pass
        
        # End Gemini session
        if self.agent_service:
            try:
                await self.agent_service.end_session()
            except Exception as e:
                logger.error(f"Error ending agent session: {e}")
        
        # Update call record
        if self.call and self.db:
            try:
                self.call.ended_at = datetime.utcnow()
                self.call.calculate_duration_and_cost()
                self.call.status = CallStatus.SUMMARIZING
                self.db.commit()
                
                # Start summarization
                asyncio.create_task(auto_summarize_call(self.call.id))
                
            except Exception as e:
                logger.error(f"Error updating call record: {e}")
            finally:
                self.db.close()
        
        # Close connection
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
        
        logger.info(f"📞 AudioSocket session ended for {self.call_uuid}")


class AudioSocketServer:
    """TCP server for Asterisk AudioSocket connections"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 9092):
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.sessions: Dict[str, AudioSocketSession] = {}
    
    async def start(self):
        """Start the AudioSocket server"""
        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"🎧 AudioSocket server listening on {addr[0]}:{addr[1]}")
        
        # Start serving
        asyncio.create_task(self.server.serve_forever())
    
    async def stop(self):
        """Stop the AudioSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("AudioSocket server stopped")
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle new AudioSocket connection"""
        session = AudioSocketSession(reader, writer)
        await session.handle()


# Global AudioSocket server instance
audiosocket_server = AudioSocketServer()

