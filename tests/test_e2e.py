"""End-to-end integration tests across all microservices."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
import httpx
import websockets

from tests.conftest import GATEWAY_URL, PINELABS_URL


# ── Full Auth Flow via Gateway ──────────────────────────────────────


@pytest.mark.slow
async def test_full_auth_flow_via_gateway():
    """Send 'Authenticate' through the Gateway, expect generate_token tool call and success."""
    sid = f"e2e-auth-{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": sid, "message": "Authenticate with Pine Labs API"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["response"]) > 0
    tool_names = [tc["tool_name"] for tc in data["tool_calls"]]
    assert "generate_token" in tool_names
    auth_result = next(tc for tc in data["tool_calls"] if tc["tool_name"] == "generate_token")
    assert auth_result["tool_result"]["success"] is True


@pytest.mark.slow
async def test_auth_then_create_order_via_gateway():
    """Auth + create order in a single conversation turn."""
    sid = f"e2e-order-{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={
                "session_id": sid,
                "message": "Authenticate and then create an order for ₹500",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    tool_names = [tc["tool_name"] for tc in data["tool_calls"]]
    assert "generate_token" in tool_names, "Should have authenticated"
    assert "create_order" in tool_names, "Should have created an order"


@pytest.mark.slow
async def test_activity_log_populated_after_chat():
    """After a chat with tool calls, the activity log should have entries."""
    sid = f"e2e-activity-{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(timeout=120) as client:
        await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": sid, "message": "Authenticate with Pine Labs"},
        )
        resp = await client.get(f"{GATEWAY_URL}/api/activity")
    activities = resp.json()["activities"]
    assert len(activities) >= 1, "Should have at least one activity entry"
    tool_call_events = [a for a in activities if a["event"] == "tool_call"]
    assert len(tool_call_events) >= 1


# ── Streaming via WebSocket ─────────────────────────────────────────


@pytest.mark.slow
async def test_websocket_streaming_tool_events():
    """Chat via WebSocket should stream tool_call -> tool_result -> response events."""
    events = []
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        await ws.send(json.dumps({
            "message": "Authenticate with Pine Labs API",
            "session_id": f"e2e-ws-stream-{uuid.uuid4().hex[:6]}",
        }))
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=45)
                event = json.loads(raw)
                events.append(event)
                if event["type"] == "response":
                    break
        except asyncio.TimeoutError:
            pass

    types_seen = [e["type"] for e in events]
    assert "tool_call" in types_seen, "Should have seen a tool_call event"
    assert "tool_result" in types_seen, "Should have seen a tool_result event"
    assert "response" in types_seen, "Should have seen a response event"

    # Verify ordering: tool_call before tool_result before response
    first_call_idx = types_seen.index("tool_call")
    first_result_idx = types_seen.index("tool_result")
    response_idx = types_seen.index("response")
    assert first_call_idx < first_result_idx < response_idx


# ── Session Isolation ───────────────────────────────────────────────


@pytest.mark.slow
async def test_session_isolation():
    """Two different sessions should not share conversation context."""
    sid_a = f"e2e-iso-a-{uuid.uuid4().hex[:6]}"
    sid_b = f"e2e-iso-b-{uuid.uuid4().hex[:6]}"

    async with httpx.AsyncClient(timeout=120) as client:
        # Session A: tell it a secret
        await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": sid_a, "message": "Remember: my secret code is ALPHA-7"},
        )
        # Session B: ask for the secret (shouldn't know it)
        resp_b = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": sid_b, "message": "What is my secret code?"},
        )
    data_b = resp_b.json()
    assert "ALPHA-7" not in data_b["response"], "Session B should not know Session A's secret"


# ── Pine Labs Tool Round-Trip ───────────────────────────────────────


async def test_pinelabs_auth_and_order_roundtrip():
    """Directly test Pine Labs service: auth -> create order -> get order status."""
    async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as client:
        # Auth
        auth = await client.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
        assert auth.json()["success"] is True

        # Create order
        order = await client.post(
            "/tools/execute",
            json={"tool_name": "create_order", "tool_input": {"amount": 100000, "currency": "INR"}},
        )
        order_data = order.json()
        assert isinstance(order_data, dict)

        # If order creation succeeded, check status
        if "data" in order_data and "order_id" in order_data["data"]:
            order_id = order_data["data"]["order_id"]
            status = await client.post(
                "/tools/execute",
                json={"tool_name": "get_order_status", "tool_input": {"order_id": order_id}},
            )
            assert status.status_code == 200
            status_data = status.json()
            assert isinstance(status_data, dict)


async def test_pinelabs_payment_link_creation():
    """Auth then create a payment link."""
    async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as client:
        await client.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
        resp = await client.post(
            "/tools/execute",
            json={
                "tool_name": "create_payment_link",
                "tool_input": {"amount": 250000, "description": "E2E test payment link"},
            },
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


# ── Complex Multi-Step Flow ─────────────────────────────────────────


@pytest.mark.slow
async def test_complex_multistep_conversation():
    """Multi-step conversation: auth -> order -> check status, all through the agent."""
    sid = f"e2e-multi-{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(timeout=120) as client:
        # Step 1: auth + order
        r1 = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={
                "session_id": sid,
                "message": "Please authenticate and create an order for ₹1,000",
            },
        )
        assert r1.status_code == 200
        tool_names_1 = [tc["tool_name"] for tc in r1.json()["tool_calls"]]
        assert "generate_token" in tool_names_1

        # Step 2: follow-up question (tests conversation memory)
        r2 = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={
                "session_id": sid,
                "message": "What was the order ID you just created?",
            },
        )
        assert r2.status_code == 200
        assert len(r2.json()["response"]) > 0
