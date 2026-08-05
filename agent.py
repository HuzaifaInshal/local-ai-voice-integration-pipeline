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

import json
import os
import re
from openai import OpenAI, AsyncOpenAI
from main import MODEL_NAME

from artifacts import build_artifacts, render_chart_result, reset_artifacts
from tools import TOOL_DISPATCH, TOOL_SCHEMAS

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"))
MAX_ITERATIONS = 6
MAX_HISTORY_MESSAGES = 16  # rolling window, excludes system prompt

SYSTEM_PROMPT = """
You are Alfa, an AI banking data assistant with access to tools.

The database contains two tables:

- clients: banking customer master (CRIMSID, T24 ID, customer name, PR category, business segment, branch code/name, SBP parent/child industry codes, client sales, client equity, opening date, legal entity type, PEP flag)

- orr_ratings: Obligor Risk Rating history (T24 ID, financial year, PR category, base rating, final rating, BU authorization date, CD authorization date)

Rules:

1. Never invent, guess, infer, or fabricate data that should come from a tool. If data is required, call the appropriate tool and wait for the real result.

2. Never pretend a tool has already been executed. Only actual tool outputs are considered valid data. If a tool fails or returns an error, clearly state the error instead of guessing.

3. If you are unsure about a table name, column name, or schema, call get_schema before generating a query.

4. Once you have sufficient real tool output to answer the user's request, provide the final response without making additional unnecessary tool calls.

5. Format monetary values (client_sales and client_equity) as readable PKR amounts whenever you present them to the user.

6. Do not create your own markdown tables, ASCII tables, HTML tables, Mermaid diagrams, SVG charts, images, or any self-rendered visualization. The frontend automatically renders outputs returned by tools.

7. Only call render_chart when the user explicitly requests a chart, graph, plot, visualization, pie chart, donut chart, bar chart, line chart, scatter plot, or asks to visualize previously retrieved data. When calling render_chart, only use columns that exist in the latest sql_query result. If the requested chart is ambiguous, ask for clarification.

8. The outputs of sql_query and render_chart are automatically rendered by the frontend and are already visible to the user.
   - If sql_query returns a dataset (multiple rows), do not repeat, summarize, reformat, or list the returned records. Simply acknowledge that the requested data has been retrieved and displayed.
   - If render_chart is used, acknowledge that the requested visualization has been rendered.
   - Only summarize, analyze, compare, explain, or provide insights when the user explicitly asks for them.
   - If a tool returns a single scalar value (such as COUNT, SUM, AVG, MIN, MAX) or a single record, you may include those values directly in your final response because they are concise answers rather than duplication of a dataset.

9. Before deciding how to respond, determine the user's intent:

    • Retrieval
      Examples: show, list, display, find, fetch
      → Execute sql_query and acknowledge that the requested data has been retrieved and displayed. Do not repeat the returned rows.

    • Aggregation
      Examples: count, total, average, minimum, maximum
      → Execute sql_query and return the resulting value(s).

    • Analysis
      Examples: summarize, explain, compare, identify trends, recommend, provide insights
      → Execute sql_query if needed, then analyze the real tool results. Do not fabricate observations.

    • Visualization
      Examples: chart, graph, plot, pie, donut, bar, line, scatter
      → Execute sql_query if needed, call render_chart, then acknowledge that the visualization has been rendered. Do not recreate or describe the chart unless the user explicitly asks for analysis.
"""

IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
DATA_IMAGE_RE = re.compile(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=\s]+")


# def _sanitize_fin_sanitize_final_textal_text(text: str) -> str:
#     """Keep final assistant text from duplicating UI-rendered artifacts."""
#     if not text:
#         return ""

#     cleaned = DATA_IMAGE_RE.sub("[chart rendered above]", text)
#     cleaned = IMAGE_MARKDOWN_RE.sub("[chart rendered above]", cleaned)

#     raw_lines = cleaned.splitlines()
#     table_like = [_looks_like_plain_table_line(line.strip()) for line in raw_lines]
#     lines = []
#     for index, line in enumerate(raw_lines):
#         stripped = line.strip()
#         if _looks_like_markdown_table_line(stripped):
#             continue
#         if table_like[index] and (
#             (index > 0 and table_like[index - 1]) or
#             (index + 1 < len(table_like) and table_like[index + 1])
#         ):
#             continue
#         lines.append(line)

#     final = "\n".join(lines).strip()
#     final = re.sub(
#         r"(?i)^here is (?:a|the) (bar|line|donut|pie|scatter|horizontal bar)? ?chart[^:\n]*:\s*",
#         "The requested chart has been rendered.",
#         final,
#     )
#     if final.startswith("The requested chart has been rendered."):
#         final = final.replace("[chart rendered above]", "")
#     return final.strip()


