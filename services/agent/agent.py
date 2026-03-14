"""Core agent logic: Bedrock Claude with tool-use loop, streams events as NDJSON."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator

import boto3
import httpx

from config import (
    AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN,
    BEDROCK_MODEL_ID, PINELABS_SERVICE_URL,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PlurAgent — an intelligent AI commerce assistant powered by Pine Labs Plural payment APIs.

You are connected to a LIVE Pine Labs test environment (Merchant ID: 121524) and can execute REAL API calls.

You help users and merchants with the full commerce lifecycle:
- Creating customers, orders, and payments
- Discovering the best EMI/BNPL offers for purchases
- Processing UPI, card, wallet, and net banking payments
- Managing refunds, settlements, and subscriptions
- Generating payment links for customers
- Handling cross-border currency conversions
- Calculating convenience fees

ACTIVE PAYMENT METHODS on this merchant account:
- Credit/Debit Cards: Visa, Mastercard, Maestro, Amex, Diners, RuPay (ACTIVE)
- UPI: Intent + Collect modes (ACTIVE)
- Netbanking: IDBI, Kotak, Andhra Bank, Allahabad Bank, and 93+ more (ACTIVE)
- Wallets: Airtel Money, Freecharge, Mobikwik, Oxigen, Paycash, and more (ACTIVE)
- EMI: Currently INACTIVE on this account
- Brand Wallet: Currently INACTIVE on this account

IMPORTANT RULES:
1. Always call generate_token first before making any other Pine Labs API call, unless you already have a valid token in this conversation.
2. When creating orders, amounts are in PAISA (100 paisa = ₹1). So ₹45,000 = 4500000 paisa.
3. For payments, you need an order_id first — always create an order before creating a payment.
4. When the user asks about offers/EMI, use discover_offers to find real-time options.
5. Be proactive: if a user wants to buy something, guide them through the full flow (customer → order → offer discovery → payment).
6. Present financial information clearly with formatting (₹ symbol, tables of EMI options, etc.).
7. For UPI payments, you need the customer's VPA (like name@upi). UPI supports both Intent and Collect modes.
8. Always confirm with the user before executing a payment or refund.
9. When showing amounts, convert from paisa to rupees for readability.
10. This is a TEST environment — only test transactions will be processed. Test card: 4012001037141112 (Visa), Expiry: any future date, CVV: 123.
11. For UPI test, use VPA: success@upi for successful payments or failure@upi for failed payments.

Be concise, helpful, and action-oriented. Guide users step-by-step through commerce workflows."""

_bedrock_client = None
_tool_definitions_cache: list[dict] | None = None


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        kwargs = {"region_name": AWS_REGION}
        if AWS_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
            if AWS_SESSION_TOKEN:
                kwargs["aws_session_token"] = AWS_SESSION_TOKEN
        _bedrock_client = boto3.client("bedrock-runtime", **kwargs)
    return _bedrock_client


async def _fetch_tool_definitions() -> list[dict]:
    """Fetch tool definitions from the Pine Labs service (cached after first call)."""
    global _tool_definitions_cache
    if _tool_definitions_cache is not None:
        return _tool_definitions_cache
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{PINELABS_SERVICE_URL}/tools/definitions")
        data = resp.json()
        _tool_definitions_cache = data["tools"]
    return _tool_definitions_cache


def _build_tool_config(definitions: list[dict]) -> dict:
    return {
        "tools": [
            {"toolSpec": {"name": t["name"], "description": t["description"], "inputSchema": {"json": t["input_schema"]}}}
            for t in definitions
        ]
    }


async def _execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool via the Pine Labs service."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{PINELABS_SERVICE_URL}/tools/execute",
            json={"tool_name": tool_name, "tool_input": tool_input},
        )
        return resp.json()


def _convert_messages(messages: list[dict]) -> list[dict]:
    bedrock_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            bedrock_msgs.append({
                "role": role,
                "content": [{"text": content}] if isinstance(content, str) else content,
            })
    return bedrock_msgs


async def run_agent_stream(messages: list[dict]) -> AsyncIterator[str]:
    """
    Run the agent loop and yield NDJSON events:
      {"type": "tool_call",   "data": {...}}
      {"type": "tool_result", "data": {...}}
      {"type": "response",    "data": {"response": "...", "tool_calls": [...]}}
    """
    client = _get_bedrock_client()
    definitions = await _fetch_tool_definitions()
    tool_config = _build_tool_config(definitions)
    all_tool_calls: list[dict] = []
    bedrock_messages = _convert_messages(messages)

    for _iteration in range(10):
        try:
            response = await asyncio.to_thread(
                client.converse,
                modelId=BEDROCK_MODEL_ID,
                messages=bedrock_messages,
                system=[{"text": SYSTEM_PROMPT}],
                toolConfig=tool_config,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.3},
            )
        except Exception as e:
            logger.exception("Bedrock API error")
            yield json.dumps({"type": "response", "data": {"response": f"Error communicating with AI: {e}", "tool_calls": all_tool_calls}}) + "\n"
            return

        stop_reason = response.get("stopReason", "")
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        bedrock_messages.append(output_message)

        if stop_reason == "tool_use":
            tool_results = []
            for block in content_blocks:
                if "toolUse" not in block:
                    continue
                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]
                ts = datetime.now(timezone.utc).isoformat()

                yield json.dumps({"type": "tool_call", "data": {"tool_name": tool_name, "tool_input": tool_input, "timestamp": ts}}) + "\n"

                tool_result = await _execute_tool(tool_name, tool_input)
                all_tool_calls.append({"tool_name": tool_name, "tool_input": tool_input, "tool_result": tool_result, "timestamp": ts})

                yield json.dumps({"type": "tool_result", "data": {"tool_name": tool_name, "tool_result": tool_result, "timestamp": ts}}) + "\n"

                tool_results.append({"toolResult": {"toolUseId": tool_use_id, "content": [{"json": tool_result}]}})

            bedrock_messages.append({"role": "user", "content": tool_results})
            continue

        text_response = "".join(b.get("text", "") for b in content_blocks)
        yield json.dumps({"type": "response", "data": {"response": text_response, "tool_calls": all_tool_calls}}) + "\n"
        return

    yield json.dumps({"type": "response", "data": {"response": "Reached maximum steps. Please rephrase your request.", "tool_calls": all_tool_calls}}) + "\n"
