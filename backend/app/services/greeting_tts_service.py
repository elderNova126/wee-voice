"""
Gemini Greeting Pre-Generation Service

Pre-generates greeting audio using GEMINI (same voice as conversation).
This ensures voice consistency between greeting and conversation.

Greetings are generated at server startup or when agents are updated.
During calls, only cached greetings are used (instant read, <50ms).
"""
import asyncio
import os
import hashlib
import logging
import audioop
import tempfile
from pathlib import Path
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)

# Cache directory for pre-generated greetings - use cross-platform temp directory
# On Windows: uses %TEMP% (e.g., C:\Users\...\AppData\Local\Temp)
# On Linux: uses /tmp
GREETING_CACHE_DIR = Path(tempfile.gettempdir()) / "weedoo_greetings_gemini"
GREETING_CACHE_DIR.mkdir(exist_ok=True)

# Audio format: 8kHz mono PCM (for Asterisk)
TARGET_SAMPLE_RATE = 8000
FRAME_SIZE = 320  # 20ms at 8kHz

# Gemini outputs 24kHz audio
GEMINI_SAMPLE_RATE = 24000

# Check if Gemini is available
try:
    from google import genai
    from app.core.config import settings
    GEMINI_AVAILABLE = bool(settings.GOOGLE_API_KEY)
    if GEMINI_AVAILABLE:
        print("[GREETING] ✅ Gemini available for greeting generation (same voice as conversation)", flush=True)
    else:
        print("[GREETING] ⚠ GOOGLE_API_KEY not set", flush=True)
except ImportError:
    GEMINI_AVAILABLE = False
    print("[GREETING] ⚠ google-genai not available", flush=True)


def get_gemini_voice_name(language: str, gender: str, voice_id: str = None) -> str:
    """
    Get Gemini voice name matching agent settings.
    
    MUST match the logic in agent_service.py EXACTLY to ensure
    greeting voice matches conversation voice!
    
    Priority (same as agent_service.py):
    1. voice_gender preference (most important)
    2. voice_id if it's a valid Gemini voice
    3. Default by language
    """
    valid_voices = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]
    
    # Priority 1: Use voice_gender preference (most important)
    if gender:
        if gender == "female":
            return "Kore"
        elif gender == "male":
            return "Charon"
        elif gender == "neutral":
            return "Puck"
        # If invalid gender value, fall through to voice_id check
    
    # Priority 2: Use voice_id if it's a valid Gemini voice
    if voice_id and voice_id in valid_voices:
        return voice_id
    
    # Priority 3: Default by language (matches agent_service.py)
    # NOTE: Puck is more neutral and handles non-English languages better
    if language:
        if language.startswith('fr'):
            return "Puck"  # Neutral voice - clearer French pronunciation than Charon
        elif language.startswith('es'):
            return "Kore"
    
    return "Puck"  # Default


def get_greeting_cache_path(greeting_text: str, voice: str) -> Path:
    """Get cache file path for a greeting"""
    cache_key = hashlib.md5(f"{greeting_text}:{voice}:gemini".encode()).hexdigest()
    return GREETING_CACHE_DIR / f"greeting_{cache_key}.pcm"


def get_cached_greeting_sync(greeting_text: str, language: str = "fr-FR", gender: str = "male", voice_id: str = None) -> Optional[bytes]:
    """
    Get cached greeting INSTANTLY (synchronous file read).
    Returns None if not cached - caller should NOT wait for generation.
    
    Args:
        greeting_text: The greeting text to look up
        language: Agent language (e.g., 'fr-FR', 'en-US')
        gender: Voice gender ('male', 'female', 'neutral')
        voice_id: Specific Gemini voice ID (e.g., 'Aoede', 'Fenrir') - takes priority
    """
    if not greeting_text:
        print(f"[GREETING-CACHE] No greeting text provided", flush=True)
        return None
    
    voice = get_gemini_voice_name(language, gender, voice_id)
    cache_path = get_greeting_cache_path(greeting_text, voice)
    
    print(f"[GREETING-CACHE] Looking for: {cache_path.name}", flush=True)
    print(f"[GREETING-CACHE] Voice={voice}, Lang={language}, Gender={gender}", flush=True)
    print(f"[GREETING-CACHE] Greeting text: '{greeting_text[:50]}...'", flush=True)
    
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                data = f.read()
            if len(data) > 0:
                print(f"[GREETING-CACHE] ✅ Found: {len(data)} bytes", flush=True)
                return data
            else:
                print(f"[GREETING-CACHE] ⚠ File exists but empty", flush=True)
        except Exception as e:
            print(f"[GREETING-CACHE] ❌ Read error: {e}", flush=True)
    else:
        print(f"[GREETING-CACHE] ⚠ File not found: {cache_path}", flush=True)
        # List available cache files for debugging
        try:
            files = list(GREETING_CACHE_DIR.glob("*.pcm"))
            if files:
                print(f"[GREETING-CACHE] Available files: {[f.name for f in files[:5]]}", flush=True)
        except:
            pass
    
    return None


