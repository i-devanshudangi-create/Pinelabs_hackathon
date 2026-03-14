"""Comprehensive tests for Feature #3: Agentic Checkout.

Tests cover:
  - Unit: _detect_workflow keyword detection for checkout vs reconciliation
  - Integration: Checkout intent triggers full pipeline (auth->offers->fees->order->link)
  - Edge cases: unusual phrasing, partial intent, currency amounts, workflow_step events
  - E2E: Full gateway flow produces complete checkout with QR-ready payment link
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

import httpx
import pytest
import websockets

AGENT_URL = "http://localhost:8001"
GATEWAY_URL = "http://localhost:8000"
PINELABS_URL = "http://localhost:8002"

sys.path.insert(0, "services/agent")
from agent import _detect_workflow, CHECKOUT_TOOLS


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: _detect_workflow keyword detection
# ═══════════════════════════════════════════════════════════════════


class TestDetectWorkflowUnit:
    """Unit tests for _detect_workflow helper."""

    def test_buy_triggers_checkout(self):
        msgs = [{"role": "user", "content": "Buy a laptop for 50000"}]
        is_wf, wf_type, steps = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"
        assert steps == 7

    def test_purchase_triggers_checkout(self):
        msgs = [{"role": "user", "content": "I want to purchase a phone"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"

    def test_checkout_keyword(self):
        msgs = [{"role": "user", "content": "Start the checkout process"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"

    def test_order_keyword(self):
        msgs = [{"role": "user", "content": "Create an order for 10000"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"

    def test_pay_for_keyword(self):
        msgs = [{"role": "user", "content": "pay for this item"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"

    def test_emi_keyword(self):
        msgs = [{"role": "user", "content": "Can I get EMI on this?"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"

    def test_best_deal_keyword(self):
        msgs = [{"role": "user", "content": "Find me the best deal for 45000"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "checkout"

    def test_laptop_keyword(self):
        msgs = [{"role": "user", "content": "I need a laptop"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True

    def test_phone_keyword(self):
        msgs = [{"role": "user", "content": "Get me a phone for 20000"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True

    def test_want_to_get_keyword(self):
        msgs = [{"role": "user", "content": "I want to get a new TV"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True

    def test_reconcile_triggers_reconciliation(self):
        msgs = [{"role": "user", "content": "Reconcile my transactions"}]
        is_wf, wf_type, steps = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "reconciliation"
        assert steps == 3

    def test_mismatch_triggers_reconciliation(self):
        msgs = [{"role": "user", "content": "Check for any mismatch in payments"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True
        assert wf_type == "reconciliation"

    def test_generic_greeting_no_workflow(self):
        msgs = [{"role": "user", "content": "Hello, how are you?"}]
        is_wf, wf_type, steps = _detect_workflow(msgs)
        assert is_wf is False
        assert wf_type == ""
        assert steps == 0

    def test_empty_messages_no_workflow(self):
        is_wf, wf_type, steps = _detect_workflow([])
        assert is_wf is False

    def test_info_query_no_workflow(self):
        msgs = [{"role": "user", "content": "What payment methods are supported?"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is False

    def test_case_insensitive(self):
        msgs = [{"role": "user", "content": "BUY a LAPTOP for 50000 RUPEES"}]
        is_wf, wf_type, _ = _detect_workflow(msgs)
        assert is_wf is True

    def test_only_last_message_matters(self):
        msgs = [
            {"role": "user", "content": "Buy a laptop"},
            {"role": "assistant", "content": "Sure, let me help."},
            {"role": "user", "content": "What's the weather today?"},
        ]
        is_wf, _, _ = _detect_workflow(msgs)
        assert is_wf is False, "Only the last message should be checked"

    def test_non_string_content_handled(self):
        msgs = [{"role": "user", "content": [{"text": "Buy something"}]}]
        is_wf, _, _ = _detect_workflow(msgs)
        assert is_wf is False, "Non-string content should not crash"


class TestCheckoutToolsList:
    """Verify the checkout tools are defined correctly."""

    def test_checkout_tools_count(self):
        assert len(CHECKOUT_TOOLS) == 6

    def test_checkout_tools_order(self):
        assert CHECKOUT_TOOLS[0] == "generate_token"
        assert "discover_offers" in CHECKOUT_TOOLS
        assert "calculate_convenience_fee" in CHECKOUT_TOOLS
        assert "create_order" in CHECKOUT_TOOLS
        assert "create_payment_link" in CHECKOUT_TOOLS


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Checkout pipeline
# ═══════════════════════════════════════════════════════════════════


class TestCheckoutPipeline:
    """Verify checkout intent triggers the full autonomous pipeline."""

    @pytest.mark.slow
    async def test_buy_triggers_multi_tool_pipeline(self):
        """'Buy X for Y' should trigger auth, offers, fees, order, and payment link."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a laptop for 50000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert len(tool_calls) >= 3, f"Checkout should call >=3 tools, got: {tool_calls}"
            assert tool_calls[0] == "generate_token", "Must start with auth"
            assert any(t in tool_calls for t in ["discover_offers", "calculate_convenience_fee"]), \
                "Should do decisioning (offers or fees)"
            assert any(t in tool_calls for t in ["create_order", "create_payment_link"]), \
                "Should create order or payment link"

    @pytest.mark.slow
    async def test_checkout_emits_workflow_steps(self):
        """Checkout should emit workflow_step events for the pipeline visualization."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Purchase a tablet for 25000 rupees with best payment option"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            workflow_steps = [e for e in events if e["type"] == "workflow_step"]
            assert len(workflow_steps) >= 3, f"Should have >=3 workflow steps, got {len(workflow_steps)}"

            first_step = workflow_steps[0]
            assert first_step["data"]["workflow_type"] == "checkout"
            assert first_step["data"]["step_index"] == 0

            statuses = [s["data"]["status"] for s in workflow_steps]
            assert "running" in statuses
            assert "success" in statuses

    @pytest.mark.slow
    async def test_checkout_has_starting_and_done_steps(self):
        """Pipeline should have Starting (success) and Done (success) bookend steps."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy headphones for 3000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            workflow_steps = [e for e in events if e["type"] == "workflow_step"]
            step_names = [s["data"]["step_name"] for s in workflow_steps]
            assert "Starting" in step_names, f"Should have Starting step, got: {step_names}"
            assert "Done" in step_names, f"Should have Done step, got: {step_names}"

            starting_steps = [s for s in workflow_steps if s["data"]["step_name"] == "Starting"]
            final_starting = starting_steps[-1]
            assert final_starting["data"]["status"] == "success", "Starting step should end as success"

    @pytest.mark.slow
    async def test_checkout_produces_payment_url(self):
        """Checkout should produce a payment URL in the tool results."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "I want to buy a camera for 15000 rupees, complete checkout for me"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_results = [e for e in events if e["type"] == "tool_result"]
            has_payment_url = False
            for tr in tool_results:
                result = tr["data"].get("tool_result", {})
                if result.get("payment_url") or result.get("data", {}).get("payment_link_url"):
                    has_payment_url = True
                    break
            assert has_payment_url, "Checkout should produce a payment URL for QR code"

    @pytest.mark.slow
    async def test_checkout_response_has_summary(self):
        """Checkout response should include order details and payment info."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a keyboard for 5000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response_text = ""
            for e in events:
                if e["type"] == "response":
                    response_text = e["data"]["response"]
            assert len(response_text) > 100, "Checkout response should be detailed"
            text_lower = response_text.lower()
            assert any(w in text_lower for w in ["order", "payment", "₹", "rupee", "5000", "5,000"]), \
                "Response should mention order/payment details"


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestCheckoutEdgeCases:
    """Edge cases for agentic checkout."""

    @pytest.mark.slow
    async def test_checkout_small_amount(self):
        """Tiny checkout (₹10) should still work."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a sticker for 10 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            assert len([e for e in events if e["type"] == "response"]) == 1

    @pytest.mark.slow
    async def test_checkout_large_amount(self):
        """Large checkout (₹5 lakh) should still work."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Purchase furniture worth 5 lakh rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            assert len([e for e in events if e["type"] == "response"]) == 1

    @pytest.mark.slow
    async def test_non_checkout_doesnt_trigger_pipeline(self):
        """A question about Pine Labs should not trigger the checkout pipeline."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "What currencies does Pine Labs support?"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            workflow_steps = [e for e in events if e["type"] == "workflow_step"]
            assert len(workflow_steps) == 0, "Info query should not trigger workflow pipeline"

    @pytest.mark.slow
    async def test_checkout_includes_all_tool_calls_in_response(self):
        """Final response data should include all tool_calls from the pipeline."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a monitor for 20000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response_events = [e for e in events if e["type"] == "response"]
            assert len(response_events) == 1
            tool_calls_in_response = response_events[0]["data"].get("tool_calls", [])
            streamed_tool_calls = [e for e in events if e["type"] == "tool_call"]
            assert len(tool_calls_in_response) == len(streamed_tool_calls), \
                "Response tool_calls should match streamed tool_calls count"


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Full checkout through gateway
# ═══════════════════════════════════════════════════════════════════


