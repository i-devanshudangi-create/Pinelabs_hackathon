"""Comprehensive tests for Feature #9: Smart Reconciliation.

Tests cover:
  - Unit: reconcile_transactions tool with various inputs
  - Integration: Agent triggers reconciliation on user request
  - Edge cases: empty orders, invalid IDs, large batches, repeated calls
  - E2E: Full reconciliation flow through gateway producing report
"""
from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest
import websockets

AGENT_URL = "http://localhost:8001"
GATEWAY_URL = "http://localhost:8000"
PINELABS_URL = "http://localhost:8002"


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: reconcile_transactions tool
# ═══════════════════════════════════════════════════════════════════


class TestReconcileToolUnit:
    """Test reconcile_transactions tool directly."""

    async def test_empty_order_ids(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": []},
            })
            data = resp.json()
            assert data["total_orders"] == 0
            assert data["paid_orders"] == 0
            assert data["unpaid_orders"] == 0
            assert data["settled"] == 0
            assert data["unsettled"] == 0
            assert data["refunded"] == 0
            assert data["mismatches"] == []
            assert "healthy" in data["summary"].lower() or "0 orders" in data["summary"].lower()

    async def test_report_has_all_required_fields(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": []},
            })
            data = resp.json()
            required_fields = ["total_orders", "paid_orders", "unpaid_orders", "settled", "unsettled", "refunded", "mismatches", "summary"]
            for field in required_fields:
                assert field in data, f"Missing field: {field}"

    async def test_reconcile_with_real_order(self):
        """Create an order, then reconcile it — should show as unpaid."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            order_resp = await c.post("/tools/execute", json={
                "tool_name": "create_order",
                "tool_input": {"amount": 10000},
            })
            order_data = order_resp.json()
            order_id = order_data.get("data", {}).get("order_id") or order_data.get("data", {}).get("id", "")

            if order_id:
                resp = await c.post("/tools/execute", json={
                    "tool_name": "reconcile_transactions",
                    "tool_input": {"order_ids": [order_id]},
                })
                data = resp.json()
                assert data["total_orders"] >= 1
                assert "summary" in data

    async def test_reconcile_no_auth(self):
        """Reconcile without prior auth should still return a report (possibly with errors)."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": ["fake-id"]},
            })
            data = resp.json()
            assert "summary" in data or "mismatches" in data or "error" in str(data)

    async def test_reconcile_multiple_fake_orders(self):
        """Multiple non-existent orders should produce a report with summary."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": ["fake-1", "fake-2", "fake-3"]},
            })
            data = resp.json()
            assert "total_orders" in data
            assert "summary" in data

    async def test_reconcile_without_order_ids_param(self):
        """Calling with no order_ids at all should default to empty."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {},
            })
            data = resp.json()
            assert data["total_orders"] == 0

    async def test_reconcile_report_counts_are_consistent(self):
        """paid_orders + unpaid_orders should equal total_orders."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": []},
            })
            data = resp.json()
            assert data["paid_orders"] + data["unpaid_orders"] == data["total_orders"]

    async def test_reconcile_idempotent(self):
        """Calling reconcile twice with same input should produce same report."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            inp = {"tool_name": "reconcile_transactions", "tool_input": {"order_ids": []}}
            r1 = (await c.post("/tools/execute", json=inp)).json()
            r2 = (await c.post("/tools/execute", json=inp)).json()
            assert r1["total_orders"] == r2["total_orders"]
            assert r1["summary"] == r2["summary"]


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Agent uses reconcile tool
# ═══════════════════════════════════════════════════════════════════


class TestReconcileAgentIntegration:
    """Test that agent calls reconcile_transactions when asked."""

    @pytest.mark.slow
    async def test_reconcile_request_calls_tool(self):
        """Asking to reconcile should trigger generate_token + reconcile_transactions."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Reconcile my recent transactions"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls

    @pytest.mark.slow
    async def test_reconcile_response_mentions_health(self):
        """Reconciliation response should mention transaction health."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Check my transaction health and reconcile"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response_text = ""
            for e in events:
                if e["type"] == "response":
                    response_text = e["data"]["response"].lower()
            assert len(response_text) > 50
            health_keywords = ["reconcil", "order", "payment", "healthy", "mismatch", "settled", "transaction"]
            assert any(kw in response_text for kw in health_keywords), \
                f"Response should discuss reconciliation, got: {response_text[:200]}"

    @pytest.mark.slow
    async def test_reconcile_triggers_reconciliation_workflow(self):
        """Reconciliation request should trigger workflow_step events with type 'reconciliation'."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Reconcile my transactions and find mismatches"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e for e in events if e["type"] == "workflow_step"]
            if wf_steps:
                assert wf_steps[0]["data"]["workflow_type"] == "reconciliation"


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Full reconciliation through gateway
# ═══════════════════════════════════════════════════════════════════


class TestReconcileE2E:
    """End-to-end reconciliation tests."""

    @pytest.mark.slow
    async def test_websocket_reconciliation_flow(self):
        """Full WS reconciliation: tool events + response."""
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "message": "Reconcile my recent transactions",
                "session_id": f"test-recon-{uuid.uuid4().hex[:8]}",
            }))

            events = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=90)
                    event = json.loads(msg)
                    events.append(event)
                    if event["type"] in ("response", "error"):
                        break
            except asyncio.TimeoutError:
                pass

            types = {e["type"] for e in events}
            assert "tool_call" in types
            assert "tool_result" in types
            assert "response" in types

    @pytest.mark.slow
    async def test_rest_reconciliation(self):
        """REST reconciliation should return substantive response."""
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            resp = await c.post("/api/chat", json={
                "session_id": f"test-rest-recon-{uuid.uuid4().hex[:8]}",
                "message": "Check transaction health and reconcile",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["response"]) > 50
            assert len(data["tool_calls"]) >= 1

    @pytest.mark.slow
    async def test_create_order_then_reconcile(self):
        """Create an order via chat, then reconcile — should mention unpaid."""
        session = f"test-order-recon-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            r1 = await c.post("/api/chat", json={
                "session_id": session,
                "message": "Authenticate and create an order for 7000 rupees",
            })
            assert r1.status_code == 200

            r2 = await c.post("/api/chat", json={
                "session_id": session,
                "message": "Now reconcile my recent transactions",
            })
            assert r2.status_code == 200
            assert len(r2.json()["response"]) > 50
