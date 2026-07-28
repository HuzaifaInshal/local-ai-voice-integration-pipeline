"""
agent.py
The ReAct loop itself, talking to the local vLLM OpenAI-compatible
server. Uses NATIVE tool calling (not text-parsed Thought/Action/
Observation) specifically so the model cannot free-text a fake
observation the way it did with the prompted-ReAct Qwen2.5 setup.
"""

import json
import os
from openai import OpenAI

from tools import TOOL_DISPATCH, TOOL_SCHEMAS

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-32B-AWQ")
MAX_ITERATIONS = 6
MAX_HISTORY_MESSAGES = 16  # rolling window, excludes system prompt

SYSTEM_PROMPT = """You are an internal data assistant with access to tools.

Rules you must always follow:
1. You must NEVER invent, guess, or fabricate data that should come from a tool.
   If you need data, call the appropriate tool and wait for the real result.
2. Do not write your own "Observation" or pretend a tool already ran. Only real
   tool results (provided back to you after a tool call) count as data.
3. If a tool call fails or returns an error, say so plainly instead of making
   up a plausible-looking substitute answer.
4. If you are unsure of a table or column name, call get_schema first instead
   of guessing.
5. Once you have enough real tool output to answer, give a direct final answer
   with no further tool calls.
"""

client = OpenAI(base_url=VLLM_BASE_URL, api_key="EMPTY")


class ConversationManager:
    """Keeps per-session chat history, trimmed to a rolling window so the
    context doesn't grow unbounded across a long session. System prompt is
    always preserved."""

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


def run_agent(session_id: str, user_message: str):
    """Runs one full ReAct turn (possibly several tool calls) for a user
    message and returns (final_reply, trace) where trace is a list of
    {tool, args, result} dicts for the UI to display."""

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
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            # Persist the assistant's tool-call request in history
            convo.append(
                session_id,
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                },
            )

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                fn = TOOL_DISPATCH.get(name)
                if fn is None:
                    result = json.dumps({"error": f"Unknown tool '{name}'"})
                else:
                    try:
                        result = fn(**args)
                    except Exception as e:
                        result = json.dumps({"error": f"Tool '{name}' raised: {e}"})

                trace.append({"tool": name, "args": args, "result": result})

                # Real tool output goes back as its own "tool" role message --
                # this is the structural guardrail against fabricated observations.
                convo.append(
                    session_id,
                    {"role": "tool", "tool_call_id": tc.id, "content": result},
                )

            continue  # let the model see the tool results and decide next step

        # No tool call -> this is the final answer
        final_text = msg.content or ""
        convo.append(session_id, {"role": "assistant", "content": final_text})
        return final_text, trace

    return "Reached max tool-call iterations without a final answer.", trace
