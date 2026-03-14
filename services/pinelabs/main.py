"""Pine Labs Service: Exposes all Pine Labs API tools as REST endpoints."""
from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools import TOOL_REGISTRY, TOOL_DEFINITIONS

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

app = FastAPI(title="PlurAgent - Pine Labs Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ToolRequest(BaseModel):
    tool_name: str
    tool_input: dict = {}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pinelabs"}


@app.get("/tools/definitions")
async def get_definitions():
    """Return all tool schemas so the Agent service can register them with Claude."""
    return {"tools": TOOL_DEFINITIONS}


@app.post("/tools/execute")
async def execute_tool(req: ToolRequest):
    """Execute a named tool with the given input."""
    fn = TOOL_REGISTRY.get(req.tool_name)
    if not fn:
        return {"error": f"Unknown tool: {req.tool_name}"}
    try:
        result = await fn(**req.tool_input)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as e:
        logger.exception(f"Tool execution error: {req.tool_name}")
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
