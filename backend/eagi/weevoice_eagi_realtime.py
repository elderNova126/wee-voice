#!/usr/bin/env python3
"""
WeeVoice Real-Time EAGI Script for Asterisk AI Voice Agent

This script uses the SAME agent configuration and Gemini integration
as the web agent (FrenchVoiceAgentService).

Place in: /var/lib/asterisk/agi-bin/weevoice_eagi.py
"""

import os
import sys
import asyncio
import audioop
import select
import time
import logging
import signal
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import deque
from datetime import datetime

# Add backend path for imports
sys.path.insert(0, '/opt/weevoice/backend')

# Load environment before importing app modules
from dotenv import load_dotenv
env_paths = ['/opt/weevoice/backend/.env', '/opt/weevoice/.env']
for p in env_paths:
    if os.path.exists(p):
        load_dotenv(p)
        break

# Logging setup
LOG_DIR = Path('/var/log/weevoice')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'eagi.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger('weevoice_eagi')

# Audio configuration
# For PSTN calls: 8kHz (telephone standard)
# For SIP/WebRTC: Can use 16kHz or higher
ASTERISK_RATE = 8000       # Default: 8kHz for PSTN compatibility
GEMINI_INPUT_RATE = 16000  # Gemini expects 16kHz input
GEMINI_OUTPUT_RATE = 24000 # Gemini outputs 24kHz (high quality)
FRAME_MS = 20

# Frame sizes
FRAME_BYTES_8K = 320       # 20ms at 8kHz (160 samples * 2 bytes)
FRAME_BYTES_16K = 640      # 20ms at 16kHz (320 samples * 2 bytes)
FRAME_BYTES_24K = 960      # 20ms at 24kHz (480 samples * 2 bytes)

# High quality mode - set via environment or channel variable
# When True, sends 24kHz directly to Asterisk (for SIP/WebRTC channels)
# HIGH_QUALITY_MODE = os.environ.get('WEEVOICE_HIGH_QUALITY', 'false').lower() == 'true'
HIGH_QUALITY_MODE = 'true'

# Temp directory for audio files
TEMP_AUDIO_DIR = Path('/tmp/weevoice_audio')
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class AGI:
    """Minimal AGI protocol handler"""
    
    def __init__(self):
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.env: Dict[str, str] = {}
        self.audio_fd: Optional[int] = None
        
    def read_env(self) -> Dict[str, str]:
        """Read AGI environment variables"""
        while True:
            line = self.stdin.readline()
            if not line or line.strip() == '':
                break
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                self.env[key.strip()] = value.strip()
        return self.env
    
    def cmd(self, command: str) -> str:
        """Send AGI command and get response"""
        self.stdout.write(f"{command}\n")
        self.stdout.flush()
        return self.stdin.readline().strip()
    
    def verbose(self, msg: str, level: int = 1):
        self.cmd(f'VERBOSE "{msg}" {level}')
    
    def set_var(self, name: str, value: str):
        self.cmd(f'SET VARIABLE {name} "{value}"')
    
    def get_var(self, name: str) -> str:
        resp = self.cmd(f'GET VARIABLE {name}')
        if '(' in resp:
            return resp.split('(')[1].rstrip(')')
        return ''
    
    def stream_file(self, filename: str, escape: str = ""):
        return self.cmd(f'STREAM FILE "{filename}" "{escape}"')


class AudioBuffer:
    """Thread-safe audio buffer with jitter handling"""
    
    def __init__(self, max_size_ms: int = 2000, sample_rate: int = 8000):
        self.buffer = deque()
        self.lock = threading.Lock()
        self.max_bytes = int(sample_rate * 2 * max_size_ms / 1000)
        self.total_bytes = 0
        
    def push(self, audio: bytes):
        with self.lock:
            self.buffer.append(audio)
            self.total_bytes += len(audio)
            while self.total_bytes > self.max_bytes and len(self.buffer) > 1:
                old = self.buffer.popleft()
                self.total_bytes -= len(old)
    
    def pop(self, size: int) -> bytes:
        with self.lock:
            if self.total_bytes == 0:
                return b'\x00' * size
            
            result = b''
            while len(result) < size and self.buffer:
                chunk = self.buffer.popleft()
                self.total_bytes -= len(chunk)
                result += chunk
            
            if len(result) > size:
                excess = result[size:]
                result = result[:size]
                self.buffer.appendleft(excess)
                self.total_bytes += len(excess)
            
            if len(result) < size:
                result += b'\x00' * (size - len(result))
            
            return result
    
    def available_ms(self) -> int:
        with self.lock:
            return int(self.total_bytes / 16)


