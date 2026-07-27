import os
from langchain_core.language_models.chat_models import BaseChatModel
from app.services.gpu_llm import InProcessGPULLM
from app.core.logger import setup_logger

logger = setup_logger("parakeet.llm")

def get_llm(tier_override: str = None) -> BaseChatModel:
    """
    Instantiates an in-process PyTorch/CUDA GPU LLM client.
    Runs directly on CUDA VRAM (Tesla T4) without external HTTP dependencies.
    """
    logger.info("Initializing In-Process GPU LLM Engine on CUDA...")
    return InProcessGPULLM()
