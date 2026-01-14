#!/usr/bin/env python3
"""
WeeVoice EAGI - Uses Backend WebSocket API

This script connects to the backend WebSocket API for voice streaming.
Audio OUTPUT uses temporary files + STREAM FILE command (EAGI limitation).

AUDIO QUALITY: Uses soxr/scipy for high-quality resampling when available.
"""

import os
import sys
import asyncio
import audioop
import base64
import json
import logging
import tempfile
import struct
import fcntl
import select
import time
import math
import array
from datetime import datetime
from pathlib import Path

# Try to import high-quality resampling libraries
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import soxr
    SOXR_AVAILABLE = True
except ImportError:
    SOXR_AVAILABLE = False

# scipy not needed - soxr handles anti-aliasing internally
SCIPY_AVAILABLE = False  # Not used for resampling

# ============================================================================
# LOGGING - Use print for immediate output
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

def log(msg):
    """Log with immediate flush"""
    logger.info(msg)
    print(f"[EAGI] {msg}", file=sys.stderr, flush=True)

# ============================================================================
# CONFIGURATION
# ============================================================================
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8000')
WS_URL = BACKEND_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/v1/eagi/stream'

# Audio rates
ASTERISK_RATE = 8000      # From/To Asterisk
GEMINI_INPUT_RATE = 16000  # Backend expects 16kHz
GEMINI_OUTPUT_RATE = 24000 # Backend sends 24kHz
FRAME_SIZE = 320           # 20ms at 8kHz

# Audio quality settings - conservative values to prevent distortion
AUDIO_TARGET_RMS = 2000    # Target RMS level (higher = louder but may clip)
AUDIO_MAX_GAIN_DB = 12.0   # Maximum gain in dB (reduced from 18 to prevent distortion)


# =============================================================================
# HIGH-QUALITY AUDIO PROCESSING
# =============================================================================

class HighQualityResampler:
    """
    High-quality streaming resampler using soxr (VHQ mode).
    Falls back to audioop if soxr not available.
    
    IMPORTANT: Uses stateful streaming for gap-free audio!
    
    This makes a HUGE difference in audio quality compared to audioop.ratecv!
    - soxr VHQ: Best quality, proper anti-aliasing, stateful streaming
    - audioop: Lower quality but always available, also stateful
    
    NOTE: scipy.signal.resample is NOT used because it's not stateful,
    causing clicks/pops at chunk boundaries in real-time streaming.
    
    CRITICAL: Call flush() at end of stream to get remaining samples!
    The resampler maintains internal state - without flushing, the last
    few samples (containing final words/syllables) are lost!
    """
    def __init__(self, from_rate: int, to_rate: int):
        self.from_rate = from_rate
        self.to_rate = to_rate
        self.resampler = None
        self.audioop_state = None
        self.method = "audioop"  # Default fallback
        self._has_pending_samples = False  # Track if we have unflushed data
        
        if SOXR_AVAILABLE and NUMPY_AVAILABLE:
            try:
                self.resampler = soxr.ResampleStream(
                    from_rate, to_rate,
                    num_channels=1,
                    dtype=np.float32,
                    quality=soxr.VHQ  # Very High Quality!
                )
                self.method = "soxr_vhq"
                log(f"Resampler: soxr VHQ {from_rate}Hz → {to_rate}Hz")
            except Exception as e:
                log(f"soxr init failed: {e}, using audioop fallback")
        else:
            log(f"Resampler: audioop {from_rate}Hz → {to_rate}Hz (install soxr for better quality)")
    
    def process(self, audio_bytes: bytes) -> bytes:
        """Resample audio chunk with high quality (stateful streaming)."""
        if len(audio_bytes) < 2:
            return audio_bytes
        
        self._has_pending_samples = True  # Mark that we have data in the pipeline
        
        if self.method == "soxr_vhq" and self.resampler:
            try:
                # Convert to float32
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_float = audio_np.astype(np.float32) / 32768.0
                
                # Streaming resample (maintains state for gap-free audio!)
                resampled = self.resampler.resample_chunk(audio_float)
                
                # Convert back to int16
                resampled_int16 = np.clip(resampled * 32768.0, -32768, 32767).astype(np.int16)
                return resampled_int16.tobytes()
            except Exception as e:
                log(f"soxr error: {e}, falling back to audioop")
        
        # Fallback to audioop (stateful resampling)
        result, self.audioop_state = audioop.ratecv(
            audio_bytes, 2, 1, self.from_rate, self.to_rate, self.audioop_state
        )
        return result
    
    def flush(self) -> bytes:
        """
        Flush any remaining samples from the resampler's internal buffer.
        
        CRITICAL: Must be called at end of audio stream to get final samples!
        Without this, the last portion of audio (final words/syllables) is lost.
        
        Returns: Remaining audio bytes (may be empty if nothing buffered)
        """
        if not self._has_pending_samples:
            return b''
        
        self._has_pending_samples = False
        
        if self.method == "soxr_vhq" and self.resampler:
            try:
                # Pass empty array to flush remaining samples from soxr's internal buffer
                # This is the documented way to get the "tail" of the resampled audio
                empty_input = np.array([], dtype=np.float32)
                final_samples = self.resampler.resample_chunk(empty_input, last=True)
                
                if len(final_samples) > 0:
                    # Convert back to int16
                    final_int16 = np.clip(final_samples * 32768.0, -32768, 32767).astype(np.int16)
                    flushed_bytes = final_int16.tobytes()
                    log(f"Resampler flush: {len(flushed_bytes)} bytes recovered")
                    return flushed_bytes
            except Exception as e:
                log(f"soxr flush error: {e}")
        
        # audioop doesn't have significant buffering, but process any remaining state
        # by passing a small silence buffer
        if self.audioop_state:
            try:
                # Process a tiny silence to flush any remaining state
                silence = b'\x00\x00' * 16  # 16 samples of silence
                result, self.audioop_state = audioop.ratecv(
                    silence, 2, 1, self.from_rate, self.to_rate, self.audioop_state
                )
                # Don't return the silence, just clear the state
            except:
                pass
        
        return b''
    
    def reset(self):
        """Reset the resampler state for a new stream."""
        self._has_pending_samples = False
        self.audioop_state = None
        if self.method == "soxr_vhq" and SOXR_AVAILABLE and NUMPY_AVAILABLE:
            try:
                self.resampler = soxr.ResampleStream(
                    self.from_rate, self.to_rate,
                    num_channels=1,
                    dtype=np.float32,
                    quality=soxr.VHQ
                )
            except Exception as e:
                log(f"soxr reset failed: {e}")


