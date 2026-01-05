#!/usr/bin/env python3
"""
WeeVoice EAGI Full Implementation
Uses the same FrenchVoiceAgentService as the web/AudioSocket handler.
Supports database-driven agent configuration with all features:
- Custom system prompts
- Voice selection
- Greeting
- RAG (document search)
- Tools
- Call logging
"""

import os
import sys

# ============================================================================
# FIX PYDANTIC SETTINGS - Set env vars BEFORE any app imports
# ============================================================================
# BACKEND_CORS_ORIGINS must be a valid JSON array for pydantic-settings
if 'BACKEND_CORS_ORIGINS' not in os.environ or not os.environ['BACKEND_CORS_ORIGINS'].startswith('['):
    os.environ['BACKEND_CORS_ORIGINS'] = '["http://localhost:3000"]'

# Ensure other required settings have defaults
if 'SECRET_KEY' not in os.environ:
    os.environ['SECRET_KEY'] = 'eagi-default-key'

# ============================================================================
# Now safe to import other modules
# ============================================================================
import asyncio
import audioop
import logging
from datetime import datetime
from typing import Optional

# ============================================================================
# LOGGING SETUP
# ============================================================================
LOG_DIR = "/var/log/weevoice"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/eagi.log"),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("weevoice_eagi")

# ============================================================================
# AUDIO CONFIGURATION
# ============================================================================
# Audio rates (matching audiosocket_handler.py)
INPUT_SAMPLE_RATE = 8000    # From Asterisk (PSTN native)
GEMINI_INPUT_RATE = 16000   # Gemini expects 16kHz input
GEMINI_OUTPUT_RATE = 24000  # Gemini outputs 24kHz

# Frame sizes (20ms frames)
INPUT_FRAME_SIZE = 320      # 20ms at 8kHz = 160 samples * 2 bytes
OUTPUT_FRAME_SIZE = 960     # 20ms at 24kHz

# High quality mode sends 24kHz directly (for SIP/WebRTC)
HIGH_QUALITY_MODE = os.environ.get('WEEVOICE_HIGH_QUALITY', 'false').lower() == 'true'


