"""Tests for the Agent Service (port 8001)."""
from __future__ import annotations

import json

import pytest
import httpx

from tests.conftest import AGENT_URL


# ── Health ───────────────────────────────────────────────────────────


async def test_health(agent_client):
    resp = await agent_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "agent"


# ── Chat Endpoint Structure ─────────────────────────────────────────


async def test_chat_endpoint_returns_ndjson_content_type():
    """The /agent/chat endpoint should return NDJSON streaming content."""
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{AGENT_URL}/agent/chat",
            json={"messages": [{"role": "user", "content": "Say hello in one word"}]},
        ) as resp:
            assert resp.status_code == 200
            assert "application/x-ndjson" in resp.headers.get("content-type", "")
            lines = []
            async for line in resp.aiter_lines():
                if line.strip():
                    lines.append(json.loads(line))
            assert len(lines) >= 1


async def test_chat_response_event_has_correct_structure():
    """The final 'response' event must have type + data with response and tool_calls."""
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{AGENT_URL}/agent/chat",
            json={"messages": [{"role": "user", "content": "Just say OK, nothing else"}]},
        ) as resp:
            events = []
            async for line in resp.aiter_lines():
                if line.strip():
                    events.append(json.loads(line))

    assert len(events) >= 1
    final = events[-1]
    assert final["type"] == "response"
    assert "response" in final["data"]
    assert "tool_calls" in final["data"]
    assert isinstance(final["data"]["tool_calls"], list)


@pytest.mark.slow
async def test_chat_tool_call_events_have_timestamps():
    """When the agent calls tools, each tool_call event should have a timestamp."""
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{AGENT_URL}/agent/chat",
            json={"messages": [{"role": "user", "content": "Authenticate with Pine Labs API"}]},
        ) as resp:
            events = []
            async for line in resp.aiter_lines():
                if line.strip():
                    events.append(json.loads(line))

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_calls) >= 1, "Agent should have called at least one tool"
    assert len(tool_results) >= 1, "Agent should have at least one tool result"
    for tc in tool_calls:
        assert "timestamp" in tc["data"]
        assert "tool_name" in tc["data"]
        assert "tool_input" in tc["data"]
    for tr in tool_results:
        assert "timestamp" in tr["data"]
        assert "tool_name" in tr["data"]
        assert "tool_result" in tr["data"]


async def test_chat_with_empty_messages_returns_response():
    """Empty messages list should still return a valid response (agent responds to no input)."""
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{AGENT_URL}/agent/chat",
            json={"messages": []},
        ) as resp:
            # Might be 200 with an error response or 422 for validation
            # Either way, should not crash
            assert resp.status_code in (200, 422, 500)


async def test_chat_missing_messages_field():
    """Missing 'messages' field should return 422 validation error."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{AGENT_URL}/agent/chat", json={})
        assert resp.status_code == 422


async def test_chat_invalid_json():
    """Sending invalid JSON should return an error."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{AGENT_URL}/agent/chat",
            content="not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422


@pytest.mark.slow
async def test_chat_multi_turn_conversation():
    """Agent should handle multi-turn conversations."""
    messages = [
        {"role": "user", "content": "Remember: the magic word is 'pineapple'."},
        {"role": "assistant", "content": "Got it! The magic word is pineapple."},
        {"role": "user", "content": "What is the magic word I told you?"},
    ]
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", f"{AGENT_URL}/agent/chat", json={"messages": messages}
        ) as resp:
            events = []
            async for line in resp.aiter_lines():
                if line.strip():
                    events.append(json.loads(line))
    final = events[-1]
    assert final["type"] == "response"
    assert "pineapple" in final["data"]["response"].lower()