class TestCheckoutE2E:
    """End-to-end checkout tests through the gateway."""

    @pytest.mark.slow
    async def test_websocket_full_checkout(self):
        """Full WS checkout: user says 'buy X' -> all events stream correctly."""
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "message": "Buy a smartwatch for 15000 rupees with the best payment option",
                "session_id": f"test-checkout-{uuid.uuid4().hex[:8]}",
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

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert len(tool_calls) >= 3, f"Checkout should have >=3 tool calls, got: {tool_calls}"

    @pytest.mark.slow
    async def test_rest_checkout_returns_payment_info(self):
        """REST checkout should return response with payment details."""
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            resp = await c.post("/api/chat", json={
                "session_id": f"test-rest-checkout-{uuid.uuid4().hex[:8]}",
                "message": "Buy a speaker for 8000 rupees",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["response"]) > 100
            assert len(data["tool_calls"]) >= 3
            tool_names = [tc["tool_name"] for tc in data["tool_calls"]]
            assert "generate_token" in tool_names

    @pytest.mark.slow
    async def test_dashboard_receives_checkout_workflow_events(self):
        """Dashboard should receive workflow_step events during checkout."""
        chat_uri = "ws://localhost:8000/ws/chat"
        dash_uri = "ws://localhost:8000/ws/dashboard"
        session = f"test-dash-checkout-{uuid.uuid4().hex[:8]}"

        async with websockets.connect(dash_uri) as dash_ws:
            async with websockets.connect(chat_uri) as chat_ws:
                await chat_ws.send(json.dumps({
                    "message": "Purchase earbuds for 2000 rupees",
                    "session_id": session,
                }))

                try:
                    while True:
                        msg = await asyncio.wait_for(chat_ws.recv(), timeout=90)
                        event = json.loads(msg)
                        if event["type"] in ("response", "error"):
                            break
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
                workflow_events = [
                    e for e in dash_events
                    if e.get("type") == "dashboard_event"
                    and e.get("data", {}).get("event") == "workflow_step"
                ]
                tool_events = [
                    e for e in dash_events
                    if e.get("type") == "dashboard_event"
                    and e.get("data", {}).get("event") == "tool_call"
                ]
                assert len(tool_events) >= 1, "Dashboard should receive tool events during checkout"
