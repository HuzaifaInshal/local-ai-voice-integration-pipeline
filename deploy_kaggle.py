"""
Kaggle Notebook One-Click Deployment Launcher
===================================================
Repository: local-ai-voice-integration-pipeline

This script handles full environment verification, automatic code sync from GitHub,
hardware acceleration checks, database seeding, ngrok tunneling, and FastAPI serving.
"""

import sys
import os
import time
import subprocess

def check_and_install_dependencies():
    """Verify required Python packages are installed, installing missing ones if needed."""
    required = [
        ("pyngrok", "pyngrok"),
        ("uvicorn", "uvicorn"),
        ("faster_whisper", "faster-whisper"),
        ("langchain", "langchain"),
        ("langchain_core", "langchain-core"),
        ("langchain_openai", "langchain-openai"),
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
            print(f"⚡ GPU Acceleration Active: {device_name}")
        else:
            print("⚠️ WARNING: CUDA GPU not detected. Running on CPU (Make sure Kaggle Accelerator is set to GPU T4).")
    except ImportError:
        print("ℹ️ PyTorch not installed. Proceeding with standard hardware detection.")

def sync_latest_github_code():
    """Auto-pull latest commits from main branch if inside a Git repository."""
    if os.path.exists(".git"):
        print("🔄 Checking for latest commits on GitHub (git pull origin main)...")
        try:
            res = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                print(f"✅ Git Sync: {res.stdout.strip()}")
            else:
                print(f"ℹ️ Git Sync notice: {res.stderr.strip()}")
        except Exception as e:
            print(f"⚠️ Skipping git pull: {e}")

def cleanup_stale_processes(port: int = 8000):
    """Kill any background uvicorn server running on the target port to avoid port conflict."""
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
    # 1. Try Kaggle Secrets
    try:
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        token = user_secrets.get_secret("NGROK_AUTH_TOKEN")
        if token:
            print("🔑 Loaded NGROK_AUTH_TOKEN from Kaggle User Secrets.")
            return token
    except Exception:
        pass

    # 2. Fallback to OS environment
    token = os.environ.get("NGROK_AUTH_TOKEN") or os.environ.get("NGROK_AUTHTOKEN")
    if token:
        print("🔑 Loaded NGROK_AUTH_TOKEN from Environment Variables.")
        return token

    return ""

def launch_deployment():
    """Main execution entrypoint with complete checks and balances."""
    print("\n" + "=" * 65)
    print("🚀 LOCAL AI VOICE INTEGRATION PIPELINE - KAGGLE DEPLOYMENT")
    print("=" * 65 + "\n")

    # Step 1: Run Dependency Check
    check_and_install_dependencies()

    # Step 2: Hardware Check
    check_hardware()

    # Step 3: Git Code Sync
    sync_latest_github_code()

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

    print("\n" + "🎉 " * 15)
    print(f"✨ APPLICATION LIVE AT : {public_url}")
    print(f"⚡ WEBSOCKET ENDPOINT  : {ws_url}")
    print("🎉 " * 15 + "\n")

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