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

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
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

7. Visualizations:
   - Call `render_chart` when the user explicitly requests a single chart, graph, plot, pie chart, donut chart, bar chart, line chart, or scatter plot.
   - Call `render_dashboard` when the user explicitly requests a dashboard, multi-chart response, portfolio summary, executive analytics report, risk distribution dashboard, or multi-angle visualizations.
   - For multi-chart dashboards, execute all required SQL queries first so all datasets are retrieved, then call `render_dashboard` specifying title, key metric KPI cards (2-4 cards with label, value, subtext, trend), and list of chart specs. Use `dataset_index` (0, 1, 2...) in chart specs if drawing from different query results in the conversation turn.

8. The outputs of sql_query, render_chart, and render_dashboard are automatically rendered by the frontend and are already visible to the user.
   - If sql_query returns a dataset (multiple rows), do not repeat, summarize, reformat, or list the returned records. Simply acknowledge that the requested data has been retrieved and displayed.
   - If render_chart or render_dashboard is used, acknowledge that the requested visualization/dashboard has been rendered.
   - Only summarize, analyze, compare, explain, or provide insights when the user explicitly asks for deep analytics or executive reasoning.

9. Before deciding how to respond, determine the user's intent:

    • Retrieval
      Examples: show, list, display, find, fetch
      → Execute sql_query and acknowledge that the requested data has been retrieved and displayed. Do not repeat the returned rows.

    • Aggregation
      Examples: count, total, average, minimum, maximum
      → Execute sql_query and return the resulting value(s).

    • Deep Analytics / Dashboard
      Examples: dashboard, portfolio analysis, risk breakdown, deep analytics, multi-chart, executive report
      → Execute targeted SQL queries, call render_dashboard with KPIs and chart specs, then provide structured executive commentary and risk observations.
"""

IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
DATA_IMAGE_RE = re.compile(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=\s]+")


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

# Enables Qwen3's native <think>...</think> deep reasoning if a Qwen3 model is specified.
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
        reset_artifacts(session_id)


convo = ConversationManager()


def _run_tool(name: str, args: dict, session_id: str) -> str:
    if name == "render_chart":
        return render_chart_result(session_id, args)
    if name == "render_dashboard":
        return json.dumps({
            "result": "Dashboard rendered.",
            "title": args.get("title", "Dashboard"),
            "kpis_count": len(args.get("kpis") or []),
            "charts_count": len(args.get("charts") or []),
        })

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
                result = _run_tool(tc.function.name, args, session_id)
                trace.append({"tool": tc.function.name, "args": args, "result": result})
                artifacts.extend(build_artifacts(tc.function.name, args, result, session_id))
                convo.append(session_id, {"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        final_text = msg.content or ""
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
      {"type": "dashboard", "title": ..., "kpis": [...], "charts": [...]}
      {"type": "diagram", "nodes": [...], "edges": [...]}
      {"type": "reasoning", "text": ...}
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
        in_think_block = False

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 1. Direct reasoning_content field (from vLLM reasoning parser)
            reasoning = getattr(delta, "reasoning_content", None)
            if not reasoning and hasattr(delta, "model_extra") and delta.model_extra:
                reasoning = delta.model_extra.get("reasoning_content")

            if reasoning:
                yield {"type": "reasoning", "text": reasoning}

            # 2. Inline <think>...</think> tags inside content buffer
            if getattr(delta, "content", None):
                text_piece = delta.content
                content_buf += text_piece

                if "<think>" in text_piece:
                    in_think_block = True
                    # Split around <think>
                    parts = text_piece.split("<think>", 1)
                    if parts[0]:
                        yield {"type": "token", "text": parts[0]}
                    if parts[1]:
                        yield {"type": "reasoning", "text": parts[1]}
                elif "</think>" in text_piece:
                    in_think_block = False
                    parts = text_piece.split("</think>", 1)
                    if parts[0]:
                        yield {"type": "reasoning", "text": parts[0]}
                    if parts[1]:
                        yield {"type": "token", "text": parts[1]}
                elif in_think_block:
                    yield {"type": "reasoning", "text": text_piece}
                else:
                    if not reasoning:  # avoid duplicating if reasoning was sent via reasoning_content
                        yield {"type": "token", "text": text_piece}

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
                result = _run_tool(tc["name"], args, session_id)
                yield {"type": "tool", "tool": tc["name"], "args": args, "result": result}
                for artifact in build_artifacts(tc["name"], args, result, session_id):
                    yield artifact
                convo.append(session_id, {"role": "tool", "tool_call_id": tc["id"], "content": result})
            continue  # loop again so the model sees the tool results

        # No tool calls in this turn -> it was the final answer
        convo.append(session_id, {"role": "assistant", "content": content_buf})
        yield {"type": "done"}
        return

    yield {"type": "error", "message": "Reached max tool-call iterations without a final answer."}
