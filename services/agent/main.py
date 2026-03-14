"""Agent Service: AI agent with Bedrock Claude, streams events as NDJSON."""
from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import run_agent_stream

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

app = FastAPI(title="PlurAgent - Agent Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    messages: list[dict]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent"}


@app.post("/agent/chat")
async def chat(req: ChatRequest):
    """Run the agent loop and stream tool_call / tool_result / response events."""
    return StreamingResponse(
        run_agent_stream(req.messages),
        media_type="application/x-ndjson",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