class WeeVoiceEAGI:
    """
    EAGI handler that uses the SAME FrenchVoiceAgentService as the web agent.
    This ensures identical voice, prompts, and behavior.
    """
    
    def __init__(self):
        self.agi = AGI()
        self.call_id = ""
        self.caller_id = ""
        self.running = False
        self._audio_fd = None
        self._resample_state_in = None
        self._resample_state_out = None
        
        # These will be set from database
        self.agent = None
        self.call = None
        self.agent_service = None
        self.db = None
        
        # Output buffer - sample rate depends on quality mode
        output_rate = 16000 if HIGH_QUALITY_MODE else ASTERISK_RATE
        self.output_buffer = AudioBuffer(max_size_ms=3000, sample_rate=output_rate)
        self.output_rate = output_rate
        
    def _resample_8k_to_16k(self, audio_8k: bytes) -> bytes:
        """Resample caller audio for Gemini"""
        if len(audio_8k) < 2:
            return b''
        try:
            result, self._resample_state_in = audioop.ratecv(
                audio_8k, 2, 1, ASTERISK_RATE, GEMINI_INPUT_RATE, self._resample_state_in
            )
            return result
        except Exception as e:
            logger.error(f"Resample 8k->16k error: {e}")
            return audio_8k
    
    def _resample_output(self, audio_24k: bytes) -> bytes:
        """
        Convert Gemini output for Asterisk playback.
        
        In HIGH_QUALITY_MODE (for SIP/WebRTC): Keep 24kHz or downsample to 16kHz
        In standard mode (for PSTN): Downsample to 8kHz
        """
        if len(audio_24k) < 2:
            return b''
        
        try:
            if HIGH_QUALITY_MODE:
                # For SIP/WebRTC: Use 16kHz (slin16) - widely supported
                target_rate = 16000
                result, self._resample_state_out = audioop.ratecv(
                    audio_24k, 2, 1, GEMINI_OUTPUT_RATE, target_rate, self._resample_state_out
                )
                return result
            else:
                # For PSTN: Standard 8kHz (slin)
                result, self._resample_state_out = audioop.ratecv(
                    audio_24k, 2, 1, GEMINI_OUTPUT_RATE, ASTERISK_RATE, self._resample_state_out
                )
                return result
        except Exception as e:
            logger.error(f"Resample output error: {e}")
            return audio_24k
    
    def _setup_from_database(self) -> bool:
        """
        Load agent and call from database - SAME as audiosocket_handler.py
        This ensures we get the same agent configuration as web calls.
        """
        try:
            # Import models
            from app.models.database import SessionLocal
            from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
            
            self.db = SessionLocal()
            
            # Find phone number with SIP config (same logic as audiosocket_handler)
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None),
                PhoneNumber.sip_username.isnot(None)
            ).first()
            
            if not phone:
                logger.error("No phone number with SIP config found")
                return False
            
            logger.info(f"Found phone: {phone.phone_number}, agent_id: {phone.agent_id}")
            
            # Get agent (SAME as audiosocket_handler)
            self.agent = self.db.query(VoiceAgent).filter(
                VoiceAgent.id == phone.agent_id
            ).first()
            
            if not self.agent:
                # Fallback to first agent
                self.agent = self.db.query(VoiceAgent).first()
            
            if not self.agent:
                logger.error("No agent found")
                return False
            
            logger.info(f"Using agent: {self.agent.name} (ID: {self.agent.id})")
            logger.info(f"  - Language: {self.agent.language}")
            logger.info(f"  - Voice Gender: {getattr(self.agent, 'voice_gender', 'default')}")
            logger.info(f"  - Voice ID: {getattr(self.agent, 'voice_id', 'default')}")
            logger.info(f"  - Greeting: {self.agent.greeting[:50] if self.agent.greeting else 'None'}...")
            
            # Create call record (SAME as audiosocket_handler)
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
        Create FrenchVoiceAgentService - SAME service as web agent.
        This ensures identical voice, prompts, and Gemini configuration.
        """
        try:
            from app.services.agent_service import FrenchVoiceAgentService
            
            logger.info("Creating FrenchVoiceAgentService (same as web agent)...")
            
            # Create the SAME service used by web agent and audiosocket
            self.agent_service = FrenchVoiceAgentService(
                self.agent,
                self.call,
                skip_greeting_trigger=False  # Let Gemini handle greeting
            )
            
            logger.info("Agent service created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Agent service error: {e}", exc_info=True)
            return False
    
    async def _start_gemini_session(self) -> bool:
        """Start Gemini session using agent service"""
        try:
            logger.info("Starting Gemini session...")
            
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
    
    async def _audio_capture_loop(self):
        """Capture audio from EAGI FD3 and send to Gemini"""
        logger.info("Starting audio capture from FD3")
        
        try:
            self._audio_fd = os.fdopen(3, 'rb', buffering=0)
        except Exception as e:
            logger.error(f"Failed to open FD3: {e}")
            return
        
        frame_count = 0
        
        while self.running:
            try:
                readable, _, _ = select.select([self._audio_fd], [], [], 0.02)
                
                if not readable:
                    continue
                
                audio_8k = self._audio_fd.read(FRAME_BYTES_8K)
                
                if not audio_8k:
                    continue
                
                frame_count += 1
                
                # Resample and send to Gemini via agent_service
                audio_16k = self._resample_8k_to_16k(audio_8k)
                if audio_16k and self.agent_service:
                    await self.agent_service.send_audio(
                        audio_16k, 
                        mime_type="audio/pcm;rate=16000"
                    )
                
                if frame_count % 250 == 0:
                    logger.debug(f"Captured {frame_count} frames")
                    
            except Exception as e:
                if 'closed' in str(e).lower():
                    break
                logger.error(f"Audio capture error: {e}")
                await asyncio.sleep(0.01)
        
        logger.info(f"Audio capture ended: {frame_count} frames")
        
        if self._audio_fd:
            try:
                self._audio_fd.close()
            except:
                pass
    
    async def _audio_receive_loop(self):
        """Receive audio from Gemini and buffer for playback"""
        logger.info("Starting Gemini audio receive loop")
        
        try:
            async for audio_data in self.agent_service.receive_audio():
                if not self.running:
                    break
                
                if audio_data:
                    # Convert Gemini 24kHz output for Asterisk
                    # (8kHz for PSTN, 16kHz for SIP/WebRTC in high quality mode)
                    audio_out = self._resample_output(audio_data)
                    if audio_out:
                        self.output_buffer.push(audio_out)
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if 'closed' not in str(e).lower():
                logger.error(f"Receive loop error: {e}")
        
        logger.info("Receive loop ended")
    
    async def _audio_playback_loop(self):
        """Play buffered audio back to caller using AGI STREAM FILE"""
        logger.info(f"Starting audio playback loop (rate={self.output_rate}Hz, high_quality={HIGH_QUALITY_MODE})")
        
        audio_dir = TEMP_AUDIO_DIR / self.call_id
        audio_dir.mkdir(exist_ok=True)
        
        chunk_index = 0
        min_buffer_ms = 200  # Wait for this much audio before playing
        
        # File extension based on sample rate
        # Asterisk uses: .sln (8kHz), .sln16 (16kHz), .sln24 (24kHz)
        if self.output_rate == 16000:
            file_ext = ".sln16"
        elif self.output_rate == 24000:
            file_ext = ".sln24"
        else:
            file_ext = ".sln"
        
        while self.running:
            try:
                available = self.output_buffer.available_ms()
                
                if available < min_buffer_ms:
                    await asyncio.sleep(0.05)
                    continue
                
                # Get 400ms of audio at current output rate
                chunk_bytes = int(self.output_rate * 2 * 0.4)
                audio_chunk = self.output_buffer.pop(chunk_bytes)
                
                # Check if it's not just silence
                if audio_chunk and audio_chunk != b'\x00' * len(audio_chunk):
                    # Save to temp file with correct extension
                    filename = audio_dir / f"chunk_{chunk_index:04d}{file_ext}"
                    with open(filename, 'wb') as f:
                        f.write(audio_chunk)
                    
                    # Play with AGI (without extension - Asterisk auto-detects)
                    self.agi.stream_file(str(filename.with_suffix('')))
                    
                    # Cleanup
                    try:
                        filename.unlink()
                    except:
                        pass
                    
                    chunk_index += 1
                else:
                    await asyncio.sleep(0.02)
                    
            except Exception as e:
                if 'closed' in str(e).lower():
                    break
                logger.error(f"Playback error: {e}")
                await asyncio.sleep(0.1)
        
        # Cleanup directory
        try:
            for f in audio_dir.glob('*'):
                f.unlink()
            audio_dir.rmdir()
        except:
            pass
        
        logger.info(f"Playback ended: {chunk_index} chunks played at {self.output_rate}Hz")
    
    async def _send_audio_input_loop(self):
        """Forward audio queue to Gemini (same as agent_service.send_realtime_input)"""
        logger.info("Starting audio input forwarding")
        await self.agent_service.send_realtime_input()
        logger.info("Audio input forwarding ended")
    
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
    
    async def run(self):
        """Main EAGI execution"""
        logger.info("=" * 60)
        logger.info("WeeVoice EAGI Started (Using FrenchVoiceAgentService)")
        logger.info(f"Audio Mode: {'HIGH QUALITY (16kHz)' if HIGH_QUALITY_MODE else 'STANDARD (8kHz PSTN)'}")
        logger.info("=" * 60)
        
        try:
            # Read AGI environment
            env = self.agi.read_env()
            
            self.call_id = env.get('agi_uniqueid', str(int(time.time())))
            self.caller_id = env.get('agi_callerid', 'Unknown')
            channel = env.get('agi_channel', 'unknown')
            
            logger.info(f"Call ID: {self.call_id}")
            logger.info(f"Caller: {self.caller_id}")
            logger.info(f"Channel: {channel}")
            
            # Step 1: Load agent from database (SAME as audiosocket_handler)
            if not self._setup_from_database():
                self.agi.verbose("WeeVoice: Database Error", 1)
                return
            
            # Step 2: Create FrenchVoiceAgentService (SAME as web agent)
            if not self._setup_agent_service():
                self.agi.verbose("WeeVoice: Agent Service Error", 1)
                return
            
            # Step 3: Start Gemini session
            if not await self._start_gemini_session():
                self.agi.verbose("WeeVoice: Gemini Error", 1)
                return
            
            self.running = True
            self.agi.verbose(f"WeeVoice: AI Agent Active - {self.agent.name}", 1)
            
            # Start all loops
            capture_task = asyncio.create_task(self._audio_capture_loop())
            receive_task = asyncio.create_task(self._audio_receive_loop())
            playback_task = asyncio.create_task(self._audio_playback_loop())
            input_task = asyncio.create_task(self._send_audio_input_loop())
            
            # Wait for any task to complete (usually capture ends when call ends)
            done, pending = await asyncio.wait(
                [capture_task, receive_task, playback_task, input_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error(f"EAGI Error: {e}", exc_info=True)
            self.agi.verbose(f"WeeVoice Error: {str(e)[:50]}", 1)
        
        finally:
            self.running = False
            
            # Save call data
            self._save_call_data()
            
            # End Gemini session
            if self.agent_service:
                try:
                    await self.agent_service.end_session()
                except:
                    pass
            
            # Close database
            if self.db:
                try:
                    self.db.close()
                except:
                    pass
            
            logger.info("WeeVoice EAGI Ended")


def main():
    """Entry point"""
    def signal_handler(sig, frame):
        logger.info(f"Signal {sig} received")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    eagi = WeeVoiceEAGI()
    
    try:
        asyncio.run(eagi.run())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
