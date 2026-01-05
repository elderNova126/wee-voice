#!/usr/bin/env python3
"""
WeeVoice EAGI - Uses Backend WebSocket API

This script connects to the backend WebSocket API for voice streaming.
Audio OUTPUT uses temporary files + STREAM FILE command (EAGI limitation).
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
from datetime import datetime
from pathlib import Path

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
        self._resample_state_in = None
        self._resample_state_out = None
        
        self.caller_id = "unknown"
        self.call_id = None
        self.session_id = None
        
        # Audio output buffer
        self._playback_queue = asyncio.Queue()
        
        # Track last audio time for timeout detection
        self._last_audio_time = time.time()
        
        log("=" * 60)
        log("WeeVoice EAGI Starting (WebSocket API Mode)")
        log(f"Backend: {WS_URL}")
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
        """Convert 8kHz from Asterisk to 16kHz for backend"""
        if len(audio_8k) < 2:
            return b''
        try:
            result, self._resample_state_in = audioop.ratecv(
                audio_8k, 2, 1, ASTERISK_RATE, GEMINI_INPUT_RATE, self._resample_state_in
            )
            return result
        except Exception as e:
            log(f"Resample 8k->16k error: {e}")
            return audio_8k
    
    def _resample_24k_to_8k(self, audio_24k: bytes) -> bytes:
        """Convert 24kHz from backend to 8kHz for Asterisk"""
        if len(audio_24k) < 2:
            return b''
        try:
            result, self._resample_state_out = audioop.ratecv(
                audio_24k, 2, 1, GEMINI_OUTPUT_RATE, ASTERISK_RATE, self._resample_state_out
            )
            return result
        except Exception as e:
            log(f"Resample 24k->8k error: {e}")
            return audio_24k
    
    def _pcm_to_ulaw(self, pcm_data: bytes) -> bytes:
        """Convert PCM16 to µ-law for Asterisk"""
        try:
            return audioop.lin2ulaw(pcm_data, 2)
        except Exception as e:
            log(f"PCM to ulaw error: {e}")
            return pcm_data
    
    # ========================================================================
    # AUDIO FILE HANDLING
    # ========================================================================
    
    def _write_audio_file(self, audio_data: bytes, file_id: int) -> str:
        """Write audio to file for playback, return filename without extension"""
        filename = f"{AUDIO_TMP_DIR}/{self.session_id}_{file_id}"
        ulaw_path = f"{filename}.ulaw"
        
        try:
            # Write as µ-law raw file (Asterisk native format)
            ulaw_data = self._pcm_to_ulaw(audio_data)
            with open(ulaw_path, 'wb') as f:
                f.write(ulaw_data)
            
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
        """Connect to backend WebSocket API"""
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
            
            # Wait for ready
            response = await asyncio.wait_for(self.ws.recv(), timeout=30)
            msg = json.loads(response)
            
            if msg.get("type") == "error":
                log(f"Backend error: {msg.get('message')}")
                return False
            
            if msg.get("type") == "ready":
                log(f"Connected! Agent: {msg.get('agent')}")
                return True
            
            log(f"Unexpected response: {msg}")
            return False
            
        except ImportError:
            log("websockets package not installed!")
            return False
        except asyncio.TimeoutError:
            log("Timeout connecting to backend")
            return False
        except Exception as e:
            log(f"WebSocket connection error: {e}")
            return False
    
    # ========================================================================
    # AUDIO LOOPS (NON-BLOCKING)
    # ========================================================================
    
    async def _capture_and_send(self):
        """Capture audio from FD3 (non-blocking) and send to backend"""
        log("CAPTURE: Starting audio capture from Asterisk")
        
        if not self._audio_fd:
            log("CAPTURE: Audio FD3 not available")
            return
        
        frame_count = 0
        buffer = b''
        empty_read_count = 0
        MAX_EMPTY_READS = 50  # ~1 second of no audio = call ended
        
        while self.running and self.ws:
            try:
                # Non-blocking read using select
                readable, _, _ = select.select([self._audio_fd], [], [], 0.02)  # 20ms timeout
                
                if readable:
                    try:
                        data = self._audio_fd.read(FRAME_SIZE * 4)  # Read multiple frames
                        if data:
                            buffer += data
                            empty_read_count = 0  # Reset counter
                            self._last_audio_time = time.time()
                        else:
                            # EOF - Asterisk closed FD3, call ended
                            empty_read_count += 1
                            if empty_read_count > MAX_EMPTY_READS:
                                log("CAPTURE: EOF detected (call ended)")
                                break
                    except BlockingIOError:
                        pass  # No data available
                    except OSError as e:
                        # Handle "Bad file descriptor" = call ended
                        if e.errno == 9:  # EBADF
                            log("CAPTURE: FD3 closed (call ended)")
                            break
                        raise
                    except Exception as e:
                        if self.running:
                            log(f"CAPTURE: FD3 read error: {e}")
                        break
                else:
                    # Timeout - check if call is still active
                    empty_read_count += 1
                    if empty_read_count > MAX_EMPTY_READS:
                        log("CAPTURE: No audio timeout (call may have ended)")
                        break
                
                # Process complete frames
                while len(buffer) >= FRAME_SIZE:
                    chunk = buffer[:FRAME_SIZE]
                    buffer = buffer[FRAME_SIZE:]
                    
                    # Resample 8kHz -> 16kHz
                    audio_16k = self._resample_8k_to_16k(chunk)
                    
                    if audio_16k and self.ws:
                        try:
                            await self.ws.send(json.dumps({
                                "type": "audio",
                                "data": base64.b64encode(audio_16k).decode()
                            }))
                            frame_count += 1
                            if frame_count == 1:
                                log("CAPTURE: First audio chunk sent to backend")
                            elif frame_count % 500 == 0:  # Log less frequently
                                log(f"CAPTURE: Sent {frame_count} chunks to backend")
                        except Exception as e:
                            if self.running:
                                log(f"CAPTURE: WebSocket send error: {e}")
                            break
                
                # Yield to other tasks
                await asyncio.sleep(0.001)
                        
            except Exception as e:
                if self.running:
                    log(f"CAPTURE: Error: {e}")
                break
        
        log(f"CAPTURE: Ended, {frame_count} frames sent")
        self.running = False  # Signal other tasks to stop
    
    async def _receive_and_buffer(self):
        """Receive audio from backend and queue for playback"""
        log("RECEIVE: Starting audio receiver from backend")
        
        chunk_count = 0
        file_id = 0
        audio_accumulator = b''
        MIN_PLAYBACK_SIZE = ASTERISK_RATE * 2 * 1  # 1 second of audio minimum
        
        try:
            while self.running and self.ws:
                try:
                    msg_str = await asyncio.wait_for(self.ws.recv(), timeout=0.1)
                    msg = json.loads(msg_str)
                    msg_type = msg.get("type")
                    
                    if msg_type == "audio":
                        # Decode audio from backend (24kHz PCM16)
                        audio_24k = base64.b64decode(msg.get("data", ""))
                        
                        if audio_24k:
                            # Resample 24kHz -> 8kHz
                            audio_8k = self._resample_24k_to_8k(audio_24k)
                            
                            if audio_8k:
                                audio_accumulator += audio_8k
                                chunk_count += 1
                                
                                if chunk_count == 1:
                                    log(f"RECEIVE: First audio from backend! ({len(audio_24k)} bytes)")
                                elif chunk_count % 50 == 0:
                                    log(f"RECEIVE: Got {chunk_count} chunks, buffer={len(audio_accumulator)}")
                                
                                # When we have enough audio, queue it for playback
                                if len(audio_accumulator) >= MIN_PLAYBACK_SIZE:
                                    file_id += 1
                                    filename = self._write_audio_file(audio_accumulator, file_id)
                                    if filename:
                                        await self._playback_queue.put(filename)
                                        log(f"RECEIVE: Queued file #{file_id} ({len(audio_accumulator)} bytes)")
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
                    # Check if call is still active
                    if not self.running:
                        break
                    # Flush remaining audio if we have some
                    if len(audio_accumulator) > 1000:
                        file_id += 1
                        filename = self._write_audio_file(audio_accumulator, file_id)
                        if filename:
                            await self._playback_queue.put(filename)
                            log(f"RECEIVE: Flushed file #{file_id} ({len(audio_accumulator)} bytes)")
                        audio_accumulator = b''
                    continue
                    
                except Exception as e:
                    if self.running and "closed" not in str(e).lower():
                        log(f"RECEIVE: Error: {e}")
                    break
                    
        except Exception as e:
            log(f"RECEIVE: Loop error: {e}")
        
        # Flush any remaining audio
        if audio_accumulator:
            file_id += 1
            filename = self._write_audio_file(audio_accumulator, file_id)
            if filename:
                await self._playback_queue.put(filename)
        
        # Signal end of playback
        await self._playback_queue.put(None)
        
        log(f"RECEIVE: Ended, got {chunk_count} chunks, wrote {file_id} files")
    
    async def _playback_worker(self):
        """Play queued audio files using Asterisk STREAM FILE"""
        log("PLAYBACK: Starting playback worker")
        
        files_played = 0
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                filename = await asyncio.wait_for(self._playback_queue.get(), timeout=0.5)
                
                if filename is None:
                    log("PLAYBACK: Received end signal")
                    break
                
                # Check if still running before playing
                if not self.running:
                    break
                
                # Play the audio file (run in thread to not block)
                log(f"PLAYBACK: Playing file: {filename}")
                
                result = await loop.run_in_executor(
                    None, self._stream_file, filename
                )
                
                files_played += 1
                log(f"PLAYBACK: Played file #{files_played}")
                
            except asyncio.TimeoutError:
                if not self.running:
                    break
                continue
            except Exception as e:
                if self.running:
                    log(f"PLAYBACK: Error: {e}")
                break
        
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
        
        # Connect to backend
        if not await self._connect_websocket():
            self._verbose("WeeVoice: Connection Error")
            return
        
        self._verbose("WeeVoice: Connected")
        self.running = True
        self._last_audio_time = time.time()
        
        try:
            # Create tasks
            log("Creating async tasks...")
            capture_task = asyncio.create_task(self._capture_and_send())
            receive_task = asyncio.create_task(self._receive_and_buffer())
            playback_task = asyncio.create_task(self._playback_worker())
            log("All tasks created")
            
            # Wait for capture task to complete (it detects call end)
            await capture_task
            
            log("Capture ended, stopping other tasks...")
            self.running = False
            
            # Give receive/playback tasks a moment to finish gracefully
            await asyncio.sleep(0.5)
            
            # Cancel pending tasks
            for task in [receive_task, playback_task]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
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
