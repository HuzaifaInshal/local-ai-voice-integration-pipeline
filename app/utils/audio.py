import io
import wave
from typing import Tuple

def validate_audio_buffer(audio_bytes: bytes) -> Tuple[bool, str]:
    """Validates raw audio binary buffer size and basic format."""
    if not audio_bytes or len(audio_bytes) < 100:
        return False, "Audio buffer empty or too small"
    return True, "Valid"

def is_wav_format(audio_bytes: bytes) -> bool:
    """Checks if binary payload has WAV header signature (RIFF...WAVE)."""
    return audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]
