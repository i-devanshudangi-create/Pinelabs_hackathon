"""Shared HTTP client for Pine Labs API calls."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx

from config import PINE_LABS_BASE_URL

_token_cache: dict = {"access_token": None, "expires_at": None}


def _headers(access_token: str | None = None) -> dict:
    h = {
        "Content-Type": "application/json",
        "Request-Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "Request-ID": str(uuid.uuid4()),
    }
    token = access_token or _token_cache.get("access_token")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def cache_token(access_token: str, expires_at: str):
    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = expires_at


def get_cached_token() -> str | None:
    return _token_cache.get("access_token")


async def api_post(path: str, body: dict, access_token: str | None = None) -> dict:
    url = f"{PINE_LABS_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=body, headers=_headers(access_token))
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}


async def api_get(path: str, params: dict | None = None, access_token: str | None = None) -> dict:
    url = f"{PINE_LABS_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=_headers(access_token))
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}


async def api_put(path: str, body: dict, access_token: str | None = None) -> dict:
    url = f"{PINE_LABS_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, json=body, headers=_headers(access_token))
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}


async def api_patch(path: str, body: dict, access_token: str | None = None) -> dict:
    url = f"{PINE_LABS_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(url, json=body, headers=_headers(access_token))
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}
