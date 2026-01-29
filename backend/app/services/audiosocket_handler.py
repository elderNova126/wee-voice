"""
Asterisk AudioSocket Handler

Uses asyncio with TCP_NODELAY to ensure immediate frame delivery.
Uses scipy for high-quality audio resampling.
"""
import asyncio
import socket
import struct
import logging
import audioop
import uuid as uuid_lib
import numpy as np
from typing import Optional
from datetime import datetime

try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("[AUDIO] WARNING: scipy not available", flush=True)

try:
    import soxr
    SOXR_AVAILABLE = True
    print("[AUDIO] Using soxr for high-quality resampling", flush=True)
except ImportError:
    SOXR_AVAILABLE = False
    print("[AUDIO] WARNING: soxr not available, using audioop", flush=True)

from sqlalchemy.orm import Session

from app.models import Call, VoiceAgent, CallStatus, PhoneNumber
from app.models.database import SessionLocal
# Note: Voice agent service is imported via factory in _connect_gemini
from app.api.websocket import auto_summarize_call
from app.services.greeting_tts_service import get_greeting_tts_service, get_cached_greeting_sync, EDGE_TTS_AVAILABLE

logger = logging.getLogger(__name__)

MSG_UUID = 0x01
MSG_AUDIO = 0x10
MSG_HANGUP = 0x00
MSG_ERROR = 0xFF

# Audio Settings
# INPUT: 8kHz from Asterisk (PSTN native)
# OUTPUT: Model-dependent:
# - OpenAI: 8kHz native (g711_ulaw) - NO resampling needed!
# - Gemini: 24kHz → 8kHz (needs resampling)
# Input routing:
# - OpenAI: 8kHz passthrough (no resampling!)
# - Gemini: 8kHz → 16kHz (upsample)
INPUT_SAMPLE_RATE = 8000   # From Asterisk (PSTN native)
OUTPUT_SAMPLE_RATE = 24000  # Gemini output rate (legacy default)
GEMINI_INPUT_RATE = 16000   # Gemini expects 16kHz input
OPENAI_SAMPLE_RATE = 8000   # OpenAI Realtime uses g711_ulaw at 8kHz (NO resampling needed!)

# Frame sizes (20ms frames)
# INPUT: 8kHz * 0.02s * 2 bytes = 320 bytes
# OUTPUT: 24kHz * 0.02s * 2 bytes = 960 bytes (Gemini)
# OPENAI OUTPUT: 16kHz * 0.02s * 2 bytes = 640 bytes
INPUT_FRAME_SIZE = 320   # 20ms at 8kHz
OUTPUT_FRAME_SIZE = 960  # 20ms at 24kHz (slin24) - Gemini
OPENAI_FRAME_SIZE = 640  # 20ms at 16kHz (slin16) - OpenAI

# Legacy aliases for backward compatibility
SAMPLE_RATE = INPUT_SAMPLE_RATE
FRAME_SIZE = INPUT_FRAME_SIZE

# Silence frames for each format
SILENCE_FRAME = b'\x00' * INPUT_FRAME_SIZE
SILENCE_FRAME_24K = b'\x00' * OUTPUT_FRAME_SIZE
SILENCE_FRAME_16K = b'\x00' * OPENAI_FRAME_SIZE

# Comfort noise frame - very low level noise that masks silence-to-audio transitions
# This is standard telephony practice to make transitions less jarring
def _generate_comfort_noise(frame_size: int, level: int = 50) -> bytes:
    """Generate comfort noise frame with very low amplitude"""
    import random
    # Generate low-level random samples (very quiet, ~-40dB)
    noise = bytes([random.randint(128-level, 128+level) if i % 2 == 0 else random.randint(128-level, 128+level) for i in range(frame_size)])
    # Convert to signed PCM16
    samples = []
    for i in range(0, frame_size, 2):
        # Very quiet noise around zero
        val = random.randint(-level, level)
        samples.extend([val & 0xFF, (val >> 8) & 0xFF])
    return bytes(samples[:frame_size])

# Pre-generate comfort noise frames (regenerate occasionally for variation)
COMFORT_NOISE_FRAME = _generate_comfort_noise(INPUT_FRAME_SIZE, 30)

# Audio Quality Settings - EXACT values from Asterisk-AI-Voice-Agent golden config
AUDIO_TARGET_RMS = 1400   # Target RMS level for normalization
AUDIO_MAX_GAIN_DB = 18.0  # Golden config uses 18dB - matches their setting exactly
AUDIO_ATTACK_MS = 20      # Standard attack envelope


def remove_dc_offset(pcm_bytes: bytes, threshold: int = 256) -> bytes:
    """
    Remove DC offset from PCM16 audio to prevent clicks and pops.
    
    Based on Asterisk-AI-Voice-Agent's DC offset handling.
    DC offset causes:
    - Clicks/pops at chunk boundaries
    - Interference with normalization
    - Asymmetric clipping
    
    Args:
        pcm_bytes: Raw PCM16 audio bytes (little-endian)
        threshold: Only correct if DC offset exceeds this (default 256)
        
    Returns:
        DC-corrected PCM16 audio bytes
    """
    if not pcm_bytes or len(pcm_bytes) < 4:
        return pcm_bytes
    
    try:
        # Use audioop to measure and correct DC offset
        dc = audioop.avg(pcm_bytes, 2)
        
        # Only correct if DC offset is significant
        if abs(dc) >= threshold:
            corrected = audioop.bias(pcm_bytes, 2, -int(dc))
            return corrected
        
        return pcm_bytes
        
    except Exception as e:
        print(f"[DC_OFFSET] Error: {e}", flush=True)
        return pcm_bytes


def normalize_audio(pcm_bytes: bytes, target_rms: int = AUDIO_TARGET_RMS, max_gain_db: float = AUDIO_MAX_GAIN_DB) -> bytes:
    """
    Apply RMS-based normalization to boost quiet audio.
    
    Based on Asterisk-AI-Voice-Agent's _apply_normalizer function.
    This ensures consistent audio levels for better voice quality.
    
    Args:
        pcm_bytes: Raw PCM16 audio bytes
        target_rms: Target RMS level (default 1400 for telephony)
        max_gain_db: Maximum gain in dB to apply (default 18.0)
        
    Returns:
        Normalized PCM16 audio bytes
    """
    import math
    import array
    
    if not pcm_bytes or len(pcm_bytes) < 4 or target_rms <= 0:
        return pcm_bytes
    
    try:
        # Decode PCM16 samples
        buf = array.array('h')
        buf.frombytes(pcm_bytes)
        
        if buf.itemsize != 2 or len(buf) == 0:
            return pcm_bytes
        
        # Compute RMS (Root Mean Square)
        acc = 0.0
        for s in buf:
            acc += float(s) * float(s)
        rms = math.sqrt(acc / float(len(buf))) if len(buf) > 0 else 0.0
        
        # Prevent divide-by-zero by clamping effective RMS to >= 1.0
        effective_rms = max(1.0, float(rms))
        
        # Compute linear gain toward target, limited by max_gain_db
        desired = float(target_rms) / effective_rms
        max_lin = math.pow(10.0, float(max_gain_db) / 20.0)
        gain = min(desired, max_lin)
        
        # Skip if gain is too small (avoid unnecessary processing)
        # Use 1.01 threshold like Asterisk-AI-Voice-Agent for consistency
        if gain <= 1.01:
            return pcm_bytes
        
        # Apply gain and clip to int16 range
        for i, s in enumerate(buf):
            y = float(s) * gain
            if y > 32767.0:
                y = 32767.0
            elif y < -32768.0:
                y = -32768.0
            buf[i] = int(y)
        
        return buf.tobytes()
        
    except Exception as e:
        print(f"[NORMALIZE] Error: {e}", flush=True)
        return pcm_bytes


