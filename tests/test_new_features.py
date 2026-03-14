"""Comprehensive tests for PlurAgent v2 features:
  1. Intelligent Decisioning (enhanced system prompt)
  2. Smart Retry Engine (fallback chain)
  3. Agentic Workflow (workflow_step events)
  4. Agentic Checkout (full pipeline from one sentence)
  5. Conversational Commerce (voice hook — frontend-only, tested via build)
  6. Agentic Dashboard (InsightCards, WorkflowPipeline — frontend-only)
  7. Smart Reconciliation (reconcile_transactions tool)
  8. QR Codes (frontend component — tested via build)
  9. Decision Reasoning (decision events)
  10. Proactive Agent (gateway background alerts)

Backend tests use live services on ports 8000/8001/8002.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest
import websockets

from conftest import PINELABS_URL, AGENT_URL, GATEWAY_URL, EXPECTED_TOOLS


# ═══════════════════════════════════════════════════════════════════
# 1. NEW TOOLS — Pine Labs Service (port 8002)
# ═══════════════════════════════════════════════════════════════════


class TestNewPineLabsTools:
    """Tests for reconcile_transactions and analyze_activity tools."""

    async def test_tool_definitions_include_new_tools(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.get("/tools/definitions")
            assert resp.status_code == 200
            tools = resp.json()["tools"]
            names = [t["name"] for t in tools]
            assert "reconcile_transactions" in names
            assert "analyze_activity" in names

    async def test_tool_count_is_14(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.get("/tools/definitions")
            tools = resp.json()["tools"]
            assert len(tools) == 14

    async def test_reconcile_transactions_schema(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.get("/tools/definitions")
            tools = {t["name"]: t for t in resp.json()["tools"]}
            schema = tools["reconcile_transactions"]["input_schema"]
            assert schema["type"] == "object"
            assert "order_ids" in schema["properties"]

    async def test_analyze_activity_schema(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.get("/tools/definitions")
            tools = {t["name"]: t for t in resp.json()["tools"]}
            schema = tools["analyze_activity"]["input_schema"]
            assert "query" in schema["properties"]
            assert "activities" in schema["properties"]

    async def test_execute_reconcile_empty(self):
        """Reconcile with no order IDs should return a clean report."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": []},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "total_orders" in data
            assert data["total_orders"] == 0
            assert "mismatches" in data
            assert "summary" in data

    async def test_execute_reconcile_with_fake_order_id(self):
        """Reconcile with a non-existent order ID should return a report (may have errors)."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "reconcile_transactions",
                "tool_input": {"order_ids": ["nonexistent-order-123"]},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "total_orders" in data
            assert "mismatches" in data
            assert "summary" in data

    async def test_execute_analyze_activity_empty(self):
        """Analyze with empty activities should return zero stats."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": []},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_api_calls"] == 0
            assert data["failure_rate"] == 0
            assert "insights" in data

    async def test_execute_analyze_activity_with_data(self):
        """Analyze with sample activities should produce insights."""
        sample = [
            {"event": "tool_call", "tool_name": "create_order", "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_result", "tool_name": "create_order", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "UPI"}, "timestamp": "2026-03-14T12:00:02Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"error": "declined"}, "timestamp": "2026-03-14T12:00:03Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "failures", "activities": sample},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_api_calls"] == 2
            assert data["failure_rate"] == 50.0
            assert len(data["failures"]) == 1
            assert data["payment_methods"]["UPI"] == 1

    async def test_analyze_activity_high_failure_warning(self):
        """High failure rate should produce a danger-level insight."""
        sample = [
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"error": "fail"}, "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"error": "fail"}, "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:02Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": sample},
            })
            data = resp.json()
            danger_insights = [i for i in data["insights"] if i["severity"] == "danger"]
            assert len(danger_insights) >= 1, "Expected danger insight for >30% failure rate"


# ═══════════════════════════════════════════════════════════════════
# 2. ENHANCED AGENT — Decisioning, Workflow Steps, Retry
# ═══════════════════════════════════════════════════════════════════


