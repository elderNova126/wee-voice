#!/usr/bin/env python3
"""
WeeVoice EAGI Script for Asterisk AI Voice Agent

This script uses Asterisk EAGI (Extended AGI) to handle voice calls with
Google Gemini Live API for real-time AI voice conversations.

Place this file in: /var/lib/asterisk/agi-bin/weevoice_eagi.py
Make executable: chmod +x /var/lib/asterisk/agi-bin/weevoice_eagi.py

Asterisk dialplan example:
  exten => s,1,Answer()
  same => n,EAGI(/var/lib/asterisk/agi-bin/weevoice_eagi.py)
  same => n,Hangup()
"""

import os
import sys
import asyncio
import audioop
import struct
import tempfile
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Add the backend path for imports
sys.path.insert(0, '/opt/weevoice/backend')

# Configure logging
LOG_DIR = Path('/var/log/weevoice')
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'eagi.log'),
        logging.StreamHandler(sys.stderr)  # EAGI uses stderr for debug
    ]
)
logger = logging.getLogger('weevoice_eagi')

# Audio settings
ASTERISK_SAMPLE_RATE = 8000   # Asterisk native (slin)
GEMINI_INPUT_RATE = 16000     # Gemini expects 16kHz
GEMINI_OUTPUT_RATE = 24000    # Gemini outputs 24kHz
FRAME_SIZE_8K = 160           # 20ms at 8kHz (160 samples * 2 bytes = 320 bytes, but slin is 160 samples)
FRAME_BYTES_8K = 320          # 20ms at 8kHz in bytes

# Temp directory for audio files
TEMP_AUDIO_DIR = Path('/tmp/weevoice_audio')
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class AGIProtocol:
    """Handle AGI protocol communication with Asterisk"""
    
    def __init__(self, stdin=sys.stdin, stdout=sys.stdout, audio_fd=3):
        self.stdin = stdin
        self.stdout = stdout
        self.audio_fd = audio_fd
        self.audio_file = None
        self.variables: Dict[str, str] = {}
        self._setup_audio()
        
    def _setup_audio(self):
        """Setup audio input from FD3"""
        try:
            self.audio_file = os.fdopen(self.audio_fd, 'rb', buffering=0)
            logger.info(f"Audio FD3 opened successfully")
        except Exception as e:
            logger.error(f"Failed to open audio FD3: {e}")
            self.audio_file = None
    
    def read_env(self):
        """Read AGI environment variables from Asterisk"""
        while True:
            line = self.stdin.readline().strip()
            if not line:
                break
            if ':' in line:
                key, value = line.split(':', 1)
                self.variables[key.strip()] = value.strip()
                logger.debug(f"AGI var: {key}={value}")
        
        logger.info(f"Read {len(self.variables)} AGI variables")
        return self.variables
    
    def send_command(self, command: str) -> Dict[str, Any]:
        """Send an AGI command and get response"""
        logger.debug(f"AGI CMD: {command}")
        self.stdout.write(f"{command}\n")
        self.stdout.flush()
        
        response = self.stdin.readline().strip()
        logger.debug(f"AGI RSP: {response}")
        
        # Parse response: "200 result=0" or "200 result=1 (timeout)"
        result = {'code': 0, 'result': '', 'data': ''}
        if response:
            parts = response.split(' ', 2)
            if len(parts) >= 1:
                result['code'] = int(parts[0]) if parts[0].isdigit() else 0
            if len(parts) >= 2 and '=' in parts[1]:
                result['result'] = parts[1].split('=')[1]
            if len(parts) >= 3:
                result['data'] = parts[2]
        
        return result
    
    def answer(self):
        """Answer the call"""
        return self.send_command("ANSWER")
    
    def hangup(self):
        """Hang up the call"""
        return self.send_command("HANGUP")
    
    def stream_file(self, filename: str, escape_digits: str = ""):
        """Play an audio file (without extension)"""
        return self.send_command(f'STREAM FILE "{filename}" "{escape_digits}"')
    
    def set_variable(self, name: str, value: str):
        """Set a channel variable"""
        return self.send_command(f'SET VARIABLE {name} "{value}"')
    
    def get_variable(self, name: str) -> str:
        """Get a channel variable"""
        result = self.send_command(f'GET VARIABLE {name}')
        if result.get('data', '').startswith('('):
            # Extract value from "(value)"
            return result['data'][1:-1]
        return result.get('result', '')
    
    def verbose(self, message: str, level: int = 1):
        """Send a verbose message to Asterisk"""
        return self.send_command(f'VERBOSE "{message}" {level}')
    
    def read_audio_frame(self, size: int = FRAME_BYTES_8K) -> bytes:
        """Read audio frame from FD3"""
        if not self.audio_file:
            return b''
        try:
            return self.audio_file.read(size)
        except Exception as e:
            logger.error(f"Error reading audio: {e}")
            return b''
    
    def close(self):
        """Close resources"""
        if self.audio_file:
            try:
                self.audio_file.close()
            except:
                pass


