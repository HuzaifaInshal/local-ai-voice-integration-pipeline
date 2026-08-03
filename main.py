"""
main.py
Run this in a Kaggle notebook cell with:  !python main.py

What it does, in order:
  1. Builds the sample SQLite database.
  2. Launches vLLM's OpenAI-compatible server as a subprocess, tensor-
     parallel across both T4s, with native tool calling enabled.
  3. Waits for vLLM to report healthy.
  4. Opens an ngrok tunnel (token pulled from Kaggle Secrets) to the
     FastAPI app.
  5. Starts the FastAPI app (chat API + UI) in the foreground.

Before running:
  - Add your ngrok authtoken as a Kaggle Secret named NGROK_TOKEN
    (Add-ons -> Secrets in the Kaggle notebook editor).
  - Make sure the notebook has GPU: 2x T4 enabled.
  - pip install -r requirements.txt in an earlier cell.

If Qwen3-32B-AWQ fails to load or OOMs on your two T4s, drop
MODEL_NAME down to "Qwen/Qwen3-14B-AWQ" (or a smaller AWQ build) --
see the README for the fallback command.

Note on T4 memory: vLLM's CUDA graph capture step alone can eat over
2 GiB per GPU, which is exactly what caused an OOM during the guided-
decoding warmup step in earlier test runs (weights + activations +
graphs left ~19 MiB free, then a routine warmup allocation failed).
--enforce-eager below trades a bit of decode latency for that memory
back -- worth keeping for a POC on T4s regardless of model size.
"""

import os
import sys
import time
import subprocess
import requests

from db_setup import build_database

# ---------------------------------------------------------------
# POSSIBLE MODEL OPTIONS ON 2x TESLA T4 - KAGGLE NOTEBOOKS:

# 1. Qwen/Qwen2.5-7B-Instruct;
#       was good model as long as system prompt contains few things/rules
#       after visualization tool was implemented and sql tool modified
#       it started to hallucinate and ignore system prompt instructions
#       especially the case where it was creating sql table data and base64 visualizations in responses

# 2a. Qwen/Qwen2.5-14B-Instruct;
#       OOM error could not be supported on 2x Tesla t4

# 2b. Qwen/Qwen2.5-14B-Instruct-AWQ;
#       same issue as that of 7b one however it was also returning responses in thai language for some reason

# 3. Qwen/Qwen3-14B-AWQ (best option so far considering others);
#       perfect model in terms of responses, does not hallucinate and keep system instructions in check
#       however is slower than 2.5-7b

# 4. Qwen/Qwen3-32B-AWQ;
#       ofcourse high context window and more parameters support very well
#       however is extremely slow at 1 or 2 tokens/sec
# ---------------------------------------------------------------

MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-14B-AWQ")
VLLM_PORT = 8000
APP_PORT = 8080
# 3072 context length leaves optimal VRAM headroom for CUDA Graphs without OOM on 2x T4
MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "3072"))

VLLM_HEALTH_URL = f"http://localhost:{VLLM_PORT}/health"


def start_vllm():
    print(f"[main] Launching vLLM server for {MODEL_NAME} ...")
    env = os.environ.copy()
    # T4 = Turing architecture: force xFormers backend & silence unsupported FlashInfer sampler
    env["VLLM_ATTENTION_BACKEND"] = "XFORMERS"
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    env["VLLM_USE_V1"] = "0"
    # CPU & NCCL inter-GPU synchronization tuning to prevent CPU thread lockup
    env["OMP_NUM_THREADS"] = "4"
    env["NCCL_P2P_DISABLE"] = "1"
    env["PYTHONWARNINGS"] = "ignore"

    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", MODEL_NAME,
        "--tensor-parallel-size", "2",
        "--dtype", "float16",
        "--max-model-len", str(MAX_MODEL_LEN),
        "--gpu-memory-utilization", "0.88",
        "--max-num-batched-tokens", "2048",       # limits prefill peak memory
        "--max-num-seqs", "4",                    # low latency sequence concurrency
        "--enable-auto-tool-choice",
        "--tool-call-parser", "hermes",
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--trust-remote-code",
    ]

    # Conditionally add AWQ quantization flag if loading an AWQ model
    if "awq" in MODEL_NAME.lower():
        cmd.extend(["--quantization", "awq"])

    # Conditionally add Qwen3 reasoning parser if loading a Qwen3 reasoning model
    if "qwen3" in MODEL_NAME.lower():
        cmd.extend(["--reasoning-parser", "qwen3"])  # splits <think> content into reasoning_content

    print("[main] Command:", " ".join(cmd))
    proc = subprocess.Popen(cmd, env=env)
    return proc


def wait_for_vllm(timeout_s=1800):
    print("[main] Waiting for vLLM to become healthy (first load can take several minutes)...")
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = requests.get(VLLM_HEALTH_URL, timeout=3)
            if r.status_code == 200:
                print("[main] vLLM is healthy.")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
    return False


def start_ngrok():
    from pyngrok import ngrok, conf

    try:
        from kaggle_secrets import UserSecretsClient
        token = UserSecretsClient().get_secret("NGROK_TOKEN")
    except Exception:
        token = os.environ.get("NGROK_TOKEN")

    if not token:
        raise RuntimeError(
            "No ngrok token found. Add it as a Kaggle Secret named NGROK_TOKEN, "
            "or set the NGROK_TOKEN environment variable."
        )

    conf.get_default().auth_token = token
    tunnel = ngrok.connect(APP_PORT, "http")
    print(f"[main] Public URL: {tunnel.public_url}")
    return tunnel


def main():
    build_database()

    vllm_proc = start_vllm()
    try:
        if not wait_for_vllm():
            print("[main] vLLM did not become healthy in time. Check logs above.")
            vllm_proc.terminate()
            sys.exit(1)

        start_ngrok()

        # Run FastAPI app in the foreground so the process (and tunnel) stays alive.
        os.environ["VLLM_BASE_URL"] = f"http://localhost:{VLLM_PORT}/v1"
        os.environ["MODEL_NAME"] = MODEL_NAME

        import uvicorn
        uvicorn.run("server:app", host="0.0.0.0", port=APP_PORT, log_level="info")

    finally:
        vllm_proc.terminate()


if __name__ == "__main__":
    main()
