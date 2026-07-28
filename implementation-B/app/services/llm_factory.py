import os
from typing import Any
from app.core.logger import setup_logger
from app.services.gpu_llm import PyTorchGPULLM

logger = setup_logger("alfa.llm_factory")

_cached_llm_instance = None

def get_llm() -> Any:
    global _cached_llm_instance
    if _cached_llm_instance is not None:
        return _cached_llm_instance

    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    
    if provider == "ollama":
        try:
            from langchain_community.chat_models import ChatOllama
            model_name = os.getenv("LLM_MODEL_NAME", "qwen2.5:1.5b")
            logger.info(f"Initializing ChatOllama with model '{model_name}'...")
            _cached_llm_instance = ChatOllama(model=model_name, temperature=0.2)
            return _cached_llm_instance
        except Exception as e:
            logger.warning(f"Failed to initialize ChatOllama: {e}. Falling back to PyTorch GPU LLM.")

    logger.info("Initializing native PyTorch GPU LLM instance...")
    _cached_llm_instance = PyTorchGPULLM()
    return _cached_llm_instance
