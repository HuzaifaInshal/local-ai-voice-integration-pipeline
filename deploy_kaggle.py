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
    # Replace with your ngrok token from https://dashboard.ngrok.com
    TOKEN = os.getenv("NGROK_AUTHTOKEN", "YOUR_NGROK_AUTHTOKEN_HERE")
    if TOKEN == "YOUR_NGROK_AUTHTOKEN_HERE":
        print("⚠️ Warning: Please set your NGROK_AUTHTOKEN in environment or pass it to launch_on_kaggle()")
    else:
        launch_on_kaggle(TOKEN)
