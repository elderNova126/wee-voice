"""
Fast TTS Greeting Service

Pre-generates greeting audio using edge-tts for IMMEDIATE playback.
Greetings are generated at server startup or when agents are updated.
During calls, only cached greetings are used (instant read, <50ms).

Uses miniaudio for pure-Python MP3 decoding (no ffmpeg required).
"""
import asyncio
import os
import hashlib
import logging
import tempfile
import audioop
from pathlib import Path
from typing import Optional, Dict
import struct

logger = logging.getLogger(__name__)

# Cache directory for pre-generated greetings - use persistent location
GREETING_CACHE_DIR = Path("/tmp/weedoo_greetings")
GREETING_CACHE_DIR.mkdir(exist_ok=True)

# Audio format: 8kHz mono PCM (for Asterisk)
TARGET_SAMPLE_RATE = 8000
FRAME_SIZE = 320  # 20ms at 8kHz

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
    print("[TTS] ✅ edge-tts available for fast greeting generation", flush=True)
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("[TTS] ⚠ edge-tts not available, will use Gemini for greetings", flush=True)

# Try miniaudio for pure-Python MP3 decoding (no ffmpeg required)
try:
    import miniaudio
    MINIAUDIO_AVAILABLE = True
    print("[TTS] ✅ miniaudio available for MP3 decoding (no ffmpeg needed)", flush=True)
except ImportError:
    MINIAUDIO_AVAILABLE = False
    print("[TTS] ⚠ miniaudio not available, trying pydub...", flush=True)

# Fallback to pydub if miniaudio not available
PYDUB_AVAILABLE = False
if not MINIAUDIO_AVAILABLE:
    try:
        from pydub import AudioSegment
        PYDUB_AVAILABLE = True
        print("[TTS] ✅ pydub available for audio conversion", flush=True)
    except ImportError:
        print("[TTS] ⚠ pydub not available", flush=True)


def get_greeting_cache_path(greeting_text: str, voice: str = "fr-FR-HenriNeural") -> Path:
    """Get cache file path for a greeting"""
    cache_key = hashlib.md5(f"{greeting_text}:{voice}".encode()).hexdigest()
    return GREETING_CACHE_DIR / f"greeting_{cache_key}.pcm"


def get_voice_for_language(language: str, gender: str = "male") -> str:
    """Get appropriate edge-tts voice for language"""
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
    
    return voice_map["fr"].get(gender, "fr-FR-HenriNeural")


def get_cached_greeting_sync(greeting_text: str, language: str = "fr-FR", gender: str = "male") -> Optional[bytes]:
    """
    Get cached greeting INSTANTLY (synchronous file read).
    Returns None if not cached - caller should NOT wait for generation.
    """
    if not greeting_text:
        return None
    
    voice = get_voice_for_language(language, gender)
    cache_path = get_greeting_cache_path(greeting_text, voice)
    
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                data = f.read()
            if len(data) > 0:
                return data
        except Exception:
            pass
    
    return None


async def generate_greeting_audio_background(
    greeting_text: str,
    language: str = "fr-FR",
    gender: str = "male"
) -> bool:
    """
    Generate greeting audio in background (for pre-warming cache).
    NOT to be called during active calls - only for pre-generation.
    """
    if not EDGE_TTS_AVAILABLE:
        return False
    
    if not greeting_text or not greeting_text.strip():
        return False
    
    voice = get_voice_for_language(language, gender)
    cache_path = get_greeting_cache_path(greeting_text, voice)
    
    # Skip if already cached
    if cache_path.exists() and cache_path.stat().st_size > 0:
        print(f"[TTS] Greeting already cached: {cache_path.name}", flush=True)
        return True
    
    try:
        import time
        start_time = time.perf_counter()
        print(f"[TTS] Generating greeting for: '{greeting_text[:50]}...'", flush=True)
        
        # Generate audio with edge-tts
        communicate = edge_tts.Communicate(greeting_text, voice)
        
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        
        if not audio_chunks:
            print("[TTS] ❌ No audio generated", flush=True)
            return False
        
        mp3_data = b''.join(audio_chunks)
        gen_time = (time.perf_counter() - start_time) * 1000
        print(f"[TTS] Generated MP3 in {gen_time:.0f}ms ({len(mp3_data)} bytes)", flush=True)
        
        # Convert MP3 to 8kHz PCM using ffmpeg
        pcm_data = await convert_mp3_to_pcm(mp3_data)
        
        if pcm_data:
            try:
                with open(cache_path, 'wb') as f:
                    f.write(pcm_data)
                total_time = (time.perf_counter() - start_time) * 1000
                print(f"[TTS] ✅ Greeting cached: {len(pcm_data)} bytes in {total_time:.0f}ms", flush=True)
                return True
            except Exception as e:
                print(f"[TTS] ❌ Cache write failed: {e}", flush=True)
        
        return False
        
    except Exception as e:
        print(f"[TTS] ❌ Generation failed: {e}", flush=True)
        return False


