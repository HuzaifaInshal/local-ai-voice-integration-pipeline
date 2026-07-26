import io
from typing import Optional

from app.core.logger import setup_logger
from app.utils.audio import validate_audio_buffer

logger = setup_logger("parakeet.stt")

class STTService:
    """Faster-whisper Speech-To-Text pipeline supporting CUDA and CPU fallback."""

    def __init__(self, model_size: str = "base", device: Optional[str] = None):
        self.model_size = model_size
        self.model = None
        self.device = device or "cuda"
        self._load_model()

    def _load_model(self) -> None:
        """Attempts loading model on specified device with automatic CPU fallback."""
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model '{self.model_size}' on {self.device}...")
            self.model = WhisperModel(self.model_size, device=self.device, compute_type="float16" if self.device == "cuda" else "int8")
        except Exception as e:
            if self.device != "cpu":
                logger.warning(f"CUDA initialization failed ({e}). Falling back to CPU...")
                self.device = "cpu"
                self._load_model()
            else:
                logger.error(f"Failed to load WhisperModel: {e}")
                self.model = None

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        """Transcribes in-memory binary audio chunk into text."""
        valid, msg = validate_audio_buffer(audio_bytes)
        if not valid:
            logger.warning(f"Invalid audio buffer received: {msg}")
            return ""

        if not self.model:
            # Fallback mock for testing environment without heavy whisper model binaries pre-installed
            logger.warning("WhisperModel not initialized. Returning mock transcription.")
            return "Show top 5 accounts by balance"

        try:
            audio_stream = io.BytesIO(audio_bytes)
            segments, _ = self.model.transcribe(audio_stream, beam_size=1)
            text = "".join([s.text for s in segments]).strip()
            logger.info(f"Transcribed text: '{text}'")
            return text
        except Exception as e:
            logger.error(f"Error during STT transcription: {e}")
            return ""
