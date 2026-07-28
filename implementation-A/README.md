# 🦜 Parakeet AI Voice Assistant (Implementation A)

An enterprise-grade, privacy-first, on-premise AI voice assistant tailored for local banking database systems and analytical workflows. It listens locally for wake-words ("Parakeet"), visualizes audio frequency flow with a dynamic 60fps equalizer canvas, streams audio commands over persistent WebSockets, executes ReAct analytical reasoning loops over local SQLite databases, and returns rich Markdown reports accompanied by interactive Chart.js visualizations and natural text-to-speech.

---

## ✨ Features

- **👂 Hands-Free Wake-Word & VAD**: Monitors background microphone input for the wake-word `"Parakeet"` and uses Voice Activity Detection (VAD) to record commands automatically.
- **🎵 Flowing Music Bars Audio Visualizer**: Real-time canvas spectrum equalizer reacting to live microphone input and speech synthesis states with dynamic glowing gradients.
- **⚡ Persistent WebSocket Channel**: Full-duplex persistent WebSocket connection (`/ws/parakeet`) for low-latency audio transmission and real-time streaming status updates.
- **🧠 ReAct Reasoning Engine**: Built on LangGraph state machines powered by local GPU models (`Qwen/Qwen2.5-1.5B-Instruct` or Ollama/PyTorch).
- **🔒 Read-Only SQL Security Guardrails**: Automatic query sanitization prohibiting any data-modifying statements (`UPDATE`, `DELETE`, `DROP`, `INSERT`).
- **📊 Executive Dashboard**: Rich Markdown rendering and automatic JSON payload extraction for metric cards, data tables, and Chart.js visualizations.
- **🔊 Natural Speech Synthesis**: Clean text-to-speech engine with non-blocking audio queueing.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BROWSER CLIENT (Glassmorphic Dashboard)                                                │
│                                                                                        │
│  1. Connection Launch  ──► Opens WebSocket (`ws://localhost:8000/ws/parakeet`)           │
│  2. Mic Active        ──► Continuous Analyser & 60fps Music Bars Visualizer            │
│  3. Wake-Word Heard   ──► Trigger VAD audio recorder -> send WAV bytes over WS        │
│  4. TTS Engine        ──► Queues and speaks final responses naturally                  │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │ Binary Audio Buffer / Text Query
┌─────────────────────────────────────────▼──────────────────────────────────────────────┐
│ FASTAPI BACKEND SERVICE                                                                │
│                                                                                        │
│  5. STT Engine        ──► `faster-whisper` transcribes audio buffer to text string       │
│  6. ReAct Agent       ──► LangGraph passes text + cached DB schema context to LLM        │
│  7. SQL Sub-Agent     ──► Executes generated SELECT query on DB (with read-only guard)   │
│  8. Payload Builder   ──► Formats Markdown answer + Chart/Table JSON payload            │
│  9. Response Stream   ──► Pushes status & final payload back over persistent WS        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```text
implementation-A/
├── app/
│   ├── main.py                     # FastAPI app entrypoint, lifespan manager & WS endpoint
│   ├── config.py                   # Pydantic BaseSettings config & env parser
│   ├── core/
│   │   └── logger.py               # Stream logger configuration
│   ├── services/
│   │   ├── stt_service.py          # Speech-to-Text engine (`faster-whisper`)
│   │   ├── db_registry.py          # DB schema introspection & sample record cache
│   │   ├── gpu_llm.py              # PyTorch GPU VRAM LLM model wrapper
│   │   └── llm_factory.py          # Dynamic LLM provider factory (GPU / Ollama / Mock)
│   ├── agent/
│   │   ├── state.py                # LangGraph state typed definition
│   │   ├── prompts.py              # System prompt builder & JSON schema specs
│   │   ├── graph.py                # ReAct state machine compile & workflow nodes
│   │   └── tools/
│   │       ├── sql_tool.py         # LangGraph tool for read-only SQL queries
│   │       └── sanitize.py         # SQL query security validator
│   └── utils/
│       ├── audio.py                # Audio stream buffer helpers
│       └── formatting.py           # Chart/Table/Metric card JSON payload builder
├── client/
│   ├── index.html                  # Dashboard HTML UI with marked.js & Chart.js
│   ├── css/
│   │   └── style.css               # Glassmorphic dark mode theme & card layouts
│   └── js/
│       ├── app.js                  # Client controller & WS state manager
│       ├── visualizer.js           # 60fps canvas audio music bars flow visualizer
│       ├── wakeword.js             # Wake-word detection & WebAudio VAD recorder
│       └── chart_renderer.js       # Dynamic UI chart & table renderer
├── data/
│   ├── banking.db                  # Pre-seeded SQLite database
│   └── seed_db.py                  # Database generation & seeding script
├── deploy_kaggle.py                # Kaggle T4 GPU deployment script with ngrok
├── tests/                          # Automated test suite
└── requirements.txt
```

---

## ⚡ Quick Start

### 1. Environment Setup

```bash
# Navigate to Implementation A directory
cd implementation-A

# Create virtual environment
python3 -m venv .virtual-environment
source .virtual-environment/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 2. Seed Mock Banking Database

```bash
python3 data/seed_db.py
```

### 3. Run Application Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your web browser.

---

## ☁️ Deploying on Kaggle GPU (with ngrok)

For GPU-accelerated inference (`Qwen2.5-1.5B-Instruct` loaded directly into CUDA VRAM):

1. Set Kaggle Accelerator to **GPU T4** and enable **Internet: ON**.
2. Add your ngrok token in Kaggle **Add-ons ➔ Secrets** as `NGROK_AUTH_TOKEN`.
3. Execute the launcher script inside Kaggle:
   ```python
   !python3 deploy_kaggle.py
   ```
