"""
Kaggle Notebook Deployment Script for Parakeet AI Voice Studio
===============================================================

Steps to deploy on Kaggle GPU Notebook:

1. Enable GPU in Kaggle Notebook settings (Accelerator: GPU T4 x2)
2. Enable Internet Access in Kaggle Notebook settings (Settings -> Internet: On)
3. Run the cells below to install dependencies, open an ngrok tunnel, and launch FastAPI.
"""

# Cell 1: Dependency Installation
"""
!pip install -q pyngrok uvicorn nest_asyncio faster-whisper langchain langchain-core langchain-openai langgraph sqlalchemy pydantic-settings python-dotenv
"""

# Cell 2: Kaggle Launcher Code
import os
import time
import subprocess
from pyngrok import ngrok

def launch_on_kaggle(ngrok_authtoken: str, port: int = 8000):
    """Launches Parakeet FastAPI backend with public ngrok tunnel inside Kaggle."""
    
    # 1. Set ngrok authtoken
    ngrok.set_auth_token(ngrok_authtoken)

    # 2. Seed Mock Banking Database
    print("📦 Seeding mock database...")
    subprocess.run(["python3", "data/seed_db.py"], check=True)

    # 3. Open Public Tunnel via ngrok
    print("🌐 Creating ngrok tunnel...")
    tunnel = ngrok.connect(port)
    public_url = tunnel.public_url
    ws_url = public_url.replace("http", "ws") + "/ws/parakeet"

    print("\n" + "=" * 60)
    print("🎉 PARAKEET AI VOICE STUDIO IS LIVE!")
    print(f"🔗 Public Dashboard URL : {public_url}")
    print(f"⚡ Public WebSocket URL : {ws_url}")
    print("=" * 60 + "\n")

    # 4. Launch FastAPI Uvicorn Server
    uvicorn_cmd = f"uvicorn app.main:app --host 0.0.0.0 --port {port}"
    print(f"🚀 Running command: {uvicorn_cmd}")
    
    process = subprocess.Popen(uvicorn_cmd, shell=True)
    
    try:
        process.wait()
    except KeyboardInterrupt:
        print("Stopping server...")
        ngrok.disconnect(public_url)
        process.terminate()

if __name__ == "__main__":
    NGROK_AUTH_TOKEN = None
    try:
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        NGROK_AUTH_TOKEN = user_secrets.get_secret("NGROK_AUTH_TOKEN")
        print("✅ Loaded NGROK_AUTH_TOKEN from Kaggle User Secrets.")
        launch_on_kaggle(NGROK_AUTH_TOKEN)
    except Exception as e:
        print("❌ Failed to load secret from Kaggle User Secrets. Checking environment variables...")
        NGROK_AUTH_TOKEN = os.environ.get("NGROK_AUTH_TOKEN")

    if not NGROK_AUTH_TOKEN:
        print("⚠️ WARNING: NGROK_AUTH_TOKEN is not set. Please add it to Add-ons -> Secrets.")