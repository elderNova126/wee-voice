#!/usr/bin/env python3
"""
WeeVoice Real-Time EAGI Script for Asterisk AI Voice Agent

This script routes incoming calls to the correct AI agent based on the
called DID (phone number). It supports multiple phone numbers, each with
their own SIP configuration and assigned agent.

Place in: /var/lib/asterisk/agi-bin/weevoice_eagi_realtime.py
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
import re
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
HIGH_QUALITY_MODE = os.environ.get('WEEVOICE_HIGH_QUALITY', 'true').lower() == 'true'

# Temp directory for audio files
# Use /dev/shm (RAM disk) for faster audio file I/O - reduces choppy audio
# Fallback to /tmp if /dev/shm doesn't exist
if Path('/dev/shm').exists():
    TEMP_AUDIO_DIR = Path('/dev/shm/weevoice_audio')
else:
    TEMP_AUDIO_DIR = Path('/tmp/weevoice_audio')
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def normalize_phone_number(number: str) -> str:
    """
    Normalize phone number for database lookup.
    Handles various formats and returns E.164 format (+XXXXXXXXXXX)
    """
    if not number:
        return ""
    
    # Remove all non-digit characters except +
    normalized = re.sub(r'[^\d+]', '', number)
    
    # Handle empty string
    if not normalized:
        return ""
    
    # Ensure + prefix for international format
    if not normalized.startswith('+'):
        # If starts with 00, replace with +
        if normalized.startswith('00'):
            normalized = '+' + normalized[2:]
        # If it looks like an international number (10+ digits), add +
        elif len(normalized) >= 10:
            normalized = '+' + normalized
    
    return normalized


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
    EAGI handler that routes calls to the correct agent based on the called DID.
    Supports multiple phone numbers with different SIP configurations.
    """
    
    def __init__(self):
        self.agi = AGI()
        self.call_id = ""
        self.caller_id = ""
        self.called_did = ""  # The phone number that was called
        self.running = False
        self._audio_fd = None
        self._resample_state_in = None
        self._resample_state_out = None
        
        # These will be set from database
        self.agent = None
        self.call = None
        self.phone_number = None  # PhoneNumber record
        self.agent_service = None
        self.db = None
        
        # LLM Model configuration (set from database)
        # - 'gemini': Native audio dialog (8kHz→16kHz input, 24kHz output)
        # - 'gpt-*': OpenAI models (can use 8kHz directly - no input resampling needed)
        self.llm_model = 'gemini'  # Default to Gemini for voice calls
        
        # Output buffer - sample rate depends on quality mode
        output_rate = 16000 if HIGH_QUALITY_MODE else ASTERISK_RATE
        self.output_buffer = AudioBuffer(max_size_ms=3000, sample_rate=output_rate)
        self.output_rate = output_rate
        
    def _resample_8k_to_16k(self, audio_8k: bytes) -> bytes:
        """
        Process caller audio for AI model input.
        
        Model-aware processing:
        - Gemini: Requires 16kHz PCM input, so upsample from 8kHz
        - OpenAI (gpt-*): g711_ulaw format - encode PCM to μ-law (no resampling!)
        """
        if len(audio_8k) < 2:
            return b''
        
        try:
            # Model-aware audio processing
            if self.llm_model and self.llm_model.lower().startswith('gpt'):
                # OpenAI g711_ulaw: Encode PCM16 → μ-law
                # This is simple encoding, NOT resampling - stays at 8kHz
                # μ-law compresses 16-bit to 8-bit (half the bytes)
                return audioop.lin2ulaw(audio_8k, 2)
            else:
                # Gemini requires 16kHz input - upsample from 8kHz
                result, self._resample_state_in = audioop.ratecv(
                    audio_8k, 2, 1, ASTERISK_RATE, GEMINI_INPUT_RATE, self._resample_state_in
                )
                return result
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return audio_8k
    
    def _get_input_sample_rate(self) -> int:
        """Get the appropriate input sample rate based on LLM model"""
        if self.llm_model and self.llm_model.lower().startswith('gpt'):
            return ASTERISK_RATE  # 8kHz for OpenAI (g711_ulaw native)
        return GEMINI_INPUT_RATE  # 16kHz for Gemini
    
    def _resample_output(self, audio_data: bytes) -> bytes:
        """
        Convert AI model output for Asterisk playback.
        
        - OpenAI (g711_ulaw): Decode μ-law → PCM16 (no resampling!)
        - Gemini: 24kHz output, needs resampling to 8kHz or 16kHz
        """
        if len(audio_data) < 1:
            return b''
        
        try:
            # OpenAI g711_ulaw: Decode μ-law → PCM16
            if self.llm_model and self.llm_model.lower().startswith('gpt'):
                # This is simple decoding, NOT resampling - stays at 8kHz
                # μ-law expands 8-bit to 16-bit (double the bytes)
                return audioop.ulaw2lin(audio_data, 2)
            
            # Gemini: 24kHz output needs resampling
            if HIGH_QUALITY_MODE:
                # For SIP/WebRTC: Use 16kHz (slin16) - widely supported
                target_rate = 16000
                result, self._resample_state_out = audioop.ratecv(
                    audio_data, 2, 1, GEMINI_OUTPUT_RATE, target_rate, self._resample_state_out
                )
                return result
            else:
                # For PSTN: Standard 8kHz (slin)
                result, self._resample_state_out = audioop.ratecv(
                    audio_data, 2, 1, GEMINI_OUTPUT_RATE, ASTERISK_RATE, self._resample_state_out
                )
                return result
        except Exception as e:
            logger.error(f"Audio output error: {e}")
            return audio_data
    
    def _extract_called_did(self, env: Dict[str, str]) -> str:
        """
        Extract the called DID (phone number) from AGI environment.
        
        The DID can come from various sources depending on the call type:
        - agi_extension: The dialed extension
        - agi_dnid: The original dialed number
        - EXTEN channel variable
        - CALLERID(dnid): Dialed number ID
        - FROM_DID channel variable (set in extensions.conf)
        """
        # Try FROM_DID first (custom variable set in extensions.conf)
        from_did = self.agi.get_var('FROM_DID')
        if from_did and from_did not in ('', 's', 'h'):
            logger.info(f"Got DID from FROM_DID: {from_did}")
            return normalize_phone_number(from_did)
        
        # Try agi_dnid (Dialed Number Identification)
        dnid = env.get('agi_dnid', '')
        if dnid and dnid not in ('', 's', 'unknown'):
            logger.info(f"Got DID from agi_dnid: {dnid}")
            return normalize_phone_number(dnid)
        
        # Try agi_extension
        extension = env.get('agi_extension', '')
        if extension and len(extension) >= 7:  # Likely a phone number, not internal ext
            logger.info(f"Got DID from agi_extension: {extension}")
            return normalize_phone_number(extension)
        
        # Try EXTEN channel variable
        exten = self.agi.get_var('EXTEN')
        if exten and len(exten) >= 7:
            logger.info(f"Got DID from EXTEN: {exten}")
            return normalize_phone_number(exten)
        
        # Try agi_calleridname (sometimes contains DID info)
        callerid_name = env.get('agi_calleridname', '')
        if callerid_name and callerid_name.startswith('+'):
            logger.info(f"Got DID from agi_calleridname: {callerid_name}")
            return normalize_phone_number(callerid_name)
        
        logger.warning("Could not extract DID from AGI environment")
        return ""
    
    def _setup_from_database(self) -> bool:
        """
        Load agent and phone number from database based on the called DID.
        Routes calls to the correct agent based on which phone number was called.
        """
        try:
            # Import models
            from app.models.database import SessionLocal
            from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
            from sqlalchemy import text
            
            logger.info("Connecting to database...")
            self.db = SessionLocal()
            
            phone = None
            
            # First try to find phone number by the called DID
            if self.called_did:
                logger.info(f"Looking up phone number by DID: {self.called_did}")
                
                # Try exact match first
                phone = self.db.query(PhoneNumber).filter(
                    PhoneNumber.phone_number == self.called_did,
                    PhoneNumber.agent_id.isnot(None)
                ).first()
                
                # Try without + prefix
                if not phone and self.called_did.startswith('+'):
                    did_without_plus = self.called_did[1:]
                    phone = self.db.query(PhoneNumber).filter(
                        PhoneNumber.phone_number == did_without_plus,
                        PhoneNumber.agent_id.isnot(None)
                    ).first()
                
                # Try LIKE search (handles format variations)
                if not phone:
                    # Remove all non-digits for comparison
                    did_digits = re.sub(r'\D', '', self.called_did)
                    if len(did_digits) >= 7:
                        # Search for numbers ending with these digits
                        result = self.db.execute(text("""
                            SELECT id FROM phone_numbers 
                            WHERE REPLACE(REPLACE(REPLACE(phone_number, '+', ''), ' ', ''), '-', '') LIKE :pattern
                            AND agent_id IS NOT NULL
                            LIMIT 1
                        """), {"pattern": f"%{did_digits[-10:]}"}).first()
                        
                        if result:
                            phone = self.db.query(PhoneNumber).filter(
                                PhoneNumber.id == result[0]
                            ).first()
                
                if phone:
                    logger.info(f"Found phone number: {phone.phone_number}, agent_id: {phone.agent_id}")
                else:
                    logger.warning(f"No phone number found for DID: {self.called_did}")
            
            # Fallback: Find any phone number with SIP config and agent
            if not phone:
                logger.warning("Falling back to first available phone number with SIP config...")
                phone = self.db.query(PhoneNumber).filter(
                    PhoneNumber.agent_id.isnot(None),
                    PhoneNumber.sip_username.isnot(None)
                ).first()
                
                if phone:
                    logger.info(f"Using fallback phone: {phone.phone_number}, agent_id: {phone.agent_id}")
            
            if not phone:
                logger.error("No phone numbers with agents configured in database")
                return self._setup_fallback_mode()
            
            self.phone_number = phone
            
            # Get LLM model from phone number configuration
            self.llm_model = getattr(phone, 'llm_model', 'gemini') or 'gemini'
            logger.info(f"LLM Model configured: {self.llm_model}")
            
            # Get the agent assigned to this phone number
            self.agent = self.db.query(VoiceAgent).filter(
                VoiceAgent.id == phone.agent_id
            ).first()
            
            if not self.agent:
                logger.error(f"Agent {phone.agent_id} not found for phone {phone.phone_number}")
                # Try fallback to first active agent
                self.agent = self.db.query(VoiceAgent).filter(
                    VoiceAgent.is_active == True
                ).first()
            
            if not self.agent:
                logger.error("No agents found in database")
                return self._setup_fallback_mode()
            
            logger.info(f"=" * 50)
            logger.info(f"CALL ROUTING RESOLVED:")
            logger.info(f"  Called DID: {self.called_did}")
            logger.info(f"  Phone Number: {phone.phone_number} (ID: {phone.id})")
            logger.info(f"  Agent: {self.agent.name} (ID: {self.agent.id})")
            logger.info(f"  LLM Model: {self.llm_model}")
            logger.info(f"  Language: {self.agent.language}")
            logger.info(f"  Voice Gender: {getattr(self.agent, 'voice_gender', 'default')}")
            logger.info(f"  Voice ID: {getattr(self.agent, 'voice_id', 'default')}")
            logger.info(f"  Greeting: {self.agent.greeting[:50] if self.agent.greeting else 'None'}...")
            
            # Audio processing optimization based on LLM model
            if self.llm_model.lower().startswith('gpt'):
                # OpenAI with g711_ulaw: 8kHz native - no resampling at all!
                self.output_rate = ASTERISK_RATE  # 8kHz
                self.output_buffer = AudioBuffer(max_size_ms=3000, sample_rate=ASTERISK_RATE)
                logger.info(f"  🎵 Audio: OpenAI mode - 8kHz native (NO resampling)")
            else:
                # Gemini: 16kHz input, 24kHz→8kHz/16kHz output
                logger.info(f"  🎵 Audio: Gemini mode - 8kHz→16kHz input, 24kHz→{self.output_rate}Hz output")
            logger.info(f"=" * 50)
            
            # Create call record
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
            logger.info("Falling back to environment-based configuration...")
            return self._setup_fallback_mode()
    
    def _setup_fallback_mode(self) -> bool:
        """
        Fallback mode when database is not available.
        Uses environment variables and creates mock objects.
        """
        try:
            logger.info("Setting up FALLBACK MODE (no database)")
            
            # Create a mock agent object
            class MockAgent:
                def __init__(self):
                    self.id = 1
                    self.user_id = 1
                    self.name = os.environ.get('AGENT_NAME', 'WeeVoice AI')
                    self.system_prompt = os.environ.get('AGENT_SYSTEM_PROMPT', 
                        "You are a helpful and professional phone assistant. "
                        "Keep responses concise and natural. Be friendly.")
                    self.greeting = os.environ.get('AGENT_GREETING', 
                        "Hello! How can I help you today?")
                    self.language = os.environ.get('AGENT_LANGUAGE', 'en-US')
                    self.voice_gender = os.environ.get('AGENT_VOICE_GENDER', 'female')
                    self.voice_id = os.environ.get('AGENT_VOICE_ID', 'Aoede')
                    self.model_name = os.environ.get('GEMINI_MODEL', 
                        'gemini-2.5-flash-native-audio-preview-09-2025')
                    self.temperature = 0.7
                    self.rag_enabled = False
                    self.tools_enabled = []
                    self.email_request_enabled = False
                    self.manager_contact = None
            
            # Create a mock call object
            class MockCall:
                def __init__(self, call_id, caller_id):
                    self.id = 1
                    self.session_id = f"eagi_{call_id}"
                    self.caller_phone = caller_id
                    self.caller_name = caller_id
                    self.status = "initiated"
                    self.started_at = datetime.utcnow()
                    self.ended_at = None
                    self.duration = 0
                    self.transcript = ""
            
            self.agent = MockAgent()
            self.call = MockCall(self.call_id, self.caller_id)
            self.db = None  # No database in fallback mode
            
            logger.info(f"Fallback agent: {self.agent.name}")
            logger.info(f"  Voice: {self.agent.voice_id}")
            logger.info(f"  Greeting: {self.agent.greeting[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Fallback setup error: {e}", exc_info=True)
            return False
    
    def _setup_agent_service(self) -> bool:
        """
        Create voice agent service based on configured LLM model.
        Uses factory function to select between Gemini and OpenAI Realtime API.
        """
        try:
            from app.services.openai_realtime_service import get_voice_agent_service, is_openai_model
            
            logger.info("Creating voice agent service...")
            logger.info(f"  LLM Model configured: {self.llm_model}")
            
            # Log model selection
            if is_openai_model(self.llm_model):
                logger.info(f"🔵 Using OpenAI Realtime API for voice (model: {self.llm_model})")
                logger.info("  Audio: 8kHz native input (no resampling needed)")
            else:
                logger.info("🟢 Using Gemini Live API for voice")
                logger.info("  Audio: 8kHz→16kHz input resampling")
            
            # Create the appropriate service using factory function
            self.agent_service = get_voice_agent_service(
                agent=self.agent,
                call=self.call,
                llm_model=self.llm_model,
                skip_greeting_trigger=False  # Let AI handle greeting
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
            
            # Update call status (only if we have database)
            if self.db:
                from app.models import CallStatus
                self.call.status = CallStatus.IN_PROGRESS
                self.db.commit()
            else:
                self.call.status = "in_progress"
            
            logger.info("Gemini session started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gemini session error: {e}", exc_info=True)
            return False
    
    async def _audio_capture_loop(self):
        """Capture audio from EAGI FD3 and send to AI model"""
        # Determine audio configuration based on LLM model
        input_rate = self._get_input_sample_rate()
        mime_type = f"audio/pcm;rate={input_rate}"
        
        logger.info(f"Starting audio capture from FD3")
        logger.info(f"  LLM Model: {self.llm_model}")
        logger.info(f"  Input Rate: {input_rate}Hz")
        logger.info(f"  MIME Type: {mime_type}")
        
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
                
                # Model-aware audio processing:
                # - OpenAI: Send 8kHz directly (native support, best quality)
                # - Gemini: Upsample to 16kHz (required by Gemini)
                audio_for_ai = self._resample_8k_to_16k(audio_8k)
                
                if audio_for_ai and self.agent_service:
                    await self.agent_service.send_audio(
                        audio_for_ai, 
                        mime_type=mime_type
                    )
                
                if frame_count % 250 == 0:
                    logger.debug(f"Captured {frame_count} frames ({input_rate}Hz)")
                    
            except Exception as e:
                if 'closed' in str(e).lower():
                    break
                logger.error(f"Audio capture error: {e}")
                await asyncio.sleep(0.01)
        
        logger.info(f"Audio capture ended: {frame_count} frames at {input_rate}Hz")
        
        if self._audio_fd:
            try:
                self._audio_fd.close()
            except:
                pass
    
    async def _audio_receive_loop(self):
        """Receive audio from AI model and buffer for playback"""
        logger.info("Starting audio receive loop")
        chunk_count = 0
        total_bytes = 0
        
        try:
            async for audio_data in self.agent_service.receive_audio():
                if not self.running:
                    break
                
                if audio_data:
                    chunk_count += 1
                    # Convert output for Asterisk (μ-law decode for OpenAI, resample for Gemini)
                    audio_out = self._resample_output(audio_data)
                    if audio_out:
                        total_bytes += len(audio_out)
                        self.output_buffer.push(audio_out)
                        
                        # Log periodically
                        if chunk_count <= 3 or chunk_count % 50 == 0:
                            buffer_ms = self.output_buffer.available_ms()
                            logger.info(f"[RECV] #{chunk_count}: {len(audio_data)}→{len(audio_out)} bytes, buffer={buffer_ms}ms")
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if 'closed' not in str(e).lower():
                logger.error(f"Receive loop error: {e}")
        
        logger.info(f"Receive loop ended: {chunk_count} chunks, {total_bytes} bytes total")
    
    async def _audio_playback_loop(self):
        """Play buffered audio back to caller using AGI STREAM FILE"""
        logger.info(f"Starting audio playback loop (rate={self.output_rate}Hz, high_quality={HIGH_QUALITY_MODE})")
        
        audio_dir = TEMP_AUDIO_DIR / self.call_id
        audio_dir.mkdir(exist_ok=True)
        
        chunk_index = 0
        min_buffer_ms = 500  # Wait for 500ms buffer before starting (more headroom)
        chunk_ms = 200       # Play 200ms chunks (less overhead per unit time)
        
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
                    await asyncio.sleep(0.02)  # Check more frequently
                    continue
                
                # Get chunk_ms of audio (200ms = smoother playback)
                chunk_bytes = int(self.output_rate * 2 * chunk_ms / 1000)
                audio_chunk = self.output_buffer.pop(chunk_bytes)
                
                # Check if it's not just silence
                if audio_chunk and audio_chunk != b'\x00' * len(audio_chunk):
                    # Save to temp file with correct extension
                    filename = audio_dir / f"chunk_{chunk_index:04d}{file_ext}"
                    with open(filename, 'wb') as f:
                        f.write(audio_chunk)
                    
                    # Log playback progress
                    if chunk_index <= 3 or chunk_index % 20 == 0:
                        remaining = self.output_buffer.available_ms()
                        logger.info(f"[PLAY] #{chunk_index}: {len(audio_chunk)} bytes, remaining={remaining}ms")
                    
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
        """Save final call data to database (if available)"""
        try:
            if self.call:
                self.call.ended_at = datetime.utcnow()
                if hasattr(self.call, 'started_at') and self.call.started_at:
                    duration = (self.call.ended_at - self.call.started_at).total_seconds()
                    self.call.duration = int(duration)
                    logger.info(f"Call duration: {self.call.duration}s")
                
                # Only save to database if we have a db connection
                if self.db:
                    from app.models import CallStatus
                    self.call.status = CallStatus.COMPLETED
                    self.db.commit()
                    logger.info(f"Call {self.call.id} saved to database")
                else:
                    logger.info("No database - call data not persisted")
                
        except Exception as e:
            logger.error(f"Failed to save call data: {e}")
    
    async def run(self):
        """Main EAGI execution"""
        logger.info("=" * 60)
        logger.info("WeeVoice EAGI Started (Multi-Number Routing)")
        logger.info(f"Audio Mode: {'HIGH QUALITY (16kHz)' if HIGH_QUALITY_MODE else 'STANDARD (8kHz PSTN)'}")
        logger.info("=" * 60)
        
        try:
            # Read AGI environment
            env = self.agi.read_env()
            
            self.call_id = env.get('agi_uniqueid', str(int(time.time())))
            self.caller_id = env.get('agi_callerid', 'Unknown')
            channel = env.get('agi_channel', 'unknown')
            
            # Extract the called DID (phone number that was dialed)
            self.called_did = self._extract_called_did(env)
            
            logger.info(f"Call ID: {self.call_id}")
            logger.info(f"Caller: {self.caller_id}")
            logger.info(f"Called DID: {self.called_did}")
            logger.info(f"Channel: {channel}")
            
            # Log all AGI variables for debugging
            logger.debug("AGI Environment Variables:")
            for key, value in env.items():
                logger.debug(f"  {key}: {value}")
            
            # Step 1: Load agent from database based on called DID
            if not self._setup_from_database():
                self.agi.verbose("WeeVoice: Database Error", 1)
                return
            
            # Step 2: Create FrenchVoiceAgentService
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
