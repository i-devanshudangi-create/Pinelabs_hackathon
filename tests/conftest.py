"""Shared fixtures for PlurAgent microservices test suite."""
from __future__ import annotations

import pytest
import httpx

PINELABS_URL = "http://localhost:8002"
AGENT_URL = "http://localhost:8001"
GATEWAY_URL = "http://localhost:8000"


@pytest.fixture
def pinelabs_url():
    return PINELABS_URL


@pytest.fixture
def agent_url():
    return AGENT_URL


@pytest.fixture
def gateway_url():
    return GATEWAY_URL


@pytest.fixture
async def pinelabs_client():
    async with httpx.AsyncClient(base_url=PINELABS_URL, timeout=10) as client:
        yield client


@pytest.fixture
async def agent_client():
    async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as client:
        yield client


@pytest.fixture
async def gateway_client():
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120) as client:
        yield client


@pytest.fixture
def unique_session_id():
    """Return a unique session ID for test isolation."""
    import uuid
    return f"test-{uuid.uuid4().hex[:8]}"


EXPECTED_TOOLS = [
    "generate_token",
    "create_customer",
    "create_order",
    "get_order_status",
    "create_payment",
    "discover_offers",
    "create_refund",
    "get_settlements",
    "create_payment_link",
    "manage_subscription",
    "calculate_convenience_fee",
    "currency_conversion",
]
