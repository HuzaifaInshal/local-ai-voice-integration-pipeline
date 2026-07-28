import os
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict

class HardwareTier(str, Enum):
    TIER_1 = "TIER_1"  # 16GB VRAM (Tesla T4)
    TIER_2 = "TIER_2"  # 24GB-32GB VRAM
    TIER_3 = "TIER_3"  # 48GB-80GB VRAM

class Settings(BaseSettings):
    hardware_tier: HardwareTier = HardwareTier.TIER_1
    vllm_endpoint: str = "http://localhost:8000/v1"
    database_url: str = "sqlite:///./data/banking.db"
    whisper_model: str = "base"
    log_level: str = "INFO"
    ws_path: str = "/ws/parakeet"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
