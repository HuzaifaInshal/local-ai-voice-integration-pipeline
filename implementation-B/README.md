# ⚡ Alfa AI Voice Assistant (Implementation B)

A minimal, high-speed, enterprise-grade AI voice assistant inspired by modern Google Assistant UI. It listens for the wake-word **"Hey Alfa"**, transcribes live speech to text directly below the listening indicator, animates a 4-bar Google Assistant capsule wave visualizer, streams responses **token-by-token from the very first token**, executes ReAct SQL reasoning over local databases, renders rich Markdown & Chart.js reports, and operates with **zero talking back (no speech synthesis)**.

---

## ✨ Features & Specification

- **👂 "Hey Alfa" Wake-Word**: Background wake-word monitoring for `"hey alfa"` / `"hey alpha"` with automatic VAD audio recording.
- **📱 Ultra-Minimal Google Assistant UI**: Clean white aesthetic matching Google Assistant layout, featuring a top brand logo, real-time live transcription display, 4-bar capsule audio animation, status pill badge, and minimal bottom navigation.
- **⚡ First-Token Real-Time Streaming**: Uses LangGraph `astream_events` to push LLM tokens (`{"type": "token"}`) over WebSockets starting from the **very first token**, creating a smooth fade-in typewriter animation.
- **🔇 Zero Talking Back**: No TTS/speech synthesis audio playback. Answers are presented purely visually to minimize hallucination risks and latency.
- **🧠 ReAct Reasoning & SQL Execution**: Complete ReAct workflow with read-only SQL tool execution (`execute_sql_query`) and security guardrails preventing data modification.
- **📊 Dynamic Visual Reports**: Supports Chart.js bar/line/pie charts, data tables, and metric cards formatted as JSON payloads.

---

## ⚡ Quick Start

```bash
# Navigate to Implementation B directory
cd implementation-B

# Create virtual environment
python3 -m venv .virtual-environment
source .virtual-environment/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed mock database
python3 data/seed_db.py

# Run application server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access the UI Dashboard at `http://localhost:8000`.

---

## ☁️ Kaggle Notebook One-Click Deployment

Run this single line inside a Kaggle Notebook cell (GPU T4 enabled):
```python
!rm -rf local-ai-voice-integration-pipeline && git clone https://github.com/HuzaifaInshal/local-ai-voice-integration-pipeline.git && python3 local-ai-voice-integration-pipeline/implementation-B/deploy_kaggle.py
```