async def generate_greeting_with_gemini(
    greeting_text: str,
    language: str = "fr-FR",
    gender: str = "male",
    voice_id: str = None
) -> bool:
    """
    Generate greeting audio using GEMINI (same voice as conversation).
    This ensures voice consistency - greeting sounds the same as conversation.
    
    Args:
        greeting_text: The greeting text to generate
        language: Agent language (e.g., 'fr-FR', 'en-US')
        gender: Voice gender ('male', 'female', 'neutral')
        voice_id: Specific Gemini voice ID (e.g., 'Aoede', 'Fenrir') - takes priority
    """
    if not GEMINI_AVAILABLE:
        print("[GREETING] ❌ Gemini not available", flush=True)
        return False
    
    if not greeting_text or not greeting_text.strip():
        return False
    
    voice = get_gemini_voice_name(language, gender, voice_id)
    cache_path = get_greeting_cache_path(greeting_text, voice)
    
    # Skip if already cached
    if cache_path.exists() and cache_path.stat().st_size > 0:
        print(f"[GREETING] Already cached: {cache_path.name}", flush=True)
        return True
    
    try:
        start_time = time.perf_counter()
        print(f"[GREETING] Generating with Gemini ({voice}): '{greeting_text[:50]}...'", flush=True)
        
        # Create Gemini client
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        
        # Build config for Gemini Live API
        config = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": voice
                    }
                }
            }
        }
        
        # Connect to Gemini and generate greeting
        audio_chunks = []
        
        async with client.aio.live.connect(
            model=settings.GEMINI_MODEL,
            config=config
        ) as session:
            # Send greeting text - keep prompt SHORT to minimize delay
            # Same simple format for all languages
            prompt = f'Say this greeting naturally: "{greeting_text}"'
            
            await session.send(input=prompt, end_of_turn=True)
            
            # Collect audio response
            turn = session.receive()
            async for response in turn:
                if hasattr(response, 'data') and response.data:
                    audio_chunks.append(response.data)
                
                # Check for turn complete
                if hasattr(response, 'server_content'):
                    if getattr(response.server_content, 'turn_complete', False):
                        break
        
        if not audio_chunks:
            print("[GREETING] ❌ No audio received from Gemini", flush=True)
            return False
        
        # Combine all audio chunks (24kHz PCM)
        audio_24k = b''.join(audio_chunks)
        gen_time = (time.perf_counter() - start_time) * 1000
        print(f"[GREETING] Gemini generated {len(audio_24k)} bytes in {gen_time:.0f}ms", flush=True)
        
        # Resample 24kHz -> 8kHz for Asterisk
        audio_8k, _ = audioop.ratecv(audio_24k, 2, 1, GEMINI_SAMPLE_RATE, TARGET_SAMPLE_RATE, None)
        
        # Cache the audio
        try:
            with open(cache_path, 'wb') as f:
                f.write(audio_8k)
            total_time = (time.perf_counter() - start_time) * 1000
            print(f"[GREETING] ✅ Cached: {len(audio_8k)} bytes in {total_time:.0f}ms", flush=True)
            return True
        except Exception as e:
            print(f"[GREETING] ❌ Cache write failed: {e}", flush=True)
            return False
        
    except Exception as e:
        print(f"[GREETING] ❌ Gemini generation failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False


async def prewarm_all_agent_greetings():
    """
    Pre-generate greetings for ALL agents at server startup using GEMINI.
    This ensures instant greeting playback with the SAME VOICE as conversation.
    """
    if not GEMINI_AVAILABLE:
        print("[GREETING] ⚠ Gemini not available, skipping pre-warm", flush=True)
        return
    
    print("[GREETING] 🔥 Pre-warming greeting cache using GEMINI (same voice as conversation)...", flush=True)
    
    try:
        from app.models.database import SessionLocal
        from app.models import VoiceAgent
        
        db = SessionLocal()
        try:
            agents = db.query(VoiceAgent).filter(VoiceAgent.greeting.isnot(None)).all()
            
            if not agents:
                print("[GREETING] No agents with greetings found", flush=True)
                return
            
            print(f"[GREETING] Found {len(agents)} agents with greetings", flush=True)
            
            for agent in agents:
                if agent.greeting:
                    language = getattr(agent, 'language', 'fr-FR')
                    gender = getattr(agent, 'voice_gender', 'male')
                    voice_id = getattr(agent, 'voice_id', None)  # Specific voice takes priority
                    
                    # Use same voice selection as agent_service.py
                    voice = get_gemini_voice_name(language, gender, voice_id)
                    print(f"[GREETING] Generating for '{agent.name}' with voice={voice}", flush=True)
                    
                    success = await generate_greeting_with_gemini(
                        agent.greeting,
                        language=language,
                        gender=gender,
                        voice_id=voice_id
                    )
                    
                    status = "✅" if success else "⚠"
                    print(f"[GREETING] {status} Agent '{agent.name}' (voice={voice})", flush=True)
                    
                    # Small delay between agents to avoid rate limiting
                    await asyncio.sleep(0.5)
            
            print("[GREETING] 🔥 Pre-warm complete! Same voice for greeting & conversation.", flush=True)
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[GREETING] ❌ Pre-warm error: {e}", flush=True)
        import traceback
        traceback.print_exc()


class GreetingTTSService:
    """
    Service for managing Gemini-generated greetings.
    
    Uses GEMINI to generate greetings (same voice as conversation).
    During calls, only returns cached greetings (instant).
    """
    
    def __init__(self):
        self._pending_generation: Dict[str, asyncio.Task] = {}
    
    def get_cached_greeting(
        self,
        greeting_text: str,
        language: str = "fr-FR",
        gender: str = "male",
        voice_id: str = None
    ) -> Optional[bytes]:
        """
        Get cached greeting INSTANTLY.
        Returns None if not cached - does NOT generate on-the-fly.
        """
        return get_cached_greeting_sync(greeting_text, language, gender, voice_id)
    
    def trigger_background_generation(
        self,
        greeting_text: str,
        language: str = "fr-FR", 
        gender: str = "male",
        voice_id: str = None
    ):
        """
        Trigger background generation for next call.
        Non-blocking - returns immediately.
        """
        if not GEMINI_AVAILABLE or not greeting_text:
            return
        
        voice = get_gemini_voice_name(language, gender, voice_id)
        cache_key = f"{greeting_text}:{voice}"
        
        # Skip if already generating
        if cache_key in self._pending_generation:
            task = self._pending_generation[cache_key]
            if not task.done():
                return
        
        # Skip if already cached
        cache_path = get_greeting_cache_path(greeting_text, voice)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return
        
        # Start background generation
        async def generate():
            try:
                await generate_greeting_with_gemini(greeting_text, language, gender, voice_id)
            except Exception as e:
                print(f"[GREETING] Background generation error: {e}", flush=True)
            finally:
                self._pending_generation.pop(cache_key, None)
        
        self._pending_generation[cache_key] = asyncio.create_task(generate())
        print(f"[GREETING] Triggered background Gemini generation", flush=True)
    
    def is_available(self) -> bool:
        return GEMINI_AVAILABLE


# Global instance
_greeting_service: Optional[GreetingTTSService] = None


def get_greeting_tts_service() -> GreetingTTSService:
    """Get the singleton greeting TTS service"""
    global _greeting_service
    if _greeting_service is None:
        _greeting_service = GreetingTTSService()
    return _greeting_service


# Keep these for backward compatibility
EDGE_TTS_AVAILABLE = GEMINI_AVAILABLE  # Alias for compatibility
