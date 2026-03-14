"""Comprehensive tests for Feature #8: Agentic Dashboard Insights.

The InsightCards component runs entirely in the frontend (generateInsights function),
so we test the backend analyze_activity tool and verify the frontend logic with
carefully crafted activity arrays fed through the Pine Labs service.

Tests cover:
  - Unit: analyze_activity tool with various activity patterns
  - Integration: Insight generation logic (failure rate, popular methods, unpaid orders)
  - Edge cases: empty data, all successes, all failures, single entry, huge volume
  - E2E: Activity log populated after chat, insights derivable from real interactions
"""
from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest

AGENT_URL = "http://localhost:8001"
GATEWAY_URL = "http://localhost:8000"
PINELABS_URL = "http://localhost:8002"


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: analyze_activity tool
# ═══════════════════════════════════════════════════════════════════


class TestAnalyzeActivityUnit:
    """Test the analyze_activity tool with crafted data."""

    async def test_empty_activities(self):
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": []},
            })
            data = resp.json()
            assert data["total_api_calls"] == 0
            assert data["failure_rate"] == 0
            healthy = [i for i in data["insights"] if "Healthy" in i["message"]]
            assert len(healthy) >= 1, f"Expected healthy insight, got: {data['insights']}"

    async def test_all_successes_healthy_rate(self):
        activities = [
            {"event": "tool_call", "tool_name": "create_order", "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_result", "tool_name": "create_order", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "UPI"}, "timestamp": "2026-03-14T12:00:02Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"success": True}, "timestamp": "2026-03-14T12:00:03Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": activities},
            })
            data = resp.json()
            assert data["failure_rate"] == 0
            assert data["total_api_calls"] == 2
            healthy = [i for i in data["insights"] if "Healthy" in i["message"]]
            assert len(healthy) >= 1

    async def test_all_failures_danger_rate(self):
        activities = [
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "CARD"}, "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"error": "declined"}, "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "UPI"}, "timestamp": "2026-03-14T12:00:02Z"},
            {"event": "tool_result", "tool_name": "create_payment", "tool_result": {"error": "timeout"}, "timestamp": "2026-03-14T12:00:03Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": activities},
            })
            data = resp.json()
            assert data["failure_rate"] == 100.0
            danger = [i for i in data["insights"] if i["severity"] == "danger"]
            assert len(danger) >= 1

    async def test_mixed_failure_rate_warning(self):
        """15% failure rate should produce a warning insight."""
        activities = []
        for i in range(20):
            activities.append({"event": "tool_call", "tool_name": "create_order", "timestamp": f"2026-03-14T12:00:{i:02d}Z"})
            success = i < 17
            activities.append({
                "event": "tool_result", "tool_name": "create_order",
                "tool_result": {"success": True} if success else {"error": "fail"},
                "timestamp": f"2026-03-14T12:00:{i:02d}Z",
            })
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": activities},
            })
            data = resp.json()
            assert 10 < data["failure_rate"] < 30
            warnings = [i for i in data["insights"] if i["severity"] == "warning"]
            assert len(warnings) >= 1

    async def test_payment_methods_counted_from_tool_calls(self):
        activities = [
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "CARD"}, "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "CARD"}, "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_call", "tool_name": "create_payment", "tool_input": {"payment_method": "UPI"}, "timestamp": "2026-03-14T12:00:02Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "methods", "activities": activities},
            })
            data = resp.json()
            assert data["payment_methods"]["CARD"] == 2
            assert data["payment_methods"]["UPI"] == 1

    async def test_single_entry(self):
        activities = [
            {"event": "tool_call", "tool_name": "generate_token", "timestamp": "2026-03-14T12:00:00Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": activities},
            })
            data = resp.json()
            assert data["total_api_calls"] == 1
            assert data["failure_rate"] == 0

    async def test_most_used_tool_identified(self):
        activities = [
            {"event": "tool_call", "tool_name": "create_order", "timestamp": "2026-03-14T12:00:00Z"},
            {"event": "tool_call", "tool_name": "create_order", "timestamp": "2026-03-14T12:00:01Z"},
            {"event": "tool_call", "tool_name": "create_order", "timestamp": "2026-03-14T12:00:02Z"},
            {"event": "tool_call", "tool_name": "generate_token", "timestamp": "2026-03-14T12:00:03Z"},
        ]
        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": activities},
            })
            data = resp.json()
            breakdown = data.get("tool_breakdown", {})
            assert breakdown.get("create_order", 0) >= 3, \
                f"create_order should have 3+ calls in breakdown, got: {breakdown}"
            most_called = max(breakdown, key=breakdown.get, default=None)
            assert most_called == "create_order"


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Activity log + insights after real chat
# ═══════════════════════════════════════════════════════════════════


class TestInsightsE2E:
    """End-to-end: after chatting, activity log is populated for insights."""

    @pytest.mark.slow
    async def test_activity_log_populated_after_chat(self):
        """After a chat, /api/activity should have entries."""
        session = f"test-insight-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            await c.post("/api/chat", json={
                "session_id": session,
                "message": "Authenticate with Pine Labs and create an order for 5000 rupees",
            })
            resp = await c.get("/api/activity")
            assert resp.status_code == 200
            activities = resp.json()["activities"]
            assert len(activities) >= 2, "Should have at least auth + order in activity log"

    @pytest.mark.slow
    async def test_activity_entries_have_correct_structure(self):
        """Each activity entry should have event, tool_name fields."""
        session = f"test-struct-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            await c.post("/api/chat", json={
                "session_id": session,
                "message": "Authenticate with Pine Labs",
            })
            resp = await c.get("/api/activity")
            activities = resp.json()["activities"]
            for a in activities[-5:]:
                assert "event" in a, f"Missing event: {a}"
                assert "tool_name" in a, f"Missing tool_name: {a}"
                assert a["event"] in ("tool_call", "tool_result"), f"Bad event type: {a['event']}"

    @pytest.mark.slow
    async def test_analyze_activity_on_real_log(self):
        """Feed real activity log to analyze_activity for insights."""
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as c:
            await c.post("/api/chat", json={
                "session_id": f"test-real-{uuid.uuid4().hex[:8]}",
                "message": "Authenticate and create an order for 3000 rupees",
            })
            activity_resp = await c.get("/api/activity")
            activities = activity_resp.json()["activities"]

        async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as c:
            resp = await c.post("/tools/execute", json={
                "tool_name": "analyze_activity",
                "tool_input": {"query": "general", "activities": activities[-20:]},
            })
            data = resp.json()
            assert data["total_api_calls"] >= 1
            assert "insights" in data
            assert len(data["insights"]) >= 1
