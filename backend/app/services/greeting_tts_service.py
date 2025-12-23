"""
Fast TTS Greeting Service

Pre-generates greeting audio using edge-tts for immediate playback.
This eliminates the 5-10 second delay waiting for Gemini to generate greetings.
"""
import asyncio
import os
import io
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import struct

logger = logging.getLogger(__name__)

# Cache directory for pre-generated greetings
GREETING_CACHE_DIR = Path(tempfile.gettempdir()) / "weedoo_greetings"
GREETING_CACHE_DIR.mkdir(exist_ok=True)

# Audio format: 8kHz mono PCM (for Asterisk)
TARGET_SAMPLE_RATE = 8000
FRAME_SIZE = 320  # 20ms at 8kHz

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
    logger.info("[TTS] edge-tts available for fast greeting generation")
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("[TTS] edge-tts not available, will use Gemini for greetings (slower)")


def get_greeting_cache_path(greeting_text: str, voice: str = "fr-FR-HenriNeural") -> Path:
    """Get cache file path for a greeting"""
    # Create hash of greeting + voice for cache key
    cache_key = hashlib.md5(f"{greeting_text}:{voice}".encode()).hexdigest()
    return GREETING_CACHE_DIR / f"greeting_{cache_key}.pcm"


def get_voice_for_language(language: str, gender: str = "male") -> str:
    """Get appropriate edge-tts voice for language"""
    # Map language codes to edge-tts voices
    voice_map = {
        "fr": {
            "male": "fr-FR-HenriNeural",
            "female": "fr-FR-DeniseNeural",
            "neutral": "fr-FR-HenriNeural",
        },
        "en": {
            "male": "en-US-GuyNeural",
            "female": "en-US-JennyNeural", 
            "neutral": "en-US-GuyNeural",
        },
        "es": {
            "male": "es-ES-AlvaroNeural",
            "female": "es-ES-ElviraNeural",
            "neutral": "es-ES-AlvaroNeural",
        },
        "de": {
            "male": "de-DE-ConradNeural",
            "female": "de-DE-KatjaNeural",
            "neutral": "de-DE-ConradNeural",
        },
    }
    
    lang_prefix = language[:2].lower() if language else "fr"
    gender = gender.lower() if gender else "male"
    
    if lang_prefix in voice_map:
        return voice_map[lang_prefix].get(gender, voice_map[lang_prefix]["male"])
    
    # Default to French
    return voice_map["fr"].get(gender, "fr-FR-HenriNeural")


async def generate_greeting_audio(
    greeting_text: str,
    language: str = "fr-FR",
    gender: str = "male",
    force_regenerate: bool = False
) -> Optional[bytes]:
    """
    Generate greeting audio using edge-tts.
    
    Returns PCM audio at 8kHz mono, ready for Asterisk playback.
    Caches result for future use.
    """
    if not EDGE_TTS_AVAILABLE:
        logger.warning("[TTS] edge-tts not available, cannot generate greeting")
        return None
    
    if not greeting_text or not greeting_text.strip():
        return None
    
    voice = get_voice_for_language(language, gender)
    cache_path = get_greeting_cache_path(greeting_text, voice)
    
    # Check cache first
    if not force_regenerate and cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                audio_data = f.read()
            if len(audio_data) > 0:
                logger.info(f"[TTS] Using cached greeting ({len(audio_data)} bytes)")
                return audio_data
        except Exception as e:
            logger.warning(f"[TTS] Cache read failed: {e}")
    
    try:
        import time
        start_time = time.perf_counter()
        
        # Generate audio with edge-tts
        communicate = edge_tts.Communicate(greeting_text, voice)
        
        # Collect audio chunks
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        
        if not audio_chunks:
            logger.error("[TTS] No audio generated")
            return None
        
        mp3_data = b''.join(audio_chunks)
        gen_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"[TTS] Generated MP3 in {gen_time:.0f}ms ({len(mp3_data)} bytes)")
        
        # Convert MP3 to 8kHz PCM using ffmpeg
        pcm_data = await convert_mp3_to_pcm(mp3_data)
        
        if pcm_data:
            # Cache for future use
            try:
                with open(cache_path, 'wb') as f:
                    f.write(pcm_data)
                logger.info(f"[TTS] Cached greeting to {cache_path}")
            except Exception as e:
                logger.warning(f"[TTS] Cache write failed: {e}")
            
            total_time = (time.perf_counter() - start_time) * 1000
            logger.info(f"[TTS] Total greeting generation: {total_time:.0f}ms, {len(pcm_data)} bytes PCM")
            return pcm_data
        
        return None
        
    except Exception as e:
        logger.error(f"[TTS] Greeting generation failed: {e}", exc_info=True)
        return None


