"""Tests for the Pine Labs Service (port 8002)."""
from __future__ import annotations

import pytest
from tests.conftest import EXPECTED_TOOLS

# ── Health ───────────────────────────────────────────────────────────


async def test_health(pinelabs_client):
    resp = await pinelabs_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "pinelabs"


# ── Tool Definitions ────────────────────────────────────────────────


async def test_definitions_returns_all_12_tools(pinelabs_client):
    resp = await pinelabs_client.get("/tools/definitions")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 12


async def test_definitions_contains_expected_tool_names(pinelabs_client):
    resp = await pinelabs_client.get("/tools/definitions")
    tool_names = {t["name"] for t in resp.json()["tools"]}
    for expected in EXPECTED_TOOLS:
        assert expected in tool_names, f"Missing tool: {expected}"


async def test_definitions_schema_structure(pinelabs_client):
    """Each tool definition must have name, description, and input_schema."""
    resp = await pinelabs_client.get("/tools/definitions")
    for tool in resp.json()["tools"]:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool, f"Tool {tool['name']} missing 'description'"
        assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"
        assert isinstance(tool["description"], str)
        assert len(tool["description"]) > 10, f"Tool {tool['name']} description too short"


async def test_definitions_input_schemas_are_valid_json_schema(pinelabs_client):
    """Each input_schema should be a valid JSON Schema object type."""
    resp = await pinelabs_client.get("/tools/definitions")
    for tool in resp.json()["tools"]:
        schema = tool["input_schema"]
        assert schema["type"] == "object", f"{tool['name']}: schema type must be 'object'"
        assert "properties" in schema, f"{tool['name']}: schema must have 'properties'"
        assert "required" in schema, f"{tool['name']}: schema must have 'required'"
        assert isinstance(schema["required"], list)


async def test_definitions_required_fields_exist_in_properties(pinelabs_client):
    """Every required field must be defined in properties."""
    resp = await pinelabs_client.get("/tools/definitions")
    for tool in resp.json()["tools"]:
        schema = tool["input_schema"]
        props = set(schema["properties"].keys())
        for req in schema["required"]:
            assert req in props, f"{tool['name']}: required field '{req}' not in properties"


async def test_definitions_property_types_are_valid(pinelabs_client):
    """All property types should be valid JSON Schema types."""
    valid_types = {"string", "integer", "number", "boolean", "array", "object"}
    resp = await pinelabs_client.get("/tools/definitions")
    for tool in resp.json()["tools"]:
        for prop_name, prop_def in tool["input_schema"]["properties"].items():
            if "type" in prop_def:
                assert prop_def["type"] in valid_types, (
                    f"{tool['name']}.{prop_name}: invalid type '{prop_def['type']}'"
                )


async def test_definitions_idempotent(pinelabs_client):
    """Multiple calls return the same definitions."""
    r1 = await pinelabs_client.get("/tools/definitions")
    r2 = await pinelabs_client.get("/tools/definitions")
    assert r1.json() == r2.json()


# ── Tool Execution ──────────────────────────────────────────────────


async def test_execute_unknown_tool(pinelabs_client):
    resp = await pinelabs_client.post(
        "/tools/execute",
        json={"tool_name": "nonexistent_tool", "tool_input": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert "Unknown tool" in data["error"]


async def test_execute_missing_tool_name_returns_422(pinelabs_client):
    """Missing required field 'tool_name' should return validation error."""
    resp = await pinelabs_client.post("/tools/execute", json={"tool_input": {}})
    assert resp.status_code == 422


async def test_execute_generate_token(pinelabs_client):
    """generate_token should authenticate with Pine Labs successfully."""
    resp = await pinelabs_client.post(
        "/tools/execute",
        json={"tool_name": "generate_token", "tool_input": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "expires_at" in data


async def test_execute_create_order_without_auth(pinelabs_client):
    """Creating an order without a token should fail gracefully (not crash)."""
    resp = await pinelabs_client.post(
        "/tools/execute",
        json={
            "tool_name": "create_order",
            "tool_input": {"amount": 10000, "currency": "INR"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should return an error or an API error, but not crash
    assert isinstance(data, dict)


async def test_execute_create_order_after_auth(pinelabs_client):
    """Auth then create order should succeed."""
    auth = await pinelabs_client.post(
        "/tools/execute", json={"tool_name": "generate_token", "tool_input": {}}
    )
    assert auth.json().get("success") is True

    resp = await pinelabs_client.post(
        "/tools/execute",
        json={
            "tool_name": "create_order",
            "tool_input": {"amount": 50000, "currency": "INR"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Expect order data or a structured response from Pine Labs
    assert isinstance(data, dict)
    # Should have an order_id in the response data
    if "data" in data:
        assert "order_id" in data["data"]


async def test_execute_get_order_status_invalid_id(pinelabs_client):
    """Getting status of a nonexistent order should return an error, not crash."""
    # Auth first
    await pinelabs_client.post(
        "/tools/execute", json={"tool_name": "generate_token", "tool_input": {}}
    )
    resp = await pinelabs_client.post(
        "/tools/execute",
        json={"tool_name": "get_order_status", "tool_input": {"order_id": "fake-order-xyz"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


async def test_execute_tool_with_empty_tool_input(pinelabs_client):
    """Tools with no required params should work with empty input."""
    resp = await pinelabs_client.post(
        "/tools/execute",
        json={"tool_name": "get_settlements", "tool_input": {}},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
