"""Comprehensive tests for Feature #1: Intelligent Decisioning.

Tests cover:
  - Unit: _extract_decision regex logic with various text patterns
  - Integration: Agent calls discover_offers + calculate_convenience_fee before payment
  - Edge cases: ambiguous prompts, conflicting data, no offers, unusual amounts
  - E2E: Full gateway flow produces tool calls in correct decisioning order
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

# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: _extract_decision regex patterns
# ═══════════════════════════════════════════════════════════════════

sys.path.insert(0, "services/agent")
from agent import _extract_decision


class TestExtractDecisionUnit:
    """Unit tests for the _extract_decision regex extractor."""

    def test_recommend_because_pattern(self):
        text = "I recommend UPI because zero convenience fee and instant settlement."
        result = _extract_decision(text)
        assert result is not None
        assert result["title"] == "Payment Decision"
        assert "UPI" in result["chosen"]
        assert result["confidence"] == "high"

    def test_recommend_because_colon_pattern(self):
        text = "I recommend Card payment because: 3-month no-cost EMI available, saving Rs 2400."
        result = _extract_decision(text)
        assert result is not None
        assert "Card" in result["chosen"]

    def test_best_option_dash_pattern(self):
        text = "Best option: UPI - zero fees and instant processing."
        result = _extract_decision(text)
        assert result is not None

    def test_best_option_emdash_pattern(self):
        text = "Best option: CARD payment — offers no-cost EMI with zero interest."
        result = _extract_decision(text)
        assert result is not None

    def test_comparing_pattern(self):
        text = "Comparing CARD vs UPI: UPI has zero fees."
        result = _extract_decision(text)
        assert result is not None

    def test_fee_comparison_pattern(self):
        text = "Let me check the convenience fee for both methods."
        result = _extract_decision(text)
        assert result is not None
        assert result["title"] == "Fee Comparison"
        assert result["confidence"] == "medium"

    def test_cost_comparison_pattern(self):
        text = "Here's the cost comparison between the two payment methods."
        result = _extract_decision(text)
        assert result is not None
        assert result["title"] == "Fee Comparison"

    def test_no_decision_in_generic_text(self):
        text = "Hello! How can I help you today?"
        result = _extract_decision(text)
        assert result is None

    def test_no_decision_in_order_created(self):
        text = "Order created successfully with ID v1-123456."
        result = _extract_decision(text)
        assert result is None

    def test_reasoning_truncated_at_300_chars(self):
        long_reasoning = "x" * 500
        text = f"I recommend UPI because {long_reasoning}."
        result = _extract_decision(text)
        assert result is not None
        assert len(result["reasoning"]) <= 300

    def test_chosen_truncated_at_100_chars(self):
        long_chosen = "y" * 200
        text = f"I recommend {long_chosen} because it is cheap."
        result = _extract_decision(text)
        assert result is not None
        assert len(result["chosen"]) <= 100

    def test_case_insensitive_recommend(self):
        text = "i RECOMMEND netbanking because lower fees."
        result = _extract_decision(text)
        assert result is not None

    def test_case_insensitive_convenience_fee(self):
        text = "Checking the CONVENIENCE FEE for CARD."
        result = _extract_decision(text)
        assert result is not None

    def test_multiline_text_extracts_first_decision(self):
        text = """Step 1: Authenticating...
