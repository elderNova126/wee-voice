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
import wave
import struct
from datetime import datetime
from pathlib import Path

# ============================================================================
# LOGGING
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
        self._resample_state_in = None
        self._resample_state_out = None
        
        self.caller_id = "unknown"
        self.call_id = None
        self.session_id = None
        
        # Audio output buffer
        self._audio_buffer = b''
        self._audio_buffer_lock = asyncio.Lock()
        self._playback_queue = asyncio.Queue()
        
        logger.info("=" * 60)
        logger.info("WeeVoice EAGI Starting (WebSocket API Mode)")
        logger.info(f"Backend: {WS_URL}")
        logger.info("=" * 60)
        
        # Open FD3 for audio input from Asterisk
        try:
            self._audio_fd = os.fdopen(3, 'rb', buffering=0)
            logger.info("Audio FD3 opened successfully")
        except Exception as e:
            logger.error(f"Failed to open FD3: {e}")
            self._audio_fd = None
    
    # ========================================================================
    # AGI PROTOCOL
    # ========================================================================
    
    def _read_agi_env(self):
        """Read AGI environment"""
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
        self.session_id = f"eagi_{self.call_id}"
        
        logger.info(f"Call ID: {self.call_id}, Caller: {self.caller_id}")
    
    def _agi_command(self, cmd: str) -> str:
        """Send AGI command and get response"""
        sys.stdout.write(f"{cmd}\n")
        sys.stdout.flush()
        response = sys.stdin.readline().strip()
        logger.debug(f"AGI: {cmd} -> {response}")
        return response
    
    def _verbose(self, msg: str):
        """Send to Asterisk CLI"""
        self._agi_command(f'VERBOSE "{msg}" 3')
    
    def _stream_file(self, filename: str) -> str:
        """Play audio file using STREAM FILE (without extension)"""
        # STREAM FILE plays until complete or digit pressed
        return self._agi_command(f'STREAM FILE "{filename}" ""')
    
    def _exec_playback(self, filename: str) -> str:
        """Play audio file using Playback application"""
        return self._agi_command(f'EXEC Playback "{filename}"')
    
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
            logger.error(f"Resample 8k->16k error: {e}")
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
            logger.error(f"Resample 24k->8k error: {e}")
            return audio_24k
    
    def _pcm_to_ulaw(self, pcm_data: bytes) -> bytes:
        """Convert PCM16 to µ-law for Asterisk"""
        try:
            return audioop.lin2ulaw(pcm_data, 2)
        except Exception as e:
            logger.error(f"PCM to ulaw error: {e}")
            return pcm_data
    
    # ========================================================================
    # AUDIO FILE HANDLING
    # ========================================================================
    
    def _write_audio_file(self, audio_data: bytes, file_id: int) -> str:
        """Write audio to WAV file for playback, return filename without extension"""
        filename = f"{AUDIO_TMP_DIR}/{self.session_id}_{file_id}"
        wav_path = f"{filename}.wav"
        ulaw_path = f"{filename}.ulaw"
        
        try:
            # Write as µ-law raw file (Asterisk native format)
            ulaw_data = self._pcm_to_ulaw(audio_data)
            with open(ulaw_path, 'wb') as f:
                f.write(ulaw_data)
            
            logger.debug(f"Wrote audio file: {ulaw_path} ({len(ulaw_data)} bytes)")
            return filename
            
        except Exception as e:
            logger.error(f"Error writing audio file: {e}")
            return None
    
    def _cleanup_audio_files(self):
        """Remove temporary audio files"""
        try:
            for f in Path(AUDIO_TMP_DIR).glob(f"{self.session_id}_*"):
                f.unlink()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    # ========================================================================
    # WEBSOCKET CONNECTION
    # ========================================================================
    
    async def _connect_websocket(self) -> bool:
        """Connect to backend WebSocket API"""
        try:
            import websockets
            
            logger.info(f"Connecting to {WS_URL}...")
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
                logger.error(f"Backend error: {msg.get('message')}")
                return False
            
            if msg.get("type") == "ready":
                logger.info(f"Connected! Agent: {msg.get('agent')}")
                return True
            
            logger.error(f"Unexpected response: {msg}")
            return False
            
        except ImportError:
            logger.error("websockets package not installed!")
            return False
        except asyncio.TimeoutError:
            logger.error("Timeout connecting to backend")
            return False
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            return False
    
    # ========================================================================
    # AUDIO LOOPS
    # ========================================================================
    
    async def _capture_and_send(self):
        """Capture audio from FD3 and send to backend"""
        logger.info("Starting audio capture from Asterisk")
        
        if not self._audio_fd:
            logger.error("Audio FD3 not available")
            return
        
        frame_count = 0
        buffer = b''
        
        while self.running and self.ws:
            try:
                # Read from Asterisk (non-blocking with small timeout)
                try:
                    data = self._audio_fd.read(FRAME_SIZE)
                except Exception as e:
                    if self.running:
                        logger.error(f"FD3 read error: {e}")
                    break
                
                if not data:
                    await asyncio.sleep(0.001)
                    continue
                
                buffer += data
                
                # Process frames
                while len(buffer) >= FRAME_SIZE:
                    chunk = buffer[:FRAME_SIZE]
                    buffer = buffer[FRAME_SIZE:]
                    
                    # Resample 8kHz -> 16kHz
                    audio_16k = self._resample_8k_to_16k(chunk)
                    
                    if audio_16k and self.ws:
                        # Send to backend as base64
                        try:
                            await self.ws.send(json.dumps({
                                "type": "audio",
                                "data": base64.b64encode(audio_16k).decode()
                            }))
                            frame_count += 1
                            if frame_count == 1:
                                logger.info("First audio chunk sent to backend")
                            elif frame_count % 100 == 0:
                                logger.info(f"Sent {frame_count} audio chunks to backend")
                        except Exception as e:
                            if self.running:
                                logger.error(f"WebSocket send error: {e}")
                            break
                        
            except Exception as e:
                if self.running:
                    logger.error(f"Capture error: {e}")
                break
        
        logger.info(f"Audio capture ended. Total frames sent: {frame_count}")
    
    async def _receive_and_buffer(self):
        """Receive audio from backend and queue for playback"""
        logger.info("Starting audio receiver from backend")
        
        chunk_count = 0
        file_id = 0
        audio_accumulator = b''
        MIN_PLAYBACK_SIZE = ASTERISK_RATE * 2 * 1  # 1 second of audio minimum
        
        try:
            while self.running and self.ws:
                try:
                    msg_str = await asyncio.wait_for(self.ws.recv(), timeout=0.5)
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
                                    logger.info("First audio chunk received from backend!")
                                
                                # When we have enough audio, queue it for playback
                                if len(audio_accumulator) >= MIN_PLAYBACK_SIZE:
                                    file_id += 1
                                    filename = self._write_audio_file(audio_accumulator, file_id)
                                    if filename:
                                        await self._playback_queue.put(filename)
                                        logger.info(f"Queued audio file #{file_id} for playback ({len(audio_accumulator)} bytes)")
                                    audio_accumulator = b''
                    
                    elif msg_type == "transcript":
                        role = msg.get("role", "")
                        text = msg.get("text", "")
                        if text:
                            logger.info(f"[{role.upper()}]: {text[:80]}...")
                    
                    elif msg_type == "error":
                        logger.error(f"Backend error: {msg.get('message')}")
                        break
                    
                    elif msg_type == "end":
                        logger.info("Backend signaled end")
                        break
                        
                except asyncio.TimeoutError:
                    # Flush remaining audio if we have some
                    if len(audio_accumulator) > 1000:  # At least some data
                        file_id += 1
                        filename = self._write_audio_file(audio_accumulator, file_id)
                        if filename:
                            await self._playback_queue.put(filename)
                            logger.info(f"Flushed audio file #{file_id} ({len(audio_accumulator)} bytes)")
                        audio_accumulator = b''
                    continue
                    
                except Exception as e:
                    if self.running and "closed" not in str(e).lower():
                        logger.error(f"Receive error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Receiver loop error: {e}")
        
        # Flush any remaining audio
        if audio_accumulator:
            file_id += 1
            filename = self._write_audio_file(audio_accumulator, file_id)
            if filename:
                await self._playback_queue.put(filename)
        
        # Signal end of playback
        await self._playback_queue.put(None)
        
        logger.info(f"Audio receiver ended. Total chunks received: {chunk_count}")
    
    async def _playback_worker(self):
        """Play queued audio files using Asterisk STREAM FILE"""
        logger.info("Starting playback worker")
        
        files_played = 0
        
        while self.running:
            try:
                filename = await asyncio.wait_for(self._playback_queue.get(), timeout=1.0)
                
                if filename is None:
                    logger.info("Playback worker received end signal")
                    break
                
                # Play the audio file
                logger.info(f"Playing audio file: {filename}")
                
                # Use STREAM FILE (run in thread to not block)
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._stream_file, filename
                )
                
                files_played += 1
                logger.info(f"Played file #{files_played}, result: {result}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Playback error: {e}")
                break
        
        logger.info(f"Playback worker ended. Files played: {files_played}")
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def _cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        
        # Send end message
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "end"}))
                await self.ws.close()
            except:
                pass
        
        # Close audio FD
        if self._audio_fd:
            try:
                self._audio_fd.close()
            except:
                pass
        
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
        
        try:
            # Create tasks
            capture_task = asyncio.create_task(self._capture_and_send())
            receive_task = asyncio.create_task(self._receive_and_buffer())
            playback_task = asyncio.create_task(self._playback_worker())
            
            # Wait for any task to complete (usually means call ended)
            done, pending = await asyncio.wait(
                [capture_task, receive_task, playback_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            logger.info("One task completed, stopping others...")
            self.running = False
            
            # Cancel pending tasks
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
        
        self._verbose("WeeVoice: Ended")
        logger.info("EAGI session ended")


def main():
    handler = EAGIHandler()
    try:
        asyncio.run(handler.run())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        sys.stdout.write('VERBOSE "WeeVoice: Error" 1\n')
        sys.stdout.flush()


if __name__ == "__main__":
    main()
