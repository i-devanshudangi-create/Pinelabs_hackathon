"""Tests for the Gateway Service (port 8000)."""
from __future__ import annotations

import asyncio
import json

import pytest
import httpx
import websockets

from tests.conftest import GATEWAY_URL


# ── Health ───────────────────────────────────────────────────────────


async def test_health_returns_200(gateway_client):
    resp = await gateway_client.get("/api/health")
    assert resp.status_code == 200


async def test_health_reports_all_services(gateway_client):
    resp = await gateway_client.get("/api/health")
    services = resp.json()["services"]
    assert "gateway" in services
    assert "agent" in services
    assert "pinelabs" in services


async def test_health_all_services_ok(gateway_client):
    resp = await gateway_client.get("/api/health")
    services = resp.json()["services"]
    for name, status in services.items():
        assert status == "ok", f"Service {name} is {status}"


# ── Activity Log ─────────────────────────────────────────────────────


async def test_activity_returns_list(gateway_client):
    resp = await gateway_client.get("/api/activity")
    assert resp.status_code == 200
    assert "activities" in resp.json()
    assert isinstance(resp.json()["activities"], list)


# ── Session Management ───────────────────────────────────────────────


async def test_clear_session(gateway_client, unique_session_id):
    resp = await gateway_client.delete(f"/api/session/{unique_session_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"


async def test_clear_nonexistent_session(gateway_client):
    resp = await gateway_client.delete("/api/session/does-not-exist-xyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"


# ── REST Chat ────────────────────────────────────────────────────────


@pytest.mark.slow
async def test_rest_chat_basic(gateway_client, unique_session_id):
    """POST /api/chat should return a structured response."""
    resp = await gateway_client.post(
        "/api/chat",
        json={"session_id": unique_session_id, "message": "Say hello in one word"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "tool_calls" in data
    assert data["session_id"] == unique_session_id
    assert len(data["response"]) > 0


async def test_rest_chat_missing_message_returns_422(gateway_client):
    resp = await gateway_client.post("/api/chat", json={"session_id": "test"})
    assert resp.status_code == 422


# ── WebSocket: Chat ──────────────────────────────────────────────────


async def test_websocket_chat_connects():
    """Should be able to connect to the chat WebSocket."""
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        # If we get here without exception, the connection succeeded
        pong = await ws.ping()
        await pong


@pytest.mark.slow
async def test_websocket_chat_send_and_receive():
    """Send a message over WebSocket and receive a response event."""
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        await ws.send(json.dumps({
            "message": "Just say OK, nothing else",
            "session_id": "ws-test-basic",
        }))
        events = []
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                event = json.loads(raw)
                events.append(event)
                if event["type"] == "response":
                    break
        except asyncio.TimeoutError:
            pass

    assert len(events) >= 1
    assert events[-1]["type"] == "response"
    assert "response" in events[-1]["data"]


# ── WebSocket: Dashboard ────────────────────────────────────────────


async def test_websocket_dashboard_connects():
    """Should be able to connect to the dashboard WebSocket."""
    async with websockets.connect("ws://localhost:8000/ws/dashboard") as ws:
        pong = await ws.ping()
        await pong


@pytest.mark.slow
async def test_dashboard_receives_tool_events():
    """Dashboard WebSocket should receive tool events when a chat triggers them."""
    dashboard_events = []

    async with websockets.connect("ws://localhost:8000/ws/dashboard") as dash_ws:
        async with websockets.connect("ws://localhost:8000/ws/chat") as chat_ws:
            await chat_ws.send(json.dumps({
                "message": "Authenticate with Pine Labs",
                "session_id": "ws-test-dashboard-events",
            }))

            try:
                while True:
                    raw = await asyncio.wait_for(dash_ws.recv(), timeout=30)
                    event = json.loads(raw)
                    dashboard_events.append(event)
                    # Wait for at least one tool_call + tool_result
                    tool_results = [e for e in dashboard_events if e.get("type") == "dashboard_event" and e.get("data", {}).get("event") == "tool_result"]
                    if tool_results:
                        break
            except asyncio.TimeoutError:
                pass

    assert len(dashboard_events) >= 1, "Dashboard should receive at least one event"
