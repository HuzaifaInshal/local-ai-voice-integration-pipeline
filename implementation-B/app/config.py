import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Alfa AI Voice Assistant"
    app_env: str = "development"
    debug: bool = True
    database_url: str = "sqlite:///./data/banking.db"
    whisper_model: str = "tiny.en"
    llm_provider: str = "auto"
    llm_model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"
    ws_path: str = "/ws/alfa"
    wake_word: str = "hey alfa"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
