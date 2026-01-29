"""
Audio Processing Utilities for Asterisk AudioSocket

Provides audio normalization, resampling, and envelope functions.
Based on Asterisk-AI-Voice-Agent patterns.
"""
import audioop
import numpy as np
from typing import Optional, Tuple

try:
    import soxr
    SOXR_AVAILABLE = True
except ImportError:
    SOXR_AVAILABLE = False

# Audio Settings
INPUT_SAMPLE_RATE = 8000    # From Asterisk (PSTN native)
OUTPUT_SAMPLE_RATE = 24000  # Gemini output rate
GEMINI_INPUT_RATE = 16000   # Gemini expects 16kHz input
OPENAI_SAMPLE_RATE = 8000   # OpenAI uses 8kHz (G.711 μ-law native)

# Frame sizes (20ms frames)
INPUT_FRAME_SIZE = 320      # 20ms at 8kHz
OUTPUT_FRAME_SIZE = 960     # 20ms at 24kHz (Gemini)
OPENAI_FRAME_SIZE = 640     # 20ms at 16kHz

# Silence frames
SILENCE_8K = b'\x00' * INPUT_FRAME_SIZE
SILENCE_24K = b'\x00' * OUTPUT_FRAME_SIZE

# Audio quality settings
AUDIO_TARGET_RMS = 1400
AUDIO_MAX_GAIN_DB = 18.0
AUDIO_ATTACK_MS = 20


def normalize_audio(pcm_bytes: bytes, target_rms: int = AUDIO_TARGET_RMS, 
                    max_gain_db: float = AUDIO_MAX_GAIN_DB) -> bytes:
    """Apply RMS-based normalization to boost quiet audio."""
    import math
    import array
    
    if not pcm_bytes or len(pcm_bytes) < 4 or target_rms <= 0:
        return pcm_bytes
    
    try:
        buf = array.array('h')
        buf.frombytes(pcm_bytes)
        
        if len(buf) == 0:
            return pcm_bytes
        
        # Compute RMS
        acc = sum(float(s) * float(s) for s in buf)
        rms = math.sqrt(acc / len(buf)) if len(buf) > 0 else 0.0
        effective_rms = max(1.0, rms)
        
        # Compute gain
        desired = float(target_rms) / effective_rms
        max_lin = math.pow(10.0, float(max_gain_db) / 20.0)
        gain = min(desired, max_lin)
        
        if gain <= 1.01:
            return pcm_bytes
        
        # Apply gain with clipping
        for i, s in enumerate(buf):
            y = float(s) * gain
            buf[i] = int(max(-32768, min(32767, y)))
        
        return buf.tobytes()
    except Exception:
        return pcm_bytes


def apply_attack_envelope(pcm_bytes: bytes, sample_rate: int = 8000, 
                          attack_ms: int = AUDIO_ATTACK_MS,
                          state: Optional[dict] = None) -> Tuple[bytes, dict]:
    """Apply linear attack envelope to prevent pops at audio start."""
    import array
    
    if not pcm_bytes or sample_rate <= 0 or attack_ms <= 0:
        return pcm_bytes, state
    
    if state is None:
        state = {'bytes_remaining': int(sample_rate * (attack_ms / 1000.0) * 2)}
    
    try:
        total_attack_bytes = int(sample_rate * (attack_ms / 1000.0) * 2)
        remaining = state.get('bytes_remaining', total_attack_bytes)
        
        if remaining <= 0:
            return pcm_bytes, state
        
        buf = array.array('h')
        buf.frombytes(pcm_bytes)
        
        shape_samples = min(len(buf), remaining // 2)
        if shape_samples <= 0:
            return pcm_bytes, state
        
        for i in range(shape_samples):
            consumed_bytes = (total_attack_bytes - remaining) + (i * 2)
            alpha = max(0.0, min(1.0, consumed_bytes / float(max(1, total_attack_bytes))))
            buf[i] = int(round(buf[i] * alpha))
        
        state['bytes_remaining'] = max(0, remaining - shape_samples * 2)
        return buf.tobytes(), state
    except Exception:
        return pcm_bytes, state


class StreamingResampler:
    """Streaming resampler using soxr for high-quality continuous resampling."""
    
    def __init__(self, from_rate: int, to_rate: int, quality: str = 'VHQ'):
        self.from_rate = from_rate
        self.to_rate = to_rate
        self.resampler = None
        
        if SOXR_AVAILABLE:
            try:
                quality_map = {'VHQ': soxr.VHQ, 'HQ': soxr.HQ, 'MQ': soxr.MQ, 'LQ': soxr.LQ}
                self.resampler = soxr.ResampleStream(
                    from_rate, to_rate, num_channels=1,
                    dtype=np.float32, quality=quality_map.get(quality, soxr.VHQ)
                )
                # Prime with silence to eliminate initial latency
                prime_samples = int(from_rate * 0.05)
                _ = self.resampler.resample_chunk(np.zeros(prime_samples, dtype=np.float32))
            except Exception:
                self.resampler = None
        
        self.audioop_state = None
    
    def process(self, audio_bytes: bytes) -> bytes:
        """Process audio chunk with streaming resampler."""
        if len(audio_bytes) < 2:
            return audio_bytes
        
        if self.resampler is not None:
            try:
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_float = audio_np.astype(np.float32) / 32768.0
                resampled = self.resampler.resample_chunk(audio_float)
                return np.clip(resampled * 32768.0, -32768, 32767).astype(np.int16).tobytes()
            except Exception:
                pass
        
        # Fallback to audioop
        result, self.audioop_state = audioop.ratecv(
            audio_bytes, 2, 1, self.from_rate, self.to_rate, self.audioop_state
        )
        return result


def simple_resample(audio_bytes: bytes, from_rate: int, to_rate: int, state=None):
    """Simple wrapper for backward compatibility."""
    if from_rate == to_rate:
        return audio_bytes, state
    
    if state is None:
        state = {}
    
    key = f'{from_rate}_{to_rate}'
    if key not in state:
        state[key] = StreamingResampler(from_rate, to_rate)
    
    return state[key].process(audio_bytes), state