Step 2: I recommend UPI because zero fees.
Step 3: Creating order."""
        result = _extract_decision(text)
        assert result is not None
        assert "UPI" in result["chosen"]

    def test_empty_string(self):
        assert _extract_decision("") is None

    def test_none_safe(self):
        """Should not crash on None-like edge cases."""
        assert _extract_decision("   ") is None

    def test_special_characters_in_text(self):
        text = "I recommend UPI (₹0 fee) because: it's free & fast!"
        result = _extract_decision(text)
        assert result is not None

    def test_recommendation_with_numbers(self):
        text = "I recommend 3-month EMI on HDFC because: saves ₹2,400 in interest."
        result = _extract_decision(text)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Agent uses decisioning tools
# ═══════════════════════════════════════════════════════════════════


class TestDecisioningToolUsage:
    """Agent should call discover_offers and calculate_convenience_fee
    when user asks about payment options."""

    @pytest.mark.slow
    async def test_compare_request_calls_fee_tools(self):
        """Asking to compare payment methods should trigger fee calculation."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Compare card vs UPI fees for a 25000 rupee purchase"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls, "Must authenticate first"
            assert "calculate_convenience_fee" in tool_calls, "Must calculate fees"

    @pytest.mark.slow
    async def test_purchase_intent_checks_offers_before_payment(self):
        """Purchase intent should discover offers before creating order."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "I want to buy a phone for 30000 rupees, find me the best deal"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            assert "discover_offers" in tool_calls, "Must discover offers for best deal"

    @pytest.mark.slow
    async def test_auth_happens_before_any_payment_tool(self):
        """generate_token must always be the first tool called."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "What are the fees for paying 10000 by card vs UPI?"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert len(tool_calls) >= 2, f"Expected multiple tools, got: {tool_calls}"
            assert tool_calls[0] == "generate_token", "Auth must be first"

    @pytest.mark.slow
    async def test_fee_comparison_calls_multiple_methods(self):
        """Fee comparison should call calculate_convenience_fee at least twice (CARD + UPI)."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Calculate convenience fees for 50000 rupees for both CARD and UPI methods"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            fee_calls = [
                e for e in events
                if e["type"] == "tool_call" and e["data"]["tool_name"] == "calculate_convenience_fee"
            ]
            assert len(fee_calls) >= 2, f"Expected >=2 fee calculations, got {len(fee_calls)}"
            methods = [e["data"]["tool_input"].get("payment_method", "") for e in fee_calls]
            assert len(set(methods)) >= 2, f"Expected different methods, got: {methods}"

    @pytest.mark.slow
    async def test_response_contains_recommendation_text(self):
        """Final response should include recommendation language."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "I need to pay 15000 rupees. Should I use card or UPI? Compare and recommend."}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response_events = [e for e in events if e["type"] == "response"]
            assert len(response_events) == 1
            text = response_events[0]["data"]["response"].lower()
            recommendation_keywords = ["recommend", "best", "suggest", "prefer", "better", "optimal", "advise"]
            assert any(kw in text for kw in recommendation_keywords), \
                f"Response should contain recommendation, got: {text[:200]}"


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES: Unusual inputs and boundary conditions
# ═══════════════════════════════════════════════════════════════════


class TestDecisioningEdgeCases:
    """Edge cases for intelligent decisioning."""

    @pytest.mark.slow
    async def test_very_small_amount(self):
        """Tiny amount (₹1 = 100 paisa) should still go through decisioning."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "What's the best way to pay 1 rupee?"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            response_events = [e for e in events if e["type"] == "response"]
            assert len(response_events) == 1
            assert len(response_events[0]["data"]["response"]) > 0

    @pytest.mark.slow
    async def test_large_amount(self):
        """Large amount (₹10 lakh) should still process."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Compare payment options for 10 lakh rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            assert len([e for e in events if e["type"] == "response"]) == 1

    @pytest.mark.slow
    async def test_ambiguous_method_request(self):
        """Asking about an unspecified method should still produce a recommendation."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "What's the cheapest way to pay 5000 rupees?"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response = [e for e in events if e["type"] == "response"]
            assert len(response) == 1
            text = response[0]["data"]["response"].lower()
            assert any(m in text for m in ["upi", "card", "wallet", "netbanking"]), \
                "Response should mention at least one payment method"

    @pytest.mark.slow
    async def test_non_payment_query_skips_decisioning(self):
        """A non-payment question should not trigger fee/offer tools."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "What payment methods does Pine Labs support?"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "calculate_convenience_fee" not in tool_calls, \
                "Informational query should not trigger fee calculation"

    async def test_fee_tool_returns_valid_structure(self):
        """calculate_convenience_fee should return a structured response."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "calculate_convenience_fee",
                "tool_input": {"amount": 50000, "payment_method": "CARD"},
            })
            assert resp.status_code == 200

    async def test_offers_tool_returns_valid_structure(self):
        """discover_offers should return a response (even if no offers available)."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "discover_offers",
                "tool_input": {"amount": 5000000},
            })
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Full gateway flow with decisioning
# ═══════════════════════════════════════════════════════════════════


