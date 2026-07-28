# 🎙️ AI Voice Studio

An enterprise-grade, privacy-first, on-premise local AI voice integration studio and pipeline. This repository houses specialized implementations for hands-free voice command processing, local Speech-to-Text (STT), ReAct reasoning over database systems, real-time WebAudio visualizers, and interactive dashboard output generation.

---

## 📁 Repository Implementations

```text
ai-voice-studio/
├── implementation-A/             # 🦜 Parakeet Voice Assistant (Complete Audio & Dashboard Stack)
│   ├── app/                      # FastAPI Backend & ReAct LangGraph Engine
│   ├── client/                   # Glassmorphic UI Dashboard & Music Visualizer
│   ├── data/                     # SQLite Database & Seeding Scripts
│   ├── deploy_kaggle.py          # Kaggle T4 GPU Deployment Launcher
│   └── README.md                 # Implementation-A Dedicated Guide
├── implementation-B/             # ⚡ Alfa Voice Assistant (Google Assistant UI & Token Streaming)
│   ├── app/                      # FastAPI Backend & First-Token Streaming Engine
│   ├── client/                   # Ultra-Minimal Google Assistant UI & 4-Bar Visualizer
│   ├── data/                     # SQLite Database & Seeding Scripts
│   ├── deploy_kaggle.py          # Kaggle T4 GPU Deployment Launcher
│   └── README.md                 # Implementation-B Dedicated Guide
└── README.md                     # Project Root Documentation
```

---

## 🚀 Available Implementations

### ⚡ Implementation B: Alfa AI Voice Assistant (Minimal Google Assistant UI & Token Streaming)

[👉 Read Full Implementation-B Documentation](./implementation-B/README.md)

An ultra-minimal Google Assistant style voice assistant with `"Hey Alfa"` wake-word activation, live real-time speech transcription display, 4-bar Google Assistant capsule audio visualizer, **first-token real-time streaming**, ReAct SQL tool execution, **zero speech synthesis / no talking back**, and dynamic Chart.js reporting.

#### Quick Run Command:
```bash
cd implementation-B
python3 -m venv .virtual-environment
source .virtual-environment/bin/activate
pip install -r requirements.txt
python3 data/seed_db.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### 🦜 Implementation A: Parakeet AI Voice Assistant

[👉 Read Full Implementation-A Documentation](./implementation-A/README.md)

An end-to-end hands-free banking voice assistant with `"Parakeet"` wake-word, GPU-accelerated ReAct reasoning (`Qwen2.5-1.5B`), STT (`faster-whisper`), 60fps glassmorphic audio visualizer, text-to-speech engine, and dynamic Chart.js visualizations.

---

## 🔒 Security & Privacy

All voice processing, Speech-to-Text transcription, and LLM analytical reasoning are designed to run **100% locally** or within private on-premise CUDA VRAM environments without transmitting sensitive data to third-party APIs.
