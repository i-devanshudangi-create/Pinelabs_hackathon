"""Edge case tests across all services."""
from __future__ import annotations

import asyncio
import json

import pytest
import httpx

from tests.conftest import PINELABS_URL, AGENT_URL, GATEWAY_URL, EXPECTED_TOOLS


# ── Pine Labs: Edge Cases ───────────────────────────────────────────


async def test_tool_names_are_valid_python_identifiers():
    """All tool names should be valid Python identifiers (no spaces, dashes, etc.)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{PINELABS_URL}/tools/definitions")
    for tool in resp.json()["tools"]:
        assert tool["name"].isidentifier(), f"'{tool['name']}' is not a valid identifier"


async def test_tool_descriptions_not_empty():
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{PINELABS_URL}/tools/definitions")
    for tool in resp.json()["tools"]:
        assert len(tool["description"].strip()) > 0, f"Tool {tool['name']} has empty description"


async def test_execute_with_extra_params_ignored():
    """Extra parameters in tool_input should be tolerated (kwargs style)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PINELABS_URL}/tools/execute",
            json={
                "tool_name": "generate_token",
                "tool_input": {"extra_field": "should_be_ignored", "another": 123},
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


async def test_execute_tool_with_wrong_types():
    """Passing wrong types (string instead of int) should fail gracefully."""
    async with httpx.AsyncClient(timeout=15) as client:
        # Auth first
        await client.post(
            f"{PINELABS_URL}/tools/execute",
            json={"tool_name": "generate_token", "tool_input": {}},
        )
        # Amount as string instead of int
        resp = await client.post(
            f"{PINELABS_URL}/tools/execute",
            json={
                "tool_name": "create_order",
                "tool_input": {"amount": "not_a_number", "currency": "INR"},
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    # Should either error gracefully or Pine Labs API returns an error
    assert isinstance(data, dict)


async def test_execute_empty_string_tool_name():
    """Empty string tool name should return an error."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{PINELABS_URL}/tools/execute",
            json={"tool_name": "", "tool_input": {}},
        )
    assert resp.status_code == 200
    assert "error" in resp.json()


async def test_concurrent_definitions_requests():
    """Multiple concurrent requests to /tools/definitions should all succeed."""
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [client.get(f"{PINELABS_URL}/tools/definitions") for _ in range(10)]
        results = await asyncio.gather(*tasks)
    for r in results:
        assert r.status_code == 200
        assert len(r.json()["tools"]) == 12


async def test_concurrent_health_checks():
    """Multiple concurrent health checks across all services."""
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [
            client.get(f"{PINELABS_URL}/health"),
            client.get(f"{AGENT_URL}/health"),
            client.get(f"{GATEWAY_URL}/api/health"),
            client.get(f"{PINELABS_URL}/health"),
            client.get(f"{AGENT_URL}/health"),
        ]
        results = await asyncio.gather(*tasks)
    for r in results:
        assert r.status_code == 200


# ── Gateway: Edge Cases ─────────────────────────────────────────────


async def test_empty_message_handling():
    """Sending an empty message should not crash the gateway."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": "edge-empty", "message": ""},
        )
    # Should return 200 with some response, or 422 for validation
    assert resp.status_code in (200, 422)


async def test_unicode_message():
    """Unicode characters should be handled properly."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": "edge-unicode", "message": "Say 'namaste' (नमस्ते)"},
        )
    assert resp.status_code == 200
    assert len(resp.json()["response"]) > 0


async def test_special_characters_in_message():
    """Messages with special chars, newlines, quotes should be handled."""
    msg = 'Test with "quotes" and \\backslash and\nnewlines and <html> & entities'
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/chat",
            json={"session_id": "edge-special", "message": msg},
        )
    assert resp.status_code == 200


async def test_gateway_nonexistent_endpoint():
    """Requesting a non-existent endpoint should return 404."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{GATEWAY_URL}/api/nonexistent")
    assert resp.status_code == 404


async def test_gateway_wrong_method():
    """Using wrong HTTP method should return 405."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{GATEWAY_URL}/api/chat")
    assert resp.status_code == 405


# ── Agent: Edge Cases ───────────────────────────────────────────────


async def test_agent_nonexistent_endpoint():
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{AGENT_URL}/nonexistent")
    assert resp.status_code in (404, 405)


async def test_agent_chat_get_not_allowed():
    """GET to /agent/chat should not be allowed."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{AGENT_URL}/agent/chat")
    assert resp.status_code == 405


# ── Cross-service: Edge Cases ───────────────────────────────────────


async def test_pinelabs_definitions_match_expected_count():
    """Definitions endpoint should have exactly the expected number of tools."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{PINELABS_URL}/tools/definitions")
    assert len(resp.json()["tools"]) == len(EXPECTED_TOOLS)


async def test_all_expected_tools_are_executable():
    """Every expected tool name should be accepted by /tools/execute (not 'Unknown tool')."""
    async with httpx.AsyncClient(timeout=10) as client:
        for tool_name in EXPECTED_TOOLS:
            resp = await client.post(
                f"{PINELABS_URL}/tools/execute",
                json={"tool_name": tool_name, "tool_input": {}},
            )
            assert resp.status_code == 200
            data = resp.json()
            if "error" in data:
                assert "Unknown tool" not in data["error"], f"{tool_name} reported as unknown"