def remove_dc_offset(pcm_bytes: bytes, threshold: int = 256) -> bytes:
    """Remove DC offset from audio to prevent clicks and pops."""
    if not pcm_bytes or len(pcm_bytes) < 4:
        return pcm_bytes
    try:
        dc = audioop.avg(pcm_bytes, 2)
        if abs(dc) >= threshold:
            return audioop.bias(pcm_bytes, 2, -int(dc))
        return pcm_bytes
    except:
        return pcm_bytes


def normalize_audio(pcm_bytes: bytes, target_rms: int = AUDIO_TARGET_RMS, 
                    max_gain_db: float = AUDIO_MAX_GAIN_DB) -> bytes:
    """Apply RMS-based normalization to ensure consistent audio levels."""
    if not pcm_bytes or len(pcm_bytes) < 4:
        return pcm_bytes
    
    try:
        buf = array.array('h')
        buf.frombytes(pcm_bytes)
        
        if len(buf) == 0:
            return pcm_bytes
        
        # Compute RMS
        acc = 0.0
        for s in buf:
            acc += float(s) * float(s)
        rms = math.sqrt(acc / float(len(buf)))
        
        if rms < 1.0:
            return pcm_bytes
        
        # Compute gain (limited by max_gain_db)
        desired = float(target_rms) / rms
        max_lin = math.pow(10.0, float(max_gain_db) / 20.0)
        gain = min(desired, max_lin)
        
        if gain <= 1.01:
            return pcm_bytes
        
        # Apply gain with clipping
        for i, s in enumerate(buf):
            y = float(s) * gain
            if y > 32767.0:
                y = 32767.0
            elif y < -32768.0:
                y = -32768.0
            buf[i] = int(y)
        
        return buf.tobytes()
    except:
        return pcm_bytes



# Audio output directory (for temporary files)
AUDIO_TMP_DIR = "/tmp/weevoice_audio"
os.makedirs(AUDIO_TMP_DIR, exist_ok=True)

# Call timeout - if no audio for this long, assume call ended
CALL_TIMEOUT_SECONDS = 5


