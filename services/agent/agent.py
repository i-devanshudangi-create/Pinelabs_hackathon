"""Core agent logic: Bedrock Claude with tool-use loop, streams events as NDJSON."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
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
- Reconciling transactions across orders, payments, and settlements

ACTIVE PAYMENT METHODS on this merchant account:
- Credit/Debit Cards: Visa, Mastercard, Maestro, Amex, Diners, RuPay (ACTIVE)
- UPI: Intent + Collect modes (ACTIVE)
- Netbanking: IDBI, Kotak, Andhra Bank, Allahabad Bank, and 93+ more (ACTIVE)
- Wallets: Airtel Money, Freecharge, Mobikwik, Oxigen, Paycash, and more (ACTIVE)
- EMI: Currently INACTIVE on this account
- Brand Wallet: Currently INACTIVE on this account

═══════════════════════════════════════════
INTELLIGENT DECISIONING RULES:
═══════════════════════════════════════════
Before executing any payment, you MUST evaluate the optimal path:
1. ALWAYS check discover_offers first to find available EMI/BNPL options for the amount.
2. ALWAYS calculate convenience fees for at least 2 payment methods (e.g., CARD vs UPI) using calculate_convenience_fee.
3. Compare options and EXPLICITLY recommend the best choice with reasoning:
   - "I recommend UPI because: zero convenience fee vs ₹150 for card, and instant settlement."
   - "Card payment is better here because: 3-month no-cost EMI available, saving ₹2,400 in interest."
4. Present your decision reasoning clearly BEFORE executing the chosen action.

═══════════════════════════════════════════
SMART RETRY ENGINE:
═══════════════════════════════════════════
When any API call or payment FAILS:
1. Analyze the specific error message and failure reason.
2. Do NOT give up after first failure. Follow this fallback chain:
   - CARD failed → Try UPI (suggest success@upi for testing)
   - UPI failed → Try WALLET
   - WALLET failed → Try NETBANKING
   - NETBANKING failed → Try BNPL
   - All methods failed → Generate a payment link as final fallback
3. For each retry, explain WHY you're switching: "Card payment failed due to insufficient funds. Trying UPI as fallback — zero convenience fee and different payment rail."
4. Track and report all attempts: "Attempt 1/3: Card → Failed (auth declined). Attempt 2/3: UPI → Processing..."

═══════════════════════════════════════════
AGENTIC CHECKOUT ORCHESTRATION:
═══════════════════════════════════════════
When a user expresses purchase intent (e.g., "buy X for ₹Y", "I want to purchase", "checkout"):
Execute the FULL autonomous checkout pipeline WITHOUT asking for each step:
1. generate_token (authenticate)
2. discover_offers (find best deals for the amount)
3. calculate_convenience_fee for CARD and UPI (compare costs)
4. create_order (with the amount)
5. Present the BEST option with reasoning (offers + lowest fee)
6. create_payment_link (so customer can pay via any method)
7. Report the complete summary with payment link

For each step, announce what you're doing: "Step 1/6: Authenticating..." "Step 2/6: Discovering offers for ₹50,000..."

═══════════════════════════════════════════
SMART RECONCILIATION:
═══════════════════════════════════════════
When asked to reconcile or check transaction health:
1. Use reconcile_transactions to cross-reference orders, payments, and settlements.
2. Report mismatches clearly: paid but unsettled, created but unpaid, refunded amounts.
3. Provide actionable suggestions for each mismatch.

═══════════════════════════════════════════
CORE RULES:
═══════════════════════════════════════════
1. Always call generate_token first before making any other Pine Labs API call, unless you already have a valid token in this conversation.
2. When creating orders, amounts are in PAISA (100 paisa = ₹1). So ₹45,000 = 4500000 paisa.
3. For payments, you need an order_id first — always create an order before creating a payment.
4. When the user asks about offers/EMI, use discover_offers to find real-time options.
5. Be proactive: if a user wants to buy something, guide them through the full flow.
6. Present financial information clearly with formatting (₹ symbol, tables of EMI options, etc.).
7. For UPI payments, you need the customer's VPA (like name@upi). UPI supports both Intent and Collect modes.
8. Always confirm with the user before executing a payment or refund.
9. When showing amounts, convert from paisa to rupees for readability.
10. This is a TEST environment — only test transactions will be processed. Test card: 4012001037141112 (Visa), Expiry: any future date, CVV: 123.
11. For UPI test, use VPA: success@upi for successful payments or failure@upi for failed payments.

Be concise, helpful, and action-oriented. Guide users step-by-step through commerce workflows."""

