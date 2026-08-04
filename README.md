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
- `main.py` — orchestrator: downloads GGUF model if needed, starts llama.cpp server (8k context window + q8_0 KV cache), waits for health, opens ngrok, runs the app

## Kaggle setup

1. **Enable GPU**: Notebook settings → Accelerator → GPU T4 x2.
2. **Add your ngrok token**: Notebook editor → Add-ons → Secrets → add secret named `NGROK_TOKEN` with your ngrok authtoken.
3. **Upload these files** as a Kaggle dataset (or paste into `/kaggle/working/` via a cell) so they sit together in one working directory.
4. In a cell (install with CUDA support enabled):
   ```bash
   !CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 pip install llama-cpp-python[server] --no-cache-dir
   !pip install -r requirements.txt
   ```
5. In the next cell:
   ```
   !python main.py
   ```
6. Wait for the log line `[main] Public URL: https://....ngrok-free.app` — open that in your browser.

## Performance & Architecture (llama.cpp Migration)

To resolve vLLM PCIe and CPU bottlenecks on Kaggle 2x T4 GPUs (5–9 tokens/sec):
- **Server Engine**: `llama.cpp` (`llama-cpp-python` / `llama-server`) with multi-GPU layer offloading (`-ngl 99`).
- **Context Window**: 8192 tokens (8k context).
- **KV Cache Quantization**: 8-bit (`q8_0`) KV cache (`--cache-type-k q8_0 --cache-type-v q8_0`).
- **Default GGUF Model**: `Qwen/Qwen3-14B` (`bartowski/Qwen_Qwen3-14B-GGUF` file `Qwen_Qwen3-14B-Q4_K_M.gguf`), auto-downloaded on launch.

Custom model override via environment variables:
```bash
MODEL_REPO="bartowski/Qwen_Qwen3-14B-GGUF" MODEL_FILE="Qwen_Qwen3-14B-Q4_K_M.gguf" python main.py
```

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