class EAGIHandler:
    """
    Full-featured EAGI handler that uses FrenchVoiceAgentService.
    Same as AudioSocket handler but for EAGI.
    """
    
    def __init__(self):
        self.env = {}
        self.running = False
        self.db = None
        self.agent = None
        self.call = None
        self.agent_service = None
        self._audio_fd = None
        self._resample_state_in = None
        self._resample_state_out = None
        
        # Caller info (from AGI env)
        self.caller_id = "unknown"
        self.call_id = None
        
        logger.info("=" * 60)
        logger.info("WeeVoice EAGI Full - Starting")
        logger.info(f"High Quality Mode: {HIGH_QUALITY_MODE}")
        logger.info("=" * 60)
    
    # ========================================================================
    # AGI PROTOCOL
    # ========================================================================
    
    def _read_agi_env(self):
        """Read AGI environment variables from stdin"""
        logger.info("Reading AGI environment...")
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            if ':' in line:
                key, value = line.split(':', 1)
                self.env[key.strip()] = value.strip()
        
        self.caller_id = self.env.get('agi_callerid', 'unknown')
        self.call_id = self.env.get('agi_uniqueid', datetime.now().strftime('%Y%m%d%H%M%S'))
        
        logger.info(f"AGI Call ID: {self.call_id}")
        logger.info(f"AGI Caller ID: {self.caller_id}")
        logger.info(f"AGI Channel: {self.env.get('agi_channel', 'unknown')}")
    
    def _agi_command(self, cmd: str) -> str:
        """Send AGI command and get response"""
        sys.stdout.write(f"{cmd}\n")
        sys.stdout.flush()
        return sys.stdin.readline().strip()
    
    def _verbose(self, msg: str):
        """Send verbose message to Asterisk CLI"""
        self._agi_command(f'VERBOSE "{msg}" 3')
    
    # ========================================================================
    # AUDIO RESAMPLING (matching audiosocket_handler.py)
    # ========================================================================
    
    def _resample_for_gemini(self, audio_8k: bytes) -> bytes:
        """
        Convert 8kHz slin from Asterisk to 16kHz for Gemini input.
        Matching audiosocket_handler.py logic.
        """
        if len(audio_8k) < 2:
            return b''
        try:
            result, self._resample_state_in = audioop.ratecv(
                audio_8k, 2, 1, INPUT_SAMPLE_RATE, GEMINI_INPUT_RATE, self._resample_state_in
            )
            return result
        except Exception as e:
            logger.error(f"Resample input error: {e}")
            return audio_8k
    
    def _resample_from_gemini(self, audio_24k: bytes) -> bytes:
        """
        Convert 24kHz from Gemini to 8kHz for Asterisk output.
        Matching audiosocket_handler.py logic.
        """
        if len(audio_24k) < 2:
            return b''
        try:
            if HIGH_QUALITY_MODE:
                # For SIP/WebRTC: Keep at higher rate
                target_rate = 16000
            else:
                # For PSTN: Downsample to 8kHz
                target_rate = INPUT_SAMPLE_RATE
            
            result, self._resample_state_out = audioop.ratecv(
                audio_24k, 2, 1, GEMINI_OUTPUT_RATE, target_rate, self._resample_state_out
            )
            return result
        except Exception as e:
            logger.error(f"Resample output error: {e}")
            return audio_24k
    
    # ========================================================================
    # DATABASE SETUP (matching audiosocket_handler.py)
    # ========================================================================
    
    def _setup_from_database(self) -> bool:
        """
        Load agent and create call from database.
        EXACTLY like audiosocket_handler._setup_call_quick()
        """
        try:
            # Import models (this may fail if settings are wrong)
            from app.models.database import SessionLocal
            from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
            
            logger.info("Connecting to database...")
            self.db = SessionLocal()
            
            # Find phone number with SIP config (same as audiosocket_handler)
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None),
                PhoneNumber.sip_username.isnot(None)
            ).first()
            
            if not phone:
                logger.warning("No phone with SIP config found, trying first agent...")
                self.agent = self.db.query(VoiceAgent).first()
            else:
                logger.info(f"Found phone: {phone.phone_number}, agent_id: {phone.agent_id}")
                
                # Get agent
                self.agent = self.db.query(VoiceAgent).filter(
                    VoiceAgent.id == phone.agent_id
                ).first()
                
                if not self.agent:
                    self.agent = self.db.query(VoiceAgent).first()
            
            if not self.agent:
                logger.error("No agent found in database")
                return False
            
            logger.info(f"Using agent: {self.agent.name} (ID: {self.agent.id})")
            logger.info(f"  Language: {self.agent.language}")
            logger.info(f"  Voice: {getattr(self.agent, 'voice_id', 'default')}")
            logger.info(f"  Greeting: {(self.agent.greeting or '')[:50]}...")
            logger.info(f"  RAG Enabled: {self.agent.rag_enabled}")
            
            # Create call record (same as audiosocket_handler)
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone=self.caller_id,
                caller_name=self.caller_id,
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"eagi_{self.call_id}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            logger.info(f"Created call record: {self.call.id}")
            return True
            
        except Exception as e:
            logger.error(f"Database setup error: {e}", exc_info=True)
            return False
    
    def _setup_agent_service(self) -> bool:
        """
        Create FrenchVoiceAgentService - SAME service as web/AudioSocket.
        This gives us full agent features: voice, prompts, tools, RAG.
        """
        try:
            from app.services.agent_service import FrenchVoiceAgentService
            
            logger.info("Creating FrenchVoiceAgentService...")
            
            # Create the SAME service used by web agent and AudioSocket
            self.agent_service = FrenchVoiceAgentService(
                self.agent,
                self.call,
                skip_greeting_trigger=False  # Let Gemini handle greeting naturally
            )
            
            logger.info("Agent service created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Agent service creation error: {e}", exc_info=True)
            return False
    
    async def _start_gemini_session(self) -> bool:
        """Start Gemini session using agent service (like audiosocket_handler)"""
        try:
            logger.info("Starting Gemini session via agent_service...")
            
            if not await self.agent_service.start_session():
                logger.error("Failed to start Gemini session")
                return False
            
            # Update call status
            from app.models import CallStatus
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            logger.info("Gemini session started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gemini session error: {e}", exc_info=True)
            return False
    
    # ========================================================================
    # AUDIO LOOPS (EAGI specific - FD3 for input, stdout for output)
    # ========================================================================
    
    async def _audio_capture_loop(self):
        """
        Capture audio from EAGI FD3 and send to Gemini via agent_service.
        Uses the same format as audiosocket_handler.
        """
        logger.info("Starting audio capture from FD3")
        
        try:
            self._audio_fd = os.fdopen(3, 'rb', buffering=0)
        except Exception as e:
            logger.error(f"Failed to open FD3: {e}")
            return
        
        frame_count = 0
        buffer = b''
        
        while self.running:
            try:
                # Read audio from Asterisk
                data = self._audio_fd.read(INPUT_FRAME_SIZE)
                if not data:
                    await asyncio.sleep(0.001)
                    continue
                
                buffer += data
                
                # Process in frame-sized chunks
                while len(buffer) >= INPUT_FRAME_SIZE:
                    chunk = buffer[:INPUT_FRAME_SIZE]
                    buffer = buffer[INPUT_FRAME_SIZE:]
                    
                    # Resample 8kHz -> 16kHz for Gemini
                    audio_16k = self._resample_for_gemini(chunk)
                    
                    if audio_16k and self.agent_service and self.agent_service.session:
                        try:
                            # Send via agent_service (same format as audiosocket)
                            await self.agent_service.audio_out_queue.put({
                                "data": audio_16k,
                                "mime_type": "audio/pcm;rate=16000"
                            })
                            frame_count += 1
                        except Exception as e:
                            if "closed" in str(e).lower():
                                logger.info("Gemini session closed")
                                self.running = False
                                break
                            logger.error(f"Audio send error: {e}")
                
            except Exception as e:
                if self.running:
                    logger.error(f"Audio capture error: {e}")
                break
        
        logger.info(f"Audio capture ended. Sent {frame_count} frames")
    
    async def _audio_playback_loop(self):
        """
        Receive audio from Gemini via agent_service and write to stdout.
        """
        logger.info("Starting audio playback loop")
        
        chunk_count = 0
        
        try:
            # Receive from agent_service (same as audiosocket)
            async for response in self.agent_service.session.receive():
                if not self.running:
                    break
                
                # Handle audio data
                if hasattr(response, 'data') and response.data:
                    # Resample 24kHz -> 8kHz for Asterisk
                    audio_out = self._resample_from_gemini(response.data)
                    
                    if audio_out:
                        try:
                            # Write to stdout (EAGI audio output)
                            sys.stdout.buffer.write(audio_out)
                            sys.stdout.buffer.flush()
                            chunk_count += 1
                        except Exception as e:
                            logger.error(f"Audio write error: {e}")
                
                # Handle transcription (for logging)
                if hasattr(response, 'server_content'):
                    sc = response.server_content
                    
                    # Output transcription
                    if hasattr(sc, 'output_transcription') and sc.output_transcription:
                        text = getattr(sc.output_transcription, 'text', '')
                        if text:
                            logger.info(f"AI: {text[:100]}...")
                    
                    # Input transcription
                    if hasattr(sc, 'input_transcription') and sc.input_transcription:
                        text = getattr(sc.input_transcription, 'text', '')
                        if text:
                            logger.info(f"User: {text[:100]}...")
                    
                    # Turn complete
                    if hasattr(sc, 'turn_complete') and sc.turn_complete:
                        logger.debug("Turn complete")
                
        except Exception as e:
            if "closed" not in str(e).lower():
                logger.error(f"Playback error: {e}")
        
        logger.info(f"Playback ended. Received {chunk_count} chunks")
    
    async def _gemini_input_loop(self):
        """Forward audio from queue to Gemini (same as agent_service.send_realtime_input)"""
        try:
            await self.agent_service.send_realtime_input()
        except Exception as e:
            if self.running:
                logger.error(f"Gemini input loop error: {e}")
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def _save_call_data(self):
        """Save final call data to database"""
        try:
            if self.call and self.db:
                from app.models import CallStatus
                
                self.call.status = CallStatus.COMPLETED
                self.call.ended_at = datetime.utcnow()
                
                if self.call.started_at:
                    duration = (self.call.ended_at - self.call.started_at).total_seconds()
                    self.call.duration = int(duration)
                
                self.db.commit()
                logger.info(f"Call {self.call.id} saved: duration={self.call.duration}s")
                
        except Exception as e:
            logger.error(f"Failed to save call data: {e}")
    
    async def _cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        
        # Stop agent service session
        if self.agent_service:
            try:
                await self.agent_service.stop_session()
            except Exception as e:
                logger.warning(f"Error stopping agent service: {e}")
        
        # Save call data
        self._save_call_data()
        
        # Close database
        if self.db:
            try:
                self.db.close()
            except:
                pass
        
        # Close audio FD
        if self._audio_fd:
            try:
                self._audio_fd.close()
            except:
                pass
        
        logger.info("Cleanup complete")
    
    # ========================================================================
    # MAIN EXECUTION
    # ========================================================================
    
    async def run(self):
        """Main EAGI execution"""
        # Read AGI environment
        self._read_agi_env()
        self._verbose("WeeVoice: Starting AI Agent")
        
        # Setup from database
        if not self._setup_from_database():
            self._verbose("WeeVoice: Database Error")
            logger.error("Database setup failed")
            return
        
        # Create agent service (full features)
        if not self._setup_agent_service():
            self._verbose("WeeVoice: Agent Service Error")
            logger.error("Agent service setup failed")
            return
        
        # Start Gemini session
        if not await self._start_gemini_session():
            self._verbose("WeeVoice: Gemini Error")
            logger.error("Gemini session start failed")
            return
        
        self._verbose("WeeVoice: Connected")
        self.running = True
        
        try:
            # Create tasks
            capture_task = asyncio.create_task(self._audio_capture_loop())
            playback_task = asyncio.create_task(self._audio_playback_loop())
            gemini_input_task = asyncio.create_task(self._gemini_input_loop())
            
            # Wait for any task to complete (usually hangup)
            done, pending = await asyncio.wait(
                [capture_task, playback_task, gemini_input_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Stop and cancel remaining
            self.running = False
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            logger.error(f"Run error: {e}", exc_info=True)
        finally:
            self.running = False
            await self._cleanup()
        
        self._verbose("WeeVoice: Call Ended")
        logger.info("WeeVoice EAGI Ended")


def main():
    """Entry point"""
    handler = EAGIHandler()
    
    try:
        asyncio.run(handler.run())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        # Send error to Asterisk
        sys.stdout.write('VERBOSE "WeeVoice: Fatal Error" 1\n')
        sys.stdout.flush()


if __name__ == "__main__":
    main()

