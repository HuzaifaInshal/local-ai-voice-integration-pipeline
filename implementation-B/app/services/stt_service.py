import os
import io
import tempfile
from typing import Optional
from app.core.logger import setup_logger

logger = setup_logger("alfa.stt")

class STTService:
    def __init__(self, model_size: str = "tiny.en"):
        self.model_size = model_size
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            logger.info(f"Loading faster-whisper model '{self.model_size}' on {device} ({compute_type})...")
            self.model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
            logger.info("STT Engine loaded successfully.")
        except Exception as e:
            logger.warning(f"faster-whisper load warning (will fallback to mock STT if unavailable): {e}")

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        if not self.model:
            logger.warning("Whisper model not initialized. Returning empty transcript.")
            return ""

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            segments, _ = self.model.transcribe(tmp_path, beam_size=5)
            transcription = " ".join([segment.text for segment in segments]).strip()

            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            logger.info(f"STT Transcription: '{transcription}'")
            return transcription
        except Exception as e:
            logger.error(f"Error transcribing audio bytes: {e}")
            return ""
