import os
import torch
import threading
import json
import re
from typing import Any, List, Optional, Iterator, Dict
from pydantic import Field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, SystemMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from app.core.logger import setup_logger

logger = setup_logger("alfa.gpu_llm")

class PyTorchGPULLM(BaseChatModel):
    model_name: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    device: str = "cuda"
    tokenizer: Any = None
    model: Any = None
    tools: List[Any] = Field(default_factory=list)

    def __init__(self, model_name: str = "Qwen/Qwen2.5-Coder-7B-Instruct"):
        super().__init__()
        self.model_name = os.getenv("LLM_MODEL_NAME", model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model()



    def _load_model(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            logger.info(f"Loading GPU LLM model '{self.model_name}' on {self.device}...")
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
            logger.info(f"GPU LLM loaded into VRAM on {self.device}!")
        except Exception as e:
            logger.error(f"Failed to load PyTorch GPU LLM: {e}")
            self.model = None

    @property
    def _llm_type(self) -> str:
        return "pytorch_gpu_llm"

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> Any:
        self.tools = tools
        return self

    def _format_messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        formatted = []
        for m in messages:
            if isinstance(m, SystemMessage):
                formatted.append({"role": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                formatted.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                formatted.append({"role": "assistant", "content": m.content})
        
        if self.tokenizer and hasattr(self.tokenizer, "apply_chat_template"):
            try:
                return self.tokenizer.apply_chat_template(formatted, tokenize=False, add_generation_prompt=True)
            except Exception:
                pass

        prompt_str = ""
        for item in formatted:
            prompt_str += f"<|im_start|>{item['role']}\n{item['content']}<|im_end|>\n"
        prompt_str += "<|im_start|>assistant\n"
        return prompt_str

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        full_text = ""
        for chunk in self._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            full_text += chunk.text
        
        message = self._parse_response_message(full_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> Iterator[ChatGenerationChunk]:
        if not self.model or not self.tokenizer:
            fallback_text = "I am Alfa Assistant. (Local GPU LLM loading or unavailable)"
            for char in fallback_text:
                chunk = ChatGenerationChunk(message=AIMessageChunk(content=char))
                if run_manager:
                    run_manager.on_llm_new_token(char)
                yield chunk
            return

        try:
            from transformers import TextIteratorStreamer
            prompt = self._format_messages_to_prompt(messages)
            inputs = self.tokenizer([prompt], return_tensors="pt").to(self.device)

            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            generation_kwargs = dict(
                inputs,
                streamer=streamer,
                max_new_tokens=512,
                temperature=0.2,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )

            thread = threading.Thread(target=self.model.generate, kwargs=generation_kwargs)
            thread.start()

            for new_text in streamer:
                if new_text:
                    chunk = ChatGenerationChunk(message=AIMessageChunk(content=new_text))
                    if run_manager:
                        run_manager.on_llm_new_token(new_text)
                    yield chunk

            thread.join()
        except Exception as e:
            logger.error(f"GPU LLM stream error: {e}")
            err_msg = f"\nExecution error: {str(e)}"
            yield ChatGenerationChunk(message=AIMessageChunk(content=err_msg))

    def _parse_response_message(self, text: str) -> AIMessage:
        if not text:
            return AIMessage(content="")

        # 1. Check for explicit JSON tool call blocks
        if "execute_sql_query" in text or "```json" in text:
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if not json_match:
                json_match = re.search(r"(\{[\s\S]*?\"execute_sql_query\"[\s\S]*?\})", text, re.DOTALL)
            
            if json_match:
                try:
                    payload = json.loads(json_match.group(1))
                    query = None
                    if "args" in payload and isinstance(payload["args"], dict):
                        query = payload["args"].get("query")
                    elif "query" in payload:
                        query = payload.get("query")

                    if query:
                        logger.info(f"🎯 Recognized JSON Tool Call: execute_sql_query -> {query}")
                        return AIMessage(
                            content="",
                            tool_calls=[{
                                "name": "execute_sql_query",
                                "args": {"query": query},
                                "id": "call_sql_001"
                            }]
                        )
                except Exception as e:
                    logger.warning(f"Failed to parse tool call JSON: {e}")

        # 2. Robust Auto-Detection: Catch ```sql ... ``` or raw SELECT query even if semicolon is missing
        sql_codeblock = re.search(r"```sql\s*(SELECT[\s\S]+?)\s*```", text, re.IGNORECASE)
        sql_query = None
        if sql_codeblock:
            sql_query = sql_codeblock.group(1).strip()
        else:
            sql_match = re.search(r"\b(SELECT\s+[\s\S]+?)(?:;|\n\n|```|$)", text, re.IGNORECASE)
            if sql_match and len(sql_match.group(1).strip()) > 10:
                sql_query = sql_match.group(1).strip()

        if sql_query:
            if not sql_query.endswith(";"):
                sql_query += ";"
            logger.info(f"🎯 Auto-detected SQL query in response: '{sql_query}' -> converting to execute_sql_query tool call")
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "execute_sql_query",
                    "args": {"query": sql_query},
                    "id": "call_sql_001"
                }]
            )

        return AIMessage(content=text)

