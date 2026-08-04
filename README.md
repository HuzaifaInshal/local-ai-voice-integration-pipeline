# ReAct Agent POC — Kaggle 2x T4

Self-hosted ReAct loop with native tool calling, a SQL tool backed by a
real SQLite database, session history management, and a browser UI —
all reachable via ngrok while the Kaggle session is running.

## Files

- `db_setup.py` — builds `company.db` (customers/products/orders sample data)
- `tools.py` — the 6 tools + their OpenAI-format schemas (edit this to swap in your client's real 7 tools)
- `agent.py` — the ReAct loop itself (native tool calling, history window)
- `server.py` — FastAPI app: `/api/chat`, `/api/reset`, serves the UI
- `static/index.html` — chat UI with a collapsible tool-call trace per message
- `main.py` — orchestrator: starts vLLM, waits for health, opens ngrok, runs the app

## Kaggle setup

1. **Enable GPU**: Notebook settings → Accelerator → GPU T4 x2.
2. **Add your ngrok token**: Notebook editor → Add-ons → Secrets → add secret named `NGROK_TOKEN` with your ngrok authtoken.
3. **Upload these files** as a Kaggle dataset (or paste into `/kaggle/working/` via a cell) so they sit together in one working directory.
4. In a cell:
   ```
   !pip install -r requirements.txt
   ```
5. In the next cell:
   ```
   !python main.py
   ```
6. Wait for the log line `[main] Public URL: https://....ngrok-free.app` — open that in your browser.

Example - Run in kaggle cell:
!rm -rf local-ai-voice-integration-pipeline && \
git clone https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git && \
cd local-ai-voice-integration-pipeline && \
pip install -r requirements.txt && \
python main.py

## What to test first

- `what tables are available?` — should call `list_tables`, not guess.
- `what's the status of order 7?` — should call `lookup_order_status` or `sql_query`, and the final answer's order id/status should match the raw tool output shown in the trace panel.
- `total revenue from delivered orders` — needs `get_schema` + `sql_query` combined, a good multi-step test.
- Ask a question needing data, then immediately ask a _follow-up_ referencing "that" — tests whether history/context carries over correctly.

Click any "tool call: ..." row under a bot reply to see the exact raw
tool output the model received — this is your fastest way to tell
"model hallucinated" apart from "model answered correctly but you
doubted it."

## Fixed: OOM during guided-decoding warmup on T4

If you saw a `CUDA out of memory` error that hit right after "Capturing
CUDA graphs" and during a `warmup_kernels`/`grammar_output` step, that's
CUDA graph capture (~2.3 GiB/GPU) leaving almost no room for the tool-call
grammar warmup. `main.py` now passes `--enforce-eager` to skip graph
capture entirely, and `MAX_MODEL_LEN` defaults to 4096 for extra margin.
This trades a little decode latency for the memory back — fine for a POC.

## If Qwen3-32B-AWQ doesn't fit or errors out on your 2x T4

Turing GPUs (T4) don't support the fast `awq_marlin` kernel or
FlashAttention-2, which `main.py` already accounts for (`--quantization
awq`, `VLLM_ATTENTION_BACKEND=XFORMERS`). If you still hit an OOM or a
kernel-compatibility error, drop to a smaller model — no code changes
needed elsewhere:

```bash
MODEL_NAME=Qwen/Qwen3-14B-AWQ python main.py
```

or edit `MAX_MODEL_LEN` down (e.g. to 4096) if you need more KV-cache headroom.

## Why this shouldn't hallucinate the way your Qwen2.5 setup did

1. **Native tool calling**, not prompted Thought/Action/Observation text —
   the model literally cannot free-text a fake "Observation," because
   tool results only ever enter its context as a separate `role: "tool"`
   message that your code inserts after the real function runs.
2. The system prompt explicitly forbids fabricating data and instructs
   the model to call `get_schema` instead of guessing column names.
3. Every tool call and its raw result is visible in the UI trace panel,
   so you can immediately tell if a hallucination is a model problem
   or a prompt/tool-description problem.

## Known Kaggle limits to plan around

- ~30 GPU hrs/week quota, 9-hour max session — fine for demoing, not for an always-on service.
- Session state doesn't persist after the notebook stops — this is a POC environment, not a deployment target.
- If the client approves the POC, the next step is moving this same code (vLLM + FastAPI are portable) onto a small rented GPU box (e.g. RunPod/Vast.ai) or their own on-prem hardware for compliance.
