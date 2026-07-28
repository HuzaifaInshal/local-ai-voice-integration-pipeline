"""
Kaggle Notebook One-Click Deployment Launcher
===================================================
Repository: https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline

Run this single line in a Kaggle Notebook cell:
!rm -rf local-ai-voice-integration-pipeline && git clone https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git && python3 local-ai-voice-integration-pipeline/implementation-A/deploy_kaggle.py
"""

import sys
import os
import time
import subprocess

REPO_URL = "https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git"
REPO_DIR = "local-ai-voice-integration-pipeline"

def check_and_install_dependencies():
    """Verify required Python packages are installed, installing missing ones if needed."""
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
        print(f"📦 Installing missing dependencies: {', '.join(missing)}...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + missing, check=True)
        print("✅ Dependencies installed successfully.")

def check_hardware():
    """Detect GPU / CUDA hardware availability."""
    print("🔍 Checking hardware environment...")
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"⚡ GPU Acceleration Active: {device_name} ({vram_gb:.1f} GB VRAM)")
        else:
            print("⚠️ WARNING: CUDA GPU not detected. Running on CPU (Make sure Kaggle Accelerator is set to GPU T4).")
    except ImportError:
        print("ℹ️ PyTorch not installed. Proceeding with standard hardware detection.")

def sync_latest_github_code():
    """Clones or pulls the latest repository code directly from GitHub into Kaggle."""
    if not os.path.exists(".git"):
        if os.path.exists(REPO_DIR):
            os.chdir(REPO_DIR)
        else:
            print(f"📥 Repository not found locally. Cloning {REPO_URL}...")
            subprocess.run(["git", "clone", REPO_URL], check=True)
            if os.path.exists(REPO_DIR):
                os.chdir(REPO_DIR)

    if os.path.exists(".git"):
        print("🔄 Pulling latest code from GitHub (git pull origin main)...")
        try:
            res = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                print(f"✅ Git Sync: {res.stdout.strip()}")
            else:
                print(f"ℹ️ Git Sync notice: {res.stderr.strip()}")
        except Exception as e:
            print(f"⚠️ Skipping git pull: {e}")

def cleanup_stale_processes(port: int = 8000):
    """Kill any background uvicorn server running on target port to avoid conflicts."""
    try:
        subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
        time.sleep(1)
    except Exception:
        pass

def seed_database():
    """Ensure database exists and is seeded with sample records."""
    db_path = "./data/banking.db"
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        print("📦 Seeding mock database...")
        subprocess.run([sys.executable, "data/seed_db.py"], check=True)
    else:
        print("✅ Database verified.")

def get_ngrok_token() -> str:
    """Retrieves NGROK_AUTH_TOKEN from Kaggle User Secrets or environment variables."""
    token = None
    try:
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        token = user_secrets.get_secret("NGROK_AUTH_TOKEN")
        if token:
            print("🔑 Loaded NGROK_AUTH_TOKEN from Kaggle User Secrets.")
            return token
    except Exception:
        pass

    token = os.environ.get("NGROK_AUTH_TOKEN") or os.environ.get("NGROK_AUTHTOKEN")
    if token:
        print("🔑 Loaded NGROK_AUTH_TOKEN from Environment Variables.")
        return token

    return ""

def launch_deployment():
    """Main execution entrypoint with complete GPU checks and self-contained server launch."""
    print("\n" + "=" * 65)
    print("🚀 LOCAL AI VOICE INTEGRATION PIPELINE - KAGGLE GPU DEPLOYMENT")
    print("=" * 65 + "\n")

    # Step 1: Clone / Sync Repository Code from GitHub
    sync_latest_github_code()

    # Step 2: Run Dependency Check
    check_and_install_dependencies()

    # Step 3: Hardware Check
    check_hardware()

    # Step 4: Database Seeding Check
    seed_database()

    # Step 5: Clean stale ports
    cleanup_stale_processes(port=8000)

    # Step 6: Retrieve ngrok Auth Token
    token = get_ngrok_token()
    if not token:
        print("\n❌ DEPLOYMENT FAILED: NGROK_AUTH_TOKEN is missing!")
        print("👉 How to fix:")
        print("   1. Get your free token from https://dashboard.ngrok.com")
        print("   2. In Kaggle Notebook menu: Add-ons -> Secrets -> Add Secret")
        print("   3. Set Label: 'NGROK_AUTH_TOKEN' and Secret Value: '<your-token>'")
        print("   4. Re-run this cell.\n")
        sys.exit(1)

    # Step 7: Connect ngrok Tunnel
    from pyngrok import ngrok
    ngrok.set_auth_token(token)

    print("🌐 Establishing public ngrok tunnel on port 8000...")
    tunnel = ngrok.connect(8000)
    public_url = tunnel.public_url
    ws_url = public_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws/parakeet"

    os.environ["PUBLIC_URL"] = public_url
    os.environ["PUBLIC_WS_URL"] = ws_url

    # Step 8: Start FastAPI Uvicorn Server
    uvicorn_cmd = f"{sys.executable} -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    print(f"🚀 Starting server: {uvicorn_cmd}")
    
    process = subprocess.Popen(uvicorn_cmd, shell=True)
    
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\n⏹️ Stopping deployment server...")
        try:
            ngrok.disconnect(public_url)
        except Exception:
            pass
        process.terminate()
        print("👋 Server stopped.")

if __name__ == "__main__":
    launch_deployment()