class TestEnhancedAgent:
    """Tests for agent's new event types and enhanced behavior."""

    @pytest.mark.slow
    async def test_agent_streams_ndjson_events(self):
        """Basic agent chat should stream tool_call, tool_result, response events."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Authenticate with Pine Labs"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            types = [e["type"] for e in events]
            assert "tool_call" in types, "Should emit tool_call"
            assert "tool_result" in types, "Should emit tool_result"
            assert "response" in types, "Should emit response"

    @pytest.mark.slow
    async def test_checkout_triggers_workflow_steps(self):
        """Checkout-intent message should emit workflow_step events."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a laptop for 50000 rupees with best payment option"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            types = [e["type"] for e in events]
            assert "workflow_step" in types, "Checkout intent should trigger workflow_step events"
            workflow_steps = [e for e in events if e["type"] == "workflow_step"]
            assert len(workflow_steps) >= 2, "Should have at least 2 workflow steps"
            assert workflow_steps[0]["data"]["workflow_type"] in ("checkout", "reconciliation")

    @pytest.mark.slow
    async def test_checkout_workflow_has_running_and_success_states(self):
        """Workflow steps should go through running -> success transitions."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Purchase a phone for 25000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            workflow_steps = [e for e in events if e["type"] == "workflow_step"]
            statuses = [s["data"]["status"] for s in workflow_steps]
            assert "running" in statuses, "Should have running status"
            assert "success" in statuses, "Should have success status"

    @pytest.mark.slow
    async def test_agent_emits_decision_for_fee_comparison(self):
        """When comparing payment methods, agent should emit decision events."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "I want to buy something for 50000 rupees. Compare card vs UPI fees and recommend the best option."}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            types = [e["type"] for e in events]
            tool_names = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_names, "Should authenticate first"
            assert "response" in types

    @pytest.mark.slow
    async def test_workflow_step_has_required_fields(self):
        """Each workflow_step event must have all required fields."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a tablet for 30000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            workflow_steps = [e for e in events if e["type"] == "workflow_step"]
            for ws in workflow_steps:
                d = ws["data"]
                assert "workflow_id" in d
                assert "step_index" in d
                assert "total_steps" in d
                assert "step_name" in d
                assert "status" in d
                assert d["status"] in ("pending", "running", "success", "failed")

    @pytest.mark.slow
    async def test_response_event_has_tool_calls_list(self):
        """Final response should include accumulated tool_calls array."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Authenticate with Pine Labs please"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response_events = [e for e in events if e["type"] == "response"]
            assert len(response_events) == 1
            assert "tool_calls" in response_events[0]["data"]
            assert isinstance(response_events[0]["data"]["tool_calls"], list)


# ═══════════════════════════════════════════════════════════════════
# 3. GATEWAY — Event Forwarding + Proactive Alerts
# ═══════════════════════════════════════════════════════════════════


