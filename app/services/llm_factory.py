import os
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings, HardwareTier
from app.core.logger import setup_logger

logger = setup_logger("parakeet.llm")

def get_llm(tier_override: str = None) -> BaseChatModel:
    """
    Instantiates an OpenAI-compatible client for local vLLM/Ollama engines.
    Dynamically scales model architecture based on hardware VRAM tier.
    """
    tier_str = tier_override or os.getenv("HARDWARE_TIER", settings.hardware_tier.value).upper()
    vllm_endpoint = os.getenv("VLLM_ENDPOINT", settings.vllm_endpoint)
    
    logger.info(f"Instantiating LLM client for tier: {tier_str} @ {vllm_endpoint}")

    if tier_str == HardwareTier.TIER_1.value:
        # 16GB VRAM (Tesla T4) - Qwen2.5-Coder-7B / Llama-3.1-8B
        return ChatOpenAI(
            base_url=vllm_endpoint,
            api_key="none-local",
            model="Qwen/Qwen2.5-Coder-7B-Instruct",
            temperature=0.0,
            max_tokens=1024,
            streaming=True
        )
    elif tier_str == HardwareTier.TIER_2.value:
        # 24GB-32GB VRAM - Qwen2.5-32B AWQ
        return ChatOpenAI(
            base_url=vllm_endpoint,
            api_key="none-local",
            model="Qwen/Qwen2.5-32B-Instruct-AWQ",
            temperature=0.0,
            max_tokens=2048,
            streaming=True
        )
    elif tier_str == HardwareTier.TIER_3.value:
        # 48GB-80GB VRAM - Llama-3.3-70B / Qwen2.5-72B
        return ChatOpenAI(
            base_url=vllm_endpoint,
            api_key="none-local",
            model="meta-llama/Llama-3.3-70B-Instruct",
            temperature=0.0,
            max_tokens=4096,
            streaming=True
        )
    else:
        raise ValueError(f"Unsupported HARDWARE_TIER: {tier_str}")
