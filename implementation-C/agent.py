"""
agent.py
The ReAct loop, talking to the local vLLM OpenAI-compatible server.
Uses NATIVE tool calling (not text-parsed Thought/Action/Observation)
so the model cannot free-text a fake observation.

Two entry points:
  - run_agent()         non-streaming, returns (final_text, trace) -- simple, good for curl/testing
  - run_agent_stream()  async generator, yields events as they happen -- what the UI uses

Qwen3's "thinking mode" is explicitly disabled via chat_template_kwargs
below. This is a deliberate choice, not just cosmetic: thinking mode
generates a full internal monologue before the answer, which (a) leaked
into the visible reply because nothing was splitting it out, and (b) was
the main reason replies felt slow -- you were waiting for 2x-3x the
tokens you actually wanted to see.
"""

from main import MODEL_NAME
import json
import os
from openai import OpenAI, AsyncOpenAI

from tools import TOOL_DISPATCH, TOOL_SCHEMAS

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
# MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
MAX_ITERATIONS = 6
MAX_HISTORY_MESSAGES = 6  # rolling window, excludes system prompt, 16 for Qwen3-32B-AWQ

SYSTEM_PROMPT = """You are Alfa, an AI banking data assistant with access to tools.

The database has two tables:
- clients: banking customer master (CRIMSID, T24 ID, customer name, PR category, business segment,
  branch code/name, SBP parent/child industry codes, client sales, client equity, opening date,
  legal entity type, PEP flag)
- orr_ratings: Obligor Risk Rating history (T24 ID, financial year, PR category, base rating,
  final rating, BU authorization date, CD authorization date)

Rules you must always follow:
1. You must NEVER invent, guess, or fabricate data that should come from a tool.
   If you need data, call the appropriate tool and wait for the real result.
2. Do not write your own "Observation" or pretend a tool already ran. Only real
   tool results (provided back to you after a tool call) count as data.
3. If a tool call fails or returns an error, say so plainly instead of making
   up a plausible-looking substitute answer.
4. If you are unsure of a table or column name, call get_schema first instead
   of guessing.
5. Format monetary values (client_sales, client_equity) in readable PKR format when presenting to users.
6. When responding to analytics, comparisons, distributions, or rankings of numeric data (e.g., top clients by sales, segment breakdowns, ORR history), call render_chart to render a visual chart alongside your written answer.
7. Once you have enough real tool output to answer, give a direct, concise final answer.
"""

# Disables Qwen3's <think>...</think> reasoning block if a Qwen3 model is specified.
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": True}} if "qwen3" in MODEL_NAME.lower() else None

client = OpenAI(base_url=VLLM_BASE_URL, api_key="EMPTY")
async_client = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="EMPTY")


class ConversationManager:
    """Per-session chat history, trimmed to a rolling window. System
    prompt is always preserved."""

    def __init__(self):
        self.sessions = {}

    def get(self, session_id: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return self.sessions[session_id]

    def append(self, session_id: str, message: dict):
        history = self.get(session_id)
        history.append(message)
        self._trim(session_id)

    def _trim(self, session_id: str):
        history = self.sessions[session_id]
        system = history[0]
        rest = history[1:]
        if len(rest) > MAX_HISTORY_MESSAGES:
            rest = rest[-MAX_HISTORY_MESSAGES:]
        self.sessions[session_id] = [system] + rest

    def reset(self, session_id: str):
        self.sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]


convo = ConversationManager()


def _run_tool(name: str, args: dict) -> str:
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool '{name}'"})
    try:
        return fn(**args)
    except Exception as e:
        return json.dumps({"error": f"Tool '{name}' raised: {e}"})


# ---------------------------------------------------------------------------
# Non-streaming version (simple, useful for testing without an SSE client)
# ---------------------------------------------------------------------------

def run_agent(session_id: str, user_message: str):
    convo.append(session_id, {"role": "user", "content": user_message})
    trace = []

    for _ in range(MAX_ITERATIONS):
        history = convo.get(session_id)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=history,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
            extra_body=EXTRA_BODY,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            convo.append(session_id, {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _run_tool(tc.function.name, args)
                trace.append({"tool": tc.function.name, "args": args, "result": result})
                convo.append(session_id, {"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        final_text = msg.content or ""
        convo.append(session_id, {"role": "assistant", "content": final_text})
        return final_text, trace

    return "Reached max tool-call iterations without a final answer.", trace


# ---------------------------------------------------------------------------
# Streaming version -- what the UI calls, via /api/chat/stream
# ---------------------------------------------------------------------------

async def run_agent_stream(session_id: str, user_message: str):
    """Async generator yielding dicts:
      {"type": "tool", "tool": ..., "args": ..., "result": ...}
      {"type": "token", "text": ...}
      {"type": "done"}
      {"type": "error", "message": ...}
    """
    convo.append(session_id, {"role": "user", "content": user_message})

    for _ in range(MAX_ITERATIONS):
        history = convo.get(session_id)

        try:
            stream = await async_client.chat.completions.create(
                model=MODEL_NAME,
                messages=history,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.2,
                extra_body=EXTRA_BODY,
                stream=True,
            )
        except Exception as e:
            yield {"type": "error", "message": f"Model request failed: {e}"}
            return

        content_buf = ""
        tool_calls_acc = {}  # index -> {"id":..., "name":..., "arguments":...}

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if getattr(delta, "content", None):
                content_buf += delta.content
                yield {"type": "token", "text": delta.content}

            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    slot = tool_calls_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc_delta.id:
                        slot["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            slot["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            slot["arguments"] += tc_delta.function.arguments

        if tool_calls_acc:
            ordered = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
            convo.append(session_id, {
                "role": "assistant",
                "content": content_buf,
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in ordered
                ],
            })
            for tc in ordered:
                try:
                    args = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _run_tool(tc["name"], args)
                yield {"type": "tool", "tool": tc["name"], "args": args, "result": result}
                convo.append(session_id, {"role": "tool", "tool_call_id": tc["id"], "content": result})
            continue  # loop again so the model sees the tool results

        # No tool calls in this turn -> it was the final answer
        convo.append(session_id, {"role": "assistant", "content": content_buf})
        yield {"type": "done"}
        return

    yield {"type": "error", "message": "Reached max tool-call iterations without a final answer."}
