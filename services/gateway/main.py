"""Gateway Service: HTTP + WebSocket entry point for the frontend."""
from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import AGENT_SERVICE_URL, PINELABS_SERVICE_URL, FRONTEND_ORIGIN

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

conversations: dict[str, list[dict]] = {}
activity_log: list[dict] = []
dashboard_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Gateway starting up")
    yield
    logger.info("Gateway shutting down")


app = FastAPI(title="PlurAgent - Gateway", version="1.0.0", lifespan=lifespan)

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
    """Health check with downstream service status."""
    statuses = {"gateway": "ok"}
    for name, url in [("agent", AGENT_SERVICE_URL), ("pinelabs", PINELABS_SERVICE_URL)]:
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{url}/health")
                statuses[name] = r.json().get("status", "unknown")
        except Exception:
            statuses[name] = "down"
    return {"status": "ok", "services": statuses}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """REST fallback: send a message, get the full response back."""
    if req.session_id not in conversations:
        conversations[req.session_id] = []
    conversations[req.session_id].append({"role": "user", "content": req.message})

    result = await _call_agent(conversations[req.session_id])

    conversations[req.session_id].append({"role": "assistant", "content": result["response"]})
    return ChatResponse(response=result["response"], tool_calls=result["tool_calls"], session_id=req.session_id)


@app.get("/api/activity")
async def get_activity():
    return {"activities": activity_log[-100:]}


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    conversations.pop(session_id, None)
    return {"status": "cleared"}


# ── WebSocket: Chat ─────────────────────────────────────────────────


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

            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                    async with client.stream(
                        "POST",
                        f"{AGENT_SERVICE_URL}/agent/chat",
                        json={"messages": conversations[session_id]},
                    ) as resp:
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            event = json.loads(line)

                            await ws.send_text(json.dumps(event))

                            if event["type"] in ("tool_call", "tool_result"):
                                entry = {"event": event["type"], **event["data"]}
                                activity_log.append(entry)
                                await _broadcast_dashboard(entry)

                            if event["type"] == "response":
                                conversations[session_id].append({
                                    "role": "assistant",
                                    "content": event["data"]["response"],
                                })

            except httpx.HTTPError as e:
                logger.exception("Agent service call failed")
                await ws.send_text(json.dumps({"type": "error", "data": {"message": f"Agent service error: {e}"}}))

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.exception("Chat WebSocket error")
        try:
            await ws.send_text(json.dumps({"type": "error", "data": {"message": str(e)}}))
        except Exception:
            pass


# ── WebSocket: Dashboard ────────────────────────────────────────────


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
    dead = []
    for ws in dashboard_connections:
        try:
            await ws.send_text(json.dumps({"type": "dashboard_event", "data": event}))
        except Exception:
            dead.append(ws)
    for ws in dead:
        dashboard_connections.remove(ws)


# ── Helpers ─────────────────────────────────────────────────────────


async def _call_agent(messages: list[dict]) -> dict:
    """Call agent service and collect the full response (for REST endpoint)."""
    result = {"response": "", "tool_calls": []}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        async with client.stream("POST", f"{AGENT_SERVICE_URL}/agent/chat", json={"messages": messages}) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event["type"] == "tool_call":
                    entry = {"event": "tool_call", **event["data"]}
                    activity_log.append(entry)
                    await _broadcast_dashboard(entry)
                elif event["type"] == "tool_result":
                    entry = {"event": "tool_result", **event["data"]}
                    activity_log.append(entry)
                    await _broadcast_dashboard(entry)
                elif event["type"] == "response":
                    result = event["data"]
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
