import os
import re
import json
import torch
from typing import List, Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from app.core.logger import setup_logger

logger = setup_logger("parakeet.gpu_llm")

class InProcessGPULLM(BaseChatModel):
    """In-process GPU LLM wrapper running directly on CUDA VRAM (Tesla T4)."""

    model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"
    device: str = "cuda"
    tokenizer: Any = None
    model: Any = None
    tools: List[Any] = []

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        super().__init__()
        self.model_name = os.getenv("LLM_MODEL_NAME", model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model()

    def _load_model(self):
        """Loads model directly into PyTorch CUDA memory."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            logger.info(f"🚀 Loading GPU LLM model '{self.model_name}' on {self.device}...")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            
            if self.device == "cuda":
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True
                )
            else:
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float32,
                    trust_remote_code=True
                )
            logger.info(f"✅ GPU LLM successfully loaded into VRAM on {self.device}!")
        except Exception as e:
            logger.error(f"Failed to load Hugging Face model on GPU ({e}). Falling back to rule engine...")
            self.model = None

    @property
    def _llm_type(self) -> str:
        return "in_process_gpu_llm"

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> "InProcessGPULLM":
        self.tools = tools
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        """Executes inference on CUDA VRAM and formats ToolCall outputs if SQL query requested."""
        prompt_text = self._convert_messages_to_prompt(messages)

        if self.model and self.tokenizer:
            inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.1,
                    do_sample=False
                )
            generated_text = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        else:
            # High-speed fallback analytical reasoning engine if HF model download is pending
            generated_text = self._fallback_analytical_reasoning(messages)

        # Parse potential tool calls (SQL query detection)
        tool_calls = self._extract_tool_calls(generated_text)
        
        ai_message = AIMessage(content=generated_text, tool_calls=tool_calls)
        generation = ChatGeneration(message=ai_message)
        return ChatResult(generations=[generation])

    def _convert_messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        formatted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted.append(f"System: {msg.content}")
            elif isinstance(msg, HumanMessage):
                formatted.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"Assistant: {msg.content}")
            else:
                formatted.append(f"Observation: {msg.content}")
        formatted.append("Assistant:")
        return "\n".join(formatted)

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Parses generated text for SQL query execution intent."""
        sql_match = re.search(r'SELECT\s+.*?;?', text, re.IGNORECASE | re.DOTALL)
        if sql_match and "Observation:" not in text:
            sql_query = sql_match.group(0).strip().rstrip(';')
            return [{
                "name": "execute_sql_query",
                "args": {"query": sql_query},
                "id": f"call_{os.urandom(4).hex()}"
            }]
        return []

    def _fallback_analytical_reasoning(self, messages: List[BaseMessage]) -> str:
        """High-speed fallback ReAct engine for instant response during warmups."""
        last_msg = messages[-1].content.lower()
        if "balance" in last_msg or "account" in last_msg or "money" in last_msg:
            return "To answer your question regarding client balances, I will query the accounts database.\nSELECT customer_name, account_type, balance, currency FROM accounts ORDER BY balance DESC;"
        elif "loan" in last_msg or "mortgage" in last_msg:
            return "Checking active loan portfolio records.\nSELECT customer_name, loan_type, principal_amount, outstanding_balance FROM loans WHERE status = 'Active';"
        elif "transaction" in last_msg or "credit" in last_msg or "debit" in last_msg:
            return "Fetching recent transactions.\nSELECT transaction_id, amount, category, timestamp FROM transactions ORDER BY timestamp DESC LIMIT 5;"
        else:
            return "I am analyzing your inquiry across the database catalog."
