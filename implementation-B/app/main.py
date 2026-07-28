import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage

from app.config import settings
from app.core.logger import setup_logger
from app.services.db_registry import DatabaseRegistry
from app.agent.tools.sql_tool import set_global_db_registry
from app.agent.pipeline import AlfaPipeline
from app.services.stt_service import STTService
from app.utils.formatting import extract_json_payload

logger = setup_logger("alfa.main")

db_registry: DatabaseRegistry = None
alfa_pipeline: AlfaPipeline = None
stt_service: STTService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_registry, alfa_pipeline, stt_service
    logger.info("Initializing Alfa AI Voice Studio Services...")
    
    db_url = settings.database_url
    db_registry = DatabaseRegistry(db_url)
    db_registry.initialize()
    set_global_db_registry(db_registry)
    
    alfa_pipeline = AlfaPipeline(db_registry.schema_context)
    stt_service = STTService(model_size=settings.whisper_model)
    
    logger.info("Alfa Backend is ready to accept WebSocket connections.")
    
    public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
    ws_url = os.getenv("PUBLIC_WS_URL", "ws://localhost:8000/ws/alfa")

    print("\n" + "✨ " * 15)
    print(f"⚡ ALFA APPLICATION LIVE AT : {public_url}")
    print(f"📡 WEBSOCKET ENDPOINT       : {ws_url}")
    print("✨ " * 15 + "\n")
    yield
    logger.info("Shutting down Alfa AI Backend Services.")

app = FastAPI(title="Alfa AI Voice Assistant", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("client"):
    if os.path.exists("client/css"):
        app.mount("/css", StaticFiles(directory="client/css"), name="css")
    if os.path.exists("client/js"):
        app.mount("/js", StaticFiles(directory="client/js"), name="js")

    @app.get("/")
    async def serve_index():
        return FileResponse("client/index.html")

@app.websocket(settings.ws_path)
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"WebSocket connection established on {settings.ws_path}.")
    
    try:
        while True:
            message = await websocket.receive()
            user_text = ""
            
            if "bytes" in message and message["bytes"]:
                logger.info("Received binary audio buffer over WebSocket.")
                user_text = stt_service.transcribe_audio_bytes(message["bytes"])
                await websocket.send_json({"type": "transcription", "text": user_text})
            elif "text" in message and message["text"]:
                raw_text = message["text"]
                try:
                    parsed_json = json.loads(raw_text)
                    if isinstance(parsed_json, dict) and "text" in parsed_json:
                        user_text = parsed_json["text"]
                    else:
                        user_text = raw_text
                except Exception:
                    user_text = raw_text

            if not user_text.strip():
                continue

            await websocket.send_json({
                "type": "status",
                "state": "processing"
            })

            try:
                raw_response = ""
                direct_payload = None

                # Stream response via 2-Stage Ultra-Fast Pipeline
                async for event in alfa_pipeline.run_pipeline_stream(user_text):
                    event_type = event.get("type")
                    if event_type == "status":
                        await websocket.send_json(event)
                    elif event_type == "token":
                        await websocket.send_json(event)
                    elif event_type == "completed":
                        raw_response = event.get("raw_response", "")
                        direct_payload = event.get("payload", None)

                clean_text, parsed_payload = extract_json_payload(raw_response)
                payload = direct_payload if (direct_payload and len(direct_payload) > 0) else parsed_payload

                await websocket.send_json({
                    "type": "final_result",
                    "content": clean_text,
                    "payload": payload
                })




            except Exception as graph_err:
                logger.error(f"ReAct agent execution error: {graph_err}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Execution error: {str(graph_err)}"
                })

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by client.")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "message": str(e)})
