#!/usr/bin/env python3
"""
WeeVoice EAGI - Uses Backend WebSocket API

This script connects to the backend WebSocket API for voice streaming.
All Gemini logic is handled by the backend - same as web agent.
NO google-genai imports needed.
"""

import os
import sys
import asyncio
import audioop
import base64
import json
import logging
from datetime import datetime

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
ASTERISK_RATE = 8000      # From Asterisk
GEMINI_INPUT_RATE = 16000  # Backend expects 16kHz
GEMINI_OUTPUT_RATE = 24000 # Backend sends 24kHz
FRAME_SIZE = 320           # 20ms at 8kHz

HIGH_QUALITY_MODE = os.environ.get('WEEVOICE_HIGH_QUALITY', 'false').lower() == 'true'


class EAGIHandler:
    """
    EAGI handler using backend WebSocket API.
    All AI logic handled by backend - this just bridges Asterisk audio.
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
        
        logger.info("=" * 60)
        logger.info("WeeVoice EAGI Starting (WebSocket API Mode)")
        logger.info(f"Backend: {WS_URL}")
        logger.info("=" * 60)
    
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
        
        logger.info(f"Call ID: {self.call_id}, Caller: {self.caller_id}")
    
    def _agi_command(self, cmd: str) -> str:
        """Send AGI command"""
        sys.stdout.write(f"{cmd}\n")
        sys.stdout.flush()
        return sys.stdin.readline().strip()
    
    def _verbose(self, msg: str):
        """Send to Asterisk CLI"""
        self._agi_command(f'VERBOSE "{msg}" 3')
    
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
            target = 16000 if HIGH_QUALITY_MODE else ASTERISK_RATE
            result, self._resample_state_out = audioop.ratecv(
                audio_24k, 2, 1, GEMINI_OUTPUT_RATE, target, self._resample_state_out
            )
            return result
        except Exception as e:
            logger.error(f"Resample 24k->8k error: {e}")
            return audio_24k
    
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
                "session_id": f"eagi_{self.call_id}"
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
        logger.info("Starting audio capture")
        
        try:
            self._audio_fd = os.fdopen(3, 'rb', buffering=0)
        except Exception as e:
            logger.error(f"Failed to open FD3: {e}")
            return
        
        frame_count = 0
        buffer = b''
        
        while self.running and self.ws:
            try:
                # Read from Asterisk
                data = self._audio_fd.read(FRAME_SIZE)
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
                    
                    if audio_16k:
                        # Send to backend as base64
                        await self.ws.send(json.dumps({
                            "type": "audio",
                            "data": base64.b64encode(audio_16k).decode()
                        }))
                        frame_count += 1
                        
            except Exception as e:
                if self.running:
                    logger.error(f"Capture error: {e}")
                break
        
        logger.info(f"Capture ended. Frames sent: {frame_count}")
    
    async def _receive_and_play(self):
        """Receive audio from backend and play to Asterisk"""
        logger.info("Starting playback receiver")
        
        chunk_count = 0
        
        try:
            while self.running and self.ws:
                try:
                    msg_str = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                    msg = json.loads(msg_str)
                    msg_type = msg.get("type")
                    
                    if msg_type == "audio":
                        # Decode audio
                        audio_24k = base64.b64decode(msg.get("data", ""))
                        
                        # Resample 24kHz -> 8kHz
                        audio_out = self._resample_24k_to_8k(audio_24k)
                        
                        if audio_out:
                            # Write to stdout (EAGI audio output)
                            sys.stdout.buffer.write(audio_out)
                            sys.stdout.buffer.flush()
                            chunk_count += 1
                            if chunk_count == 1:
                                logger.info("First audio chunk received and sent to Asterisk")
                    
                    elif msg_type == "transcript":
                        role = msg.get("role", "")
                        text = msg.get("text", "")
                        if text:
                            logger.info(f"{role.upper()}: {text[:80]}...")
                    
                    elif msg_type == "error":
                        logger.error(f"Backend error: {msg.get('message')}")
                        break
                        
                except asyncio.TimeoutError:
                    # No message received, continue waiting
                    continue
                except Exception as e:
                    if self.running and "closed" not in str(e).lower():
                        logger.error(f"Receive error: {e}", exc_info=True)
                    break
        except Exception as e:
            logger.error(f"Playback loop error: {e}", exc_info=True)
        
        logger.info(f"Playback ended. Chunks received: {chunk_count}")
    
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
            # Run audio loops
            capture = asyncio.create_task(self._capture_and_send())
            playback = asyncio.create_task(self._receive_and_play())
            
            # Wait for either to complete
            done, pending = await asyncio.wait(
                [capture, playback],
                return_when=asyncio.FIRST_COMPLETED
            )
            
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
        
        self._verbose("WeeVoice: Ended")
        logger.info("EAGI Ended")


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
