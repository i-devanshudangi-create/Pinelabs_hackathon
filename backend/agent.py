"""Core agent logic: Bedrock Claude client with tool-use loop."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import boto3

from config import AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, BEDROCK_MODEL_ID
from tools import TOOL_REGISTRY, TOOL_DEFINITIONS

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
- Wallets: Airtel Money, Freecharge, ICC Cash Card, Itz Cash Card, Mobikwik, Oxigen, Paycash, and more (ACTIVE)
- EMI: Currently INACTIVE on this account
- Brand Wallet: Currently INACTIVE on this account

IMPORTANT RULES:
1. Always call generate_token first before making any other Pine Labs API call, unless you already have a valid token in this conversation.
2. When creating orders, amounts are in PAISA (100 paisa = ₹1). So ₹45,000 = 4500000 paisa.
3. For payments, you need an order_id first — always create an order before creating a payment.
4. When the user asks about offers/EMI, use discover_offers to find real-time options. Note that EMI is inactive, so mention this if relevant.
5. Be proactive: if a user wants to buy something, guide them through the full flow (customer → order → offer discovery → payment).
6. Present financial information clearly with formatting (₹ symbol, tables of EMI options, etc.).
7. For UPI payments, you need the customer's VPA (like name@upi). UPI supports both Intent and Collect modes.
8. Always confirm with the user before executing a payment or refund.
9. When showing amounts, convert from paisa to rupees for readability.
10. You are talking to the user via a chat interface. A live dashboard on the right shows transactions in real-time.
11. This is a TEST environment — only test transactions will be processed. Test card: 4012001037141112 (Visa), Expiry: any future date, CVV: 123.
12. For UPI test, use VPA: success@upi for successful payments or failure@upi for failed payments.

Be concise, helpful, and action-oriented. Guide users step-by-step through commerce workflows. When demonstrating capabilities, don't hesitate to execute real test API calls to show the system working live."""


def _get_bedrock_client():
    kwargs = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
        if AWS_SESSION_TOKEN:
            kwargs["aws_session_token"] = AWS_SESSION_TOKEN
    return boto3.client("bedrock-runtime", **kwargs)


def _build_tool_config() -> dict:
    return {
        "tools": [
            {"toolSpec": {"name": t["name"], "description": t["description"], "inputSchema": {"json": t["input_schema"]}}}
            for t in TOOL_DEFINITIONS
        ]
    }


async def run_agent(messages: list[dict], on_event=None) -> dict:
    """
    Run the agent loop. Sends messages to Bedrock Claude, handles tool use
    calls by executing the corresponding Pine Labs API tool, feeds results
    back, and repeats until the model produces a final text response.

    on_event: async callback(event_type, data) for streaming UI updates.
    Returns {"response": str, "tool_calls": list[dict]}
    """
    client = _get_bedrock_client()
    tool_config = _build_tool_config()
    all_tool_calls = []

    bedrock_messages = _convert_messages(messages)

    for _iteration in range(10):
        try:
            response = client.converse(
                modelId=BEDROCK_MODEL_ID,
                messages=bedrock_messages,
                system=[{"text": SYSTEM_PROMPT}],
                toolConfig=tool_config,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.3},
            )
        except Exception as e:
            logger.exception("Bedrock API error")
            return {"response": f"Error communicating with AI: {str(e)}", "tool_calls": all_tool_calls}

        stop_reason = response.get("stopReason", "")
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])

        bedrock_messages.append(output_message)

        if stop_reason == "tool_use":
            tool_results = []
            for block in content_blocks:
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})
                    tool_use_id = tool_use["toolUseId"]

                    if on_event:
                        await on_event("tool_call", {
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                    tool_result = await _execute_tool(tool_name, tool_input)
                    all_tool_calls.append({
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_result": tool_result,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                    if on_event:
                        await on_event("tool_result", {
                            "tool_name": tool_name,
                            "tool_result": tool_result,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"json": tool_result}],
                        }
                    })

            bedrock_messages.append({"role": "user", "content": tool_results})
            continue

        text_response = ""
        for block in content_blocks:
            if "text" in block:
                text_response += block["text"]

        return {"response": text_response, "tool_calls": all_tool_calls}

    return {"response": "I've reached the maximum number of steps. Please try rephrasing your request.", "tool_calls": all_tool_calls}


async def _execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a registered tool and return the result."""
    fn = TOOL_REGISTRY.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        result = await fn(**tool_input)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as e:
        logger.exception(f"Tool execution error: {tool_name}")
        return {"error": str(e)}


def _convert_messages(messages: list[dict]) -> list[dict]:
    """Convert frontend message format to Bedrock Converse format."""
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
