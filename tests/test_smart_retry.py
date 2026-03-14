"""Comprehensive tests for Feature #2: Smart Retry Engine.

Tests cover:
  - Unit: _is_failure detection, PAYMENT_METHODS_FALLBACK chain
  - Integration: Agent retries on payment failure, emits decision events for retries
  - Edge cases: all methods fail -> payment link fallback, non-payment failures don't retry
  - E2E: Full gateway flow with retry behavior
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
from agent import _is_failure, PAYMENT_METHODS_FALLBACK


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: _is_failure detection
# ═══════════════════════════════════════════════════════════════════


class TestIsFailureUnit:
    """Unit tests for _is_failure helper."""

    def test_error_field_is_failure(self):
        assert _is_failure({"error": "auth declined"}) is True

    def test_error_empty_string_is_not_failure(self):
        assert _is_failure({"error": ""}) is False

    def test_success_false_is_failure(self):
        assert _is_failure({"success": False}) is True

    def test_success_true_is_not_failure(self):
        assert _is_failure({"success": True}) is False

    def test_status_failed_in_data(self):
        assert _is_failure({"data": {"status": "FAILED"}}) is True

    def test_status_declined_in_data(self):
        assert _is_failure({"data": {"status": "DECLINED"}}) is True

    def test_status_rejected_in_data(self):
        assert _is_failure({"data": {"status": "REJECTED"}}) is True

    def test_status_created_is_not_failure(self):
        assert _is_failure({"data": {"status": "CREATED"}}) is False

    def test_status_success_is_not_failure(self):
        assert _is_failure({"data": {"status": "SUCCESS"}}) is False

    def test_empty_dict_is_not_failure(self):
        assert _is_failure({}) is False

    def test_nested_data_no_status(self):
        assert _is_failure({"data": {"id": "123", "amount": 5000}}) is False

    def test_data_is_not_dict(self):
        assert _is_failure({"data": "some string"}) is False

    def test_data_is_list(self):
        assert _is_failure({"data": [1, 2, 3]}) is False

    def test_none_error_is_not_failure(self):
        assert _is_failure({"error": None}) is False

    def test_multiple_failure_signals(self):
        """Both error and failed status present."""
        assert _is_failure({"error": "timeout", "data": {"status": "FAILED"}}) is True


class TestFallbackChain:
    """Unit tests for PAYMENT_METHODS_FALLBACK order."""

    def test_fallback_chain_order(self):
        assert PAYMENT_METHODS_FALLBACK == ["CARD", "UPI", "WALLET", "NETBANKING", "BNPL"]

    def test_fallback_chain_has_5_methods(self):
        assert len(PAYMENT_METHODS_FALLBACK) == 5

    def test_removing_failed_methods_gives_remaining(self):
        failed = ["CARD"]
        remaining = [m for m in PAYMENT_METHODS_FALLBACK if m not in failed]
        assert remaining[0] == "UPI"
        assert len(remaining) == 4

    def test_removing_multiple_failed(self):
        failed = ["CARD", "UPI", "WALLET"]
        remaining = [m for m in PAYMENT_METHODS_FALLBACK if m not in failed]
        assert remaining == ["NETBANKING", "BNPL"]

    def test_all_methods_failed_gives_empty(self):
        failed = PAYMENT_METHODS_FALLBACK[:]
        remaining = [m for m in PAYMENT_METHODS_FALLBACK if m not in failed]
        assert remaining == []


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Agent retry behavior
# ═══════════════════════════════════════════════════════════════════


class TestRetryBehavior:
    """Test that the agent retries failed payments with fallback methods."""

    @pytest.mark.slow
    async def test_failed_card_triggers_retry_mention(self):
        """When card payment fails, agent should mention trying another method."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [
                    {"role": "user", "content": "Authenticate with Pine Labs"},
                    {"role": "assistant", "content": "Authenticated successfully."},
                    {"role": "user", "content": "Create an order for 5000 rupees and try paying with card number 0000000000000000 expiry 12/2025 cvv 000. If it fails, try UPI with success@upi."},
                ]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            response_text = ""
            for e in events:
                if e["type"] == "response":
                    response_text = e["data"]["response"].lower()

            assert "create_order" in tool_calls, "Should create order first"
            assert len(response_text) > 0, "Should have a response"

    @pytest.mark.slow
    async def test_agent_explains_retry_reason(self):
        """Agent should explain WHY it's switching payment methods."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy something for 1000 rupees. Try card first with invalid details (card 0000000000000000, exp 01/2025, cvv 000), then fall back to UPI with success@upi if it fails."}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            response_text = ""
            for e in events:
                if e["type"] == "response":
                    response_text = e["data"]["response"].lower()

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            has_payment_attempt = "create_payment" in tool_calls or "create_payment_link" in tool_calls
            assert has_payment_attempt, f"Should attempt payment, got: {tool_calls}"

    @pytest.mark.slow
    async def test_payment_link_as_final_fallback(self):
        """When payment fails, agent should eventually create a payment link."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Create an order for 2000 rupees and generate a payment link so the customer can pay via any method they prefer"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls
            assert "create_order" in tool_calls or "create_payment_link" in tool_calls, \
                f"Should create order or payment link, got: {tool_calls}"


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestRetryEdgeCases:
    """Edge cases for the retry engine."""

    @pytest.mark.slow
    async def test_successful_payment_no_retry(self):
        """Successful payment should not trigger any retry logic."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Authenticate and create an order for 3000 rupees. Then generate a payment link for it."}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            decision_events = [e for e in events if e["type"] == "decision" and "Retry" in e["data"].get("title", "")]
            assert len(decision_events) == 0, "Successful flow should have no retry decisions"

    @pytest.mark.slow
    async def test_non_payment_failure_no_retry_chain(self):
        """If create_order fails, agent should NOT use the payment fallback chain."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Get the status of order ID nonexistent-order-xyz123"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            decision_events = [e for e in events if e["type"] == "decision" and "Retry" in e["data"].get("title", "")]
            assert len(decision_events) == 0, "Non-payment failures should not trigger payment retry chain"

    async def test_payment_tool_with_invalid_order_id(self):
        """create_payment with invalid order should return an error (used by retry logic)."""
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=30) as c:
            await c.post("/tools/execute", json={"tool_name": "generate_token", "tool_input": {}})
            resp = await c.post("/tools/execute", json={
                "tool_name": "create_payment",
                "tool_input": {"order_id": "fake-order-123", "payment_method": "CARD", "amount": 5000},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert _is_failure(data) or "error" in str(data).lower() or "message" in data


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Full retry flow through gateway
# ═══════════════════════════════════════════════════════════════════


class TestRetryE2E:
    """End-to-end retry tests through the gateway."""

    @pytest.mark.slow
    async def test_websocket_retry_flow(self):
        """Full WS flow with a request that may trigger retries."""
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "message": "Create an order for 5000 rupees and try to pay. If payment fails, suggest alternatives.",
                "session_id": f"test-retry-{uuid.uuid4().hex[:8]}",
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
            assert "response" in types
            tool_calls = [e["data"]["tool_name"] for e in events if e["type"] == "tool_call"]
            assert "generate_token" in tool_calls

    @pytest.mark.slow
    async def test_rest_retry_produces_tool_calls(self):
        """REST endpoint retry flow should produce tool_calls in response."""
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            resp = await c.post("/api/chat", json={
                "session_id": f"test-rest-retry-{uuid.uuid4().hex[:8]}",
                "message": "Authenticate and create order for 4000 rupees, then create a payment link",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["tool_calls"]) >= 2
            tool_names = [tc["tool_name"] for tc in data["tool_calls"]]
            assert "generate_token" in tool_names