def apply_attack_envelope(pcm_bytes: bytes, sample_rate: int = 8000, attack_ms: int = AUDIO_ATTACK_MS, 
                          attack_state: dict = None) -> tuple:
    """
    Apply a linear attack envelope at the start of audio to avoid harsh starts.
    
    Based on Asterisk-AI-Voice-Agent's _apply_attack_envelope function.
    This prevents "popping" or harsh audio starts.
    
    Args:
        pcm_bytes: Raw PCM16 audio bytes
        sample_rate: Sample rate in Hz
        attack_ms: Attack duration in milliseconds
        attack_state: Dictionary to track state across calls
        
    Returns:
        Tuple of (processed_bytes, updated_state)
    """
    import array
    
    if not pcm_bytes or sample_rate <= 0 or attack_ms <= 0:
        return pcm_bytes, attack_state
    
    if attack_state is None:
        attack_state = {'bytes_remaining': int(sample_rate * (attack_ms / 1000.0) * 2)}
    
    try:
        total_attack_bytes = int(max(0, int(sample_rate * (attack_ms / 1000.0)) * 2))
        remaining = int(attack_state.get('bytes_remaining', total_attack_bytes))
        
        if remaining <= 0:
            return pcm_bytes, attack_state
        
        buf = array.array('h')
        buf.frombytes(pcm_bytes)
        
        if buf.itemsize != 2:
            return pcm_bytes, attack_state
        
        # Number of samples to shape in this buffer
        shape_samples = min(len(buf), remaining // 2)
        if shape_samples <= 0:
            return pcm_bytes, attack_state
        
        # Linear ramp from ~0 -> 1 over remaining bytes
        for i in range(shape_samples):
            consumed_bytes = (total_attack_bytes - remaining) + (i * 2)
            alpha = max(0.0, min(1.0, consumed_bytes / float(max(1, total_attack_bytes))))
            s = int(buf[i])
            buf[i] = int(round(s * alpha))
        
        remaining -= shape_samples * 2
        attack_state['bytes_remaining'] = max(0, remaining)
        
        return buf.tobytes(), attack_state
        
    except Exception as e:
        print(f"[ATTACK] Error: {e}", flush=True)
        return pcm_bytes, attack_state


class StreamingResampler:
    """
    Streaming resampler using soxr for high-quality continuous resampling.
    
    Unlike stateless soxr.resample(), this maintains state between calls
    for smooth, gap-free audio.
    
    Uses VHQ (Very High Quality) mode for best audio quality.
    
    IMPORTANT: We "prime" the resampler with silence to eliminate initial latency.
    soxr's streaming mode has filter delay that causes the first output to be empty.
    """
    def __init__(self, from_rate: int, to_rate: int, quality: str = 'VHQ'):
        self.from_rate = from_rate
        self.to_rate = to_rate
        self.resampler = None
        self.quality = quality
        self.primed = False
        
        if SOXR_AVAILABLE:
            try:
                # Create streaming resampler with VHQ quality for best audio
                # soxr quality options: VHQ (best), HQ (default), MQ, LQ, QQ
                quality_map = {
                    'VHQ': soxr.VHQ,
                    'HQ': soxr.HQ,
                    'MQ': soxr.MQ,
                    'LQ': soxr.LQ,
                }
                soxr_quality = quality_map.get(quality, soxr.VHQ)
                
                self.resampler = soxr.ResampleStream(
                    from_rate, to_rate,
                    num_channels=1,
                    dtype=np.float32,
                    quality=soxr_quality  # Use VHQ for best quality
                )
                
                # Prime the resampler with silence to eliminate initial latency
                # This fills the filter's internal buffer so first real audio outputs immediately
                prime_samples = int(from_rate * 0.05)  # 50ms of silence
                silence = np.zeros(prime_samples, dtype=np.float32)
                _ = self.resampler.resample_chunk(silence)  # Discard priming output
                self.primed = True
                
                print(f"[RESAMPLE] Using soxr {quality} quality: {from_rate}Hz -> {to_rate}Hz (primed)", flush=True)
            except Exception as e:
                print(f"[RESAMPLE] soxr stream init error: {e}", flush=True)
        
        # Fallback state for audioop
        self.audioop_state = None
    
    def process(self, audio_bytes: bytes) -> bytes:
        """Process audio chunk with streaming resampler."""
        if len(audio_bytes) < 2:
            return audio_bytes
        
        if self.resampler is not None:
            try:
                # Convert to float32
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_float = audio_np.astype(np.float32) / 32768.0
                
                # Streaming resample (maintains state!)
                resampled = self.resampler.resample_chunk(audio_float)
                
                # Convert back to int16
                resampled_int16 = np.clip(resampled * 32768.0, -32768, 32767).astype(np.int16)
                return resampled_int16.tobytes()
            except Exception as e:
                print(f"[RESAMPLE] soxr process error: {e}", flush=True)
        
        # Fallback to audioop (also stateful)
        result, self.audioop_state = audioop.ratecv(
            audio_bytes, 2, 1, self.from_rate, self.to_rate, self.audioop_state
        )
        return result


def simple_resample(audio_bytes: bytes, from_rate: int, to_rate: int, state=None):
    """
    Simple wrapper for backward compatibility.
    For new code, use StreamingResampler directly.
    """
    if from_rate == to_rate:
        return audio_bytes, state
    
    if state is None:
        state = {}
    
    # Create or get streaming resampler
    key = f'{from_rate}_{to_rate}'
    if key not in state:
        state[key] = StreamingResampler(from_rate, to_rate)
    
    result = state[key].process(audio_bytes)
    return result, state

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
        self.greeting_audio = None  # Pre-generated greeting audio (PCM 8kHz)
        self.greeting_played = False  # Flag to skip Gemini greeting if TTS greeting was played
        # LLM Model configuration
        # - 'gemini': Native audio dialog (8kHz→16kHz input, 24kHz→8kHz output)
        # - 'gpt-*': OpenAI Realtime (8kHz passthrough - NO resampling!)
        self.llm_model = 'gemini'  # Default to Gemini for voice calls
        
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
            
            # Send first frames directly via writer (8kHz for AudioSocket)
            header = struct.pack('>BH', MSG_AUDIO, INPUT_FRAME_SIZE)
            for i in range(5):
                self.writer.write(header + SILENCE_FRAME)
            await self.writer.drain()
            print(f"{ts()} 5 silence frames sent via writer.drain() (8kHz)", flush=True)
            
            # Note: Audio sending is handled by _unified_audio_loop (started later)
            print(f"{ts()} Ready for audio", flush=True)
            
            # Read UUID - do this quickly
            print(f"{ts()} Starting UUID read...", flush=True)
            await self._read_uuid()
            print(f"{ts()} UUID read complete: {self.call_uuid}", flush=True)
            
            if not self.call_uuid:
                logger.error("No UUID")
                return
            
            logger.info(f"Call UUID: {self.call_uuid}")
            
            # OPTIMIZATION: Pipeline greeting and Gemini connection
            # Phase 1: Quick DB setup (agent lookup, busy/block check) + cache lookup
            # Phase 2: Start TTS greeting playback IMMEDIATELY (parallel with Gemini)
            # Phase 3: Connect to Gemini (happens while greeting plays)
            print(f"{ts()} [HANDLE] Starting _setup_call_quick...", flush=True)
            setup_start = time.time()
            if not await self._setup_call_quick():
                print(f"{ts()} [HANDLE] _setup_call_quick FAILED", flush=True)
                
                # Check if this was due to busy line or blocked call
                if self.is_busy_response:
                    print(f"{ts()} [HANDLE] Playing BUSY message...", flush=True)
                    await self._play_busy_message()
                return
            setup_time = (time.time() - setup_start) * 1000
            print(f"{ts()} [HANDLE] Setup complete in {setup_time:.0f}ms", flush=True)
            
            # CRITICAL: Start receiving audio from Asterisk IMMEDIATELY
            # This prevents Asterisk's buffer from filling up during greeting
            # (_process_audio will skip frames until ai_ready is set)
            receive_task = asyncio.create_task(self._receive_loop())
            print(f"{ts()} Started receive loop (draining Asterisk buffer)", flush=True)
            
            # Start TTS greeting playback (for Gemini only)
            # For OpenAI models, skip TTS - let OpenAI generate greeting with same voice
            greeting_task = None
            if self.llm_model.startswith('gpt-'):
                # OpenAI: Let the AI generate greeting with its own voice
                # This ensures consistent voice throughout the call
                print(f"{ts()} 🔵 OpenAI mode: Skipping TTS greeting (AI will generate)", flush=True)
                self.greeting_audio = None  # Clear TTS greeting so AI generates it
            elif self.greeting_audio:
                # Gemini: Use cached TTS greeting (parallel with connection)
                print(f"{ts()} 🎤 IMMEDIATE GREETING START ({len(self.greeting_audio)} bytes)", flush=True)
                greeting_task = asyncio.create_task(self._play_tts_greeting())
            else:
                print(f"{ts()} ⚠ No cached greeting - AI will generate", flush=True)
            
            # Connect to AI IN PARALLEL with greeting playback
            print(f"{ts()} Connecting to AI (parallel)...", flush=True)
            gemini_start = time.time()
            if not await self._connect_gemini():
                print(f"{ts()} [HANDLE] AI connection FAILED", flush=True)
                if greeting_task:
                    greeting_task.cancel()
                receive_task.cancel()
                return
            gemini_time = (time.time() - gemini_start) * 1000
            print(f"{ts()} AI connected in {gemini_time:.0f}ms", flush=True)
            
            # Wait for greeting to finish if it's still playing
            if greeting_task:
                try:
                    await greeting_task
                    print(f"{ts()} TTS greeting playback complete", flush=True)
                except asyncio.CancelledError:
                    pass
            
            # Signal AI is ready - now process caller audio!
            self.ai_ready.set()
            print(f"{ts()} AI READY - will now process caller audio", flush=True)
            
            # Start remaining tasks
            unified_audio_task = asyncio.create_task(self._unified_audio_loop())
            caller_to_ai_task = asyncio.create_task(self._caller_audio_to_gemini_loop())
            gemini_input_task = asyncio.create_task(self.agent_service.send_realtime_input())
            print(f"{ts()} Unified audio loop STARTED", flush=True)
            
            # Wait for receive loop to complete (call ends when Asterisk hangs up)
            await receive_task
            
            # Cancel all tasks
            for task in [caller_to_ai_task, gemini_input_task, unified_audio_task, receive_task]:
                if task and not task.done():
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
    
    async def _unified_audio_loop(self):
        """
        ASYNC implementation for smooth audio playback.
        
        ROOT CAUSE OF CHOPPY AUDIO: Gemini sends audio in bursts with gaps.
        
        FIX: Large jitter buffer + long grace period to absorb Gemini's bursty output.
        The greeting plays smoothly because it's a continuous file.
        Conversation is choppy because Gemini generates in real-time with pauses.
        """
        import time
        print(f"[UNIFIED] Starting ASYNC pacer (large buffer for AI bursts)", flush=True)
        
        # === BUFFER SETTINGS for smooth audio ===
        # Optimized for OpenAI Realtime which sends audio in bursts
        CHUNK_SIZE_MS = 20           # Fixed: 20ms frames for Asterisk
        MIN_START_MS = 400           # Buffer 400ms before starting playback
        RESUME_BUFFER_MS = 300       # Buffer 300ms before resuming after dry
        JITTER_BUFFER_MS = 2000      # 2 second jitter buffer for AI bursts
        LOW_WATERMARK_MS = 200       # Refill when below 200ms
        EMPTY_BACKOFF_MAX = 50       # Mark buffer dry after 1000ms (50 * 20ms) - only for real pauses
        
        # Derived values - now using actual milliseconds, not chunk counts
        TICK_SECONDS = CHUNK_SIZE_MS / 1000.0  # 0.02s = 20ms per tick
        
        # AudioSocket uses 8kHz slin by default - always send 8kHz to Asterisk
        # OpenAI: 8kHz native (no resampling), Gemini: 24kHz→8kHz
        frame_size = INPUT_FRAME_SIZE  # 320 bytes (20ms at 8kHz)
        output_rate = INPUT_SAMPLE_RATE  # 8kHz for Asterisk
        
        print(f"[UNIFIED] Config: start={MIN_START_MS}ms, resume={RESUME_BUFFER_MS}ms, dry_detect={EMPTY_BACKOFF_MAX*20}ms, fade=80ms, comfort_noise=ON", flush=True)
        
        if self.llm_model.startswith('gpt-'):
            ai_rate = OPENAI_SAMPLE_RATE  # 8kHz from OpenAI (g711_ulaw - NO resampling!)
            print(f"[UNIFIED] OpenAI→Asterisk: {ai_rate}Hz (NO resampling), frames={frame_size}b", flush=True)
        else:
            ai_rate = OUTPUT_SAMPLE_RATE  # 24kHz from Gemini
            print(f"[UNIFIED] Gemini→Asterisk: {ai_rate}Hz→{output_rate}Hz, frames={frame_size}b", flush=True)
        
        # AudioSocket frame header (type + length) - 8kHz frames
        header = struct.pack('>BH', MSG_AUDIO, frame_size)
        
        # Async jitter buffer - large enough for 10 seconds of audio
        jitter_buffer = asyncio.Queue(maxsize=1000)
        
        # State
        attack_state = None
        pending = b''  # Frame remainder buffer
        startup_ready = False
        needs_rebuffer = False  # True when we've been dry and need to rebuffer before resuming
        empty_backoff = 0
        last_real_emit_ts = 0.0
        
        stats = {
            'sent': 0, 'recv': 0, 'underruns': 0, 
            'underrun_empty': 0, 'underrun_partial': 0,
            'wait_recoveries': 0, 'first_audio_time': None,
            'playback_start_time': None, 'min_buffer': 999999,
        }
        
        async def pacer_loop():
            """
            ASYNC pacer loop - EXACT copy of Asterisk-AI-Voice-Agent's _pacer_loop + _drain_next_frame.
            Runs at steady 20ms cadence, draining jitter buffer.
            
            Key fix: When buffer goes dry during a response pause, we set needs_rebuffer=True.
            This ensures we wait for RESUME_BUFFER_CHUNKS before resuming playback,
            preventing the "choppy start" at the beginning of each new response.
            """
            nonlocal pending, startup_ready, needs_rebuffer, empty_backoff, last_real_emit_ts
            
            next_tick = time.perf_counter()
            sentinel_seen = False
            
            print(f"[PACER] Starting async pacer loop (20ms cadence)", flush=True)
            
            while self.is_running:
                # === TIMING (like _pacer_loop) ===
                now = time.perf_counter()
                sleep_for = next_tick - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                else:
                    next_tick = now  # Reset if behind
                
                # === DRAIN ALL AVAILABLE AUDIO FROM JITTER BUFFER ===
                # Drain everything available into pending buffer for accurate size tracking
                while True:
                    try:
                        chunk = jitter_buffer.get_nowait()
                        if chunk is None:
                            sentinel_seen = True
                            continue
                        pending += chunk
                    except asyncio.QueueEmpty:
                        break
                
                buf_level = len(pending)
                buf_ms = buf_level // (output_rate * 2 // 1000)  # Convert to milliseconds
                
                if buf_level < stats['min_buffer']:
                    stats['min_buffer'] = buf_level
                
                # === STARTUP GATE - Use actual buffer SIZE in milliseconds ===
                if not startup_ready:
                    if buf_ms >= MIN_START_MS:
                        startup_ready = True
                        stats['playback_start_time'] = time.perf_counter()
                        lat_ms = (stats['playback_start_time'] - stats['first_audio_time']) * 1000 if stats['first_audio_time'] else 0
                        print(f"[PACER] ▶ START: {buf_ms}ms buffered ({output_rate}Hz), latency={lat_ms:.0f}ms", flush=True)
                    else:
                        # Not enough buffer yet - send comfort noise to keep stream alive
                        # Comfort noise masks the transition better than pure silence
                        try:
                            self.writer.write(header + COMFORT_NOISE_FRAME)
                            stats['sent'] += 1
                        except:
                            break
                        next_tick += TICK_SECONDS
                        continue
                
                # === REBUFFER GATE - Use actual buffer SIZE in milliseconds ===
                # When resuming after a pause, wait for minimum buffer before playing
                if needs_rebuffer:
                    if buf_ms >= RESUME_BUFFER_MS:
                        needs_rebuffer = False
                        empty_backoff = 0  # Reset backoff counter
                        # Apply smooth fade-in over 80ms (longer = smoother transition)
                        if len(pending) >= frame_size:
                            fade_samples = min(len(pending) // 2, 640)  # 80ms fade at 8kHz (640 samples)
                            try:
                                buf = np.frombuffer(pending[:fade_samples * 2], dtype=np.int16).copy()
                                # Use smooth S-curve (sine) for most natural fade
                                t = np.linspace(0, np.pi/2, len(buf))
                                fade_curve = np.sin(t)  # Smooth S-curve
                                buf = (buf * fade_curve).astype(np.int16)
                                pending = buf.tobytes() + pending[fade_samples * 2:]
                            except:
                                pass
                        print(f"[PACER] ▶ RESUME: {buf_ms}ms rebuffered (80ms fade-in)", flush=True)
                    else:
                        # Not enough buffer yet - send comfort noise
                        try:
                            self.writer.write(header + COMFORT_NOISE_FRAME)
                            stats['sent'] += 1
                        except:
                            break
                        next_tick += TICK_SECONDS
                        continue
                
                # === EMIT FRAME with smooth fade-out when buffer is draining ===
                if buf_level >= frame_size:
                    frame = pending[:frame_size]
                    pending = pending[frame_size:]
                    
                    # Apply smooth FADE-OUT when buffer is getting low (< 160ms remaining)
                    # Uses cosine curve for natural sound
                    LOW_BUFFER_THRESHOLD = frame_size * 8  # 160ms at 8kHz
                    if len(pending) < LOW_BUFFER_THRESHOLD:
                        # Calculate fade factor based on how much buffer remains
                        # From 1.0 (full) to 0.2 (nearly out) using cosine curve
                        buffer_ratio = len(pending) / LOW_BUFFER_THRESHOLD
                        # Cosine fade: smooth start, smooth end
                        fade_factor = 0.2 + 0.8 * (np.cos((1 - buffer_ratio) * np.pi / 2))
                        
                        try:
                            frame_arr = np.frombuffer(frame, dtype=np.int16).copy()
                            frame_arr = (frame_arr * fade_factor).astype(np.int16)
                            frame = frame_arr.tobytes()
                        except:
                            pass
                    
                    try:
                        self.writer.write(header + frame)
                        write_buf = self.writer.transport.get_write_buffer_size()
                        if write_buf > 4096:
                            await self.writer.drain()
                        stats['sent'] += 1
                        empty_backoff = 0
                        last_real_emit_ts = time.perf_counter()
                    except:
                        break
                
                elif sentinel_seen:
                    # End of stream - send any remaining partial data with fade
                    if pending:
                        # Apply fade-out to final chunk
                        try:
                            padded = pending.ljust(frame_size, b'\x00')
                            frame_arr = np.frombuffer(padded, dtype=np.int16).copy()
                            fade = np.linspace(1.0, 0.0, len(frame_arr))
                            frame_arr = (frame_arr * fade).astype(np.int16)
                            self.writer.write(header + frame_arr.tobytes())
                            stats['sent'] += 1
                        except:
                            self.writer.write(header + pending.ljust(frame_size, b'\x00'))
                            stats['sent'] += 1
                    try:
                        await self.writer.drain()
                    except:
                        pass
                    print(f"[PACER] ✓ Done: {stats['sent']} frames ({output_rate}Hz), under={stats['underruns']}", flush=True)
                    break
                
                elif startup_ready and len(pending) < frame_size:
                    # Buffer empty - send silence (we already faded out above)
                    if len(pending) > 0:
                        # Send remaining partial audio (already faded above)
                        frame = pending + (b'\x00' * (frame_size - len(pending)))
                        pending = b''
                        try:
                            self.writer.write(header + frame)
                            stats['sent'] += 1
                            stats['underrun_partial'] += 1
                        except:
                            break
                    else:
                        # Completely empty - mark for rebuffer
                        if not needs_rebuffer:
                            empty_backoff += 1
                            if empty_backoff >= EMPTY_BACKOFF_MAX:
                                needs_rebuffer = True
                                print(f"[PACER] ⏸ Buffer dry, will rebuffer on resume", flush=True)
                        
                        # Send comfort noise (sounds more natural than pure silence)
                        try:
                            self.writer.write(header + COMFORT_NOISE_FRAME)
                            stats['sent'] += 1
                            stats['underrun_empty'] += 1
                        except:
                            break
                    
                    stats['underruns'] += 1
                
                next_tick += TICK_SECONDS
                
                # Reset timing if we're behind (prevents drift from drain latency)
                now_after = time.perf_counter()
                if next_tick < now_after:
                    next_tick = now_after
                
                # Periodic log
                if stats['sent'] > 0 and stats['sent'] % 500 == 0:
                    bytes_per_ms = output_rate * 2 // 1000
                    print(f"[PACER] {stats['sent']} frames ({output_rate}Hz), buf={buf_level/bytes_per_ms:.0f}ms, q={jitter_buffer.qsize()}, under={stats['underruns']}", flush=True)
        
        async def receiver():
            """
            Receive from AI model, resample to 8kHz, and send to Asterisk.
            
            AudioSocket uses 8kHz slin format by default.
            
            Processing:
            1. Receive PCM from AI (16kHz for OpenAI, 24kHz for Gemini)
            2. Resample to 8kHz for AudioSocket
            3. Apply attack envelope (20ms) to prevent pop
            4. Apply normalization (target_rms=1400, max_gain=18dB)
            5. Send 8kHz audio to Asterisk
            """
            nonlocal attack_state
            first_chunk = True
            attack_done = False
            resample_state = None  # For stateful resampling
            
            print(f"[RECV] AI ({ai_rate}Hz) → Asterisk ({output_rate}Hz)", flush=True)
            
            try:
                async for audio_from_ai in self.agent_service.receive_audio():
                    if not self.is_running:
                        break
                    if not audio_from_ai or len(audio_from_ai) < 2:
                        continue
                    if len(audio_from_ai) % 2:
                        audio_from_ai = audio_from_ai[:-1]
                    
                    # Track first audio timing
                    if first_chunk:
                        stats['first_audio_time'] = time.perf_counter()
                        print(f"[RECV] ▶ FIRST: {len(audio_from_ai)}b @ {ai_rate}Hz", flush=True)
                        first_chunk = False
                    
                    # Resample AI audio to 8kHz for AudioSocket
                    audio_8k, resample_state = simple_resample(
                        audio_from_ai, ai_rate, output_rate, resample_state
                    )
                    
                    # Skip empty chunks (can happen due to resampler latency)
                    if len(audio_8k) < 2:
                        continue
                    
                    # === Apply attack envelope ONLY at very start (prevents pop) ===
                    if not attack_done:
                        audio_8k, attack_state = apply_attack_envelope(
                            audio_8k, output_rate, AUDIO_ATTACK_MS, attack_state
                        )
                        if attack_state and attack_state.get('bytes_remaining', 0) <= 0:
                            attack_done = True
                    
                    # === Normalize audio (target_rms=1400, max_gain=18dB) ===
                    audio_8k = normalize_audio(audio_8k, AUDIO_TARGET_RMS, AUDIO_MAX_GAIN_DB)
                    
                    # Put in async jitter buffer (8kHz audio)
                    try:
                        jitter_buffer.put_nowait(audio_8k)
                        stats['recv'] += 1
                    except asyncio.QueueFull:
                        pass  # Drop if full
                    
                    # IMPORTANT: Yield to event loop to allow pacer to run
                    # This prevents receiver from starving the pacer
                    await asyncio.sleep(0)
                    
                    # Log progress
                    if stats['recv'] <= 3 or stats['recv'] % 50 == 0:
                        print(f"[RECV] #{stats['recv']}: {len(audio_8k)}b (8kHz), q={jitter_buffer.qsize()}", flush=True)
                        
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[RECV] Error: {e}", flush=True)
            
            # Signal end with sentinel
            try:
                await jitter_buffer.put(None)
            except:
                pass
            print(f"[RECV] Done: {stats['recv']} chunks", flush=True)
        
        # Run both async tasks concurrently (like Asterisk-AI-Voice-Agent)
        pacer_task = asyncio.create_task(pacer_loop())
        recv_task = asyncio.create_task(receiver())
        
        try:
            # Wait for receiver to finish (it completes when Gemini is done)
            await recv_task
            # Give pacer time to drain remaining audio
            await asyncio.wait_for(pacer_task, timeout=10)
        except asyncio.CancelledError:
            pacer_task.cancel()
            recv_task.cancel()
        except asyncio.TimeoutError:
            pacer_task.cancel()
        
        # Final summary
        print(f"\n[UNIFIED] === CALL SUMMARY ===", flush=True)
        print(f"[UNIFIED] Frames sent: {stats['sent']}", flush=True)
        print(f"[UNIFIED] Chunks received: {stats['recv']}", flush=True)
        print(f"[UNIFIED] Underruns: {stats['underruns']} (empty={stats['underrun_empty']}, partial={stats['underrun_partial']})", flush=True)
        print(f"[UNIFIED] Wait recoveries: {stats['wait_recoveries']} (backoffs)", flush=True)
        min_buf = stats['min_buffer'] if stats['min_buffer'] < 999999 else 0
        print(f"[UNIFIED] Min buffer: {min_buf}b", flush=True)
        if stats['first_audio_time'] and stats['playback_start_time']:
            latency = (stats['playback_start_time'] - stats['first_audio_time']) * 1000
            print(f"[UNIFIED] Pre-buffer latency: {latency:.0f}ms", flush=True)
        print(f"[UNIFIED] ===================\n", flush=True)
    
    async def _send_loop(self):
        """
        Send audio frames to Asterisk at precise 20ms intervals.
        
        Uses pre-buffer and grace period to ensure smooth playback.
        Like browser's Web Audio API - buffers enough to absorb Gemini's timing.
        """
        import time
        t0 = time.time()
        print(f"[SEND] Loop STARTED", flush=True)
        
        frames_sent = 0
        transport = self.writer.transport
        audio_buffer = b''
        header = struct.pack('>BH', MSG_AUDIO, FRAME_SIZE)
        
        # Pre-buffer: wait for 120ms of audio before starting playback
        # This absorbs Gemini's generation timing variations
        PRE_BUFFER_BYTES = FRAME_SIZE * 6  # 120ms
        playback_started = False
        
        # Grace period: wait 200ms before sending silence (10 frames)
        # Bridges Gemini's pauses between phrases
        empty_count = 0
        MAX_EMPTY_BEFORE_SILENCE = 10  # 200ms
        
        frame_duration = 0.02  # 20ms
        next_frame_time = time.time()
        
        try:
            while self.is_running:
                # Collect all available audio
                while True:
                    try:
                        chunk = self.ai_audio_queue.get_nowait()
                        audio_buffer += chunk
                    except asyncio.QueueEmpty:
                        break
                
                # Pre-buffer phase: accumulate audio before starting
                if not playback_started:
                    if len(audio_buffer) >= PRE_BUFFER_BYTES:
                        playback_started = True
                        print(f"[SEND] Playback started with {len(audio_buffer)} bytes buffered", flush=True)
                        # Send first frame
                        audio_data = audio_buffer[:FRAME_SIZE]
                        audio_buffer = audio_buffer[FRAME_SIZE:]
                    else:
                        # Still buffering - send silence
                        audio_data = SILENCE_FRAME
                elif len(audio_buffer) >= FRAME_SIZE:
                    # Normal playback
                    audio_data = audio_buffer[:FRAME_SIZE]
                    audio_buffer = audio_buffer[FRAME_SIZE:]
                    empty_count = 0
                elif len(audio_buffer) > 0:
                    # Partial frame - use it
                    audio_data = audio_buffer + b'\x00' * (FRAME_SIZE - len(audio_buffer))
                    audio_buffer = b''
                    empty_count = 0
                else:
                    # Buffer empty - wait for more audio
                    empty_count += 1
                    if empty_count <= MAX_EMPTY_BEFORE_SILENCE:
                        # Wait briefly for more audio
                        try:
                            chunk = await asyncio.wait_for(
                                self.ai_audio_queue.get(),
                                timeout=0.018  # 18ms
                            )
                            audio_buffer += chunk
                            empty_count = 0
                            if len(audio_buffer) >= FRAME_SIZE:
                                audio_data = audio_buffer[:FRAME_SIZE]
                                audio_buffer = audio_buffer[FRAME_SIZE:]
                            else:
                                audio_data = audio_buffer + b'\x00' * (FRAME_SIZE - len(audio_buffer))
                                audio_buffer = b''
                        except asyncio.TimeoutError:
                            audio_data = SILENCE_FRAME
                    else:
                        # Real pause in speech
                        audio_data = SILENCE_FRAME
                
                try:
                    transport.write(header + audio_data)
                except Exception as e:
                    print(f"[SEND] Write FAILED: {e}", flush=True)
                    break
                
                frames_sent += 1
                if frames_sent % 100 == 0:
                    print(f"[SEND] {frames_sent} frames, buf={len(audio_buffer)}", flush=True)
                
                # Precise timing
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                elif sleep_time < -0.1:
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
        asterisk_uuid = None  # The UUID Asterisk used (for caller ID file)
        
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
                print(f"[UUID] Payload received ({len(uuid_bytes)} bytes): {uuid_bytes[:50]}...")
                
                # Try to parse as string UUID (36 chars)
                try:
                    decoded = uuid_bytes.decode('ascii').strip()
                    # Remove null bytes
                    decoded = decoded.replace('\x00', '')
                    print(f"[UUID] Decoded as string: '{decoded}' (len={len(decoded)})")
                    
                    if len(decoded) == 36 and '-' in decoded:
                        self.call_uuid = decoded
                        asterisk_uuid = decoded
                        print(f"[UUID] Valid string UUID: {self.call_uuid}")
                except Exception as e:
                    print(f"[UUID] String decode failed: {e}")
                
                # Try to parse as 16-byte binary UUID
                if not asterisk_uuid and len(uuid_bytes) == 16:
                    try:
                        parsed_uuid = uuid_lib.UUID(bytes=uuid_bytes)
                        self.call_uuid = str(parsed_uuid)
                        asterisk_uuid = self.call_uuid
                        print(f"[UUID] Parsed binary UUID: {self.call_uuid}")
                    except Exception as e:
                        print(f"[UUID] Binary UUID parse failed: {e}")
            
            # If we couldn't parse, generate one
            if not self.call_uuid:
                self.call_uuid = str(uuid_lib.uuid4())
                print(f"[UUID] Generated new UUID: {self.call_uuid}")
            
            # Always try to read caller ID file using Asterisk's UUID
            if asterisk_uuid:
                # Small delay to ensure Asterisk's System() command has written the file
                await asyncio.sleep(0.1)  # 100ms delay
                self._read_caller_id_file(asterisk_uuid)
            else:
                print(f"[UUID] No Asterisk UUID available, can't read caller ID file")
                self.caller_id = None
            
        except asyncio.TimeoutError:
            print(f"[UUID] TIMEOUT waiting for header!")
            self.call_uuid = str(uuid_lib.uuid4())
            self.caller_id = None
        except Exception as e:
            print(f"[UUID] ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.call_uuid = str(uuid_lib.uuid4())
            self.caller_id = None
    
    def _read_caller_id_file(self, asterisk_uuid: str = None):
        """Read caller ID from temp file created by Asterisk dialplan"""
        import os
        try:
            # Use provided UUID or fall back to self.call_uuid
            uuid_to_use = asterisk_uuid or self.call_uuid
            callerid_file = f"/tmp/callerid_{uuid_to_use}"
            print(f"[UUID] Looking for caller ID file: {callerid_file}", flush=True)
            
            if os.path.exists(callerid_file):
                with open(callerid_file, 'r') as f:
                    raw_caller_id = f.read().strip()
                
                # Try to delete the file (may fail due to /tmp sticky bit)
                try:
                    os.unlink(callerid_file)
                except PermissionError:
                    pass  # Can't delete, that's OK - Asterisk can clean it up
                
                print(f"[UUID] Raw file content: '{raw_caller_id}'", flush=True)
                
                # Clean up caller ID (remove quotes, extra chars)
                cleaned = raw_caller_id.strip('"\'').strip()
                
                # Check for empty or invalid values
                if not cleaned or cleaned.lower() in ('none', 'null', 'unknown', ''):
                    print(f"[UUID] Invalid caller ID in file: '{raw_caller_id}', setting to None", flush=True)
                    self.caller_id = None
                    return
                
                self.caller_id = cleaned
                
                # Normalize: ensure it starts with + for international
                if self.caller_id and self.caller_id[0].isdigit():
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
    
    async def _setup_call_quick(self) -> bool:
        """
        Quick setup: DB queries, agent lookup, restrictions check.
        Does NOT connect to Gemini - that's done separately for pipelining.
        Also generates TTS greeting for immediate playback.
        """
        print(f"[SETUP] _setup_call_quick() STARTED", flush=True)
        logger.info(f"[SETUP] _setup_call_quick() STARTED")
        
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
            
            # Get LLM model from phone number configuration
            self.llm_model = getattr(phone, 'llm_model', 'gemini') or 'gemini'
            print(f"[SETUP] LLM Model: {self.llm_model}", flush=True)
            logger.info(f"[SETUP] LLM Model configured: {self.llm_model}")
            
            # Audio processing optimization based on LLM model:
            # - Gemini: Requires 16kHz input (upsample from 8kHz PSTN)
            # - OpenAI: Supports 8kHz natively (no input resampling needed!)
            if self.llm_model.startswith('gpt-'):
                print(f"[SETUP] 🎵 OpenAI model detected - 8kHz audio supported natively (no input resampling)", flush=True)
            else:
                print(f"[SETUP] 🎵 Gemini model - will upsample 8kHz→16kHz for input", flush=True)
            
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
            has_attr = hasattr(self, 'caller_id')
            attr_value = getattr(self, 'caller_id', 'N/A')
            attr_type = type(attr_value).__name__
            print(f"[SETUP] Checking self.caller_id: hasattr={has_attr}, value='{attr_value}', type={attr_type}", flush=True)
            
            if has_attr and self.caller_id and self.caller_id != 'None':
                caller_phone = self.caller_id
                print(f"[SETUP] Using caller_id: {caller_phone}", flush=True)
            else:
                print(f"[SETUP] WARNING: No valid caller_id (hasattr={has_attr}, value={repr(attr_value)}), using 'Unknown'", flush=True)
            
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
                await self._release_line()  # Release the line since we blocked the call
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
            
            # Get CACHED greeting INSTANTLY (no generation during call!)
            # Greetings are pre-generated at server startup using GEMINI (same voice)
            if self.agent.greeting:
                language = getattr(self.agent, 'language', 'fr-FR')
                gender = getattr(self.agent, 'voice_gender', 'male')
                voice_id = getattr(self.agent, 'voice_id', None)  # Specific voice takes priority
                
                print(f"[SETUP] Looking for cached greeting (lang={language}, gender={gender}, voice_id={voice_id})...", flush=True)
                
                # INSTANT cache lookup (no await, no blocking!)
                # IMPORTANT: Pass voice_id to ensure greeting uses same voice as conversation
                self.greeting_audio = get_cached_greeting_sync(
                    self.agent.greeting,
                    language=language,
                    gender=gender,
                    voice_id=voice_id
                )
                
                if self.greeting_audio:
                    print(f"[SETUP] ✅ Greeting from cache: {len(self.greeting_audio)} bytes (INSTANT!)", flush=True)
                else:
                    print(f"[SETUP] ⚠ No cached greeting found, Gemini will generate during call", flush=True)
                    # Trigger background generation for NEXT call (non-blocking)
                    tts_service = get_greeting_tts_service()
                    tts_service.trigger_background_generation(
                        self.agent.greeting,
                        language=language,
                        gender=gender,
                        voice_id=voice_id  # Pass voice_id for correct voice
                    )
            else:
                print(f"[SETUP] No greeting configured for agent", flush=True)
            
            print(f"[SETUP] _setup_call_quick() DONE", flush=True)
            return True
            
        except Exception as e:
            logger.error(f"Setup error: {e}", exc_info=True)
            await self._release_line()
            return False
    
    async def _connect_gemini(self) -> bool:
        """Connect to AI model and start the voice session"""
        try:
            from app.services.openai_realtime_service import get_voice_agent_service, is_openai_model
            
            # Log model selection
            if is_openai_model(self.llm_model):
                print(f"[AI] 🔵 Using OpenAI Realtime API (model: {self.llm_model})", flush=True)
                logger.info(f"Using OpenAI Realtime API for voice (model: {self.llm_model})")
            else:
                print(f"[AI] 🟢 Using Gemini Live API for voice", flush=True)
                logger.info("Using Gemini Live API for voice")
            
            print(f"[AI] Creating agent service...", flush=True)
            
            # Create agent service using factory - selects Gemini or OpenAI based on model
            self.agent_service = get_voice_agent_service(
                agent=self.agent,
                call=self.call,
                llm_model=self.llm_model,
                skip_greeting_trigger=bool(self.greeting_audio)  # Skip if TTS greeting is available
            )
            
            print(f"[AI] Starting session (skip_greeting={bool(self.greeting_audio)})...", flush=True)
            if not await self.agent_service.start_session():
                logger.error("AI session failed to start")
                await self._release_line()
                return False
            
            self.call.status = CallStatus.IN_PROGRESS
            self.db.commit()
            
            logger.info(f"Call {self.call.id} ready")
            print(f"[AI] Session started successfully", flush=True)
            return True
            
        except Exception as e:
            logger.error(f"AI connection error: {e}", exc_info=True)
            await self._release_line()
            return False
    
    async def _play_tts_greeting(self):
        """
        Play pre-generated greeting IMMEDIATELY.
        This runs in parallel with Gemini connection, eliminating the 5-10s delay.
        """
        if not self.greeting_audio:
            print(f"[GREETING-PLAY] ⚠ No greeting audio to play", flush=True)
            return
        
        import time
        t0 = time.perf_counter()
        audio_duration_ms = len(self.greeting_audio) / 16  # 8kHz * 2 bytes = 16 bytes/ms
        
        # Check audio quality before playback
        try:
            rms_before = audioop.rms(self.greeting_audio, 2)
            print(f"[GREETING-PLAY] 🎤 Starting playback: {len(self.greeting_audio)} bytes ({audio_duration_ms:.0f}ms), RMS={rms_before}", flush=True)
        except:
            print(f"[GREETING-PLAY] 🎤 Starting playback: {len(self.greeting_audio)} bytes ({audio_duration_ms:.0f}ms)", flush=True)
        
        # Apply normalization for consistent volume (on 8kHz audio)
        audio_8k = normalize_audio(self.greeting_audio, AUDIO_TARGET_RMS, AUDIO_MAX_GAIN_DB)
        
        # Apply attack envelope to prevent pop at start of greeting
        audio_8k, _ = apply_attack_envelope(audio_8k, INPUT_SAMPLE_RATE, AUDIO_ATTACK_MS, None)
        
        # AudioSocket uses 8kHz slin by default - NO upsampling needed!
        # The audio is already 8kHz from TTS cache
        audio_data = audio_8k
        target_rate = INPUT_SAMPLE_RATE  # 8kHz
        frame_size = INPUT_FRAME_SIZE    # 320 bytes (20ms at 8kHz)
        silence_frame = SILENCE_FRAME    # 8kHz silence
        print(f"[GREETING-PLAY] Using native 8kHz (AudioSocket default format)", flush=True)
        
        # Check RMS after normalization
        try:
            rms_after = audioop.rms(audio_data, 2)
            print(f"[GREETING-PLAY] Normalized RMS: {rms_after}", flush=True)
        except:
            pass
        
        # Use model-specific frame size
        header = struct.pack('>BH', MSG_AUDIO, frame_size)
        frames_sent = 0
        
        # Send lead-in silence BEFORE greeting to let Asterisk audio path initialize
        LEAD_IN_FRAMES = 8  # 160ms of silence (8 frames * 20ms)
        print(f"[GREETING-PLAY] Sending {LEAD_IN_FRAMES} lead-in silence frames ({target_rate}Hz)...", flush=True)
        for _ in range(LEAD_IN_FRAMES):
            self.writer.write(header + silence_frame)
        await self.writer.drain()
        
        # Send audio in 20ms frames with proper timing
        frame_duration = 0.02  # 20ms
        next_frame_time = time.perf_counter()
        
        try:
            for i in range(0, len(audio_data), frame_size):
                if not self.is_running:
                    print(f"[GREETING-PLAY] ⚠ Stopped early (is_running=False)", flush=True)
                    break
                
                chunk = audio_data[i:i + frame_size]
                if len(chunk) < frame_size:
                    chunk += b'\x00' * (frame_size - len(chunk))
                
                self.writer.write(header + chunk)
                frames_sent += 1
                
                # Log first few frames for debugging
                if frames_sent <= 3:
                    print(f"[GREETING-PLAY] Frame #{frames_sent} sent ({len(chunk)} bytes, {target_rate}Hz)", flush=True)
                
                # Drain periodically to prevent buffer overflow
                if frames_sent % 25 == 0:
                    await self.writer.drain()
                
                # Precise timing
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.perf_counter()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            await self.writer.drain()
            
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[GREETING-PLAY] ✅ Complete: {frames_sent} frames ({target_rate}Hz) in {elapsed:.0f}ms", flush=True)
            
            self.greeting_played = True
            
        except Exception as e:
            print(f"[GREETING-PLAY] ❌ Error: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    async def _setup_call(self) -> bool:
        """Legacy setup method - calls new split methods for compatibility"""
        if not await self._setup_call_quick():
            return False
        return await self._connect_gemini()
    
    async def _release_line(self):
        """Release the phone line when call ends"""
        if self.phone_number_id:
            async with _active_calls_lock:
                if self.phone_number_id in _active_calls:
                    del _active_calls[self.phone_number_id]
                    print(f"[SETUP] Released line for phone_id {self.phone_number_id}", flush=True)
    
    async def _process_audio(self, audio_8k: bytes):
        """
        Process audio from Asterisk (8kHz) and send to AI model.
        
        Audio flow (input side):
        - Asterisk receives ulaw/alaw (8kHz) from PSTN/Zadarma
        - AudioSocket sends 8kHz PCM to Python
        
        Both models use 16kHz PCM16 input (matching reference implementation):
        - Gemini: Upsample 8kHz → 16kHz
        - OpenAI: Upsample 8kHz → 16kHz (OpenAI Realtime optimized for 16kHz)
        """
        if not self.ai_ready.is_set():
            return
        if len(audio_8k) < 2:
            return
        
        try:
            if len(audio_8k) % 2:
                audio_8k = audio_8k[:-1]
            
            # OpenAI: 8kHz passthrough (no resampling!)
            # Gemini: 8kHz → 16kHz (upsample)
            if self.llm_model.startswith('gpt-'):
                # OpenAI uses 8kHz native - no resampling needed!
                audio_for_ai = audio_8k
            else:
                # Gemini needs 16kHz - resample
                if not hasattr(self, '_caller_resample_state'):
                    self._caller_resample_state = None
                
                target_rate = GEMINI_INPUT_RATE   # 16kHz
                audio_for_ai, self._caller_resample_state = simple_resample(
                    audio_8k, INPUT_SAMPLE_RATE, target_rate, self._caller_resample_state
                )
            
            # Queue for sending to AI
            try:
                self.caller_audio_queue.put_nowait(audio_for_ai)
            except asyncio.QueueFull:
                pass
        except Exception as e:
            print(f"[AUDIO→AI] Queue ERROR: {e}", flush=True)
    
    async def _caller_audio_to_gemini_loop(self):
        """Forward caller audio to AI model with low latency and diagnostics"""
        import time
        packets_sent = 0
        audio_buffer = b''
        total_bytes = 0
        last_send_time = None
        silence_start = None
        
        # Model-specific audio rates
        # OpenAI: 8kHz native (no resampling!)
        # Gemini: 16kHz input
        if self.llm_model.startswith('gpt-'):
            audio_rate = OPENAI_SAMPLE_RATE  # 8kHz (native - no resampling!)
            BATCH_SIZE = audio_rate * 2 // 25  # 40ms = 640 bytes at 8kHz
            print(f"[CALLER→AI] OpenAI mode: {audio_rate}Hz (NO resampling)", flush=True)
        else:
            audio_rate = GEMINI_INPUT_RATE  # 16kHz
            BATCH_SIZE = audio_rate * 2 // 25  # 40ms = 1280 bytes at 16kHz
            print(f"[CALLER→AI] Gemini mode: {audio_rate}Hz audio", flush=True)
        
        print(f"[CALLER→AI] Loop STARTED (batch={BATCH_SIZE}b, rate={audio_rate}Hz)", flush=True)
        try:
            while self.is_running:
                try:
                    # Get audio from queue with short timeout
                    audio_16k = await asyncio.wait_for(
                        self.caller_audio_queue.get(),
                        timeout=0.04  # 40ms timeout
                    )
                    audio_buffer += audio_16k
                    
                    # Track when caller is speaking
                    if silence_start:
                        silence_duration = (time.perf_counter() - silence_start) * 1000
                        if silence_duration > 200:  # Log silences > 200ms
                            print(f"[CALLER→AI] Caller silent for {silence_duration:.0f}ms", flush=True)
                        silence_start = None
                        
                except asyncio.TimeoutError:
                    # Track silence periods
                    if silence_start is None:
                        silence_start = time.perf_counter()
                    
                    # Send whatever we have even if not full batch (for responsiveness)
                    if len(audio_buffer) >= 640 and self.agent_service:  # At least 20ms
                        packets_sent += 1
                        total_bytes += len(audio_buffer)
                        send_start = time.perf_counter()
                        await self.agent_service.send_audio(audio_buffer)
                        send_time = (time.perf_counter() - send_start) * 1000
                        
                        if packets_sent <= 10 or packets_sent % 100 == 0:
                            print(f"[CALLER→AI] #{packets_sent}: {len(audio_buffer)}b in {send_time:.1f}ms", flush=True)
                        audio_buffer = b''
                        last_send_time = time.perf_counter()
                    continue
                
                # Send when buffer is big enough
                if len(audio_buffer) >= BATCH_SIZE and self.agent_service:
                    packets_sent += 1
                    total_bytes += len(audio_buffer)
                    send_start = time.perf_counter()
                    
                    # Send with appropriate MIME type based on model
                    mime_type = f"audio/pcm;rate={audio_rate}"
                    await self.agent_service.send_audio(audio_buffer, mime_type=mime_type)
                    send_time = (time.perf_counter() - send_start) * 1000
                    
                    if packets_sent <= 10 or packets_sent % 100 == 0:
                        print(f"[CALLER→AI] #{packets_sent}: {len(audio_buffer)}b ({audio_rate}Hz) in {send_time:.1f}ms", flush=True)
                    
                    # Warn if send is slow (> 50ms)
                    if send_time > 50:
                        print(f"[CALLER→AI] ⚠ Slow send: {send_time:.0f}ms", flush=True)
                    
                    audio_buffer = b''
                    last_send_time = time.perf_counter()
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[CALLER→AI] ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
        print(f"[CALLER→AI] ENDED: {packets_sent} packets, {total_bytes} bytes total", flush=True)
    
    async def _ai_receive_loop(self):
        """Receive audio from AI and queue for sending - immediate processing"""
        ai_packets = 0
        resample_state = None  # Stateful resampling for smooth audio
        total_bytes_in = 0
        total_bytes_out = 0
        
        # Determine source rate based on model
        # OpenAI: 8kHz (g711_ulaw native, NO resampling!)
        # Gemini: 24kHz output (needs resampling to 8kHz)
        if self.llm_model.startswith('gpt-'):
            source_rate = OPENAI_SAMPLE_RATE  # 8kHz (native!)
            needs_resample = False
            print(f"[AI→AUDIO] Receive loop STARTED (OpenAI {source_rate}Hz - NO resampling)", flush=True)
        else:
            source_rate = OUTPUT_SAMPLE_RATE  # 24kHz (Gemini)
            needs_resample = True
            print(f"[AI→AUDIO] Receive loop STARTED (Gemini {source_rate}Hz → 8kHz)", flush=True)
        
        try:
            async for audio_from_ai in self.agent_service.receive_audio():
                if not self.is_running:
                    break
                if not audio_from_ai or len(audio_from_ai) < 2:
                    continue
                
                if len(audio_from_ai) % 2:
                    audio_from_ai = audio_from_ai[:-1]
                
                total_bytes_in += len(audio_from_ai)
                
                # Resample to 8kHz for Asterisk (only if needed)
                if needs_resample:
                    audio_8k, resample_state = simple_resample(audio_from_ai, source_rate, INPUT_SAMPLE_RATE, resample_state)
                else:
                    audio_8k = audio_from_ai  # OpenAI is already 8kHz
                total_bytes_out += len(audio_8k)
                
                await self.ai_audio_queue.put(audio_8k)
                
                ai_packets += 1
                if ai_packets <= 5 or ai_packets % 50 == 0:
                    if needs_resample:
                        ratio = total_bytes_out / total_bytes_in if total_bytes_in > 0 else 0
                        print(f"[AI→AUDIO] #{ai_packets}, {source_rate}Hz→8kHz, in={len(audio_from_ai)}, out={len(audio_8k)}, ratio={ratio:.2f}", flush=True)
                    else:
                        print(f"[AI→AUDIO] #{ai_packets}, {source_rate}Hz passthrough, {len(audio_8k)}b", flush=True)
                
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
        """Play standard busy signal tone with proper 20ms frame timing"""
        import math
        import time
        
        # Generate busy tone at 24kHz (to match Asterisk's expected slin24 format)
        sample_rate = OUTPUT_SAMPLE_RATE  # 24000 Hz
        duration_on = 0.5  # 500ms tone
        duration_off = 0.5  # 500ms silence
        num_cycles = 3  # Play 3 beeps
        
        samples_on = int(sample_rate * duration_on)
        samples_off = int(sample_rate * duration_off)
        
        # Create tone (480Hz + 620Hz = standard busy signal) at 24kHz
        tone_data = b''
        for i in range(samples_on):
            # Mix 480Hz and 620Hz for authentic busy tone
            value = int(12000 * (math.sin(2 * math.pi * 480 * i / sample_rate) + 
                                  math.sin(2 * math.pi * 620 * i / sample_rate)))
            tone_data += struct.pack('<h', max(-32768, min(32767, value)))
        
        silence_data = b'\x00' * (samples_off * 2)
        header = struct.pack('>BH', MSG_AUDIO, OUTPUT_FRAME_SIZE)
        
        print(f"[BUSY] Starting busy tone playback ({num_cycles} cycles, 24kHz)", flush=True)
        
        frame_duration = 0.02  # 20ms per frame
        next_frame_time = time.time()
        frames_sent = 0
        
        for cycle in range(num_cycles):
            # Send tone in chunks with proper timing
            for i in range(0, len(tone_data), OUTPUT_FRAME_SIZE):
                chunk = tone_data[i:i + OUTPUT_FRAME_SIZE]
                if len(chunk) < OUTPUT_FRAME_SIZE:
                    chunk += b'\x00' * (OUTPUT_FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
                frames_sent += 1
                
                # Wait for next frame time
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            # Send silence with proper timing
            for i in range(0, len(silence_data), OUTPUT_FRAME_SIZE):
                chunk = silence_data[i:i + OUTPUT_FRAME_SIZE]
                if len(chunk) < OUTPUT_FRAME_SIZE:
                    chunk += b'\x00' * (OUTPUT_FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
                frames_sent += 1
                
                # Wait for next frame time
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        
        await self.writer.drain()
        print(f"[BUSY] Busy tone complete ({frames_sent} frames sent, 24kHz)", flush=True)
    
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
            
            # Convert to 24kHz mono PCM using ffmpeg (to match Asterisk's slin24 format)
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
                raw_path = f.name
            
            result = subprocess.run([
                'ffmpeg', '-y', '-i', input_path,
                '-ar', '24000', '-ac', '1', '-f', 's16le', raw_path
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
            
            print(f"[BUSY] Converted to {len(audio_data)} bytes of 24kHz PCM", flush=True)
            
            # Send audio to Asterisk with proper 20ms timing (24kHz frames)
            import time
            header = struct.pack('>BH', MSG_AUDIO, OUTPUT_FRAME_SIZE)
            frame_duration = 0.02  # 20ms per frame
            next_frame_time = time.time()
            frames_sent = 0
            
            for i in range(0, len(audio_data), OUTPUT_FRAME_SIZE):
                chunk = audio_data[i:i + OUTPUT_FRAME_SIZE]
                if len(chunk) < OUTPUT_FRAME_SIZE:
                    chunk += b'\x00' * (OUTPUT_FRAME_SIZE - len(chunk))
                self.writer.write(header + chunk)
                frames_sent += 1
                
                # Wait for next frame time
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            await self.writer.drain()
            print(f"[BUSY] Finished playing audio file ({frames_sent} frames)", flush=True)
            
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
        self._greetings_prewarmed = False
    
    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, self.host, self.port
        )
        logger.info(f"AudioSocket on {self.host}:{self.port}")
        print(f"[AudioSocket] Starting AudioSocket server...")
        print(f"[AudioSocket] ✅ AudioSocket server started on port {self.port}")
        
        # Pre-warm greeting cache for INSTANT playback on first call
        if not self._greetings_prewarmed:
            asyncio.create_task(self._prewarm_greetings())
        
        asyncio.create_task(self._serve())
    
    async def _prewarm_greetings(self):
        """Pre-generate TTS greetings for all agents at startup"""
        try:
            from app.services.greeting_tts_service import prewarm_all_agent_greetings
            await prewarm_all_agent_greetings()
            self._greetings_prewarmed = True
        except Exception as e:
            print(f"[AudioSocket] ⚠ Greeting pre-warm failed: {e}", flush=True)
    
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