class GeminiSession:
    """Handle Gemini Live API session"""
    
    def __init__(self, api_key: str, agent_config: Dict[str, Any]):
        self.api_key = api_key
        self.agent_config = agent_config
        self.client = None
        self.session = None
        self.session_context = None
        self.audio_queue = asyncio.Queue()
        self.response_queue = asyncio.Queue()
        self._running = False
        
    async def connect(self) -> bool:
        """Connect to Gemini Live API"""
        try:
            from google import genai
            
            self.client = genai.Client(api_key=self.api_key)
            
            # Build config
            config = {
                "response_modalities": ["AUDIO"],
                "input_audio_transcription": {},
                "output_audio_transcription": {},
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": self.agent_config.get('voice', 'Aoede')
                        }
                    }
                },
                "system_instruction": self.agent_config.get('system_prompt', 
                    "You are a helpful AI voice assistant. Be concise and friendly.")
            }
            
            model = self.agent_config.get('model', 'gemini-2.5-flash-native-audio-preview-09-2025')
            
            logger.info(f"Connecting to Gemini model: {model}")
            self.session_context = self.client.aio.live.connect(
                model=model,
                config=config
            )
            self.session = await self.session_context.__aenter__()
            self._running = True
            
            logger.info("Gemini session connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Gemini: {e}", exc_info=True)
            return False
    
    async def send_audio(self, audio_16k: bytes):
        """Send audio to Gemini (expects 16kHz PCM)"""
        if not self.session or not self._running:
            return
        try:
            await self.session.send_realtime_input(audio={
                "data": audio_16k,
                "mime_type": "audio/pcm;rate=16000"
            })
        except Exception as e:
            logger.error(f"Error sending audio to Gemini: {e}")
    
    async def send_text(self, text: str, end_of_turn: bool = True):
        """Send text to Gemini"""
        if not self.session or not self._running:
            return
        try:
            await self.session.send(input=text, end_of_turn=end_of_turn)
        except Exception as e:
            logger.error(f"Error sending text to Gemini: {e}")
    
    async def receive_responses(self):
        """Receive audio and text responses from Gemini"""
        if not self.session:
            return
        
        try:
            while self._running:
                try:
                    turn = self.session.receive()
                    async for response in turn:
                        # Handle audio data
                        if hasattr(response, 'data') and response.data:
                            await self.response_queue.put({
                                'type': 'audio',
                                'data': response.data
                            })
                        
                        # Handle transcripts
                        if hasattr(response, 'server_content'):
                            sc = response.server_content
                            if hasattr(sc, 'output_transcription') and sc.output_transcription:
                                text = getattr(sc.output_transcription, 'text', None)
                                if text:
                                    await self.response_queue.put({
                                        'type': 'agent_transcript',
                                        'text': text.strip()
                                    })
                            
                            if hasattr(sc, 'input_transcription') and sc.input_transcription:
                                text = getattr(sc.input_transcription, 'text', None)
                                if text:
                                    await self.response_queue.put({
                                        'type': 'user_transcript',
                                        'text': text.strip()
                                    })
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if "1000" in str(e) or "1011" in str(e) or "closed" in str(e).lower():
                        logger.info("Gemini session closed normally")
                        break
                    logger.error(f"Error receiving from Gemini: {e}")
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self._running = False
    
    async def close(self):
        """Close the Gemini session"""
        self._running = False
        if self.session_context:
            try:
                await self.session_context.__aexit__(None, None, None)
            except:
                pass
        self.session = None
        self.session_context = None


