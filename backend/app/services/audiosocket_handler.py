"""
Asterisk AudioSocket Handler

Uses asyncio with TCP_NODELAY to ensure immediate frame delivery.
"""
import asyncio
import socket
import struct
import logging
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

FRAME_SIZE = 320  # 160 samples * 2 bytes = 20ms at 8kHz
SILENCE_FRAME = b'\x00' * FRAME_SIZE


class ResampleState:
    """Maintains resampling state for continuous audio streams"""
    def __init__(self):
        self.state_24_12 = None
        self.state_12_8 = None
        self.state_8_16 = None


def high_quality_resample(audio_bytes: bytes, from_rate: int, to_rate: int, state=None):
    """
    Higher quality resampling using audioop with proper state management.
    For downsampling, we do it in steps to preserve quality.
    """
    if from_rate == to_rate:
        return audio_bytes, state
    
    if state is None:
        state = ResampleState()
    
    # For large rate changes, do in steps for better quality
    if from_rate == 24000 and to_rate == 8000:
        # 24k -> 12k -> 8k (two steps with maintained state)
        audio_12k, state.state_24_12 = audioop.ratecv(audio_bytes, 2, 1, 24000, 12000, state.state_24_12)
        audio_8k, state.state_12_8 = audioop.ratecv(audio_12k, 2, 1, 12000, 8000, state.state_12_8)
        return audio_8k, state
    elif from_rate == 8000 and to_rate == 16000:
        # Direct 2x upsampling is fine
        audio_16k, state.state_8_16 = audioop.ratecv(audio_bytes, 2, 1, from_rate, to_rate, state.state_8_16)
        return audio_16k, state
    else:
        # Default single-step conversion
        return audioop.ratecv(audio_bytes, 2, 1, from_rate, to_rate, None)

# Track active calls per phone number
_active_calls: dict[int, str] = {}  # phone_number_id -> call_uuid
_active_calls_lock = asyncio.Lock()


class AudioSocketSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.call_uuid = None
        self.call = None
        self.agent = None
        self.agent_service = None
        self.is_running = False
        self.db = None
        self.send_task = None
        self.ai_ready = asyncio.Event()
        self.ai_audio_queue = asyncio.Queue()  # AI audio to send to Asterisk
        self.caller_audio_queue = asyncio.Queue(maxsize=100)  # Caller audio to send to Gemini
        self._write_lock = asyncio.Lock()
        self.phone_number_id = None  # Track which phone number this call is using
        self.is_busy_response = False  # Flag for busy response mode
        self.busy_config = None  # Store busy action config (busy_tone/voicemail)
        
    async def handle(self):
        import time
        import traceback
        t0 = time.time()
        def ts():
            return f"[{(time.time()-t0)*1000:.1f}ms]"
        
        addr = self.writer.get_extra_info('peername')
        print(f"{ts()} === AudioSocket CONNECTED from {addr} ===", flush=True)
        
        try:
            self.is_running = True
            print(f"{ts()} is_running set", flush=True)
            
            # Get the raw socket for direct operations
            sock = self.writer.get_extra_info('socket')
            print(f"{ts()} Got socket: {sock}", flush=True)
            if not sock:
                print(f"{ts()} ERROR: Could not get socket!", flush=True)
                return
            
            # CRITICAL: Set TCP_NODELAY
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(f"{ts()} TCP_NODELAY set", flush=True)
            except Exception as e:
                print(f"{ts()} TCP_NODELAY failed: {e}", flush=True)
            
            # Send first frames directly via writer (simpler approach)
            header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
            for i in range(5):
                self.writer.write(header + SILENCE_FRAME)
            await self.writer.drain()
            print(f"{ts()} 5 silence frames sent via writer.drain()", flush=True)
            
            # Start the continuous send task
            self.send_task = asyncio.create_task(self._send_loop())
            print(f"{ts()} Send task CREATED", flush=True)
            
            # Read UUID
            print(f"{ts()} Starting UUID read...", flush=True)
            await self._read_uuid()
            print(f"{ts()} UUID read complete: {self.call_uuid}", flush=True)
            
            if not self.call_uuid:
                logger.error("No UUID")
                return
            
            logger.info(f"Call UUID: {self.call_uuid}")
            
            # Setup call (takes time for Gemini init)
            print(f"[HANDLE] Starting _setup_call...", flush=True)
            if not await self._setup_call():
                print(f"[HANDLE] _setup_call FAILED", flush=True)
                
                # Check if this was due to busy line
                if self.is_busy_response:
                    print(f"[HANDLE] Playing BUSY message...", flush=True)
                    await self._play_busy_message()
                return
            
            # Signal AI is ready
            self.ai_ready.set()
            print(f"[HANDLE] AI READY - will now process caller audio", flush=True)
            
            # Start AI tasks - CRITICAL: must start send_realtime_input to consume audio queue!
            ai_receive_task = asyncio.create_task(self._ai_receive_loop())
            caller_to_ai_task = asyncio.create_task(self._caller_audio_to_gemini_loop())
            gemini_input_task = asyncio.create_task(self.agent_service.send_realtime_input())
            print(f"[HANDLE] Gemini input task STARTED", flush=True)
            
            # Main receive loop
            await self._receive_loop()
            
            # Cancel all tasks
            for task in [caller_to_ai_task, gemini_input_task, ai_receive_task]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            print(f"[HANDLE] EXCEPTION: {e}", flush=True)
            import traceback
            traceback.print_exc()
            logger.error(f"AudioSocket error: {e}", exc_info=True)
        finally:
            print(f"[HANDLE] Cleanup starting...", flush=True)
            await self._cleanup()
            print(f"[HANDLE] Cleanup done", flush=True)
    
    async def _send_loop(self):
        """Continuously send audio frames to Asterisk at precise 20ms intervals"""
        import time
        t0 = time.time()
        print(f"[SEND] Loop STARTED", flush=True)
        
        frames_sent = 0
        transport = self.writer.transport
        audio_buffer = b''  # Buffer to accumulate AI audio
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        
        # Timing: maintain precise 20ms frame rate
        frame_duration = 0.02  # 20ms
        next_frame_time = time.time()
        
        # Track if we're in the middle of playing AI speech
        ai_speaking = False
        silence_frames_sent = 0
        MAX_SILENCE_DURING_SPEECH = 3  # Only allow 3 silence frames (60ms) during speech
        
        # Pre-buffer threshold: wait for this much audio before starting to play
        PRE_BUFFER_SIZE = FRAME_SIZE * 5  # 100ms of pre-buffering
        pre_buffering = True
        
        try:
            while self.is_running:
                # Collect all available AI audio into buffer
                collected = 0
                while True:
                    try:
                        chunk = self.ai_audio_queue.get_nowait()
                        audio_buffer += chunk
                        collected += len(chunk)
                    except asyncio.QueueEmpty:
                        break
                
                # Pre-buffering phase: wait until we have enough audio
                if pre_buffering and len(audio_buffer) < PRE_BUFFER_SIZE:
                    # Send silence while pre-buffering
                    try:
                        transport.write(header + SILENCE_FRAME)
                    except Exception as e:
                        print(f"[SEND] Transport write FAILED: {e}", flush=True)
                        break
                    
                    frames_sent += 1
                    if frames_sent <= 5:
                        print(f"[SEND] Pre-buffer frame #{frames_sent}, buffer={len(audio_buffer)}", flush=True)
                    
                    next_frame_time += frame_duration
                    sleep_time = next_frame_time - time.time()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    continue
                
                if pre_buffering:
                    print(f"[SEND] Pre-buffer complete, starting playback with {len(audio_buffer)} bytes", flush=True)
                    pre_buffering = False
                
                # Get one frame's worth of data
                if len(audio_buffer) >= FRAME_SIZE:
                    audio_data = audio_buffer[:FRAME_SIZE]
                    audio_buffer = audio_buffer[FRAME_SIZE:]
                    ai_speaking = True
                    silence_frames_sent = 0
                elif ai_speaking and silence_frames_sent < MAX_SILENCE_DURING_SPEECH:
                    # During AI speech, if buffer is temporarily empty, wait a bit for more audio
                    # instead of immediately sending silence
                    try:
                        # Wait up to 40ms for more audio
                        chunk = await asyncio.wait_for(self.ai_audio_queue.get(), timeout=0.04)
                        audio_buffer += chunk
                        # Try to get more if available
                        while True:
                            try:
                                chunk = self.ai_audio_queue.get_nowait()
                                audio_buffer += chunk
                            except asyncio.QueueEmpty:
                                break
                        
                        if len(audio_buffer) >= FRAME_SIZE:
                            audio_data = audio_buffer[:FRAME_SIZE]
                            audio_buffer = audio_buffer[FRAME_SIZE:]
                            silence_frames_sent = 0
                        else:
                            audio_data = SILENCE_FRAME
                            silence_frames_sent += 1
                    except asyncio.TimeoutError:
                        audio_data = SILENCE_FRAME
                        silence_frames_sent += 1
                else:
                    # Not in AI speech or exceeded silence limit
                    audio_data = SILENCE_FRAME
                    if silence_frames_sent >= MAX_SILENCE_DURING_SPEECH:
                        ai_speaking = False  # AI stopped speaking
                        pre_buffering = True  # Re-enable pre-buffering for next speech
                
                # Send frame
                try:
                    transport.write(header + audio_data)
                except Exception as e:
                    print(f"[SEND] Transport write FAILED: {e}", flush=True)
                    break
                
                frames_sent += 1
                if frames_sent <= 5:
                    print(f"[SEND] Frame #{frames_sent} at {(time.time()-t0)*1000:.1f}ms", flush=True)
                if frames_sent % 100 == 0:
                    print(f"[SEND] {frames_sent} frames, buffer={len(audio_buffer)}, speaking={ai_speaking}", flush=True)
                
                # Precise timing: wait until next frame time
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                elif sleep_time < -0.1:  # More than 100ms behind, reset timing
                    next_frame_time = time.time()
                
        except asyncio.CancelledError:
            print(f"[SEND] CANCELLED after {frames_sent}", flush=True)
        except Exception as e:
            print(f"[SEND] ERROR: {e}", flush=True)
        
        print(f"[SEND] ENDED: {frames_sent} total", flush=True)
    
    async def _receive_loop(self):
        """Receive audio from Asterisk"""
        import time
        t0 = time.time()
        print(f"[RECV] Loop STARTED")
        
        frames = 0
        try:
            while self.is_running:
                # Read header
                try:
                    header = await asyncio.wait_for(
                        self.reader.readexactly(3),
                        timeout=60.0
                    )
                except asyncio.IncompleteReadError as e:
                    print(f"[RECV] IncompleteReadError: {e}")
                    break
                except asyncio.TimeoutError:
                    print(f"[RECV] Timeout after {frames} frames")
                    break
                
                msg_type = header[0]
                payload_len = struct.unpack('>H', header[1:3])[0]
                
                # Read payload
                if payload_len > 0:
                    try:
                        payload = await self.reader.readexactly(payload_len)
                    except asyncio.IncompleteReadError:
                        print(f"[RECV] Payload incomplete")
                        break
                else:
                    payload = b''
                
                if msg_type == MSG_AUDIO:
                    frames += 1
                    elapsed = (time.time() - t0) * 1000
                    if frames <= 10 or frames % 50 == 0:
                        print(f"[RECV] Frame #{frames} at {elapsed:.0f}ms", flush=True)
                    await self._process_audio(payload)
                elif msg_type == MSG_HANGUP:
                    print(f"[RECV] HANGUP received")
                    break
                elif msg_type == MSG_ERROR:
                    print(f"[RECV] ERROR from Asterisk")
                    break
                else:
                    print(f"[RECV] Unknown type: 0x{msg_type:02x}")
                    
        except Exception as e:
            print(f"[RECV] Exception: {e}")
        
        print(f"[RECV] Loop ENDED: {frames} frames total")
    
    async def _read_uuid(self):
        """Read UUID packet"""
        import time
        import os
        t0 = time.time()
        try:
            print(f"[UUID] Waiting for header...")
            header = await asyncio.wait_for(
                self.reader.readexactly(3), 
                timeout=5.0
            )
            elapsed = (time.time() - t0) * 1000
            print(f"[UUID] Header received at {elapsed:.1f}ms: {header.hex()}")
            
            msg_type = header[0]
            payload_len = struct.unpack('>H', header[1:3])[0]
            
            print(f"[UUID] type=0x{msg_type:02x}, len={payload_len}")
            
            if msg_type == MSG_UUID and payload_len > 0:
                uuid_bytes = await asyncio.wait_for(
                    self.reader.readexactly(payload_len),
                    timeout=5.0
                )
                print(f"[UUID] Payload received: {uuid_bytes[:50]}...")
                try:
                    self.call_uuid = uuid_bytes.decode('ascii').strip()
                    if len(self.call_uuid) == 36:
                        print(f"[UUID] Valid: {self.call_uuid}")
                        # Try to read caller ID from temp file (written by Asterisk)
                        self._read_caller_id_file()
                        return
                except:
                    pass
            
            self.call_uuid = str(uuid_lib.uuid4())
            print(f"[UUID] Generated: {self.call_uuid}")
            
        except asyncio.TimeoutError:
            print(f"[UUID] TIMEOUT waiting for header!")
            self.call_uuid = str(uuid_lib.uuid4())
        except Exception as e:
            print(f"[UUID] ERROR: {e}")
            self.call_uuid = str(uuid_lib.uuid4())
    
    def _read_caller_id_file(self):
        """Read caller ID from temp file created by Asterisk dialplan"""
        import os
        try:
            callerid_file = f"/tmp/callerid_{self.call_uuid}"
            if os.path.exists(callerid_file):
                with open(callerid_file, 'r') as f:
                    raw_caller_id = f.read().strip()
                os.unlink(callerid_file)  # Delete after reading
                
                # Clean up caller ID (remove quotes, extra chars)
                self.caller_id = raw_caller_id.strip('"\'').strip()
                
                # Normalize: ensure it starts with + for international
                if self.caller_id and not self.caller_id.startswith('+') and self.caller_id[0].isdigit():
                    # If starts with country code like 84xxx, add +
                    if len(self.caller_id) > 9:
                        self.caller_id = '+' + self.caller_id
                
                print(f"[UUID] Caller ID from file: raw='{raw_caller_id}', normalized='{self.caller_id}'", flush=True)
                logger.info(f"[UUID] Read caller ID: raw='{raw_caller_id}', normalized='{self.caller_id}' from {callerid_file}")
            else:
                print(f"[UUID] No caller ID file found at {callerid_file}", flush=True)
                logger.warning(f"[UUID] No caller ID file at {callerid_file}")
                self.caller_id = None
        except Exception as e:
            print(f"[UUID] Error reading caller ID: {e}", flush=True)
            logger.error(f"[UUID] Error reading caller ID: {e}")
            self.caller_id = None
    
    def _parse_restriction_list(self, value) -> list:
        """Parse restriction list that might be JSON, PostgreSQL array, or already a list"""
        import json
        
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            if not value or value.strip() in ('', '[]', '{}'):
                return []
            # Handle PostgreSQL array format: {VN} or {VN,UK}
            if value.startswith('{') and value.endswith('}') and not value.startswith('{"'):
                inner = value[1:-1]
                if not inner:
                    return []
                return [item.strip().strip('"') for item in inner.split(',') if item.strip()]
            # Handle JSON array format: ["VN"] or ["VN","UK"]
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def _is_caller_blocked(self, phone, caller_phone: str) -> bool:
        """Check if caller is blocked based on phone number restrictions"""
        print(f"[RESTRICT] === _is_caller_blocked() CALLED ===", flush=True)
        print(f"[RESTRICT] caller_phone: {caller_phone}", flush=True)
        print(f"[RESTRICT] phone.restriction_mode: '{phone.restriction_mode}'", flush=True)
        
        restriction_mode = phone.restriction_mode or 'none'
        
        # Log the restriction settings
        logger.info(f"[RESTRICT] Checking call from {caller_phone}")
        logger.info(f"[RESTRICT] Mode: {restriction_mode}")
        logger.info(f"[RESTRICT] Raw blocked_countries: {phone.blocked_countries}")
        logger.info(f"[RESTRICT] Raw blocked_numbers: {phone.blocked_numbers}")
        logger.info(f"[RESTRICT] Raw allowed_countries: {phone.allowed_countries}")
        print(f"[RESTRICT] Effective mode after 'or none': '{restriction_mode}'", flush=True)
        print(f"[RESTRICT] Raw blocked_countries: {phone.blocked_countries}", flush=True)
        print(f"[RESTRICT] Raw blocked_numbers: {phone.blocked_numbers}", flush=True)
        
        if restriction_mode == 'none':
            logger.info(f"[RESTRICT] No restrictions, allowing call")
            print(f"[RESTRICT] No restrictions, allowing call", flush=True)
            return False
        
        # Parse restriction lists (handles both JSON and PostgreSQL array formats)
        blocked_countries = self._parse_restriction_list(phone.blocked_countries)
        blocked_numbers = self._parse_restriction_list(phone.blocked_numbers)
        allowed_countries = self._parse_restriction_list(phone.allowed_countries)
        
        logger.info(f"[RESTRICT] Parsed blocked_countries: {blocked_countries}")
        logger.info(f"[RESTRICT] Parsed blocked_numbers: {blocked_numbers}")
        logger.info(f"[RESTRICT] Parsed allowed_countries: {allowed_countries}")
        print(f"[RESTRICT] Parsed: blocked_countries={blocked_countries}, blocked_numbers={blocked_numbers}, allowed_countries={allowed_countries}", flush=True)
        
        # Get country code from phone number (basic extraction)
        caller_country = self._get_country_from_number(caller_phone)
        logger.info(f"[RESTRICT] Detected caller country: {caller_country} from number {caller_phone}")
        print(f"[RESTRICT] Caller country detected: {caller_country}", flush=True)
        
        if restriction_mode == 'blacklist':
            # Check if caller's country is blocked
            if caller_country and caller_country.upper() in [c.upper() for c in blocked_countries]:
                logger.warning(f"[RESTRICT] BLOCKED: Country {caller_country} is in blacklist")
                print(f"[RESTRICT] BLOCKED: Country {caller_country} is in blacklist", flush=True)
                return True
            
            # Check if caller's number matches blocked patterns
            for pattern in blocked_numbers:
                if self._number_matches_pattern(caller_phone, pattern):
                    logger.warning(f"[RESTRICT] BLOCKED: Number {caller_phone} matches pattern {pattern}")
                    print(f"[RESTRICT] BLOCKED: Number {caller_phone} matches pattern {pattern}", flush=True)
                    return True
            
            logger.info(f"[RESTRICT] ALLOWED: Caller {caller_phone} not in blacklist")
            print(f"[RESTRICT] ALLOWED: Not in blacklist", flush=True)
            return False
        
        elif restriction_mode == 'whitelist':
            # Only allow if caller's country is in whitelist
            if not allowed_countries:
                # Empty whitelist = block all
                logger.warning(f"[RESTRICT] BLOCKED: Empty whitelist blocks all")
                print(f"[RESTRICT] BLOCKED: Empty whitelist", flush=True)
                return True
            
            if caller_country and caller_country.upper() in [c.upper() for c in allowed_countries]:
                logger.info(f"[RESTRICT] ALLOWED: Country {caller_country} is in whitelist")
                print(f"[RESTRICT] ALLOWED: In whitelist", flush=True)
                return False
            
            logger.warning(f"[RESTRICT] BLOCKED: Country {caller_country} not in whitelist {allowed_countries}")
            print(f"[RESTRICT] BLOCKED: Country {caller_country} not in whitelist", flush=True)
            return True
        
        return False
    
    def _get_country_from_number(self, phone_number: str) -> str:
        """Extract country code from phone number (basic implementation)"""
        # Common country prefixes
        country_prefixes = {
            '+1': 'US', '+44': 'UK', '+33': 'FR', '+49': 'DE', '+32': 'BE',
            '+31': 'NL', '+34': 'ES', '+39': 'IT', '+41': 'CH', '+43': 'AT',
            '+81': 'JP', '+86': 'CN', '+91': 'IN', '+61': 'AU', '+64': 'NZ',
            '+55': 'BR', '+52': 'MX', '+7': 'RU', '+82': 'KR', '+84': 'VN',
            '+62': 'ID', '+60': 'MY', '+65': 'SG', '+66': 'TH', '+63': 'PH',
        }
        
        if not phone_number or phone_number == 'Unknown':
            return ''
        
        # Check longer prefixes first
        for prefix in sorted(country_prefixes.keys(), key=len, reverse=True):
            if phone_number.startswith(prefix):
                return country_prefixes[prefix]
        
        return ''
    
    def _number_matches_pattern(self, phone_number: str, pattern: str) -> bool:
        """Check if phone number matches a pattern (supports * wildcard)"""
        if not phone_number or phone_number == 'Unknown':
            return False
        
        # Exact match
        if phone_number == pattern:
            return True
        
        # Wildcard match (e.g., +1* matches all US numbers)
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return phone_number.startswith(prefix)
        
        return False
    
    async def _setup_call(self) -> bool:
        """Setup call record and AI"""
        print(f"[SETUP] _setup_call() STARTED", flush=True)
        logger.info(f"[SETUP] _setup_call() STARTED")
        
        self.db = SessionLocal()
        try:
            print(f"[SETUP] Querying phone numbers...", flush=True)
            
            # Find phone number with Zadarma/SIP config (the one receiving calls)
            phone = self.db.query(PhoneNumber).filter(
                PhoneNumber.agent_id.isnot(None),
                PhoneNumber.sip_username.isnot(None)  # Has SIP config = receives calls
            ).first()
            
            if not phone:
                print(f"[SETUP] ERROR: No phone number with SIP config found!", flush=True)
                logger.error("No phone number with SIP config found")
                return False
            
            # Refresh to get latest data from database
            self.db.refresh(phone)
            
            print(f"[SETUP] Found phone: {phone.phone_number}, agent_id: {phone.agent_id}", flush=True)
            print(f"[SETUP] Phone restriction_mode from DB: '{phone.restriction_mode}'", flush=True)
            print(f"[SETUP] Phone blocked_countries from DB: '{phone.blocked_countries}'", flush=True)
            print(f"[SETUP] Phone blocked_numbers from DB: '{phone.blocked_numbers}'", flush=True)
            logger.info(f"[SETUP] Phone ID: {phone.id}, Number: {phone.phone_number}")
            logger.info(f"[SETUP] Restriction config: mode={phone.restriction_mode}, blocked_countries={phone.blocked_countries}, blocked_numbers={phone.blocked_numbers}")
            self.phone_number_id = phone.id
            
            # Check if line is busy
            async with _active_calls_lock:
                if phone.id in _active_calls:
                    existing_uuid = _active_calls[phone.id]
                    print(f"[SETUP] LINE BUSY! Phone {phone.phone_number} already has active call: {existing_uuid}", flush=True)
                    logger.info(f"Line busy for {phone.phone_number}, active call: {existing_uuid}")
                    self.is_busy_response = True
                    # Store busy config for message
                    self.busy_config = {
                        'action': phone.busy_action or 'busy_tone',
                        'audio_file_url': phone.busy_audio_file_url
                    }
                    print(f"[SETUP] Busy action: {self.busy_config['action']}, audio_url: {self.busy_config.get('audio_file_url', 'none')}", flush=True)
                    return False  # Will trigger busy response
                
                # Reserve this line
                _active_calls[phone.id] = self.call_uuid
                print(f"[SETUP] Reserved line for call {self.call_uuid}", flush=True)
            
            # Get agent
            self.agent = self.db.query(VoiceAgent).filter(
                VoiceAgent.id == phone.agent_id
            ).first()
            
            if self.agent:
                print(f"[SETUP] Using agent: {self.agent.name} (ID: {self.agent.id})", flush=True)
            
            if not self.agent:
                # Fallback to first agent
                self.agent = self.db.query(VoiceAgent).first()
                print(f"[SETUP] Fallback to first agent: {self.agent.name if self.agent else 'None'}", flush=True)
            
            if not self.agent:
                logger.error("No agent")
                await self._release_line()
                return False
            
            # Extract caller ID from UUID if available (format: callerid_uuid or just uuid)
            caller_phone = "Unknown"
            print(f"[SETUP] Checking self.caller_id: hasattr={hasattr(self, 'caller_id')}, value='{getattr(self, 'caller_id', 'N/A')}'", flush=True)
            if hasattr(self, 'caller_id') and self.caller_id:
                caller_phone = self.caller_id
                print(f"[SETUP] Using caller_id: {caller_phone}", flush=True)
            else:
                print(f"[SETUP] WARNING: No caller_id available, using 'Unknown'", flush=True)
            
            logger.info(f"[SETUP] Incoming call from: {caller_phone}")
            logger.info(f"[SETUP] Phone number config - restriction_mode: {phone.restriction_mode}")
            logger.info(f"[SETUP] Phone number config - blocked_countries: {phone.blocked_countries}")
            logger.info(f"[SETUP] Phone number config - blocked_numbers: {phone.blocked_numbers}")
            print(f"[SETUP] === RESTRICTION CHECK START ===", flush=True)
            print(f"[SETUP] Caller: {caller_phone}", flush=True)
            print(f"[SETUP] restriction_mode: '{phone.restriction_mode}'", flush=True)
            print(f"[SETUP] blocked_countries: '{phone.blocked_countries}'", flush=True)
            print(f"[SETUP] blocked_numbers: '{phone.blocked_numbers}'", flush=True)
            
            # Check call restrictions
            print(f"[SETUP] Calling _is_caller_blocked({caller_phone})...", flush=True)
            is_blocked = self._is_caller_blocked(phone, caller_phone)
            print(f"[SETUP] _is_caller_blocked returned: {is_blocked}", flush=True)
            
            if is_blocked:
                print(f"[SETUP] >>> CALL BLOCKED! Caller {caller_phone} is restricted <<<", flush=True)
                logger.warning(f"[SETUP] Call BLOCKED from {caller_phone} due to restrictions")
                self.is_busy_response = True
                self.busy_config = {'action': 'busy_tone', 'audio_file_url': None}
                return False
            
            print(f"[SETUP] >>> CALL ALLOWED <<<", flush=True)
            logger.info(f"[SETUP] Call ALLOWED from {caller_phone}")
            
            self.call = Call(
                user_id=self.agent.user_id,
                agent_id=self.agent.id,
                caller_phone=caller_phone,
                caller_name=caller_phone,  # Use phone number as name
                direction="inbound",
                status=CallStatus.INITIATED,
                session_id=f"audiosocket_{self.call_uuid}",
                started_at=datetime.utcnow()
            )
            self.db.add(self.call)
            self.db.commit()
            self.db.refresh(self.call)
            
            logger.info(f"Created call {self.call.id}")
            
            self.agent_service = FrenchVoiceAgentService(self.agent, self.call)
            if not await self.agent_service.start_session():
                logger.error("Gemini failed")
                await self._release_line()
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            logger.info(f"Call {self.call.id} ready")
            return True
            
        except Exception as e:
            logger.error(f"Setup error: {e}", exc_info=True)
            await self._release_line()
            return False
    
    async def _release_line(self):
        """Release the phone line when call ends"""
        if self.phone_number_id:
            async with _active_calls_lock:
                if self.phone_number_id in _active_calls:
                    del _active_calls[self.phone_number_id]
                    print(f"[SETUP] Released line for phone_id {self.phone_number_id}", flush=True)
    
    async def _process_audio(self, audio_8k: bytes):
        """Process audio from Asterisk, queue for sending to AI"""
        if not self.ai_ready.is_set():
            return
        if len(audio_8k) < 2:
            return
        
        try:
            if len(audio_8k) % 2:
                audio_8k = audio_8k[:-1]
            
            # Check audio level (for debugging)
            if not hasattr(self, '_audio_level_count'):
                self._audio_level_count = 0
                self._caller_resample_state = ResampleState()
            self._audio_level_count += 1
            
            try:
                rms = audioop.rms(audio_8k, 2)
                max_val = audioop.max(audio_8k, 2)
                if self._audio_level_count <= 20 or self._audio_level_count % 100 == 0:
                    print(f"[AUDIO-LEVEL] #{self._audio_level_count} RMS={rms}, MAX={max_val}", flush=True)
            except:
                pass
            
            # Upsample 8kHz to 16kHz for Gemini (with state for continuity)
            audio_16k, self._caller_resample_state = high_quality_resample(
                audio_8k, 8000, 16000, self._caller_resample_state
            )
            
            # Queue for sending (non-blocking, drop if queue full)
            try:
                self.caller_audio_queue.put_nowait(audio_16k)
            except asyncio.QueueFull:
                pass  # Drop audio if queue is full (backpressure)
        except Exception as e:
            print(f"[AUDIO→AI] Queue ERROR: {e}", flush=True)
    
    async def _caller_audio_to_gemini_loop(self):
        """Forward caller audio to Gemini with low latency"""
        packets_sent = 0
        audio_buffer = b''
        # Smaller batch for lower latency (50ms instead of 100ms)
        # 16kHz * 2 bytes * 0.05s = 1600 bytes
        BATCH_SIZE = 1600  # ~50ms of 16kHz audio
        
        print(f"[AUDIO→AI] Queue loop STARTED", flush=True)
        try:
            while self.is_running:
                try:
                    # Get audio from queue with short timeout
                    audio_16k = await asyncio.wait_for(
                        self.caller_audio_queue.get(),
                        timeout=0.05  # Shorter timeout for responsiveness
                    )
                    audio_buffer += audio_16k
                except asyncio.TimeoutError:
                    # Send whatever we have even if not full batch (for responsiveness)
                    if len(audio_buffer) >= 640 and self.agent_service:  # At least 20ms
                        packets_sent += 1
                        await self.agent_service.send_audio(audio_buffer)
                        if packets_sent <= 10 or packets_sent % 50 == 0:
                            print(f"[AUDIO→AI] #{packets_sent} sent ({len(audio_buffer)} bytes)", flush=True)
                        audio_buffer = b''
                    continue
                
                # Send when buffer is big enough
                if len(audio_buffer) >= BATCH_SIZE and self.agent_service:
                    packets_sent += 1
                    await self.agent_service.send_audio(audio_buffer)
                    
                    if packets_sent <= 10 or packets_sent % 50 == 0:
                        print(f"[AUDIO→AI] #{packets_sent} sent ({len(audio_buffer)} bytes)", flush=True)
                    audio_buffer = b''
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[AUDIO→AI] Queue loop ERROR: {e}", flush=True)
        print(f"[AUDIO→AI] Queue loop ENDED, {packets_sent} packets", flush=True)
    
    async def _ai_receive_loop(self):
        """Receive audio from AI and queue for sending"""
        ai_packets = 0
        resample_state = ResampleState()  # Maintain state for better resampling
        total_bytes_in = 0
        total_bytes_out = 0
        print(f"[AI→AUDIO] Receive loop STARTED", flush=True)
        try:
            async for audio_24k in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                if not audio_24k or len(audio_24k) < 2:
                    continue
                
                if len(audio_24k) % 2:
                    audio_24k = audio_24k[:-1]
                
                total_bytes_in += len(audio_24k)
                
                # Use high quality resampling (24kHz → 8kHz in two steps)
                audio_8k, resample_state = high_quality_resample(audio_24k, 24000, 8000, resample_state)
                total_bytes_out += len(audio_8k)
                
                await self.ai_audio_queue.put(audio_8k)
                
                ai_packets += 1
                if ai_packets <= 5 or ai_packets % 50 == 0:
                    ratio = total_bytes_out / total_bytes_in if total_bytes_in > 0 else 0
                    print(f"[AI→AUDIO] #{ai_packets}, in={len(audio_24k)}, out={len(audio_8k)}, ratio={ratio:.2f}", flush=True)
                
        except asyncio.CancelledError:
            print(f"[AI→AUDIO] Cancelled after {ai_packets} packets", flush=True)
        except Exception as e:
            print(f"[AI→AUDIO] ERROR: {e}", flush=True)
        print(f"[AI→AUDIO] ENDED, total {ai_packets} packets, {total_bytes_in}→{total_bytes_out} bytes", flush=True)
    
    async def _play_busy_message(self):
        """Play a busy message (tone or voicemail audio) and hangup"""
        try:
            action = self.busy_config.get('action', 'busy_tone') if self.busy_config else 'busy_tone'
            audio_file_url = self.busy_config.get('audio_file_url') if self.busy_config else None
            
            if action == 'voicemail' and audio_file_url:
                print(f"[BUSY] Playing voicemail audio from: {audio_file_url}", flush=True)
                await self._play_audio_file(audio_file_url)
            else:
                print(f"[BUSY] Playing busy tone", flush=True)
                await self._play_busy_tone()
            
            # Send hangup
            hangup_header = struct.pack('>BH', MSG_HANGUP, 0)
            self.writer.write(hangup_header)
            await self.writer.drain()
            print(f"[BUSY] Sent hangup, closing connection", flush=True)
            
        except Exception as e:
            print(f"[BUSY] Error playing busy message: {e}", flush=True)
        finally:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
    
    async def _play_busy_tone(self):
        """Play standard busy signal tone"""
        import math
        
        sample_rate = 8000
        duration_on = 0.5  # 500ms tone
        duration_off = 0.5  # 500ms silence
        num_cycles = 3  # Play 3 beeps
        
        samples_on = int(sample_rate * duration_on)
        samples_off = int(sample_rate * duration_off)
        
        # Create tone (480Hz)
        tone_data = b''
        for i in range(samples_on):
            value = int(16000 * math.sin(2 * math.pi * 480 * i / sample_rate))
            tone_data += struct.pack('<h', max(-32768, min(32767, value)))
        
        silence_data = b'\x00' * (samples_off * 2)
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        
        for cycle in range(num_cycles):
            # Send tone in chunks
            for i in range(0, len(tone_data), FRAME_SIZE):
                chunk = tone_data[i:i + FRAME_SIZE]
                if len(chunk) < FRAME_SIZE:
                    chunk += b'\x00' * (FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
            await self.writer.drain()
            
            # Send silence
            for i in range(0, len(silence_data), FRAME_SIZE):
                chunk = silence_data[i:i + FRAME_SIZE]
                if len(chunk) < FRAME_SIZE:
                    chunk += b'\x00' * (FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
            await self.writer.drain()
    
    async def _play_audio_file(self, audio_url: str):
        """Download and play an audio file"""
        try:
            import httpx
            import tempfile
            import subprocess
            import os
            
            print(f"[BUSY] Downloading audio from: {audio_url}", flush=True)
            
            # Download the audio file
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url, timeout=10.0)
                if response.status_code != 200:
                    print(f"[BUSY] Failed to download audio: HTTP {response.status_code}", flush=True)
                    await self._play_busy_tone()
                    return
                audio_content = response.content
            
            print(f"[BUSY] Downloaded {len(audio_content)} bytes", flush=True)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as f:
                input_path = f.name
                f.write(audio_content)
            
            # Convert to 8kHz mono PCM using ffmpeg
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
                raw_path = f.name
            
            result = subprocess.run([
                'ffmpeg', '-y', '-i', input_path,
                '-ar', '8000', '-ac', '1', '-f', 's16le', raw_path
            ], capture_output=True)
            
            if result.returncode != 0:
                print(f"[BUSY] FFmpeg conversion failed: {result.stderr.decode()[:200]}", flush=True)
                os.unlink(input_path)
                await self._play_busy_tone()
                return
            
            # Read converted audio
            with open(raw_path, 'rb') as f:
                audio_data = f.read()
            
            # Cleanup temp files
            os.unlink(input_path)
            os.unlink(raw_path)
            
            print(f"[BUSY] Converted to {len(audio_data)} bytes of 8kHz PCM", flush=True)
            
            # Send audio to Asterisk
            header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
            for i in range(0, len(audio_data), FRAME_SIZE):
                chunk = audio_data[i:i + FRAME_SIZE]
                if len(chunk) < FRAME_SIZE:
                    chunk += b'\x00' * (FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
                if i % (FRAME_SIZE * 10) == 0:  # Drain every 10 frames
                    await self.writer.drain()
            await self.writer.drain()
            
            print(f"[BUSY] Finished playing audio file", flush=True)
            
        except Exception as e:
            print(f"[BUSY] Audio file error, falling back to tone: {e}", flush=True)
            import traceback
            traceback.print_exc()
            await self._play_busy_tone()
    
    async def _cleanup(self):
        """Cleanup"""
        logger.info(f"Cleanup {self.call_uuid}")
        self.is_running = False
        
        # Release the phone line
        await self._release_line()
        
        if self.send_task:
            self.send_task.cancel()
            try:
                await self.send_task
            except:
                pass
        
        if self.agent_service:
            try:
                await self.agent_service.end_session()
            except:
                pass
        
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
                self.db.close()
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass


class AudioSocketServer:
    def __init__(self, host='0.0.0.0', port=9092):
        self.host = host
        self.port = port
        self.server = None
    
    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, self.host, self.port
        )
        logger.info(f"AudioSocket on {self.host}:{self.port}")
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
    
    async def _handle(self, reader, writer):
        import time
        print(f"\n{'='*60}", flush=True)
        print(f"[SERVER] New connection at {time.strftime('%H:%M:%S')}", flush=True)
        print(f"{'='*60}", flush=True)
        session = AudioSocketSession(reader, writer)
        await session.handle()
        print(f"[SERVER] Connection handler finished", flush=True)


audiosocket_server = AudioSocketServer()