class EAGIHandler:
    """
    EAGI handler using backend WebSocket API.
    Uses temporary WAV files for audio output (EAGI limitation).
    """
    
    def __init__(self):
        self.env = {}
        self.running = False
        self.ws = None
        self._audio_fd = None
        self._audio_fd_num = None
        
        # HIGH-QUALITY resamplers (use soxr VHQ if available)
        self._resampler_8k_to_16k = HighQualityResampler(ASTERISK_RATE, GEMINI_INPUT_RATE)
        self._resampler_24k_to_8k = HighQualityResampler(GEMINI_OUTPUT_RATE, ASTERISK_RATE)
        
        self.caller_id = "unknown"
        self.call_id = None
        self.session_id = None
        
        # Audio output buffer
        self._playback_queue = asyncio.Queue()
        
        # Track last audio time for timeout detection
        self._last_audio_time = time.time()
        
        # Pending greeting to play in background
        self._pending_greeting = None
        
        # Synchronization flag: prevents audio capture/playback during greeting
        # This ensures the greeting is not interrupted by Gemini responding to background noise
        self._greeting_done = asyncio.Event()
        self._greeting_done.set()  # Default: no greeting pending, allow audio immediately
        
        log("=" * 60)
        log("WeeVoice EAGI Starting (WebSocket API Mode)")
        log(f"Backend: {WS_URL}")
        log(f"Audio: soxr={SOXR_AVAILABLE}, scipy={SCIPY_AVAILABLE}, numpy={NUMPY_AVAILABLE}")
        log("=" * 60)
        
        # Open FD3 for audio input from Asterisk (NON-BLOCKING)
        try:
            self._audio_fd_num = 3
            self._audio_fd = os.fdopen(3, 'rb', buffering=0)
            # Make FD3 non-blocking
            fd = self._audio_fd.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            log("Audio FD3 opened (non-blocking)")
        except Exception as e:
            log(f"Failed to open FD3: {e}")
            self._audio_fd = None
    
    # ========================================================================
    # AGI PROTOCOL
    # ========================================================================
    
    def _read_agi_env(self):
        """Read AGI environment"""
        log("Reading AGI environment...")
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            if ':' in line:
                key, value = line.split(':', 1)
                self.env[key.strip()] = value.strip()
        
        self.caller_id = self.env.get('agi_callerid', 'unknown')
        self.call_id = self.env.get('agi_uniqueid', datetime.now().strftime('%Y%m%d%H%M%S'))
        self.session_id = f"eagi_{self.call_id}"
        
        log(f"Call ID: {self.call_id}, Caller: {self.caller_id}")
    
    def _agi_command(self, cmd: str) -> str:
        """Send AGI command and get response"""
        sys.stdout.write(f"{cmd}\n")
        sys.stdout.flush()
        response = sys.stdin.readline().strip()
        return response
    
    def _verbose(self, msg: str):
        """Send to Asterisk CLI"""
        self._agi_command(f'VERBOSE "{msg}" 3')
    
    def _stream_file(self, filename: str) -> str:
        """Play audio file using STREAM FILE (without extension)"""
        return self._agi_command(f'STREAM FILE "{filename}" ""')
    
    def _check_channel_status(self) -> bool:
        """Check if channel is still active"""
        try:
            result = self._agi_command('CHANNEL STATUS')
            # Result format: "200 result=X" where X is status code
            # Status 6 = up/connected, others might indicate hangup
            if '200 result=' in result:
                status = int(result.split('=')[1].split()[0])
                return status == 6  # 6 = channel up
            return False
        except:
            return False
    
    # ========================================================================
    # AUDIO RESAMPLING
    # ========================================================================
    
    def _resample_8k_to_16k(self, audio_8k: bytes) -> bytes:
        """Convert 8kHz from Asterisk to 16kHz for backend (HIGH QUALITY)"""
        if len(audio_8k) < 2:
            return b''
        try:
            # Remove DC offset first (prevents clicks)
            audio_8k = remove_dc_offset(audio_8k)
            
            # High-quality resample using soxr VHQ
            result = self._resampler_8k_to_16k.process(audio_8k)
            return result
        except Exception as e:
            log(f"Resample 8k->16k error: {e}")
            return audio_8k
    
    def _resample_24k_to_8k(self, audio_24k: bytes) -> bytes:
        """Convert 24kHz from backend to 8kHz for Asterisk (HIGH QUALITY)"""
        if len(audio_24k) < 2:
            return b''
        try:
            # High-quality resample using soxr VHQ
            # soxr handles anti-aliasing internally
            result = self._resampler_24k_to_8k.process(audio_24k)
            
            # Only apply DC offset removal (lightweight, prevents clicks)
            # Skip normalization - Gemini output is already normalized
            result = remove_dc_offset(result)
            
            return result
        except Exception as e:
            log(f"Resample 24k->8k error: {e}")
            return audio_24k
    
    def _flush_output_resampler(self) -> bytes:
        """
        Flush the output resampler to recover any buffered samples.
        
        CRITICAL: This must be called at end of audio stream!
        Without flushing, the final samples (last words/syllables) are lost
        because the streaming resampler holds samples in its internal buffer.
        
        Returns: Remaining 8kHz audio bytes
        """
        try:
            flushed = self._resampler_24k_to_8k.flush()
            if flushed:
                flushed = remove_dc_offset(flushed)
                log(f"Output resampler flushed: {len(flushed)} bytes recovered")
            return flushed
        except Exception as e:
            log(f"Output resampler flush error: {e}")
            return b''
    
    def _pcm_to_ulaw(self, pcm_data: bytes) -> bytes:
        """Convert PCM16 to µ-law for Asterisk"""
        try:
            return audioop.lin2ulaw(pcm_data, 2)
        except Exception as e:
            log(f"PCM to ulaw error: {e}")
            return pcm_data
    
    def _pcm_to_alaw(self, pcm_data: bytes) -> bytes:
        """Convert PCM16 to A-law for Asterisk (used by some SIP providers like Zadarma)"""
        try:
            return audioop.lin2alaw(pcm_data, 2)
        except Exception as e:
            log(f"PCM to alaw error: {e}")
            return pcm_data
    
    # ========================================================================
    # AUDIO FILE HANDLING
    # ========================================================================
    
    def _write_audio_file(self, audio_data: bytes, file_id: int, add_padding: bool = True) -> str:
        """
        Write audio to file for playback, return filename without extension.
        
        Creates BOTH ulaw and alaw versions so Asterisk can pick the matching codec.
        This avoids transcoding which can cause timing issues.
        
        IMPORTANT: Adds silence padding at the end of each file to mask the gap
        between sequential STREAM FILE commands. This prevents audible dropouts.
        """
        filename = f"{AUDIO_TMP_DIR}/{self.session_id}_{file_id}"
        ulaw_path = f"{filename}.ulaw"
        alaw_path = f"{filename}.alaw"
        sln_path = f"{filename}.sln"  # Also create slin for best compatibility
        
        try:
            # Add silence padding at the end to mask inter-file gaps
            # The gap between STREAM FILE commands is typically 20-50ms
            # We add 60ms of silence to ensure smooth transitions
            PADDING_SAMPLES = 480  # 60ms at 8kHz
            
            # Convert to µ-law
            ulaw_data = self._pcm_to_ulaw(audio_data)
            if add_padding:
                # In µ-law encoding, 0xFF (255) represents zero amplitude (silence)
                ulaw_data = ulaw_data + bytes([0xFF] * PADDING_SAMPLES)
            
            with open(ulaw_path, 'wb') as f:
                f.write(ulaw_data)
            
            # Convert to A-law (for Zadarma and other providers that prefer alaw)
            alaw_data = self._pcm_to_alaw(audio_data)
            if add_padding:
                # In A-law encoding, 0xD5 (213) represents zero amplitude (silence)
                alaw_data = alaw_data + bytes([0xD5] * PADDING_SAMPLES)
            
            with open(alaw_path, 'wb') as f:
                f.write(alaw_data)
            
            # Also write raw slin (signed linear 8kHz) as fallback
            sln_data = audio_data
            if add_padding:
                # slin silence is 0x00 bytes (2 bytes per sample)
                sln_data = sln_data + bytes([0x00] * PADDING_SAMPLES * 2)
            
            with open(sln_path, 'wb') as f:
                f.write(sln_data)
            
            return filename
            
        except Exception as e:
            log(f"Error writing audio file: {e}")
            return None
    
    def _cleanup_audio_files(self):
        """Remove temporary audio files"""
        try:
            for f in Path(AUDIO_TMP_DIR).glob(f"{self.session_id}_*"):
                f.unlink()
        except Exception as e:
            log(f"Cleanup error: {e}")
    
    # ========================================================================
    # WEBSOCKET CONNECTION
    # ========================================================================
    
    async def _connect_websocket(self) -> bool:
        """
        Connect to backend WebSocket API.
        
        OPTIMIZATION: Backend may send pre-cached greeting IMMEDIATELY 
        before Gemini is ready. We play it while waiting for "ready".
        """
        try:
            import websockets
            
            log(f"Connecting to {WS_URL}...")
            self.ws = await websockets.connect(WS_URL)
            
            # Send start message
            await self.ws.send(json.dumps({
                "type": "start",
                "caller_id": self.caller_id,
                "session_id": self.session_id
            }))
            
            # Wait for ready - but handle greeting messages first if sent
            greeting_chunks = []
            
            while True:
                response = await asyncio.wait_for(self.ws.recv(), timeout=30)
                msg = json.loads(response)
                msg_type = msg.get("type")
                
                if msg_type == "error":
                    log(f"Backend error: {msg.get('message')}")
                    return False
                
                if msg_type == "greeting":
                    # Legacy single-message greeting (small greetings)
                    log("Received pre-cached greeting - playing IMMEDIATELY!")
                    await self._play_greeting_immediately(msg.get("data"))
                    continue
                
                if msg_type == "greeting_start":
                    # Chunked greeting start
                    total_bytes = msg.get("total_bytes", 0)
                    chunks = msg.get("chunks", 0)
                    log(f"Receiving greeting: {total_bytes} bytes in {chunks} chunks")
                    greeting_chunks = []
                    continue
                
                if msg_type == "greeting_chunk":
                    # Accumulate greeting chunks
                    chunk_data = msg.get("data", "")
                    if chunk_data:
                        greeting_chunks.append(base64.b64decode(chunk_data))
                    continue
                
                if msg_type == "greeting_end":
                    # All chunks received - DON'T wait for greeting to finish!
                    # Store greeting and continue - we'll play it async
                    if greeting_chunks:
                        full_audio = b''.join(greeting_chunks)
                        log(f"Greeting complete: {len(full_audio)} bytes - will play in background")
                        self._pending_greeting = full_audio
                        greeting_chunks = []
                    continue
                
                if msg_type == "ready":
                    log(f"Connected! Agent: {msg.get('agent')}")
                    return True
                
                log(f"Unexpected response type: {msg_type}")
                # Don't fail on unexpected messages, keep waiting for ready
            
        except ImportError:
            log("websockets package not installed!")
            return False
        except asyncio.TimeoutError:
            log("Timeout connecting to backend")
            return False
        except Exception as e:
            log(f"WebSocket connection error: {e}")
            return False
    
    async def _play_greeting_immediately(self, audio_b64: str):
        """
        Play pre-cached greeting from base64 string.
        Legacy method for backwards compatibility.
        """
        if not audio_b64:
            log("No greeting audio data")
            return
        audio_24k = base64.b64decode(audio_b64)
        await self._play_greeting_audio(audio_24k)
    
    async def _play_greeting_audio(self, audio_24k: bytes):
        """
        Play pre-cached greeting IMMEDIATELY.
        This runs before Gemini session is ready, eliminating the 5+ second delay.
        
        IMPORTANT: This blocks audio capture/playback until done to prevent
        Gemini from responding to background noise and interrupting the greeting.
        """
        if not audio_24k or len(audio_24k) < 100:
            log("No greeting audio data")
            self._greeting_done.set()  # Allow audio even if no greeting
            return
        
        try:
            import time
            t0 = time.perf_counter()
            
            # CRITICAL: Block audio capture/playback until greeting is done
            self._greeting_done.clear()
            log(f"Greeting received: {len(audio_24k)} bytes (24kHz) - blocking audio until done")
            
            # Resample 24kHz -> 8kHz for Asterisk
            audio_8k = self._resample_24k_to_8k(audio_24k)
            log(f"Greeting resampled to 8kHz: {len(audio_8k)} bytes")
            
            # Write to file in MULTIPLE formats for codec compatibility
            # This avoids transcoding delays that can cause audio issues
            greeting_file = f"{AUDIO_TMP_DIR}/{self.session_id}_greeting"
            
            # µ-law (common in North America)
            ulaw_data = self._pcm_to_ulaw(audio_8k)
            with open(f"{greeting_file}.ulaw", 'wb') as f:
                f.write(ulaw_data)
            
            # A-law (common in Europe, used by Zadarma)
            alaw_data = self._pcm_to_alaw(audio_8k)
            with open(f"{greeting_file}.alaw", 'wb') as f:
                f.write(alaw_data)
            
            # slin (signed linear - best quality, Asterisk native)
            with open(f"{greeting_file}.sln", 'wb') as f:
                f.write(audio_8k)
            
            log(f"Greeting saved in ulaw/alaw/sln formats")
            
            # Play via STREAM FILE (blocking but quick for greeting)
            log(f"Playing greeting via STREAM FILE...")
            
            # Run in executor to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._stream_file, greeting_file
            )
            
            elapsed_ms = (time.perf_counter() - t0) * 1000
            log(f"✅ Greeting played in {elapsed_ms:.0f}ms total - unblocking audio")
            
        except Exception as e:
            log(f"Error playing greeting: {e}")
        finally:
            # ALWAYS unblock audio capture/playback
            self._greeting_done.set()
    
    # ========================================================================
    # AUDIO LOOPS (NON-BLOCKING)
    # ========================================================================
    
    async def _capture_and_send(self):
        """Capture audio from FD3 and send to backend in batches for efficiency.
        
        CRITICAL FIX: We MUST drain FD3 continuously, even during greeting playback!
        If we don't read from FD3, the buffer fills up and causes backpressure,
        resulting in 'write() failed: Resource temporarily unavailable' during STREAM FILE.
        
        During greeting: Read and DISCARD audio (don't send to Gemini)
        After greeting: Read and SEND audio to Gemini
        """
        log("CAPTURE: Starting audio capture from Asterisk")
        
        if not self._audio_fd:
            log("CAPTURE: Audio FD3 not available")
            return
        
        # NOTE: We start reading immediately but only SEND after greeting
        greeting_done = self._greeting_done.is_set()
        if not greeting_done:
            log("CAPTURE: Draining FD3 during greeting (discarding audio)")
        
        frame_count = 0
        buffer = b''
        send_buffer = b''  # Accumulate audio before sending
        empty_read_count = 0
        MAX_EMPTY_READS = 150  # ~3 seconds of no audio = call ended (increased to allow listening)
        
        # Batch size for sending - 40ms at 16kHz = 1280 bytes
        # Smaller batches = faster audio to Gemini = faster VAD detection
        SEND_BATCH_SIZE = 1280  # ~40ms at 16kHz
        last_send_time = time.time()
        MAX_SEND_DELAY = 0.025  # Force send every 25ms even if buffer not full
        
        while self.running and self.ws:
            try:
                # Non-blocking read using select
                readable, _, _ = select.select([self._audio_fd], [], [], 0.015)  # 15ms timeout (faster)
                
                if readable:
                    try:
                        data = self._audio_fd.read(FRAME_SIZE * 4)  # Read multiple frames
                        if data:
                            buffer += data
                            empty_read_count = 0
                            self._last_audio_time = time.time()
                        else:
                            empty_read_count += 1
                            if empty_read_count > MAX_EMPTY_READS:
                                log("CAPTURE: EOF detected (call ended)")
                                break
                    except BlockingIOError:
                        pass
                    except OSError as e:
                        if e.errno == 9:
                            log("CAPTURE: FD3 closed (call ended)")
                            break
                        raise
                    except Exception as e:
                        if self.running:
                            log(f"CAPTURE: FD3 read error: {e}")
                        break
                else:
                    empty_read_count += 1
                    if empty_read_count > MAX_EMPTY_READS:
                        log("CAPTURE: No audio timeout (call may have ended)")
                        break
                
                # Process complete frames and accumulate for batch send
                while len(buffer) >= FRAME_SIZE:
                    chunk = buffer[:FRAME_SIZE]
                    buffer = buffer[FRAME_SIZE:]
                    
                    # Resample 8kHz -> 16kHz
                    audio_16k = self._resample_8k_to_16k(chunk)
                    if audio_16k:
                        send_buffer += audio_16k
                        frame_count += 1
                
                # Check if greeting is now done (transition from draining to sending)
                if not greeting_done and self._greeting_done.is_set():
                    greeting_done = True
                    log("CAPTURE: Greeting finished, now sending audio to Gemini")
                    # Clear any buffered audio from during greeting - we don't want to send that
                    send_buffer = b''
                
                # Send when buffer is full OR timeout reached (whichever comes first)
                # BUT only if greeting is done - during greeting we just drain and discard
                current_time = time.time()
                should_send = (
                    greeting_done and  # Only send AFTER greeting is done
                    (len(send_buffer) >= SEND_BATCH_SIZE or 
                     (len(send_buffer) > 0 and current_time - last_send_time >= MAX_SEND_DELAY))
                )
                
                if should_send and self.ws:
                    try:
                        await self.ws.send(json.dumps({
                            "type": "audio",
                            "data": base64.b64encode(send_buffer).decode()
                        }))
                        if frame_count <= 5 or frame_count % 200 == 0:
                            log(f"CAPTURE: Sent batch ({len(send_buffer)}b, {frame_count} frames total)")
                        send_buffer = b''
                        last_send_time = current_time
                    except Exception as e:
                        if self.running:
                            log(f"CAPTURE: WebSocket send error: {e}")
                        break
                elif not greeting_done and len(send_buffer) > SEND_BATCH_SIZE * 2:
                    # During greeting, discard buffered audio to prevent memory buildup
                    send_buffer = b''
                
                # Yield to other tasks
                await asyncio.sleep(0)  # Minimal yield
                        
            except Exception as e:
                if self.running:
                    log(f"CAPTURE: Error: {e}")
                break
        
        log(f"CAPTURE: Ended, {frame_count} frames sent")
        self.running = False
    
    async def _receive_and_buffer(self):
        """
        Receive audio from backend and queue for playback.
        
        Uses LARGE buffer to minimize gaps between files.
        The key to smooth audio is fewer, larger files.
        
        NOTE: Discards audio received during greeting to prevent
        Gemini responses from interrupting the greeting playback.
        """
        log("RECEIVE: Starting audio receiver from backend")
        
        # Track if we should discard audio (during greeting)
        audio_discarded_during_greeting = 0
        
        chunk_count = 0
        file_id = 0
        audio_accumulator = b''
        
        # === BUFFER SETTINGS FOR CONTINUOUS AUDIO ===
        # CRITICAL: Larger buffers = fewer files = fewer gaps = smoother audio
        # The file-based playback (STREAM FILE) has inherent latency between files.
        # Using larger buffers creates fewer files with longer audio each,
        # which dramatically reduces audible dropouts.
        #
        # Trade-off: Larger buffers = slightly higher initial latency, but much smoother audio
        FIRST_PLAYBACK_SIZE = int(ASTERISK_RATE * 2 * 0.6)   # 600ms for first chunk (balance speed vs smoothness)
        MIN_PLAYBACK_SIZE = int(ASTERISK_RATE * 2 * 1.5)     # 1.5 seconds for subsequent chunks (smooth!)
        FLUSH_THRESHOLD = int(ASTERISK_RATE * 2 * 0.3)       # 300ms minimum for flush (avoid tiny files)
        
        # Track silence for smart flushing
        last_audio_time = time.time()
        SILENCE_FLUSH_MS = 200  # Flush after 200ms of silence (longer to accumulate complete phrases)
        
        is_first_chunk = True  # Track if this is the first response
        
        log(f"RECEIVE: Buffer config: first={FIRST_PLAYBACK_SIZE}b (600ms), normal={MIN_PLAYBACK_SIZE}b (1.5s), flush={FLUSH_THRESHOLD}b (300ms)")
        
        try:
            while self.running and self.ws:
                try:
                    # Use shorter timeout for more responsive audio buffering
                    # This allows us to queue audio files more quickly
                    msg_str = await asyncio.wait_for(self.ws.recv(), timeout=0.03)  # 30ms timeout
                    msg = json.loads(msg_str)
                    msg_type = msg.get("type")
                    
                    if msg_type == "audio":
                        # Decode audio from backend (24kHz PCM16)
                        audio_24k = base64.b64decode(msg.get("data", ""))
                        
                        if audio_24k:
                            # CRITICAL: Discard audio if greeting is still playing
                            # This prevents Gemini responses (triggered by background noise)
                            # from interrupting the greeting
                            if not self._greeting_done.is_set():
                                audio_discarded_during_greeting += len(audio_24k)
                                if audio_discarded_during_greeting == len(audio_24k):
                                    log(f"RECEIVE: Discarding audio during greeting playback...")
                                continue
                            
                            # Log if we just finished discarding
                            if audio_discarded_during_greeting > 0:
                                log(f"RECEIVE: Greeting done, discarded {audio_discarded_during_greeting} bytes of early audio")
                                audio_discarded_during_greeting = 0
                            
                            # Resample 24kHz -> 8kHz
                            audio_8k = self._resample_24k_to_8k(audio_24k)
                            
                            if audio_8k:
                                audio_accumulator += audio_8k
                                chunk_count += 1
                                last_audio_time = time.time()
                                
                                if chunk_count == 1:
                                    log(f"RECEIVE: First audio from backend! ({len(audio_24k)} bytes)")
                                elif chunk_count % 100 == 0:
                                    log(f"RECEIVE: Got {chunk_count} chunks, buffer={len(audio_accumulator)}b")
                                
                                # Determine buffer threshold (smaller for first response)
                                current_threshold = FIRST_PLAYBACK_SIZE if is_first_chunk else MIN_PLAYBACK_SIZE
                                
                                # Queue when we have enough audio
                                if len(audio_accumulator) >= current_threshold:
                                    file_id += 1
                                    filename = self._write_audio_file(audio_accumulator, file_id)
                                    if filename:
                                        await self._playback_queue.put(filename)
                                        duration_ms = len(audio_accumulator) / (ASTERISK_RATE * 2) * 1000
                                        if is_first_chunk:
                                            log(f"RECEIVE: ⚡ FIRST response queued in {duration_ms:.0f}ms!")
                                            is_first_chunk = False  # Switch to normal buffer size
                                        else:
                                            log(f"RECEIVE: Queued file #{file_id} ({duration_ms:.0f}ms)")
                                    audio_accumulator = b''
                    
                    elif msg_type == "transcript":
                        role = msg.get("role", "")
                        text = msg.get("text", "")
                        if text:
                            log(f"[{role.upper()}]: {text[:60]}...")
                    
                    elif msg_type == "error":
                        log(f"RECEIVE: Backend error: {msg.get('message')}")
                        break
                    
                    elif msg_type == "end":
                        log("RECEIVE: Backend signaled end")
                        break
                        
                except asyncio.TimeoutError:
                    if not self.running:
                        break
                    
                    # Smart flush: After speech pause, flush accumulated audio
                    # This ensures we don't wait forever for buffer to fill
                    silence_ms = (time.time() - last_audio_time) * 1000
                    if len(audio_accumulator) >= FLUSH_THRESHOLD and silence_ms > SILENCE_FLUSH_MS:
                        file_id += 1
                        filename = self._write_audio_file(audio_accumulator, file_id)
                        if filename:
                            await self._playback_queue.put(filename)
                            duration_ms = len(audio_accumulator) / (ASTERISK_RATE * 2) * 1000
                            log(f"RECEIVE: Flushed file #{file_id} after {silence_ms:.0f}ms silence ({duration_ms:.0f}ms audio)")
                        audio_accumulator = b''
                    continue
                    
                except Exception as e:
                    if self.running and "closed" not in str(e).lower():
                        log(f"RECEIVE: Error: {e}")
                    break
                    
        except Exception as e:
            log(f"RECEIVE: Loop error: {e}")
        
        # CRITICAL: Flush the resampler to get any remaining buffered samples
        # This recovers the final words/syllables that would otherwise be lost!
        flushed_audio = self._flush_output_resampler()
        if flushed_audio:
            audio_accumulator += flushed_audio
            log(f"RECEIVE: Recovered {len(flushed_audio)} bytes from resampler flush")
        
        # Flush any remaining audio (including resampler flush)
        if audio_accumulator and len(audio_accumulator) > 50:  # Lower threshold to catch final syllables
            file_id += 1
            filename = self._write_audio_file(audio_accumulator, file_id)
            if filename:
                await self._playback_queue.put(filename)
                duration_ms = len(audio_accumulator) / (ASTERISK_RATE * 2) * 1000
                log(f"RECEIVE: Final flush file #{file_id} ({duration_ms:.0f}ms audio)")
        
        # Signal end of playback
        await self._playback_queue.put(None)
        
        log(f"RECEIVE: Ended, got {chunk_count} chunks, wrote {file_id} files")
    
    async def _playback_worker(self):
        """
        Play queued audio files using Asterisk STREAM FILE.
        
        CRITICAL: This worker continues until it receives None from the queue,
        ensuring ALL audio is played including the final words.
        
        PRE-BUFFERING: Waits for multiple files to be queued before starting
        playback, ensuring the receiver stays ahead and preventing dropouts.
        """
        log("PLAYBACK: Starting playback worker")
        
        # CRITICAL: Wait for greeting to finish before playing Gemini audio
        # This prevents Gemini responses from interrupting the greeting
        if not self._greeting_done.is_set():
            log("PLAYBACK: Waiting for greeting to finish before playing Gemini audio...")
            await self._greeting_done.wait()
            log("PLAYBACK: Greeting done, starting playback")
        
        files_played = 0
        loop = asyncio.get_event_loop()
        
        # PRE-BUFFERING: Wait until we have at least 2 files queued
        # This ensures the receiver stays ahead of playback, preventing
        # the situation where playback catches up and causes gaps
        PRE_BUFFER_FILES = 2
        prebuffer_timeout = 3.0  # Maximum time to wait for pre-buffer
        prebuffer_start = time.time()
        
        while self._playback_queue.qsize() < PRE_BUFFER_FILES:
            if time.time() - prebuffer_start > prebuffer_timeout:
                log(f"PLAYBACK: Pre-buffer timeout, starting with {self._playback_queue.qsize()} files")
                break
            if not self.running:
                log("PLAYBACK: Stopping during pre-buffer (call ended)")
                return
            await asyncio.sleep(0.05)  # Check every 50ms
        
        log(f"PLAYBACK: Pre-buffer complete, {self._playback_queue.qsize()} files ready")
        
        # Continue until we receive the end signal (None) from the queue
        # IMPORTANT: Don't stop just because self.running=False - we need to 
        # finish playing all queued files to avoid cutting off final words!
        while True:
            try:
                # Use longer timeout when running=False to allow queue to drain
                timeout = 0.5 if self.running else 2.0
                filename = await asyncio.wait_for(self._playback_queue.get(), timeout=timeout)
                
                if filename is None:
                    log("PLAYBACK: Received end signal - all audio played")
                    break
                
                # Play the audio file (run in thread to not block)
                queue_depth = self._playback_queue.qsize()
                
                # DROPOUT DETECTION: If queue is empty or nearly empty, we're at risk
                # of catching up to the receiver, which causes dropouts
                if queue_depth == 0 and files_played > 0:
                    log(f"PLAYBACK: ⚠️ Queue empty! May cause dropout after file #{files_played}")
                
                try:
                    result = await loop.run_in_executor(
                        None, self._stream_file, filename
                    )
                    files_played += 1
                    if files_played <= 3 or files_played % 10 == 0:
                        log(f"PLAYBACK: Played file #{files_played} (queue depth: {queue_depth})")
                except Exception as e:
                    log(f"PLAYBACK: Error playing file: {e}")
                    # Continue to next file even if one fails
                    files_played += 1
                
            except asyncio.TimeoutError:
                # Only exit on timeout if not running AND queue is empty
                if not self.running and self._playback_queue.empty():
                    log("PLAYBACK: Timeout with empty queue - exiting")
                    break
                continue
            except asyncio.CancelledError:
                # If cancelled, try to play remaining files quickly
                log(f"PLAYBACK: Cancelled - draining remaining {self._playback_queue.qsize()} files")
                while not self._playback_queue.empty():
                    try:
                        filename = self._playback_queue.get_nowait()
                        if filename is None:
                            break
                        await loop.run_in_executor(None, self._stream_file, filename)
                        files_played += 1
                    except:
                        break
                raise  # Re-raise to properly handle cancellation
            except Exception as e:
                log(f"PLAYBACK: Error: {e}")
                # Continue trying to play remaining files
                continue
        
        log(f"PLAYBACK: Ended, played {files_played} files")
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def _cleanup(self):
        """Clean up resources"""
        log("Cleaning up...")
        
        # Send end message
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "end"}))
                await self.ws.close()
            except:
                pass
            self.ws = None
        
        # Close audio FD
        if self._audio_fd:
            try:
                self._audio_fd.close()
            except:
                pass
            self._audio_fd = None
        
        # Clean up audio files
        self._cleanup_audio_files()
    
    # ========================================================================
    # MAIN
    # ========================================================================
    
    async def run(self):
        """Main execution"""
        self._read_agi_env()
        self._verbose("WeeVoice: Starting")
        
        # Connect to backend (greeting stored in self._pending_greeting)
        if not await self._connect_websocket():
            self._verbose("WeeVoice: Connection Error")
            return
        
        self._verbose("WeeVoice: Connected")
        self.running = True
        self._last_audio_time = time.time()
        
        try:
            # Create tasks
            log("Creating async tasks...")
            
            # Start all tasks including greeting (greeting runs in parallel!)
            capture_task = asyncio.create_task(self._capture_and_send())
            receive_task = asyncio.create_task(self._receive_and_buffer())
            playback_task = asyncio.create_task(self._playback_worker())
            
            # Greeting task - runs and BLOCKS capture/playback until done
            # This prevents Gemini from responding to background noise during greeting
            greeting_task = None
            if self._pending_greeting:
                log("Starting greeting playback task (capture/playback blocked until done)...")
                self._greeting_done.clear()  # Block audio until greeting done
                greeting_task = asyncio.create_task(self._play_greeting_audio(self._pending_greeting))
                self._pending_greeting = None
            else:
                # No greeting - allow audio immediately
                self._greeting_done.set()
            
            log("All tasks created")
            
            # Wait for capture task to complete (it detects call end)
            await capture_task
            
            log("Capture ended, waiting for playback to complete...")
            self.running = False
            
            # CRITICAL FIX: Wait for receive_task to finish and flush final audio
            # This ensures the resampler is flushed and final audio is queued
            try:
                await asyncio.wait_for(receive_task, timeout=3.0)
                log("Receive task completed - all audio queued")
            except asyncio.TimeoutError:
                log("Receive task timeout - cancelling")
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
            
            # CRITICAL FIX: Wait for playback to complete ALL queued files
            # This ensures the final words are not cut off
            # The playback_worker will exit when it receives None from the queue
            try:
                # Calculate reasonable timeout based on queue size
                queue_size = self._playback_queue.qsize()
                # Each file could be up to 500ms, plus processing time
                playback_timeout = max(5.0, queue_size * 1.0 + 2.0)
                log(f"Waiting for playback to complete ({queue_size} files in queue, timeout={playback_timeout:.0f}s)")
                
                await asyncio.wait_for(playback_task, timeout=playback_timeout)
                log("Playback task completed - all audio played")
            except asyncio.TimeoutError:
                log(f"Playback timeout after {playback_timeout:.0f}s - some audio may be cut off")
                playback_task.cancel()
                try:
                    await playback_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel greeting if still running (it should be done by now)
            if greeting_task and not greeting_task.done():
                greeting_task.cancel()
                try:
                    await greeting_task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            log(f"Run error: {e}")
        finally:
            self.running = False
            await self._cleanup()
        
        self._verbose("WeeVoice: Ended")
        log("EAGI session ended - process exiting")


def main():
    handler = EAGIHandler()
    try:
        asyncio.run(handler.run())
    except KeyboardInterrupt:
        log("Interrupted")
    except Exception as e:
        log(f"Fatal: {e}")
        sys.stdout.write('VERBOSE "WeeVoice: Error" 1\n')
        sys.stdout.flush()
    finally:
        log("EAGI process terminating")
        sys.exit(0)


if __name__ == "__main__":
    main()
