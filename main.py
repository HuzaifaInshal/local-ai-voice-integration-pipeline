"""
main.py
Run this in a Kaggle notebook cell with:  !python main.py

What it does, in order:
  1. Builds the sample SQLite database.
  2. Ensures the GGUF model file is present (downloading from HF if needed).
  3. Launches llama.cpp OpenAI-compatible server as a subprocess, offloading
     all layers across available GPUs, with an 8k context window and q8_0 KV cache.
  4. Waits for llama.cpp server to report healthy.
  5. Opens an ngrok tunnel (token pulled from Kaggle Secrets) to the FastAPI app.
  6. Starts the FastAPI app (chat API + UI) in the foreground.

Before running:
  - Add your ngrok authtoken as a Kaggle Secret named NGROK_TOKEN
    (Add-ons -> Secrets in the Kaggle notebook editor).
  - Make sure the notebook has GPU: 2x T4 enabled.
  - pip install -r requirements.txt in an earlier cell.
"""

import os
import sys
import time
import shutil
import subprocess
import requests

from db_setup import build_database

# ---------------------------------------------------------------
# MODEL CONFIGURATION FOR LLAMA.CPP ON 2x TESLA T4
# ---------------------------------------------------------------
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-14B")
MODEL_REPO = os.environ.get("MODEL_REPO", "bartowski/Qwen_Qwen3-14B-GGUF")
MODEL_FILE = os.environ.get("MODEL_FILE", "Qwen_Qwen3-14B-Q4_K_M.gguf")

LLM_PORT = 8000
APP_PORT = 8080
MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "8192"))  # 8k context window requested
KV_CACHE_DTYPE = os.environ.get("KV_CACHE_DTYPE", "8")      # q8_0 8-bit KV cache requested

LLM_HEALTH_URL = f"http://localhost:{LLM_PORT}/health"


def ensure_model_downloaded() -> str:
    local_path = os.environ.get("MODEL_PATH")
    if local_path and os.path.exists(local_path):
        print(f"[main] Using local GGUF model at: {local_path}")
        return local_path

    cwd_path = os.path.join(os.getcwd(), MODEL_FILE)
    if os.path.exists(cwd_path):
        print(f"[main] Found model file in working directory: {cwd_path}")
        return cwd_path

    print(f"[main] Downloading GGUF model '{MODEL_FILE}' from Hugging Face repo '{MODEL_REPO}'...")
    try:
        from huggingface_hub import hf_hub_download
        downloaded_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
        print(f"[main] Model downloaded to: {downloaded_path}")
        return downloaded_path
    except Exception as e:
        print(f"[main] Error downloading GGUF model: {e}")
        sys.exit(1)


def start_llama_server(model_path: str):
    print(f"[main] Launching llama.cpp server for {MODEL_NAME} ...")
    print(f"[main] Context size: {MAX_MODEL_LEN}, KV cache quantization: {KV_CACHE_DTYPE}")
    env = os.environ.copy()

    llama_server_bin = shutil.which("llama-server")
    if llama_server_bin:
        cmd = [
            llama_server_bin,
            "-m", model_path,
            # "-c", str(MAX_MODEL_LEN),
            # "--cache-type-k", KV_CACHE_DTYPE,
            # "--cache-type-v", KV_CACHE_DTYPE,
            "-ngl", "99",
            "--host", "0.0.0.0",
            "--port", str(LLM_PORT),
            "--alias", MODEL_NAME,
        ]
    else:
        cmd = [
            sys.executable, "-m", "llama_cpp.server",
            "--model", model_path,
            # "--n_ctx", str(MAX_MODEL_LEN),
            # "--type_k", KV_CACHE_DTYPE,
            # "--type_v", KV_CACHE_DTYPE,
            "--n_gpu_layers", "99",
            "--host", "0.0.0.0",
            "--port", str(LLM_PORT),
            "--model_alias", MODEL_NAME,
        ]

    print("[main] Command:", " ".join(cmd))
    proc = subprocess.Popen(cmd, env=env)
    return proc


def wait_for_llama_server(timeout_s=1800):
    print("[main] Waiting for llama.cpp server to become healthy (first load can take a couple of minutes)...")
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = requests.get(LLM_HEALTH_URL, timeout=3)
            if r.status_code == 200:
                print("[main] llama.cpp server is healthy.")
                return True
        except requests.exceptions.RequestException:
            pass
        try:
            r = requests.get(f"http://localhost:{LLM_PORT}/v1/models", timeout=3)
            if r.status_code == 200:
                print("[main] llama.cpp server is healthy.")
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

    model_path = ensure_model_downloaded()
    llama_proc = start_llama_server(model_path)
    try:
        if not wait_for_llama_server():
            print("[main] llama.cpp server did not become healthy in time. Check logs above.")
            llama_proc.terminate()
            sys.exit(1)

        start_ngrok()

        # Run FastAPI app in the foreground so the process (and tunnel) stays alive.
        os.environ["LLM_BASE_URL"] = f"http://localhost:{LLM_PORT}/v1"
        os.environ["VLLM_BASE_URL"] = f"http://localhost:{LLM_PORT}/v1"
        os.environ["MODEL_NAME"] = MODEL_NAME

        import uvicorn
        uvicorn.run("server:app", host="0.0.0.0", port=APP_PORT, log_level="info")

    finally:
        llama_proc.terminate()


if __name__ == "__main__":
    main()

