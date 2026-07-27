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
from app.agent.graph import build_parakeet_agent
from app.services.stt_service import STTService
from app.utils.formatting import extract_json_payload

logger = setup_logger("parakeet.main")

db_registry: DatabaseRegistry = None
agent_executor = None
stt_service: STTService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_registry, agent_executor, stt_service
    logger.info("Initializing Parakeet AI Backend Services...")
    
    # 1. Startup DB Inspection & Cache
    db_url = settings.database_url
    db_registry = DatabaseRegistry(db_url)
    db_registry.initialize()
    set_global_db_registry(db_registry)
    
    # 2. Build ReAct State Machine Graph
    agent_executor = build_parakeet_agent(db_registry.schema_context)
    
    # 3. Load STT Engine Pipeline
    stt_service = STTService(model_size=settings.whisper_model)
    
    logger.info("Parakeet Backend is ready to accept WebSocket connections.")
    
    public_url = os.getenv("PUBLIC_URL", "http://localhost:8000")
    ws_url = os.getenv("PUBLIC_WS_URL", "ws://localhost:8000/ws/parakeet")

    print("\n" + "🎉 " * 15)
    print(f"✨ APPLICATION LIVE AT : {public_url}")
    print(f"⚡ WEBSOCKET ENDPOINT  : {ws_url}")
    print("🎉 " * 15 + "\n")
    yield
    logger.info("Shutting down Parakeet AI Backend Services.")

app = FastAPI(title="Parakeet AI Service", version="1.0.0", lifespan=lifespan)

# Allow CORS for UI client dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Parakeet AI Banking Voice Assistant",
        "tables_cataloged": len(db_registry.catalog) if db_registry else 0
    }

# Mount client directory static assets (/css, /js)
if os.path.exists("client"):
    if os.path.exists("client/css"):
        app.mount("/css", StaticFiles(directory="client/css"), name="css")
    if os.path.exists("client/js"):
        app.mount("/js", StaticFiles(directory="client/js"), name="js")

    @app.get("/")
    async def serve_index():
        return FileResponse("client/index.html")

@app.websocket(settings.ws_path)
async def persistent_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"Persistent WebSocket connection established on {settings.ws_path}.")
    
    try:
        while True:
            message = await websocket.receive()
            user_text = ""
            
            if "bytes" in message and message["bytes"]:
                logger.info("Received binary audio buffer over WebSocket channel.")
                user_text = stt_service.transcribe_audio_bytes(message["bytes"])
                await websocket.send_json({"type": "transcription", "text": user_text})
            elif "text" in message and message["text"]:
                user_text = message["text"]

            if not user_text.strip():
                continue

            await websocket.send_json({
                "type": "status",
                "state": "processing",
                "speak": "Sure, let me read the essentials from the database."
            })

            # Execute LangGraph ReAct Workflow
            try:
                initial_state = {"messages": [HumanMessage(content=user_text)]}
                result = agent_executor.invoke(initial_state)
                raw_response = result["messages"][-1].content
                clean_text, payload = extract_json_payload(raw_response)

                await websocket.send_json({
                    "type": "final_result",
                    "content": clean_text,
                    "payload": payload
                })
            except Exception as graph_err:
                logger.error(f"ReAct agent invocation error: {graph_err}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Agent execution error: {str(graph_err)}"
                })

    except WebSocketDisconnect:
        logger.info("Persistent WebSocket connection closed by client.")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "message": str(e)})
