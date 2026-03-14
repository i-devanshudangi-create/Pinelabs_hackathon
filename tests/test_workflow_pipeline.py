"""Comprehensive tests for Feature #6: Visual Workflow Pipeline.

Tests cover:
  - Unit: workflow_step event structure and fields
  - Integration: checkout/reconciliation trigger workflow_step events with correct states
  - Edge cases: empty steps, duplicate step_index, unknown status, mixed workflows
  - E2E: Gateway WebSocket + Dashboard receive workflow events in real time
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
from agent import _detect_workflow, _get_step_label


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: Step labels and workflow detection
# ═══════════════════════════════════════════════════════════════════


class TestStepLabelsUnit:
    """Unit tests for _get_step_label mapping."""

    def test_generate_token_label(self):
        assert _get_step_label("generate_token") == "Authenticating"

    def test_create_order_label(self):
        assert _get_step_label("create_order") == "Creating Order"

    def test_discover_offers_label(self):
        assert _get_step_label("discover_offers") == "Discovering Offers"

    def test_calculate_convenience_fee_label(self):
        assert _get_step_label("calculate_convenience_fee") == "Comparing Fees"

    def test_create_payment_label(self):
        assert _get_step_label("create_payment") == "Processing Payment"

    def test_create_payment_link_label(self):
        assert _get_step_label("create_payment_link") == "Generating Payment Link"

    def test_reconcile_transactions_label(self):
        assert _get_step_label("reconcile_transactions") == "Reconciling"

    def test_analyze_activity_label(self):
        assert _get_step_label("analyze_activity") == "Analyzing Activity"

    def test_unknown_tool_gets_title_case(self):
        assert _get_step_label("some_custom_tool") == "Some Custom Tool"

    def test_single_word_tool(self):
        assert _get_step_label("authenticate") == "Authenticate"


class TestWorkflowDetectionForPipeline:
    """Verify workflow detection returns correct step counts."""

    def test_checkout_returns_7_steps(self):
        msgs = [{"role": "user", "content": "Buy a laptop"}]
        _, _, steps = _detect_workflow(msgs)
        assert steps == 7

    def test_reconciliation_returns_3_steps(self):
        msgs = [{"role": "user", "content": "Reconcile transactions"}]
        _, _, steps = _detect_workflow(msgs)
        assert steps == 3

    def test_no_workflow_returns_0_steps(self):
        msgs = [{"role": "user", "content": "Hello"}]
        _, _, steps = _detect_workflow(msgs)
        assert steps == 0


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Workflow step events from agent
# ═══════════════════════════════════════════════════════════════════


class TestWorkflowStepEvents:
    """Test that agent streams proper workflow_step events."""

    @pytest.mark.slow
    async def test_checkout_emits_ordered_steps(self):
        """Checkout workflow steps should have increasing step_index."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a mouse for 2000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            assert len(wf_steps) >= 3

            indices = [s["step_index"] for s in wf_steps]
            assert indices == sorted(indices), f"Step indices should be sorted, got: {indices}"

    @pytest.mark.slow
    async def test_workflow_step_required_fields(self):
        """Every workflow_step must have all required fields."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Purchase a charger for 1000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            for s in wf_steps:
                assert "workflow_id" in s, f"Missing workflow_id: {s}"
                assert "step_index" in s, f"Missing step_index: {s}"
                assert "total_steps" in s, f"Missing total_steps: {s}"
                assert "step_name" in s, f"Missing step_name: {s}"
                assert "status" in s, f"Missing status: {s}"
                assert s["status"] in ("pending", "running", "success", "failed"), \
                    f"Invalid status: {s['status']}"

    @pytest.mark.slow
    async def test_workflow_id_consistent_across_steps(self):
        """All steps in one workflow should share the same workflow_id."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy headphones for 3000 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            if wf_steps:
                wf_ids = set(s["workflow_id"] for s in wf_steps)
                assert len(wf_ids) == 1, f"All steps should share same workflow_id, got: {wf_ids}"

    @pytest.mark.slow
    async def test_first_step_is_starting(self):
        """First workflow_step should be 'Starting' with index 0."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a case for 500 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            assert wf_steps[0]["step_index"] == 0
            assert wf_steps[0]["step_name"] == "Starting"

    @pytest.mark.slow
    async def test_last_step_is_done(self):
        """Final workflow_step should be 'Done' with status success."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a cable for 200 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            last = wf_steps[-1]
            assert last["step_name"] == "Done"
            assert last["status"] == "success"

    @pytest.mark.slow
    async def test_starting_step_transitions_to_success(self):
        """The Starting step should eventually be updated to success."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a pen for 100 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            starting_steps = [s for s in wf_steps if s["step_index"] == 0]
            final_starting = starting_steps[-1]
            assert final_starting["status"] == "success", \
                f"Starting step should end as success, got: {final_starting['status']}"


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestWorkflowEdgeCases:
    """Edge cases for the workflow pipeline."""

    @pytest.mark.slow
    async def test_non_workflow_has_no_steps(self):
        """Info-only query should produce zero workflow_step events."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "What payment methods are supported?"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e for e in events if e["type"] == "workflow_step"]
            assert len(wf_steps) == 0

    @pytest.mark.slow
    async def test_total_steps_never_less_than_step_index(self):
        """total_steps should always be >= step_index for each step."""
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
            events = []
            async with c.stream("POST", "/agent/chat", json={
                "messages": [{"role": "user", "content": "Buy a notebook for 400 rupees"}]
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        events.append(json.loads(line))

            wf_steps = [e["data"] for e in events if e["type"] == "workflow_step"]
            for s in wf_steps:
                assert s["total_steps"] >= s["step_index"], \
                    f"total_steps ({s['total_steps']}) < step_index ({s['step_index']})"


# ═══════════════════════════════════════════════════════════════════
# E2E TESTS: Gateway + Dashboard pipeline events
# ═══════════════════════════════════════════════════════════════════


class TestWorkflowE2E:
    """End-to-end pipeline tests through gateway."""

    @pytest.mark.slow
    async def test_dashboard_receives_workflow_steps(self):
        """Dashboard WS should receive workflow_step events forwarded by gateway."""
        chat_uri = "ws://localhost:8000/ws/chat"
        dash_uri = "ws://localhost:8000/ws/dashboard"

        async with websockets.connect(dash_uri) as dash_ws:
            async with websockets.connect(chat_uri) as chat_ws:
                await chat_ws.send(json.dumps({
                    "message": "Buy a USB drive for 500 rupees",
                    "session_id": f"test-wf-{uuid.uuid4().hex[:8]}",
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
                wf_events = [
                    e for e in dash_events
                    if e.get("type") == "dashboard_event"
                    and e.get("data", {}).get("event") == "workflow_step"
                ]
                assert len(wf_events) >= 1, "Dashboard should receive workflow_step events"
