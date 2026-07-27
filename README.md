# Local AI Voice Integration Pipeline

An enterprise-grade, privacy-first, on-premise AI voice integration pipeline tailored for local database systems and analytical workflows. It listens locally for wake-words using client-side speech recognition / WebAssembly, streams audio commands over a persistent WebSocket connection, executes ReAct analytical reasoning loops over SQL databases, and returns structured JSON payloads to render interactive visual reports (charts, metrics, tables) on screen.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BROWSER / UI CLIENT                                                                    │
│                                                                                        │
│  1. App Launches ──────────► Opens Persistent WebSocket (`ws://localhost:8000/ws/parakeet`)│
│  2. Mic Active    ──────────► Background Wake-Word listener actively monitors mic      │
│  3. Wake-Word Detected ─────► Records VAD audio buffer & sends binary bytes over WS    │
└─────────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │ Binary Audio Buffer (over open WS)
┌─────────────────────────────────────────▼──────────────────────────────────────────────┐
│ FASTAPI BACKEND SERVICE                                                                │
│                                                                                        │
│  4. STT Engine      ──► `faster-whisper` transcribes audio buffer to text string       │
│  5. ReAct Agent     ──► LangGraph passes text + cached DB schema context to LLM        │
│  6. SQL Sub-Agent   ──► Executes generated SELECT query on DB (with read-only guardrails)│
│  7. Payload Builder ──► Encodes final answer + Chart/Table JSON format                 │
│  8. Response       ──► Pushes JSON payload back through the PERSISTENT WS channel      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```text
local-ai-voice-integration-pipeline/
├── app/
│   ├── main.py                     # FastAPI app entrypoint, lifespan manager, WS handler
│   ├── config.py                   # Pydantic BaseSettings config & env parser
│   ├── core/
│   │   └── logger.py               # Application stream logger
│   ├── services/
│   │   ├── stt_service.py          # Speech-to-Text transcriber with CUDA/CPU fallback
│   │   ├── db_registry.py          # DB schema introspection & sample record cache
│   │   └── llm_factory.py          # Multi-tier dynamic LLM client provider
│   ├── agent/
│   │   ├── state.py                # LangGraph state typed definition
│   │   ├── prompts.py              # System prompt builder & JSON output definitions
│   │   ├── graph.py                # ReAct state machine compile & workflow nodes
│   │   └── tools/
│   │       ├── sql_tool.py         # LangGraph tool for read-only database query execution
│   │       └── sanitize.py         # SQL query security validator & keyword sanitizer
│   └── utils/
│       ├── audio.py                # Audio stream buffer helper & format checker
│       └── formatting.py           # Structured chart/table/metric card payload builder
├── client/
│   ├── index.html                  # Glassmorphic web dashboard markup
│   ├── css/
│   │   └── style.css               # Dark mode theme & micro-animations
│   └── js/
│       ├── app.js                  # Main client controller & WS state management
│       ├── chart_renderer.js       # Dynamic UI chart & table renderer (Chart.js)
│       └── wakeword.js             # Wake-word listener module & VAD recorder
├── data/
│   ├── banking.db                  # Pre-seeded SQLite mock database
│   └── seed_db.py                  # Database generation & seeding script
├── deploy_kaggle.py                # Kaggle GPU notebook deployment launcher
├── tests/                          # Automated unit test suite
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚡ Getting Started

### 1. Installation & Environment Setup

```bash
# Clone repository
git clone https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git
cd local-ai-voice-integration-pipeline

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

### 2. Seed Mock Database

```bash
python3 data/seed_db.py
```

### 3. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access the UI Dashboard at `http://localhost:8000`.

---

## ☁️ Deploying on Kaggle Notebook (with ngrok)

For GPU acceleration and public hosting via ngrok tunnel:

1. Enable **GPU T4** and **Internet: ON** in Kaggle notebook settings.
2. Add your ngrok token to Kaggle **Add-ons ➔ Secrets** as `NGROK_AUTH_TOKEN`.
3. Run `deploy_kaggle.py` inside Kaggle cell:
   ```python
   !python3 deploy_kaggle.py
   ```

---

## 🔒 Security Guardrails

The system enforces strict read-only database interaction:
- Queries containing data-modifying keywords (`UPDATE`, `DELETE`, `DROP`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`) are rejected immediately by `app/agent/tools/sanitize.py`.
- SQL tools operate strictly through read-only parameterized sessions.
