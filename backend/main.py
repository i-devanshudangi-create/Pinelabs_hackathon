"""FastAPI server: REST + WebSocket endpoints for PlurAgent."""
from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import FRONTEND_ORIGIN
from agent import run_agent

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# In-memory stores (sufficient for hackathon demo)
conversations: dict[str, list[dict]] = {}
activity_log: list[dict] = []
dashboard_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PlurAgent backend starting up")
    yield
    logger.info("PlurAgent backend shutting down")


app = FastAPI(title="PlurAgent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict]
    session_id: str


# ── REST endpoints ──────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "PlurAgent"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to the agent and get a response (REST fallback)."""
    if req.session_id not in conversations:
        conversations[req.session_id] = []

    conversations[req.session_id].append({"role": "user", "content": req.message})

    async def on_event(event_type, data):
        entry = {"event": event_type, **data}
        activity_log.append(entry)
        await _broadcast_dashboard(entry)

    result = await run_agent(conversations[req.session_id], on_event=on_event)

    conversations[req.session_id].append({"role": "assistant", "content": result["response"]})

    return ChatResponse(
        response=result["response"],
        tool_calls=result["tool_calls"],
        session_id=req.session_id,
    )


@app.get("/api/activity")
async def get_activity():
    """Get the agent activity log for the dashboard."""
    return {"activities": activity_log[-100:]}


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a conversation session."""
    conversations.pop(session_id, None)
    return {"status": "cleared"}


# ── WebSocket for chat ──────────────────────────────────────────────


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    session_id = "ws-default"
    logger.info("Chat WebSocket connected")

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg = data.get("message", "")
            session_id = data.get("session_id", session_id)

            if session_id not in conversations:
                conversations[session_id] = []

            conversations[session_id].append({"role": "user", "content": msg})

            async def on_event(event_type, event_data):
                entry = {"event": event_type, **event_data}
                activity_log.append(entry)
                await ws.send_text(json.dumps({"type": event_type, "data": event_data}))
                await _broadcast_dashboard(entry)

            result = await run_agent(conversations[session_id], on_event=on_event)

            conversations[session_id].append({"role": "assistant", "content": result["response"]})

            await ws.send_text(json.dumps({
                "type": "response",
                "data": {
                    "response": result["response"],
                    "tool_calls": result["tool_calls"],
                },
            }))

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.exception("Chat WebSocket error")
        try:
            await ws.send_text(json.dumps({"type": "error", "data": {"message": str(e)}}))
        except Exception:
            pass


# ── WebSocket for dashboard live updates ────────────────────────────


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    dashboard_connections.append(ws)
    logger.info(f"Dashboard WebSocket connected (total: {len(dashboard_connections)})")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        dashboard_connections.remove(ws)
        logger.info("Dashboard WebSocket disconnected")


async def _broadcast_dashboard(event: dict):
    """Send an event to all connected dashboard WebSocket clients."""
    dead = []
    for ws in dashboard_connections:
        try:
            await ws.send_text(json.dumps({"type": "dashboard_event", "data": event}))
        except Exception:
            dead.append(ws)
    for ws in dead:
        dashboard_connections.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