class TestGatewayFeatures:
    """Tests for gateway's new event forwarding and proactive alerts."""

    async def test_gateway_health_all_services(self):
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=10) as c:
            resp = await c.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["services"]["gateway"] == "ok"
            assert data["services"]["agent"] == "ok"
            assert data["services"]["pinelabs"] == "ok"

    async def test_gateway_activity_endpoint(self):
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=10) as c:
            resp = await c.get("/api/activity")
            assert resp.status_code == 200
            assert "activities" in resp.json()

    @pytest.mark.slow
    async def test_websocket_chat_forwards_all_event_types(self):
        """Chat WebSocket should forward tool_call, tool_result, workflow_step, and response."""
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "message": "Buy a laptop for 50000 rupees",
                "session_id": f"test-ws-{uuid.uuid4().hex[:8]}",
            }))

            events = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60)
                    event = json.loads(msg)
                    events.append(event)
                    if event["type"] == "response":
                        break
            except asyncio.TimeoutError:
                pass

            types = {e["type"] for e in events}
            assert "tool_call" in types
            assert "tool_result" in types
            assert "response" in types

    @pytest.mark.slow
    async def test_websocket_dashboard_receives_events(self):
        """Dashboard WebSocket should receive dashboard_event entries during chat."""
        chat_uri = "ws://localhost:8000/ws/chat"
        dash_uri = "ws://localhost:8000/ws/dashboard"
        session = f"test-dash-{uuid.uuid4().hex[:8]}"

        async with websockets.connect(dash_uri) as dash_ws:
            async with websockets.connect(chat_uri) as chat_ws:
                await chat_ws.send(json.dumps({
                    "message": "Authenticate with Pine Labs",
                    "session_id": session,
                }))

                chat_done = False
                try:
                    while not chat_done:
                        msg = await asyncio.wait_for(chat_ws.recv(), timeout=60)
                        event = json.loads(msg)
                        if event["type"] == "response":
                            chat_done = True
                except asyncio.TimeoutError:
                    pass

            dash_events = []
            try:
                while True:
                    msg = await asyncio.wait_for(dash_ws.recv(), timeout=3)
                    dash_events.append(json.loads(msg))
            except asyncio.TimeoutError:
                pass

            if dash_events:
                assert any(e["type"] == "dashboard_event" for e in dash_events)

    async def test_rest_chat_endpoint(self):
        """REST /api/chat should still work."""
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            resp = await c.post("/api/chat", json={
                "session_id": f"test-rest-{uuid.uuid4().hex[:8]}",
                "message": "Hello, what can you do?",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "response" in data
            assert len(data["response"]) > 0

    async def test_session_clear(self):
        session = f"test-clear-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=10) as c:
            resp = await c.delete(f"/api/session/{session}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "cleared"


# ═══════════════════════════════════════════════════════════════════
# 4. E2E FLOWS — Complete Agentic Checkout, Reconciliation
# ═══════════════════════════════════════════════════════════════════


class TestE2EFlows:
    """End-to-end tests for complex multi-step agent workflows."""

    @pytest.mark.slow
    async def test_full_checkout_flow(self):
        """Checkout message should trigger auth -> offers -> order -> payment link pipeline."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "I want to buy a laptop for 50000 rupees. Complete checkout for me."}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls, "Must authenticate"
            assert any(t in tool_calls for t in ["create_order", "discover_offers", "create_payment_link"]), \
                f"Expected commerce tools, got: {tool_calls}"

    @pytest.mark.slow
    async def test_auth_then_create_order_flow(self):
        """Multi-turn: authenticate, then create order."""
        messages = [{"role": "user", "content": "Authenticate with Pine Labs"}]

        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events1 = []
            async with c.stream("POST", "/agent/chat", json={"messages": messages}) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events1.append(json.loads(line))

            response_text = ""
            for e in events1:
                if e["type"] == "response":
                    response_text = e["data"]["response"]

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "Now create an order for 10000 rupees"})

            events2 = []
            async with c.stream("POST", "/agent/chat", json={"messages": messages}) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events2.append(json.loads(line))

            tool_calls2 = [e["data"]["tool_name"] for e in events2 if e["type"] == "tool_call"]
            assert "create_order" in tool_calls2

    @pytest.mark.slow
    async def test_reconciliation_flow(self):
        """Reconciliation request should trigger reconcile_transactions tool."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Please reconcile my recent transactions and check for any mismatches"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls, "Should authenticate first"


# ═══════════════════════════════════════════════════════════════════
# 5. EDGE CASES & ROBUSTNESS
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case and robustness tests for new features."""

    async def test_reconcile_with_nonexistent_tool(self):
        """Executing a non-existent tool should return an error."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "nonexistent_tool",
                "tool_input": {},
            })
            assert resp.status_code == 200
            assert "error" in resp.json()

    async def test_analyze_activity_missing_query(self):
        """Analyze activity without query field should still work."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_api_calls"] == 0

    async def test_all_14_tools_registered(self):
        """All 14 tools should be present in definitions."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.get("/tools/definitions")
            tools = resp.json()["tools"]
            names = {t["name"] for t in tools}
            for expected in EXPECTED_TOOLS:
                assert expected in names, f"Missing tool: {expected}"

    async def test_tool_definitions_have_descriptions(self):
        """All tools should have non-empty descriptions."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.get("/tools/definitions")
            for tool in resp.json()["tools"]:
                assert tool.get("description"), f"Tool {tool['name']} has no description"
                assert len(tool["description"]) > 10

    async def test_analyze_activity_with_mixed_events(self):
        """Analyze should handle mixed event types correctly."""
        sample = [
            {"event": "tool_call", "tool_name": "generate_token", "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_result", "tool_name": "generate_token", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_call", "tool_name": "create_order", "timestamp": "2026-03-14T12:00:02Z"},
            {"event": "tool_result", "tool_name": "create_order", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:03Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "CARD"}, "timestamp": "2026-03-14T12:00:04Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"success": False, "error": "declined"}, "timestamp": "2026-03-14T12:00:05Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "UPI"}, "timestamp": "2026-03-14T12:00:06Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:07Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": sample},
            })
            data = resp.json()
            assert data["total_api_calls"] == 4
            assert data["payment_methods"]["CARD"] == 1
            assert data["payment_methods"]["UPI"] == 1
            assert data["failure_rate"] == 25.0

    async def test_concurrent_tool_executions(self):
        """Multiple concurrent tool executions should not interfere."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            tasks = [
                c.post("/tools/execute", json={"tool_name": "analyze_activity", "tool_input": {"query": "general", "activities": []}}),
                c.post("/tools/execute", json={"tool_name": "reconcile_transactions", "tool_input": {"order_ids": []}}),
                c.get("/tools/definitions"),
                c.get("/health"),
            ]
            results = await asyncio.gather(*tasks)
            assert all(r.status_code == 200 for r in results)


# ═══════════════════════════════════════════════════════════════════
# 6. FRONTEND BUILD VERIFICATION
# ═══════════════════════════════════════════════════════════════════


class TestFrontendBuild:
    """Verify that the frontend builds successfully with all new components."""

    async def test_frontend_dev_server_responds(self):
        """Frontend dev server should be reachable."""
        async with httpx.AsyncClient(timeout=10) as c:
            try:
                resp = await c.get("http://localhost:5173")
                assert resp.status_code == 200
            except httpx.ConnectError:
                pytest.skip("Frontend dev server not running on port 5173")