async def convert_mp3_to_pcm(mp3_data: bytes) -> Optional[bytes]:
    """
    Convert MP3 audio to 8kHz mono PCM.
    Uses miniaudio (pure Python, no ffmpeg required).
    Falls back to pydub if miniaudio not available.
    """
    if MINIAUDIO_AVAILABLE:
        return await _convert_with_miniaudio(mp3_data)
    elif PYDUB_AVAILABLE:
        return await _convert_with_pydub(mp3_data)
    else:
        print("[TTS] ❌ No MP3 decoder available (install miniaudio or pydub)", flush=True)
        return None


async def _convert_with_miniaudio(mp3_data: bytes) -> Optional[bytes]:
    """Convert MP3 to 8kHz PCM using miniaudio (pure Python, no ffmpeg)"""
    try:
        import numpy as np
        
        # Decode MP3 to raw PCM
        decoded = miniaudio.decode(mp3_data, output_format=miniaudio.SampleFormat.SIGNED16)
        
        # Get the raw samples
        samples = np.frombuffer(decoded.samples, dtype=np.int16)
        
        # Convert to mono if stereo
        if decoded.nchannels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1).astype(np.int16)
        
        # Resample to 8kHz if needed
        if decoded.sample_rate != TARGET_SAMPLE_RATE:
            # Use audioop for resampling
            pcm_bytes = samples.tobytes()
            resampled, _ = audioop.ratecv(
                pcm_bytes, 2, 1, 
                decoded.sample_rate, TARGET_SAMPLE_RATE, 
                None
            )
            return resampled
        
        return samples.tobytes()
        
    except Exception as e:
        print(f"[TTS] miniaudio conversion failed: {e}", flush=True)
        return None


async def _convert_with_pydub(mp3_data: bytes) -> Optional[bytes]:
    """Convert MP3 to 8kHz PCM using pydub (may require ffmpeg)"""
    try:
        import io
        from pydub import AudioSegment
        
        # Load MP3 from bytes
        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        
        # Convert to mono, 8kHz, 16-bit
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
        audio = audio.set_sample_width(2)  # 16-bit
        
        # Get raw PCM data
        return audio.raw_data
        
    except Exception as e:
        print(f"[TTS] pydub conversion failed: {e}", flush=True)
        return None


async def prewarm_all_agent_greetings():
    """
    Pre-generate greetings for ALL agents at server startup.
    This ensures instant greeting playback for all calls.
    """
    if not EDGE_TTS_AVAILABLE:
        print("[TTS] ⚠ edge-tts not available, skipping pre-warm", flush=True)
        return
    
    print("[TTS] 🔥 Pre-warming greeting cache for all agents...", flush=True)
    
    try:
        from app.models.database import SessionLocal
        from app.models import VoiceAgent
        
        db = SessionLocal()
        try:
            agents = db.query(VoiceAgent).filter(VoiceAgent.greeting.isnot(None)).all()
            
            if not agents:
                print("[TTS] No agents with greetings found", flush=True)
                return
            
            print(f"[TTS] Found {len(agents)} agents with greetings", flush=True)
            
            for agent in agents:
                if agent.greeting:
                    language = getattr(agent, 'language', 'fr-FR')
                    gender = getattr(agent, 'voice_gender', 'male')
                    
                    success = await generate_greeting_audio_background(
                        agent.greeting,
                        language=language,
                        gender=gender
                    )
                    
                    if success:
                        print(f"[TTS] ✅ Agent '{agent.name}' greeting ready", flush=True)
                    else:
                        print(f"[TTS] ⚠ Agent '{agent.name}' greeting failed", flush=True)
            
            print("[TTS] 🔥 Pre-warm complete!", flush=True)
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[TTS] ❌ Pre-warm error: {e}", flush=True)


class GreetingTTSService:
    """
    Service for managing TTS greetings.
    
    IMPORTANT: During calls, only returns cached greetings (instant).
    If not cached, returns None - caller should use Gemini fallback.
    Background generation is triggered for next call.
    """
    
    def __init__(self):
        self._pending_generation: Dict[str, asyncio.Task] = {}
    
    def get_cached_greeting(
        self,
        greeting_text: str,
        language: str = "fr-FR",
        gender: str = "male"
    ) -> Optional[bytes]:
        """
        Get cached greeting INSTANTLY.
        Returns None if not cached - does NOT generate on-the-fly.
        """
        return get_cached_greeting_sync(greeting_text, language, gender)
    
    def trigger_background_generation(
        self,
        greeting_text: str,
        language: str = "fr-FR", 
        gender: str = "male"
    ):
        """
        Trigger background generation for next call.
        Non-blocking - returns immediately.
        """
        if not EDGE_TTS_AVAILABLE or not greeting_text:
            return
        
        voice = get_voice_for_language(language, gender)
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
                await generate_greeting_audio_background(greeting_text, language, gender)
            except Exception as e:
                print(f"[TTS] Background generation error: {e}", flush=True)
            finally:
                self._pending_generation.pop(cache_key, None)
        
        self._pending_generation[cache_key] = asyncio.create_task(generate())
        print(f"[TTS] Triggered background generation for next call", flush=True)
    
    def is_available(self) -> bool:
        return EDGE_TTS_AVAILABLE


# Global instance
_greeting_service: Optional[GreetingTTSService] = None


def get_greeting_tts_service() -> GreetingTTSService:
    """Get the singleton greeting TTS service"""
    global _greeting_service
    if _greeting_service is None:
        _greeting_service = GreetingTTSService()
    return _greeting_service
