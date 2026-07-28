"""
server.py
FastAPI app exposing:
  POST /api/chat   {session_id, message} -> {reply, trace}
  POST /api/reset   {session_id}
  GET  /            -> the test UI
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import json
import os

from agent import run_agent, run_agent_stream, convo

app = FastAPI(title="ReAct POC")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ResetRequest(BaseModel):
    session_id: str


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Non-streaming endpoint -- simple to curl/test with."""
    reply, trace = run_agent(req.session_id, req.message)
    return {"reply": reply, "trace": trace}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming endpoint (SSE) -- what the UI uses for the fade-in effect."""
    async def event_gen():
        async for event in run_agent_stream(req.session_id, req.message):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/reset")
def reset(req: ResetRequest):
    convo.reset(req.session_id)
    return {"status": "ok"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
