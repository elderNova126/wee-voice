#!/usr/bin/env python3
"""
WeeVoice EAGI Full Implementation
Connects directly to database WITHOUT using app.core.config (avoids pydantic issues)
Uses same agent logic as web backend.
"""

import os
import sys
import asyncio
import audioop
import logging
from datetime import datetime
from typing import Optional, Any

# ============================================================================
# LOGGING SETUP - Before any other imports
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
# AUDIO CONFIGURATION
# ============================================================================
INPUT_SAMPLE_RATE = 8000    # From Asterisk
GEMINI_INPUT_RATE = 16000   # Gemini expects 16kHz
GEMINI_OUTPUT_RATE = 24000  # Gemini outputs 24kHz
INPUT_FRAME_SIZE = 320      # 20ms at 8kHz

HIGH_QUALITY_MODE = os.environ.get('WEEVOICE_HIGH_QUALITY', 'false').lower() == 'true'


class DirectDatabaseConnection:
    """
    Direct database connection that bypasses app.core.config
    Avoids pydantic-settings parsing issues
    """
    
    def __init__(self):
        self.engine = None
        self.Session = None
        
    def connect(self) -> bool:
        """Connect to database using DATABASE_URL from environment"""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            database_url = os.environ.get('DATABASE_URL', '')
            if not database_url:
                logger.error("DATABASE_URL not set!")
                return False
            
            logger.info(f"Connecting to database: {database_url[:50]}...")
            
            self.engine = create_engine(database_url)
            self.Session = sessionmaker(bind=self.engine)
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            
            logger.info("Database connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def get_session(self):
        """Get a new database session"""
        if self.Session:
            return self.Session()
        return None


class EAGIHandler:
    """
    Full-featured EAGI handler with direct database access
    """
    
    def __init__(self):
        self.env = {}
        self.running = False
        self.db_connection = DirectDatabaseConnection()
        self.db = None
        self.agent = None
        self.call = None
        self.gemini_session = None
        self.gemini_client = None
        self._audio_fd = None
        self._resample_state_in = None
        self._resample_state_out = None
        self.audio_queue = asyncio.Queue(maxsize=10)
        
        # Caller info
        self.caller_id = "unknown"
        self.call_id = None
        
        logger.info("=" * 60)
        logger.info("WeeVoice EAGI Starting (Direct DB Mode)")
        logger.info(f"High Quality Mode: {HIGH_QUALITY_MODE}")
        logger.info("=" * 60)
    
    # ========================================================================
    # AGI PROTOCOL
    # ========================================================================
    
    def _read_agi_env(self):
        """Read AGI environment variables"""
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
        """Send message to Asterisk CLI"""
        self._agi_command(f'VERBOSE "{msg}" 3')
    
    # ========================================================================
    # AUDIO RESAMPLING
    # ========================================================================
    
    def _resample_for_gemini(self, audio_8k: bytes) -> bytes:
        """Convert 8kHz to 16kHz for Gemini"""
        if len(audio_8k) < 2:
            return b''
        try:
            result, self._resample_state_in = audioop.ratecv(
                audio_8k, 2, 1, INPUT_SAMPLE_RATE, GEMINI_INPUT_RATE, self._resample_state_in
            )
            return result
        except Exception as e:
            logger.error(f"Resample in error: {e}")
            return audio_8k
    
    def _resample_from_gemini(self, audio_24k: bytes) -> bytes:
        """Convert 24kHz to 8kHz for Asterisk"""
        if len(audio_24k) < 2:
            return b''
        try:
            target = 16000 if HIGH_QUALITY_MODE else INPUT_SAMPLE_RATE
            result, self._resample_state_out = audioop.ratecv(
                audio_24k, 2, 1, GEMINI_OUTPUT_RATE, target, self._resample_state_out
            )
            return result
        except Exception as e:
            logger.error(f"Resample out error: {e}")
            return audio_24k
    
    # ========================================================================
    # DATABASE SETUP (Direct - no app.core.config)
    # ========================================================================
    
    def _setup_from_database(self) -> bool:
        """Load agent from database directly"""
        try:
            if not self.db_connection.connect():
                return False
            
            self.db = self.db_connection.get_session()
            if not self.db:
                logger.error("Could not create database session")
                return False
            
            # Import models (these don't use Settings)
            from sqlalchemy import text
            
            # Find phone with agent (raw SQL to avoid model dependencies)
            result = self.db.execute(text("""
                SELECT p.agent_id, a.id, a.user_id, a.name, a.system_prompt, 
                       a.greeting, a.language, a.voice_id, a.voice_gender,
                       a.model_name, a.temperature, a.rag_enabled
                FROM phone_numbers p
                JOIN voice_agents a ON p.agent_id = a.id
                WHERE p.agent_id IS NOT NULL 
                  AND p.sip_username IS NOT NULL
                LIMIT 1
            """)).fetchone()
            
            if not result:
                # Fallback: get first agent
                result = self.db.execute(text("""
                    SELECT id, id as agent_id, user_id, name, system_prompt,
                           greeting, language, voice_id, voice_gender,
                           model_name, temperature, rag_enabled
                    FROM voice_agents
                    WHERE is_active = true
                    LIMIT 1
                """)).fetchone()
            
            if not result:
                logger.error("No agent found in database")
                return False
            
            # Create agent-like object
            class AgentData:
                pass
            
            self.agent = AgentData()
            self.agent.id = result[1]
            self.agent.user_id = result[2]
            self.agent.name = result[3]
            self.agent.system_prompt = result[4] or "You are a helpful phone assistant."
            self.agent.greeting = result[5] or "Hello! How can I help you?"
            self.agent.language = result[6] or "en-US"
            self.agent.voice_id = result[7] or "Aoede"
            self.agent.voice_gender = result[8] or "female"
            self.agent.model_name = result[9] or "gemini-2.5-flash-preview-native-audio-dialog"
            self.agent.temperature = float(result[10] or 0.7)
            self.agent.rag_enabled = bool(result[11])
            
            logger.info(f"Loaded agent: {self.agent.name} (ID: {self.agent.id})")
            logger.info(f"  Voice: {self.agent.voice_id}, Language: {self.agent.language}")
            logger.info(f"  Greeting: {self.agent.greeting[:50]}...")
            
            # Create call record
            self.db.execute(text("""
                INSERT INTO calls (user_id, agent_id, caller_phone, caller_name, 
                                   direction, status, session_id, started_at)
                VALUES (:user_id, :agent_id, :caller_phone, :caller_name,
                        'inbound', 'in_progress', :session_id, :started_at)
            """), {
                'user_id': self.agent.user_id,
                'agent_id': self.agent.id,
                'caller_phone': self.caller_id,
                'caller_name': self.caller_id,
                'session_id': f"eagi_{self.call_id}",
                'started_at': datetime.utcnow()
            })
            self.db.commit()
            
            logger.info("Call record created")
            return True
            
        except Exception as e:
            logger.error(f"Database setup error: {e}", exc_info=True)
            return False
    
    # ========================================================================
    # GEMINI CONNECTION (Direct - like FrenchVoiceAgentService)
    # ========================================================================
    
    async def _connect_gemini(self) -> bool:
        """Connect to Gemini Live API directly"""
        try:
            from google import genai
            from google.genai import types
            
            api_key = os.environ.get('GOOGLE_API_KEY', '')
            if not api_key:
                logger.error("GOOGLE_API_KEY not set!")
                return False
            
            logger.info("Connecting to Gemini...")
            
            # Create client
            self.gemini_client = genai.Client(api_key=api_key)
            
            # Select voice based on agent config
            voice_name = self.agent.voice_id
            if self.agent.voice_gender == "female":
                voice_name = "Kore"
            elif self.agent.voice_gender == "male":
                voice_name = "Charon"
            
            # Build system instruction (like FrenchVoiceAgentService)
            system_instruction = f"""{self.agent.system_prompt}

GREETING PROTOCOL:
- When conversation starts, say: "{self.agent.greeting}"
- Use natural, friendly tone
- Keep responses concise for voice conversation

VOICE INSTRUCTION:
- Maintain consistent voice throughout
- Speak clearly and naturally
- Language: {self.agent.language}
"""
            
            # Configure Gemini Live
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=system_instruction)]
                )
            )
            
            # Connect
            model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-preview-native-audio-dialog')
            self.gemini_session = await self.gemini_client.aio.live.connect(
                model=model,
                config=config
            ).__aenter__()
            
            logger.info(f"Gemini connected (model: {model}, voice: {voice_name})")
            return True
            
        except Exception as e:
            logger.error(f"Gemini connection error: {e}", exc_info=True)
            return False
    
    async def _send_greeting_trigger(self):
        """Send greeting trigger to Gemini"""
        try:
            lang_prefix = "[Respond in English]"
            if self.agent.language.startswith('fr'):
                lang_prefix = "[Réponds en français]"
            elif self.agent.language.startswith('es'):
                lang_prefix = "[Responde en español]"
            
            await self.gemini_session.send(
                input=f"<CALL_START> {lang_prefix}",
                end_of_turn=True
            )
            logger.info("Greeting trigger sent")
        except Exception as e:
            logger.error(f"Greeting trigger error: {e}")
    
    # ========================================================================
    # AUDIO LOOPS
    # ========================================================================
    
    async def _audio_capture_loop(self):
        """Capture audio from FD3 and send to Gemini"""
        logger.info("Starting audio capture")
        
        try:
            self._audio_fd = os.fdopen(3, 'rb', buffering=0)
        except Exception as e:
            logger.error(f"Failed to open FD3: {e}")
            return
        
        frame_count = 0
        buffer = b''
        
        while self.running:
            try:
                data = self._audio_fd.read(INPUT_FRAME_SIZE)
                if not data:
                    await asyncio.sleep(0.001)
                    continue
                
                buffer += data
                
                while len(buffer) >= INPUT_FRAME_SIZE:
                    chunk = buffer[:INPUT_FRAME_SIZE]
                    buffer = buffer[INPUT_FRAME_SIZE:]
                    
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
                                self.running = False
                                break
                            
            except Exception as e:
                if self.running:
                    logger.error(f"Capture error: {e}")
                break
        
        logger.info(f"Capture ended. Frames: {frame_count}")
    
    async def _audio_playback_loop(self):
        """Receive audio from Gemini and write to stdout"""
        logger.info("Starting playback")
        
        chunk_count = 0
        
        try:
            async for response in self.gemini_session.receive():
                if not self.running:
                    break
                
                if hasattr(response, 'data') and response.data:
                    audio_out = self._resample_from_gemini(response.data)
                    if audio_out:
                        sys.stdout.buffer.write(audio_out)
                        sys.stdout.buffer.flush()
                        chunk_count += 1
                
                # Log transcriptions
                if hasattr(response, 'server_content'):
                    sc = response.server_content
                    if hasattr(sc, 'output_transcription') and sc.output_transcription:
                        text = getattr(sc.output_transcription, 'text', '')
                        if text:
                            logger.info(f"AI: {text[:80]}...")
                    if hasattr(sc, 'input_transcription') and sc.input_transcription:
                        text = getattr(sc.input_transcription, 'text', '')
                        if text:
                            logger.info(f"User: {text[:80]}...")
                            
        except Exception as e:
            if "closed" not in str(e).lower():
                logger.error(f"Playback error: {e}")
        
        logger.info(f"Playback ended. Chunks: {chunk_count}")
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def _cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        
        if self.gemini_session:
            try:
                await self.gemini_session.__aexit__(None, None, None)
            except:
                pass
        
        if self.db:
            try:
                self.db.close()
            except:
                pass
        
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
        
        # Setup database
        if not self._setup_from_database():
            self._verbose("WeeVoice: DB Error")
            return
        
        # Connect to Gemini
        if not await self._connect_gemini():
            self._verbose("WeeVoice: Gemini Error")
            return
        
        self._verbose("WeeVoice: Connected")
        self.running = True
        
        try:
            # Send greeting trigger
            await self._send_greeting_trigger()
            
            # Run audio loops
            capture = asyncio.create_task(self._audio_capture_loop())
            playback = asyncio.create_task(self._audio_playback_loop())
            
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
        sys.stdout.write('VERBOSE "WeeVoice: Fatal Error" 1\n')
        sys.stdout.flush()


if __name__ == "__main__":
    main()