def _looks_like_markdown_table_line(line: str) -> bool:
    if not line:
        return False
    if line.startswith("|") and line.endswith("|") and line.count("|") >= 2:
        return True
    if line.count("|") >= 2 and re.fullmatch(r"[:\-\|\s]+", line):
        return True
    return False


def _looks_like_plain_table_line(line: str) -> bool:
    if not line:
        return False
    if "\t" in line and len([part for part in line.split("\t") if part.strip()]) >= 2:
        return True
    # Catches simple two-column aligned output like "Customer Name    Client Sales (PKR)".
    if re.search(r"\S\s{2,}\S", line) and not line.endswith((".", "!", "?")):
        return True
    return False

# Disables Qwen3's <think>...</think> reasoning block if a Qwen3 model is specified.
EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}} if "qwen3" in MODEL_NAME.lower() else None

client = OpenAI(base_url=LLM_BASE_URL, api_key="EMPTY")
async_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="EMPTY")


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
        reset_artifacts(session_id)


def extract_text_tool_calls(content: str):
    """Extract tool calls embedded as <tool_call>{...}</tool_call> in assistant text."""
    if not content or "<tool_call>" not in content:
        return []

    tool_calls = []
    matches = re.finditer(r"<tool_call>\s*({.*?})\s*</tool_call>", content, re.DOTALL)
    for idx, match in enumerate(matches):
        try:
            raw_json = match.group(1)
            data = json.loads(raw_json)
            name = data.get("name")
            args = data.get("arguments", {})
            if name:
                tool_calls.append({
                    "id": f"call_text_{idx}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                    },
                })
        except Exception as e:
            print(f"[agent] Error parsing text tool call: {e}")
    return tool_calls


convo = ConversationManager()


def _run_tool(name: str, args: dict, session_id: str) -> str:
    if name == "render_chart":
        return render_chart_result(session_id, args)

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
    artifacts = []

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

        tool_calls = []
        if msg.tool_calls:
            tool_calls = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        elif msg.content and "<tool_call>" in msg.content:
            tool_calls = extract_text_tool_calls(msg.content)

        if tool_calls:
            convo.append(session_id, {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                tc_id = tc["id"]
                tc_name = tc["function"]["name"]
                tc_args_raw = tc["function"]["arguments"]
                try:
                    args = json.loads(tc_args_raw) if isinstance(tc_args_raw, str) else tc_args_raw
                except json.JSONDecodeError:
                    args = {}
                result = _run_tool(tc_name, args, session_id)
                trace.append({"tool": tc_name, "args": args, "result": result})
                artifacts.extend(build_artifacts(tc_name, args, result, session_id))
                convo.append(session_id, {"role": "tool", "tool_call_id": tc_id, "content": result})
            continue

        final_text = re.sub(r"<think>.*?</think>", "", msg.content or "", flags=re.DOTALL).strip()
        convo.append(session_id, {"role": "assistant", "content": final_text})
        return final_text, trace, artifacts

    return "Reached max tool-call iterations without a final answer.", trace, artifacts


# ---------------------------------------------------------------------------
# Streaming version -- what the UI calls, via /api/chat/stream
# ---------------------------------------------------------------------------

async def run_agent_stream(session_id: str, user_message: str):
    """Async generator yielding dicts:
      {"type": "tool", "tool": ..., "args": ..., "result": ...}
      {"type": "table", "title": ..., "columns": [...], "rows": [...]}
      {"type": "chart", "chart_type": "bar|horizontal_bar|line|donut|pie|scatter", ...}
      {"type": "diagram", "nodes": [...], "edges": [...]}
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

        parsed_tool_calls = []
        if tool_calls_acc:
            ordered = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
            parsed_tool_calls = [
                {"id": tc["id"] or f"call_{i}", "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for i, tc in enumerate(ordered)
            ]
        elif "<tool_call>" in content_buf:
            parsed_tool_calls = extract_text_tool_calls(content_buf)

        if parsed_tool_calls:
            convo.append(session_id, {
                "role": "assistant",
                "content": content_buf,
                "tool_calls": parsed_tool_calls,
            })
            for tc in parsed_tool_calls:
                tc_id = tc["id"]
                func_name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                result = _run_tool(func_name, args, session_id)
                yield {"type": "tool", "tool": func_name, "args": args, "result": result}
                for artifact in build_artifacts(func_name, args, result, session_id):
                    yield artifact
                convo.append(session_id, {"role": "tool", "tool_call_id": tc_id, "content": result})
            continue  # loop again so the model sees the tool results

        # No tool calls in this turn -> it was the final answer
        final_content = re.sub(r"<think>.*?</think>", "", content_buf, flags=re.DOTALL).strip()
        convo.append(session_id, {"role": "assistant", "content": final_content})
        yield {"type": "done"}
        return

    yield {"type": "error", "message": "Reached max tool-call iterations without a final answer."}