_bedrock_client = None
_tool_definitions_cache: list[dict] | None = None

CHECKOUT_TOOLS = [
    "generate_token", "discover_offers", "calculate_convenience_fee",
    "create_order", "create_payment", "create_payment_link",
]

PAYMENT_METHODS_FALLBACK = ["CARD", "UPI", "WALLET", "NETBANKING", "BNPL"]


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


def _detect_workflow(messages: list[dict]) -> tuple[bool, str, int]:
    """Detect if the user message implies a multi-step workflow (checkout, reconciliation, etc.)."""
    if not messages:
        return False, "", 0
    last_msg = messages[-1].get("content", "").lower() if isinstance(messages[-1].get("content"), str) else ""
    checkout_keywords = ["buy", "purchase", "checkout", "order", "pay for", "emi", "best deal", "laptop", "phone", "want to get"]
    recon_keywords = ["reconcile", "reconciliation", "mismatch", "unsettle", "transaction health"]
    for kw in checkout_keywords:
        if kw in last_msg:
            return True, "checkout", 7
    for kw in recon_keywords:
        if kw in last_msg:
            return True, "reconciliation", 3
    return False, "", 0


def _is_failure(tool_result: dict) -> bool:
    """Check if a tool result indicates failure."""
    if tool_result.get("error"):
        return True
    if tool_result.get("success") is False:
        return True
    data = tool_result.get("data", {})
    if isinstance(data, dict) and data.get("status") in ("FAILED", "DECLINED", "REJECTED"):
        return True
    return False


async def run_agent_stream(messages: list[dict]) -> AsyncIterator[str]:
    """
    Run the agent loop and yield NDJSON events:
      {"type": "tool_call",      "data": {...}}
      {"type": "tool_result",    "data": {...}}
      {"type": "decision",       "data": {...}}
      {"type": "workflow_step",  "data": {...}}
      {"type": "response",       "data": {"response": "...", "tool_calls": [...]}}
    """
    client = _get_bedrock_client()
    definitions = await _fetch_tool_definitions()
    tool_config = _build_tool_config(definitions)
    all_tool_calls: list[dict] = []
    bedrock_messages = _convert_messages(messages)

    is_workflow, workflow_type, total_steps = _detect_workflow(messages)
    workflow_id = str(uuid.uuid4())[:8] if is_workflow else None
    step_index = 0
    retry_count = 0
    failed_methods: list[str] = []

    if is_workflow:
        yield json.dumps({"type": "workflow_step", "data": {
            "workflow_id": workflow_id,
            "step_index": 0,
            "total_steps": total_steps,
            "step_name": "Starting" if workflow_type == "checkout" else "Analyzing",
            "status": "running",
            "workflow_type": workflow_type,
        }}) + "\n"

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
                if "text" in block:
                    text = block["text"]
                    decision = _extract_decision(text)
                    if decision:
                        yield json.dumps({"type": "decision", "data": decision}) + "\n"

                if "toolUse" not in block:
                    continue
                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]
                ts = datetime.now(timezone.utc).isoformat()

                if is_workflow:
                    if step_index == 0:
                        yield json.dumps({"type": "workflow_step", "data": {
                            "workflow_id": workflow_id,
                            "step_index": 0,
                            "total_steps": total_steps,
                            "step_name": "Starting" if workflow_type == "checkout" else "Analyzing",
                            "status": "success",
                            "workflow_type": workflow_type,
                        }}) + "\n"
                    step_index += 1
                    step_label = _get_step_label(tool_name)
                    yield json.dumps({"type": "workflow_step", "data": {
                        "workflow_id": workflow_id,
                        "step_index": step_index,
                        "total_steps": max(total_steps, step_index + 1),
                        "step_name": step_label,
                        "status": "running",
                        "tool_name": tool_name,
                        "workflow_type": workflow_type,
                    }}) + "\n"

                yield json.dumps({"type": "tool_call", "data": {"tool_name": tool_name, "tool_input": tool_input, "timestamp": ts}}) + "\n"

                tool_result = await _execute_tool(tool_name, tool_input)
                all_tool_calls.append({"tool_name": tool_name, "tool_input": tool_input, "tool_result": tool_result, "timestamp": ts})

                yield json.dumps({"type": "tool_result", "data": {"tool_name": tool_name, "tool_result": tool_result, "timestamp": ts}}) + "\n"

                if is_workflow:
                    status = "failed" if _is_failure(tool_result) else "success"
                    yield json.dumps({"type": "workflow_step", "data": {
                        "workflow_id": workflow_id,
                        "step_index": step_index,
                        "total_steps": max(total_steps, step_index + 1),
                        "step_name": _get_step_label(tool_name),
                        "status": status,
                        "tool_name": tool_name,
                        "workflow_type": workflow_type,
                    }}) + "\n"

                if _is_failure(tool_result) and tool_name == "create_payment":
                    retry_count += 1
                    method = tool_input.get("payment_method", "UNKNOWN")
                    failed_methods.append(method)
                    remaining = [m for m in PAYMENT_METHODS_FALLBACK if m not in failed_methods]
                    if remaining:
                        yield json.dumps({"type": "decision", "data": {
                            "title": f"Payment Retry (Attempt {retry_count + 1})",
                            "reasoning": f"{method} payment failed. Switching to {remaining[0]} as fallback.",
                            "options_considered": [
                                {"option": method, "verdict": f"Failed — {tool_result.get('error', 'declined')}"},
                                {"option": remaining[0], "verdict": "Next in fallback chain"},
                            ],
                            "chosen": remaining[0],
                            "confidence": "medium",
                        }}) + "\n"

                tool_results.append({"toolResult": {"toolUseId": tool_use_id, "content": [{"json": tool_result}]}})

            bedrock_messages.append({"role": "user", "content": tool_results})
            continue

        for block in content_blocks:
            if "text" in block:
                decision = _extract_decision(block["text"])
                if decision:
                    yield json.dumps({"type": "decision", "data": decision}) + "\n"

        text_response = "".join(b.get("text", "") for b in content_blocks)

        if is_workflow:
            yield json.dumps({"type": "workflow_step", "data": {
                "workflow_id": workflow_id,
                "step_index": step_index + 1,
                "total_steps": step_index + 2,
                "step_name": "Done",
                "status": "success",
                "workflow_type": workflow_type,
            }}) + "\n"

        yield json.dumps({"type": "response", "data": {"response": text_response, "tool_calls": all_tool_calls}}) + "\n"
        return

    yield json.dumps({"type": "response", "data": {"response": "Reached maximum steps. Please rephrase your request.", "tool_calls": all_tool_calls}}) + "\n"


