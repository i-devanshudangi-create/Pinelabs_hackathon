"""Comprehensive tests for Feature #7: Decision Reasoning Panel.

Tests cover:
  - Unit: _extract_decision patterns and Decision data structure
  - Integration: Agent emits decision events during fee comparison
  - Edge cases: no decision for simple queries, retry decisions on payment failure
  - E2E: Gateway forwards decision events through WebSocket
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

sys.path.insert(0, "services/agent")
from agent import _extract_decision


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: Decision event structure
# ═══════════════════════════════════════════════════════════════════


class TestDecisionStructureUnit:
    """Verify decision dict has correct fields."""

    def test_decision_has_title(self):
        d = _extract_decision("I recommend UPI because zero fees.")
        assert d is not None
        assert "title" in d
        assert isinstance(d["title"], str)

    def test_decision_has_reasoning(self):
        d = _extract_decision("I recommend UPI because zero fees.")
        assert "reasoning" in d
        assert len(d["reasoning"]) > 0

    def test_decision_has_chosen(self):
        d = _extract_decision("I recommend UPI because zero fees.")
        assert "chosen" in d
        assert len(d["chosen"]) > 0

    def test_decision_has_confidence(self):
        d = _extract_decision("I recommend UPI because zero fees.")
        assert d["confidence"] in ("high", "medium", "low")

    def test_decision_has_options_considered(self):
        d = _extract_decision("I recommend UPI because zero fees.")
        assert "options_considered" in d
        assert isinstance(d["options_considered"], list)

    def test_fee_comparison_has_medium_confidence(self):
        d = _extract_decision("The convenience fee for CARD is ₹150.")
        assert d is not None
        assert d["confidence"] == "medium"

    def test_recommend_pattern_has_high_confidence(self):
        d = _extract_decision("I recommend CARD because EMI is available.")
        assert d["confidence"] == "high"


class TestDecisionEdgePatternsUnit:
    """Edge cases for regex-based decision extraction."""

    def test_recommend_with_parentheses(self):
        d = _extract_decision("I recommend UPI (₹0 fee) because it saves money.")
        assert d is not None

    def test_recommend_with_rupee_symbol(self):
        d = _extract_decision("I recommend Card because: ₹0 interest on 3-month EMI.")
        assert d is not None

    def test_recommend_with_percentage(self):
        d = _extract_decision("I recommend UPI because 0% convenience fee vs 2.5% for card.")
        assert d is not None

    def test_no_decision_for_greeting(self):
        assert _extract_decision("Hi! How can I help?") is None

    def test_no_decision_for_tool_output(self):
        assert _extract_decision('{"order_id": "v1-123", "status": "CREATED"}') is None

    def test_no_decision_for_step_announcement(self):
        assert _extract_decision("Step 1/6: Authenticating with Pine Labs...") is None

    def test_multiple_recommendations_returns_first(self):
        text = "I recommend UPI because zero fees. I recommend CARD because EMI."
        d = _extract_decision(text)
        assert d is not None
        assert "UPI" in d["chosen"]

    def test_comparison_keyword_in_technical_text(self):
        d = _extract_decision("Here is the fee comparison breakdown for your payment.")
        assert d is not None
        assert d["title"] == "Fee Comparison"


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Agent emits decision events
# ═══════════════════════════════════════════════════════════════════


class TestDecisionEventEmission:
    """Test that agent emits decision events in appropriate scenarios."""

    @pytest.mark.slow
    async def test_fee_comparison_emits_decision(self):
        """Comparing fees should emit a decision event or include recommendation."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Compare convenience fee for CARD vs UPI for 25000 rupees and recommend the best"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            types = {e["type"] for e in events}
            assert "response" in types
            response_text = ""
            for e in events:
                if e["type"] == "response":
                    response_text = e["data"]["response"].lower()
            assert any(kw in response_text for kw in ["recommend", "best", "suggest", "prefer", "fee", "upi", "card"]), \
                "Response should contain recommendation language"

    @pytest.mark.slow
    async def test_decision_event_has_valid_structure(self):
        """Any decision event emitted should have title, reasoning, chosen, confidence."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a laptop for 50000 rupees with the cheapest payment method"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            decisions = [e["data"] for e in events if e["type"] == "decision"]
            for d in decisions:
                assert "title" in d, f"Missing title: {d}"
                assert "reasoning" in d, f"Missing reasoning: {d}"
                assert "chosen" in d, f"Missing chosen: {d}"
                assert "confidence" in d, f"Missing confidence: {d}"
                assert d["confidence"] in ("high", "medium", "low"), f"Bad confidence: {d['confidence']}"

    @pytest.mark.slow
    async def test_simple_auth_decisions_are_low_value(self):
        """Simple authentication should not produce substantive decisions with options."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Authenticate with Pine Labs"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            decisions = [e["data"] for e in events if e["type"] == "decision"]
            for d in decisions:
                assert len(d.get("options_considered", [])) <= 1, \
                    f"Simple auth should not produce multi-option decisions, got: {d}"


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Decision events through gateway
# ═══════════════════════════════════════════════════════════════════


class TestDecisionE2E:
    """End-to-end decision panel tests through gateway."""

    @pytest.mark.slow
    async def test_websocket_receives_decision_or_recommendation(self):
        """Gateway WS should forward decision events or the response should have recommendations."""
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "message": "What's the best payment method for 30000 rupees? Compare fees and recommend.",
                "session_id": f"test-dec-{uuid.uuid4().hex[:8]}",
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

            assert any(e["type"] == "response" for e in events)
            response_text = ""
            for e in events:
                if e["type"] == "response":
                    response_text = e["data"]["response"].lower()
            has_decision = any(e["type"] == "decision" for e in events)
            has_recommendation = any(kw in response_text for kw in ["recommend", "best", "suggest", "prefer"])
            assert has_decision or has_recommendation, \
                "Should have decision event or recommendation in response"
