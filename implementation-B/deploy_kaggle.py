"""
Kaggle Notebook One-Click Deployment Launcher for Implementation-B (Alfa AI)
=============================================================================
Repository: https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline

Run this single line in a Kaggle Notebook cell:
!rm -rf local-ai-voice-integration-pipeline && git clone https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git && python3 local-ai-voice-integration-pipeline/implementation-B/deploy_kaggle.py
"""

import sys
import os
import time
import subprocess

REPO_URL = "https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git"
REPO_DIR = "local-ai-voice-integration-pipeline"

def check_and_install_dependencies():
    required = [
        ("pyngrok", "pyngrok"),
        ("uvicorn", "uvicorn"),
        ("faster_whisper", "faster-whisper"),
        ("transformers", "transformers"),
        ("accelerate", "accelerate"),
        ("langchain", "langchain"),
        ("langchain_core", "langchain-core"),
        ("langgraph", "langgraph"),
        ("sqlalchemy", "sqlalchemy"),
        ("pydantic_settings", "pydantic-settings"),
        ("dotenv", "python-dotenv"),
    ]
    missing = []
    for mod_name, pkg_name in required:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg_name)
    
    if missing:
        print(f"📦 Installing missing packages: {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing)

def main():
    check_and_install_dependencies()
    from pyngrok import ngrok, conf

    current_dir = os.path.abspath(os.getcwd())
    if os.path.basename(current_dir) != "implementation-B":
        target_dir = os.path.join(current_dir, REPO_DIR, "implementation-B")
        if os.path.exists(target_dir):
            os.chdir(target_dir)

    print(f"📁 Current Working Directory: {os.getcwd()}")

    # Seed Database
    try:
        from data.seed_db import seed_database
        seed_database()
    except Exception as e:
        print(f"⚠️ Seed DB Warning: {e}")

    # Set up ngrok
    ngrok_token = os.environ.get("NGROK_AUTH_TOKEN")
    if not ngrok_token and os.path.exists("/kaggle/input"):
        try:
            from kaggle_secrets import UserSecretsClient
            user_secrets = UserSecretsClient()
            ngrok_token = user_secrets.get_secret("NGROK_AUTH_TOKEN")
        except Exception:
            pass

    if ngrok_token:
        print("🔑 Authenticating ngrok...")
        ngrok.set_auth_token(ngrok_token)

    public_tunnel = ngrok.connect(8000)
    public_url = public_tunnel.public_url
    ws_url = public_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws/alfa"

    os.environ["PUBLIC_URL"] = public_url
    os.environ["PUBLIC_WS_URL"] = ws_url

    print("\n" + "✨ " * 15)
    print(f"🚀 ALFA ASSISTANT (Implementation-B) LIVE AT : {public_url}")
    print(f"📡 WEBSOCKET ENDPOINT                      : {ws_url}")
    print("✨ " * 15 + "\n")

    subprocess.run([
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", "8000"
    ])

if __name__ == "__main__":
    main()