async def convert_mp3_to_pcm(mp3_data: bytes) -> Optional[bytes]:
    """Convert MP3 audio to 8kHz mono PCM using ffmpeg"""
    try:
        import subprocess
        
        # Write MP3 to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as mp3_file:
            mp3_file.write(mp3_data)
            mp3_path = mp3_file.name
        
        # Output PCM file
        pcm_path = mp3_path.replace('.mp3', '.pcm')
        
        try:
            # Run ffmpeg to convert
            result = await asyncio.create_subprocess_exec(
                'ffmpeg', '-y', '-i', mp3_path,
                '-ar', '8000', '-ac', '1', '-f', 's16le',
                pcm_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"[TTS] ffmpeg conversion failed")
                return None
            
            # Read PCM data
            with open(pcm_path, 'rb') as f:
                pcm_data = f.read()
            
            return pcm_data
            
        finally:
            # Cleanup temp files
            try:
                os.unlink(mp3_path)
            except:
                pass
            try:
                os.unlink(pcm_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"[TTS] MP3 to PCM conversion failed: {e}")
        return None


def get_cached_greeting(greeting_text: str, language: str = "fr-FR", gender: str = "male") -> Optional[bytes]:
    """Get cached greeting if available (synchronous)"""
    if not greeting_text:
        return None
    
    voice = get_voice_for_language(language, gender)
    cache_path = get_greeting_cache_path(greeting_text, voice)
    
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                return f.read()
        except Exception:
            pass
    
    return None


async def pregenerate_agent_greeting(agent) -> bool:
    """
    Pre-generate greeting audio for an agent.
    Call this when agent is created/updated.
    """
    if not agent.greeting:
        return False
    
    if not EDGE_TTS_AVAILABLE:
        return False
    
    try:
        language = getattr(agent, 'language', 'fr-FR')
        gender = getattr(agent, 'voice_gender', 'male')
        
        audio_data = await generate_greeting_audio(
            agent.greeting,
            language=language,
            gender=gender,
            force_regenerate=True
        )
        
        return audio_data is not None
        
    except Exception as e:
        logger.error(f"[TTS] Pre-generation failed: {e}")
        return False


# Singleton service instance
class GreetingTTSService:
    """Service for managing TTS greetings"""
    
    def __init__(self):
        self._generation_lock = asyncio.Lock()
    
    async def get_greeting_audio(
        self,
        greeting_text: str,
        language: str = "fr-FR",
        gender: str = "male"
    ) -> Optional[bytes]:
        """Get greeting audio, generating if needed"""
        # Check cache first
        cached = get_cached_greeting(greeting_text, language, gender)
        if cached:
            return cached
        
        # Generate with lock to prevent duplicate generation
        async with self._generation_lock:
            # Check cache again (may have been generated while waiting)
            cached = get_cached_greeting(greeting_text, language, gender)
            if cached:
                return cached
            
            return await generate_greeting_audio(greeting_text, language, gender)
    
    def is_available(self) -> bool:
        """Check if TTS is available"""
        return EDGE_TTS_AVAILABLE


# Global instance
_greeting_service: Optional[GreetingTTSService] = None


def get_greeting_tts_service() -> GreetingTTSService:
    """Get the singleton greeting TTS service"""
    global _greeting_service
    if _greeting_service is None:
        _greeting_service = GreetingTTSService()
    return _greeting_service