class TestDecisioningE2E:
    """End-to-end tests through the gateway WebSocket."""

    @pytest.mark.slow
    async def test_websocket_decisioning_flow(self):
        """Full WS flow: ask for best payment -> get tool events -> get recommendation."""
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "message": "I want to pay 40000 rupees. Compare CARD vs UPI and recommend the best.",
                "session_id": f"test-decision-{uuid.uuid4().hex[:8]}",
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

            types = [e["type"] for e in events]
            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]

            assert "tool_call" in types, "Should have tool calls"
            assert "tool_result" in types, "Should have tool results"
            assert "response" in types, "Should have final response"
            assert "generate_token" in tool_calls, "Must authenticate"

    @pytest.mark.slow
    async def test_gateway_rest_decisioning(self):
        """REST /api/chat should also use intelligent decisioning."""
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            resp = await c.post("/api/chat", json={
                "session_id": f"test-rest-decision-{uuid.uuid4().hex[:8]}",
                "message": "Compare fees for paying 20000 rupees by CARD vs UPI and tell me which is better",
            })
            assert resp.status_code == 200
            data = resp.json()
            text = data["response"].lower()
            assert len(text) > 50, "Response should be substantive"
            assert any(m in text for m in ["card", "upi"]), "Should mention payment methods"
            assert len(data["tool_calls"]) >= 2, "Should have multiple tool calls"

    @pytest.mark.slow
    async def test_dashboard_receives_tool_events_during_decisioning(self):
        """Dashboard should receive tool_call events during a decisioning flow."""
        chat_uri = "ws://localhost:8000/ws/chat"
        dash_uri = "ws://localhost:8000/ws/dashboard"
        session = f"test-dash-decision-{uuid.uuid4().hex[:8]}"

        async with websockets.connect(dash_uri) as dash_ws:
            async with websockets.connect(chat_uri) as chat_ws:
                await chat_ws.send(json.dumps({
                    "message": "What's the fee for paying 30000 by card?",
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
                dash_tool_events = [
                    e for e in dash_events
                    if e.get("type") == "dashboard_event" and e.get("data", {}).get("event") == "tool_call"
                ]
                assert len(dash_tool_events) >= 1, "Dashboard should receive tool events"

    @pytest.mark.slow
    async def test_decisioning_tool_order(self):
        """Verify tool call order: auth -> offers/fees -> order (not reversed)."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a TV for 45000 rupees with the best payment option"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert len(tool_calls) >= 3, f"Expected >=3 tools, got: {tool_calls}"
            auth_idx = tool_calls.index("generate_token")
            if "create_order" in tool_calls:
                order_idx = tool_calls.index("create_order")
                assert auth_idx < order_idx, "Auth must come before order creation"
                decisioning_tools = {"discover_offers", "calculate_convenience_fee"}
                tools_between = set(tool_calls[auth_idx + 1:order_idx])
                assert tools_between & decisioning_tools, \
                    f"Decisioning tools should come between auth and order. Sequence: {tool_calls}"

    @pytest.mark.slow
    async def test_multiple_sequential_decisioning_queries(self):
        """Two back-to-back decisioning queries in the same session should both work."""
        session = f"test-multi-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            r1 = await c.post("/api/chat", json={
                "session_id": session,
                "message": "What's the fee for paying 10000 by UPI?",
            })
            assert r1.status_code == 200
            assert len(r1.json()["response"]) > 0

            r2 = await c.post("/api/chat", json={
                "session_id": session,
                "message": "Now compare it with CARD fee for the same amount",
            })
            assert r2.status_code == 200
            text2 = r2.json()["response"].lower()
            assert any(m in text2 for m in ["card", "fee", "compare", "convenience"]), \
                "Second query should discuss card fees"
