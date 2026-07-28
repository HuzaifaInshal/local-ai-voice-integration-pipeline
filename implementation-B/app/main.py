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
from app.agent.graph import build_alfa_agent
from app.services.stt_service import STTService
from app.utils.formatting import extract_json_payload

logger = setup_logger("alfa.main")

db_registry: DatabaseRegistry = None
agent_executor = None
stt_service: STTService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_registry, agent_executor, stt_service
    logger.info("Initializing Alfa AI Voice Studio Services...")
    
    db_url = settings.database_url
    db_registry = DatabaseRegistry(db_url)
    db_registry.initialize()
    set_global_db_registry(db_registry)
    
    agent_executor = build_alfa_agent(db_registry.schema_context)
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
                user_text = message["text"]

            if not user_text.strip():
                continue

            await websocket.send_json({
                "type": "status",
                "state": "processing"
            })

            try:
                initial_state = {"messages": [HumanMessage(content=user_text)]}
                raw_response = ""

                # Real-time Event & Token Streaming starting from FIRST TOKEN
                async for event in agent_executor.astream_events(initial_state, version="v2"):
                    event_type = event.get("event")
                    
                    if event_type == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            content_str = chunk.content
                            # Skip raw tool JSON blocks during token stream
                            if "```json" not in content_str and "execute_sql_query" not in content_str:
                                raw_response += content_str
                                await websocket.send_json({
                                    "type": "token",
                                    "content": content_str
                                })
                    elif event_type == "on_tool_start":
                        tool_name = event.get("name", "tool")
                        await websocket.send_json({
                            "type": "status",
                            "state": "executing_tool",
                            "tool": tool_name,
                            "message": f"Querying banking database..."
                        })

                clean_text, payload = extract_json_payload(raw_response)

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
