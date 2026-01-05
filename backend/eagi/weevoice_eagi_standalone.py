#!/usr/bin/env python3
"""
WeeVoice EAGI Standalone - Direct Gemini Integration
Works without backend database dependencies.
"""

import os
import sys
import asyncio
import audioop
import logging
from datetime import datetime

# Configure logging FIRST
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

# Audio constants
ASTERISK_RATE = 8000      # Asterisk sends/receives 8kHz
GEMINI_INPUT_RATE = 16000  # Gemini expects 16kHz input
GEMINI_OUTPUT_RATE = 24000 # Gemini outputs 24kHz

# High quality mode (16kHz output instead of 8kHz)
HIGH_QUALITY_MODE = os.environ.get('WEEVOICE_HIGH_QUALITY', 'false').lower() == 'true'

class EAGIHandler:
    """Standalone EAGI handler with direct Gemini integration"""
    
    def __init__(self):
        self.env = {}
        self.running = False
        self.gemini_session = None
        self._audio_fd = None
        self._resample_state_in = None
        self._resample_state_out = None
        
        # Configuration from environment
        self.api_key = os.environ.get('GOOGLE_API_KEY', '')
        self.voice = os.environ.get('GEMINI_VOICE', 'Aoede')
        self.model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-preview-native-audio-dialog')
        self.greeting = os.environ.get('AGENT_GREETING', 'Hello! How can I help you today?')
        self.system_prompt = os.environ.get('AGENT_SYSTEM_PROMPT', 
            "You are a helpful and professional phone assistant. "
            "Keep responses concise and natural for voice conversation. "
            "Be friendly and helpful.")
        
        logger.info(f"EAGI Handler initialized")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Voice: {self.voice}")
        logger.info(f"  High Quality: {HIGH_QUALITY_MODE}")
    
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
        
        logger.info(f"Call ID: {self.call_id}")
        logger.info(f"Caller: {self.caller_id}")
    
    def _agi_command(self, cmd: str) -> str:
        """Send AGI command and get response"""
        sys.stdout.write(f"{cmd}\n")
        sys.stdout.flush()
        return sys.stdin.readline().strip()
    
    def _verbose(self, msg: str):
        """Send verbose message to Asterisk"""
        self._agi_command(f'VERBOSE "{msg}" 3')
    
    def _resample_for_gemini(self, audio_8k: bytes) -> bytes:
        """Convert 8kHz slin to 16kHz for Gemini input"""
        if len(audio_8k) < 2:
            return b''
        try:
            result, self._resample_state_in = audioop.ratecv(
                audio_8k, 2, 1, ASTERISK_RATE, GEMINI_INPUT_RATE, self._resample_state_in
            )
            return result
        except Exception as e:
            logger.error(f"Resample input error: {e}")
            return audio_8k
    
    def _resample_from_gemini(self, audio_24k: bytes) -> bytes:
        """Convert 24kHz from Gemini to 8kHz for Asterisk"""
        if len(audio_24k) < 2:
            return b''
        try:
            if HIGH_QUALITY_MODE:
                # For SIP/WebRTC: 16kHz
                target_rate = 16000
            else:
                # For PSTN: 8kHz
                target_rate = ASTERISK_RATE
            
            result, self._resample_state_out = audioop.ratecv(
                audio_24k, 2, 1, GEMINI_OUTPUT_RATE, target_rate, self._resample_state_out
            )
            return result
        except Exception as e:
            logger.error(f"Resample output error: {e}")
            return audio_24k
    
    async def _connect_gemini(self) -> bool:
        """Connect to Google Gemini Live API"""
        try:
            from google import genai
            from google.genai import types
            
            if not self.api_key:
                logger.error("GOOGLE_API_KEY not set!")
                self._verbose("WeeVoice: No API Key")
                return False
            
            logger.info("Connecting to Gemini...")
            
            # Create client
            client = genai.Client(api_key=self.api_key)
            
            # Configure for voice
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.voice
                        )
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=self.system_prompt)]
                )
            )
            
            # Connect
            self.gemini_session = client.aio.live.connect(
                model=self.model,
                config=config
            )
            
            # Enter the async context
            self.gemini_session = await self.gemini_session.__aenter__()
            
            logger.info("Gemini connected successfully")
            self._verbose("WeeVoice: Connected")
            return True
            
        except Exception as e:
            logger.error(f"Gemini connection error: {e}", exc_info=True)
            self._verbose(f"WeeVoice: Connection Error")
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
        buffer = b''
        CHUNK_SIZE = 320  # 20ms at 8kHz = 160 samples * 2 bytes
        
        while self.running:
            try:
                # Read audio from Asterisk
                data = self._audio_fd.read(CHUNK_SIZE)
                if not data:
                    await asyncio.sleep(0.001)
                    continue
                
                buffer += data
                
                # Send chunks to Gemini
                while len(buffer) >= CHUNK_SIZE:
                    chunk = buffer[:CHUNK_SIZE]
                    buffer = buffer[CHUNK_SIZE:]
                    
                    # Resample 8kHz -> 16kHz
                    audio_16k = self._resample_for_gemini(chunk)
                    
                    if audio_16k and self.gemini_session:
                        try:
                            from google.genai import types
                            await self.gemini_session.send(
                                input=types.LiveClientRealtimeInput(
                                    media_chunks=[
                                        types.Blob(
                                            data=audio_16k,
                                            mime_type="audio/pcm;rate=16000"
                                        )
                                    ]
                                ),
                                end_of_turn=False
                            )
                            frame_count += 1
                        except Exception as e:
                            if "closed" in str(e).lower():
                                logger.info("Gemini session closed")
                                self.running = False
                                break
                            logger.error(f"Send error: {e}")
                
            except Exception as e:
                if self.running:
                    logger.error(f"Capture error: {e}")
                break
        
        logger.info(f"Audio capture ended. Sent {frame_count} frames")
    
    async def _audio_playback_loop(self):
        """Receive audio from Gemini and write to stdout"""
        logger.info("Starting audio playback")
        
        chunk_count = 0
        
        try:
            async for response in self.gemini_session.receive():
                if not self.running:
                    break
                
                # Handle audio data
                if hasattr(response, 'data') and response.data:
                    # Resample 24kHz -> 8kHz
                    audio_out = self._resample_from_gemini(response.data)
                    
                    if audio_out:
                        try:
                            sys.stdout.buffer.write(audio_out)
                            sys.stdout.buffer.flush()
                            chunk_count += 1
                        except Exception as e:
                            logger.error(f"Playback write error: {e}")
                
                # Handle text (for logging)
                if hasattr(response, 'text') and response.text:
                    logger.info(f"Gemini: {response.text[:100]}...")
                
                # Handle turn completion
                if hasattr(response, 'server_content'):
                    sc = response.server_content
                    if hasattr(sc, 'turn_complete') and sc.turn_complete:
                        logger.debug("Turn complete")
                
        except Exception as e:
            if "closed" not in str(e).lower():
                logger.error(f"Playback error: {e}")
        
        logger.info(f"Playback ended. Received {chunk_count} chunks")
    
    async def _send_greeting(self):
        """Send initial greeting to start conversation"""
        if not self.greeting:
            return
        
        try:
            logger.info(f"Sending greeting: {self.greeting[:50]}...")
            await self.gemini_session.send(
                input=self.greeting,
                end_of_turn=True
            )
        except Exception as e:
            logger.error(f"Greeting error: {e}")
    
    async def run(self):
        """Main EAGI execution"""
        logger.info("=" * 50)
        logger.info("WeeVoice EAGI Starting")
        logger.info("=" * 50)
        
        # Read AGI environment
        self._read_agi_env()
        self._verbose("WeeVoice: Starting AI Agent")
        
        # Connect to Gemini
        if not await self._connect_gemini():
            self._verbose("WeeVoice: Failed to connect")
            return
        
        self.running = True
        
        try:
            # Send greeting
            await self._send_greeting()
            
            # Run audio loops
            capture_task = asyncio.create_task(self._audio_capture_loop())
            playback_task = asyncio.create_task(self._audio_playback_loop())
            
            # Wait for either to complete
            done, pending = await asyncio.wait(
                [capture_task, playback_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining
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
            
            # Close Gemini
            if self.gemini_session:
                try:
                    await self.gemini_session.__aexit__(None, None, None)
                except:
                    pass
            
            # Close audio FD
            if self._audio_fd:
                try:
                    self._audio_fd.close()
                except:
                    pass
        
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
        sys.stdout.write('VERBOSE "WeeVoice: Error" 1\n')
        sys.stdout.flush()


if __name__ == "__main__":
    main()