def _get_step_label(tool_name: str) -> str:
    labels = {
        "generate_token": "Authenticating",
        "create_customer": "Creating Customer",
        "create_order": "Creating Order",
        "get_order_status": "Checking Order",
        "create_payment": "Processing Payment",
        "discover_offers": "Discovering Offers",
        "create_refund": "Processing Refund",
        "get_settlements": "Fetching Settlements",
        "create_payment_link": "Generating Payment Link",
        "manage_subscription": "Managing Subscription",
        "calculate_convenience_fee": "Comparing Fees",
        "currency_conversion": "Converting Currency",
        "reconcile_transactions": "Reconciling",
        "analyze_activity": "Analyzing Activity",
    }
    return labels.get(tool_name, tool_name.replace("_", " ").title())


def _extract_decision(text: str) -> dict | None:
    """Extract decision reasoning from Claude's text response using pattern matching."""
    recommend_patterns = [
        r"(?i)I recommend (.+?) because[:\s]+(.+?)(?:\.|$)",
        r"(?i)Best option[:\s]+(.+?)(?:—|-)(.+?)(?:\.|$)",
        r"(?i)(?:comparing|analysis)[:\s]+(.+?)(?:\.|$)",
    ]
    for pattern in recommend_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            chosen = groups[0].strip() if len(groups) > 0 else ""
            reasoning = groups[1].strip() if len(groups) > 1 else groups[0].strip()
            return {
                "title": "Payment Decision",
                "reasoning": reasoning[:300],
                "options_considered": [],
                "chosen": chosen[:100],
                "confidence": "high",
            }

    fee_pattern = r"(?i)(convenience fee|fee comparison|cost comparison)"
    if re.search(fee_pattern, text):
        return {
            "title": "Fee Comparison",
            "reasoning": text[:300].strip(),
            "options_considered": [],
            "chosen": "",
            "confidence": "medium",
        }
    return None