class WeeVoiceEAGI:
    """Main EAGI handler for WeeVoice AI Voice Agent"""
    
    def __init__(self):
        self.agi = AGIProtocol()
        self.gemini: Optional[GeminiSession] = None
        self.call_id: Optional[str] = None
        self.caller_id: str = "Unknown"
        self.agent_config: Dict[str, Any] = {}
        self._running = False
        self._audio_buffer = b''
        self._resample_state_in = None
        self._resample_state_out = None
        
    def load_config(self) -> bool:
        """Load configuration from environment or config file"""
        try:
            # Try to load from environment
            api_key = os.environ.get('GOOGLE_API_KEY', '')
            
            # Try to load from .env file if not in environment
            if not api_key:
                env_paths = [
                    '/opt/weevoice/backend/.env',
                    '/opt/weevoice/.env'
                ]
                for env_path in env_paths:
                    if os.path.exists(env_path):
                        with open(env_path) as f:
                            for line in f:
                                if line.startswith('GOOGLE_API_KEY='):
                                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                                    break
                        if api_key:
                            break
            
            if not api_key:
                logger.error("GOOGLE_API_KEY not found!")
                return False
            
            # Default agent config
            self.agent_config = {
                'api_key': api_key,
                'model': os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-native-audio-preview-09-2025'),
                'voice': os.environ.get('GEMINI_VOICE', 'Aoede'),
                'system_prompt': os.environ.get('AGENT_SYSTEM_PROMPT', 
                    "You are a helpful AI voice assistant. Keep responses brief and natural. "
                    "You are answering phone calls. Be professional yet friendly."),
                'greeting': os.environ.get('AGENT_GREETING', 
                    "Hello! How can I help you today?")
            }
            
            logger.info(f"Config loaded: model={self.agent_config['model']}, voice={self.agent_config['voice']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False
    
    def resample_8k_to_16k(self, audio_8k: bytes) -> bytes:
        """Resample 8kHz audio to 16kHz for Gemini input"""
        if len(audio_8k) < 2:
            return b''
        try:
            result, self._resample_state_in = audioop.ratecv(
                audio_8k, 2, 1, 
                ASTERISK_SAMPLE_RATE, GEMINI_INPUT_RATE, 
                self._resample_state_in
            )
            return result
        except Exception as e:
            logger.error(f"Resample 8k->16k error: {e}")
            return audio_8k
    
    def resample_24k_to_8k(self, audio_24k: bytes) -> bytes:
        """Resample 24kHz Gemini output to 8kHz for Asterisk"""
        if len(audio_24k) < 2:
            return b''
        try:
            result, self._resample_state_out = audioop.ratecv(
                audio_24k, 2, 1,
                GEMINI_OUTPUT_RATE, ASTERISK_SAMPLE_RATE,
                self._resample_state_out
            )
            return result
        except Exception as e:
            logger.error(f"Resample 24k->8k error: {e}")
            return audio_24k
    
    def save_audio_file(self, audio_8k: bytes, prefix: str = "response") -> str:
        """Save audio to a temporary file for Asterisk playback"""
        try:
            # Create unique filename
            timestamp = int(time.time() * 1000)
            filename = TEMP_AUDIO_DIR / f"{prefix}_{self.call_id}_{timestamp}"
            
            # Write as raw slin (signed linear 8kHz)
            slin_file = f"{filename}.sln"
            with open(slin_file, 'wb') as f:
                f.write(audio_8k)
            
            logger.info(f"Saved audio: {slin_file} ({len(audio_8k)} bytes)")
            return str(filename)  # Return without extension for STREAM FILE
            
        except Exception as e:
            logger.error(f"Failed to save audio file: {e}")
            return ""
    
    async def run_audio_capture(self):
        """Capture audio from Asterisk (FD3) and send to Gemini"""
        logger.info("Starting audio capture loop")
        frame_count = 0
        
        while self._running:
            try:
                # Read audio frame from FD3
                audio_8k = self.agi.read_audio_frame(FRAME_BYTES_8K)
                
                if not audio_8k:
                    await asyncio.sleep(0.005)
                    continue
                
                frame_count += 1
                
                # Resample to 16kHz for Gemini
                audio_16k = self.resample_8k_to_16k(audio_8k)
                
                # Send to Gemini
                if self.gemini and audio_16k:
                    await self.gemini.send_audio(audio_16k)
                
                if frame_count % 100 == 0:
                    logger.debug(f"Captured {frame_count} audio frames")
                    
            except Exception as e:
                if "closed" in str(e).lower():
                    logger.info("Audio capture: connection closed")
                    break
                logger.error(f"Audio capture error: {e}")
                await asyncio.sleep(0.01)
        
        logger.info(f"Audio capture ended after {frame_count} frames")
    
    async def run_response_handler(self):
        """Handle responses from Gemini and play audio"""
        logger.info("Starting response handler loop")
        audio_buffer = b''
        MIN_BUFFER_MS = 200  # Buffer 200ms before playing
        MIN_BUFFER_BYTES = int(GEMINI_OUTPUT_RATE * 2 * MIN_BUFFER_MS / 1000)
        
        while self._running:
            try:
                # Get response from Gemini
                response = await asyncio.wait_for(
                    self.gemini.response_queue.get(),
                    timeout=0.5
                )
                
                if response['type'] == 'audio':
                    # Buffer audio
                    audio_buffer += response['data']
                    
                    # When we have enough, play it
                    if len(audio_buffer) >= MIN_BUFFER_BYTES:
                        # Resample 24kHz to 8kHz
                        audio_8k = self.resample_24k_to_8k(audio_buffer)
                        audio_buffer = b''
                        
                        # Save to file and play
                        if audio_8k:
                            filename = self.save_audio_file(audio_8k)
                            if filename:
                                self.agi.stream_file(filename)
                
                elif response['type'] == 'agent_transcript':
                    logger.info(f"Agent: {response['text']}")
                
                elif response['type'] == 'user_transcript':
                    logger.info(f"User: {response['text']}")
                    
            except asyncio.TimeoutError:
                # If we have buffered audio, play it
                if audio_buffer:
                    audio_8k = self.resample_24k_to_8k(audio_buffer)
                    audio_buffer = b''
                    if audio_8k:
                        filename = self.save_audio_file(audio_8k)
                        if filename:
                            self.agi.stream_file(filename)
                continue
            except Exception as e:
                if "closed" in str(e).lower():
                    break
                logger.error(f"Response handler error: {e}")
                await asyncio.sleep(0.1)
        
        logger.info("Response handler ended")
    
    async def run(self):
        """Main EAGI execution"""
        logger.info("=" * 50)
        logger.info("WeeVoice EAGI Script Started")
        logger.info("=" * 50)
        
        try:
            # Read AGI environment
            env = self.agi.read_env()
            
            self.call_id = env.get('agi_uniqueid', str(int(time.time())))
            self.caller_id = env.get('agi_callerid', 'Unknown')
            
            logger.info(f"Call ID: {self.call_id}")
            logger.info(f"Caller ID: {self.caller_id}")
            logger.info(f"Channel: {env.get('agi_channel', 'unknown')}")
            
            # Load configuration
            if not self.load_config():
                self.agi.verbose("WeeVoice: Configuration error", 1)
                return
            
            # Connect to Gemini
            self.gemini = GeminiSession(
                self.agent_config['api_key'],
                self.agent_config
            )
            
            if not await self.gemini.connect():
                self.agi.verbose("WeeVoice: Gemini connection failed", 1)
                return
            
            self._running = True
            
            # Send greeting
            if self.agent_config.get('greeting'):
                logger.info("Triggering greeting...")
                await self.gemini.send_text("<CALL_START>", end_of_turn=True)
            
            # Start tasks
            capture_task = asyncio.create_task(self.run_audio_capture())
            response_task = asyncio.create_task(self.run_response_handler())
            receive_task = asyncio.create_task(self.gemini.receive_responses())
            
            self.agi.verbose("WeeVoice: AI Agent Active", 1)
            
            # Wait for tasks (they'll run until call ends)
            try:
                await asyncio.gather(capture_task, response_task, receive_task)
            except asyncio.CancelledError:
                pass
            
        except Exception as e:
            logger.error(f"EAGI Error: {e}", exc_info=True)
            self.agi.verbose(f"WeeVoice Error: {str(e)[:50]}", 1)
        
        finally:
            self._running = False
            
            # Cleanup
            if self.gemini:
                await self.gemini.close()
            
            self.agi.close()
            
            # Cleanup temp files
            try:
                for f in TEMP_AUDIO_DIR.glob(f"*_{self.call_id}_*"):
                    f.unlink()
            except:
                pass
            
            logger.info("WeeVoice EAGI Script Ended")


def main():
    """Entry point"""
    eagi = WeeVoiceEAGI()
    
    # Run async main
    try:
        asyncio.run(eagi.run())
    except KeyboardInterrupt:
        logger.info("EAGI interrupted")
    except Exception as e:
        logger.error(f"EAGI fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

