"""All Pine Labs API tool implementations and their schema definitions."""
from __future__ import annotations

import uuid

from config import PINE_LABS_CLIENT_ID, PINE_LABS_CLIENT_SECRET, PINE_LABS_MID
from pine_client import api_post, api_get, cache_token


# ── Tool implementations ────────────────────────────────────────────


async def generate_token(**kwargs) -> dict:
    body = {
        "client_id": PINE_LABS_CLIENT_ID,
        "client_secret": PINE_LABS_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    result = await api_post("/auth/v1/token", body)
    if "access_token" in result:
        cache_token(result["access_token"], result.get("expires_at", ""))
        return {"success": True, "message": "Authentication successful", "expires_at": result.get("expires_at", "")}
    return {"success": False, "error": result}


async def create_customer(**kwargs) -> dict:
    body = {
        "merchant_customer_reference": kwargs.get("merchant_customer_reference", str(uuid.uuid4())),
        "first_name": kwargs["first_name"],
        "last_name": kwargs["last_name"],
        "email_id": kwargs["email"],
        "mobile_number": kwargs["phone"],
        "country_code": "91",
    }
    return await api_post("/pay/v1/customers", body)


async def create_order(**kwargs) -> dict:
    body = {
        "merchant_order_reference": kwargs.get("merchant_order_reference", str(uuid.uuid4())),
        "order_amount": {"value": kwargs["amount"], "currency": kwargs.get("currency", "INR")},
        "notes": kwargs.get("notes", ""),
    }
    if kwargs.get("customer_id"):
        body["purchase_details"] = {"customer": {"customer_id": kwargs["customer_id"]}}
    if kwargs.get("callback_url"):
        body["callback_url"] = kwargs["callback_url"]
    return await api_post("/pay/v1/orders", body)


async def get_order_status(**kwargs) -> dict:
    return await api_get(f"/pay/v1/orders/{kwargs['order_id']}")


async def create_payment(**kwargs) -> dict:
    order_id = kwargs["order_id"]
    method = kwargs["payment_method"]
    amount = kwargs["amount"]
    currency = kwargs.get("currency", "INR")

    payment_obj = {
        "payment_method": method,
        "merchant_payment_reference": str(uuid.uuid4()),
        "payment_amount": {"value": amount, "currency": currency},
    }

    if method == "UPI":
        upi_mode = kwargs.get("upi_mode", "COLLECT")
        upi_details = {"txn_mode": upi_mode}
        if upi_mode == "COLLECT" and kwargs.get("upi_vpa"):
            upi_details["payer"] = {"vpa": kwargs["upi_vpa"]}
            if kwargs.get("phone"):
                upi_details["payer"]["phone_number"] = kwargs["phone"]
        payment_obj["payment_option"] = {"upi_details": upi_details}
    elif method == "CARD":
        payment_obj["payment_option"] = {
            "card_details": {
                "card_number": kwargs.get("card_number", ""),
                "expiry_month": kwargs.get("card_expiry_month", ""),
                "expiry_year": kwargs.get("card_expiry_year", ""),
                "cvv": kwargs.get("card_cvv", ""),
                "card_holder_name": kwargs.get("card_holder_name", ""),
            }
        }

    body = {"payments": [payment_obj]}
    return await api_post(f"/api/pay/v1/orders/{order_id}/payments", body)


async def discover_offers(**kwargs) -> dict:
    body = {"order_amount": {"value": kwargs["amount"], "currency": kwargs.get("currency", "INR")}}
    if kwargs.get("card_number"):
        body["card_number"] = kwargs["card_number"]
    if kwargs.get("product_code"):
        body["product_code"] = kwargs["product_code"]
    return await api_post("/pay/v1/affordability/offer-discovery", body)


async def create_refund(**kwargs) -> dict:
    body = {
        "order_id": kwargs["order_id"],
        "payment_id": kwargs["payment_id"],
        "merchant_refund_reference": kwargs.get("merchant_refund_reference", str(uuid.uuid4())),
    }
    if kwargs.get("amount"):
        body["refund_amount"] = {"value": kwargs["amount"], "currency": kwargs.get("currency", "INR")}
    return await api_post("/pay/v1/refunds", body)


async def get_settlements(**kwargs) -> dict:
    if kwargs.get("utr"):
        return await api_get(f"/pay/v1/settlements/utr/{kwargs['utr']}")
    params = {}
    if kwargs.get("from_date"):
        params["from_date"] = kwargs["from_date"]
    if kwargs.get("to_date"):
        params["to_date"] = kwargs["to_date"]
    return await api_get("/pay/v1/settlements", params=params if params else None)


async def create_payment_link(**kwargs) -> dict:
    body = {
        "merchant_payment_link_reference": str(uuid.uuid4()),
        "payment_link_amount": {"value": kwargs["amount"], "currency": kwargs.get("currency", "INR")},
        "description": kwargs.get("description", "Payment"),
    }
    if kwargs.get("customer_name"):
        body["customer"] = {"name": kwargs["customer_name"]}
        if kwargs.get("customer_email"):
            body["customer"]["email_id"] = kwargs["customer_email"]
        if kwargs.get("customer_phone"):
            body["customer"]["mobile_number"] = kwargs["customer_phone"]
    if kwargs.get("expiry_minutes"):
        body["expiry_in_minutes"] = kwargs["expiry_minutes"]
    result = await api_post("/pay/v1/payment-links", body)

    url = (result.get("payment_link_url")
           or result.get("data", {}).get("payment_link_url")
           or result.get("url")
           or result.get("data", {}).get("url"))
    if url:
        result["payment_url"] = url
        return result

    # Fallback: construct the Pine Labs checkout URL from an order
    order_result = await api_post("/pay/v1/orders", {
        "merchant_order_reference": body["merchant_payment_link_reference"],
        "order_amount": body["payment_link_amount"],
    })
    order_id = order_result.get("data", {}).get("order_id", "")
    mid = PINE_LABS_MID or "121524"
    if order_id:
        checkout_url = f"https://pci.pluralonline.com/pay/{mid}/{order_id}"
        return {
            "success": True,
            "order_id": order_id,
            "payment_url": checkout_url,
            "description": body["description"],
            "amount": kwargs["amount"],
            "currency": kwargs.get("currency", "INR"),
        }
    return result


async def manage_subscription(**kwargs) -> dict:
    action = kwargs["action"]
    if action == "create_plan":
        body = {
            "merchant_plan_reference": str(uuid.uuid4()),
            "plan_name": kwargs.get("plan_name", "Default Plan"),
            "plan_amount": {"value": kwargs.get("plan_amount", 0), "currency": kwargs.get("currency", "INR")},
            "frequency": kwargs.get("frequency", "MONTHLY"),
        }
        return await api_post("/pay/v1/subscriptions/plans", body)
    elif action == "create_subscription":
        body = {"merchant_subscription_reference": str(uuid.uuid4()), "plan_id": kwargs.get("plan_id", "")}
        if kwargs.get("customer_id"):
            body["customer_id"] = kwargs["customer_id"]
        return await api_post("/pay/v1/subscriptions", body)
    elif action == "pause":
        return await api_post(f"/pay/v1/subscriptions/{kwargs.get('subscription_id', '')}/pause", {})
    elif action == "resume":
        return await api_post(f"/pay/v1/subscriptions/{kwargs.get('subscription_id', '')}/resume", {})
    elif action == "cancel":
        return await api_post(f"/pay/v1/subscriptions/{kwargs.get('subscription_id', '')}/cancel", {})
    elif action == "get_status":
        return await api_get(f"/pay/v1/subscriptions/{kwargs.get('subscription_id', '')}")
    return {"error": f"Unknown subscription action: {action}"}


async def calculate_convenience_fee(**kwargs) -> dict:
    body = {
        "order_amount": {"value": kwargs["amount"], "currency": kwargs.get("currency", "INR")},
        "payment_method": kwargs["payment_method"],
    }
    return await api_post("/pay/v1/convenience-fee/calculate", body)


async def currency_conversion(**kwargs) -> dict:
    body = {
        "amount": {"value": kwargs["amount"], "currency": kwargs["source_currency"]},
        "target_currency": kwargs["target_currency"],
    }
    return await api_post("/pay/v1/international/currency-conversion", body)


async def reconcile_transactions(**kwargs) -> dict:
    """Cross-reference recent orders, payments, and settlements to find mismatches."""
    report = {
        "total_orders": 0, "paid_orders": 0, "unpaid_orders": 0,
        "settled": 0, "unsettled": 0, "refunded": 0,
        "mismatches": [], "summary": "",
    }
    try:
        settlements = await get_settlements()
        settlement_list = settlements.get("data", []) if isinstance(settlements.get("data"), list) else []
        report["settled"] = len(settlement_list)

        settled_order_ids = set()
        for s in settlement_list:
            oid = s.get("order_id", "")
            if oid:
                settled_order_ids.add(oid)

        order_ids = kwargs.get("order_ids", [])
        for oid in order_ids:
            try:
                order = await get_order_status(order_id=oid)
                order_data = order.get("data", order)
                status = order_data.get("status", "UNKNOWN")
                report["total_orders"] += 1

                payments = order_data.get("payments", [])
                has_payment = any(p.get("status") == "PROCESSED" for p in payments)
                has_refund = any(p.get("refund_status") == "REFUNDED" for p in payments)

                if has_payment:
                    report["paid_orders"] += 1
                else:
                    report["unpaid_orders"] += 1

                if has_refund:
                    report["refunded"] += 1

                if has_payment and oid not in settled_order_ids:
                    report["mismatches"].append({
                        "order_id": oid, "type": "PAID_NOT_SETTLED",
                        "message": f"Order {oid} is paid but not yet settled.",
                    })

                if status == "CREATED" and not has_payment:
                    report["mismatches"].append({
                        "order_id": oid, "type": "CREATED_NOT_PAID",
                        "message": f"Order {oid} was created but has no payment.",
                    })
            except Exception as e:
                report["mismatches"].append({"order_id": oid, "type": "ERROR", "message": str(e)})

        report["unsettled"] = report["paid_orders"] - report["settled"]
        total_mismatches = len(report["mismatches"])
        if total_mismatches == 0:
            report["summary"] = f"All {report['total_orders']} orders are healthy. No mismatches found."
        else:
            report["summary"] = f"Found {total_mismatches} mismatch(es) across {report['total_orders']} orders."

    except Exception as e:
        report["summary"] = f"Reconciliation encountered an error: {e}"
        report["mismatches"].append({"type": "SYSTEM_ERROR", "message": str(e)})

    return report


async def analyze_activity(**kwargs) -> dict:
    """Analyze provided activity data for patterns, failure rates, and insights."""
    activities = kwargs.get("activities", [])
    query = kwargs.get("query", "general")

    total_calls = len([a for a in activities if a.get("event") == "tool_call"])
    total_results = len([a for a in activities if a.get("event") == "tool_result"])

    tool_counts: dict[str, int] = {}
    failures: list[dict] = []
    methods_used: dict[str, int] = {}

    for a in activities:
        name = a.get("tool_name", "unknown")
        if a.get("event") == "tool_call":
            tool_counts[name] = tool_counts.get(name, 0) + 1
            if name == "create_payment":
                method = a.get("tool_input", {}).get("payment_method", "UNKNOWN")
                methods_used[method] = methods_used.get(method, 0) + 1
        if a.get("event") == "tool_result":
            result = a.get("tool_result", {})
            if result.get("error") or result.get("success") is False:
                failures.append({"tool": name, "error": str(result.get("error", "unknown"))})

    failure_rate = (len(failures) / total_results * 100) if total_results > 0 else 0
    most_used = max(tool_counts, key=tool_counts.get) if tool_counts else "none"
    popular_method = max(methods_used, key=methods_used.get) if methods_used else "none"

    insights = []
    if failure_rate > 30:
        insights.append({"severity": "danger", "message": f"High failure rate: {failure_rate:.0f}% of API calls failed."})
    elif failure_rate > 10:
        insights.append({"severity": "warning", "message": f"Elevated failure rate: {failure_rate:.0f}%."})
    else:
        insights.append({"severity": "info", "message": f"Healthy failure rate: {failure_rate:.0f}%."})

    if popular_method != "none":
        insights.append({"severity": "info", "message": f"Most popular payment method: {popular_method}."})

    insights.append({"severity": "info", "message": f"Most called API: {most_used} ({tool_counts.get(most_used, 0)} calls)."})

    return {
        "total_api_calls": total_calls,
        "total_results": total_results,
        "failure_rate": round(failure_rate, 1),
        "failures": failures[:10],
        "tool_breakdown": tool_counts,
        "payment_methods": methods_used,
        "insights": insights,
        "query": query,
    }


# ── Registry & definitions ──────────────────────────────────────────

TOOL_REGISTRY: dict[str, callable] = {
    "generate_token": generate_token,
    "create_customer": create_customer,
    "create_order": create_order,
    "get_order_status": get_order_status,
    "create_payment": create_payment,
    "discover_offers": discover_offers,
    "create_refund": create_refund,
    "get_settlements": get_settlements,
    "create_payment_link": create_payment_link,
    "manage_subscription": manage_subscription,
    "calculate_convenience_fee": calculate_convenience_fee,
    "currency_conversion": currency_conversion,
    "reconcile_transactions": reconcile_transactions,
    "analyze_activity": analyze_activity,
}

TOOL_DEFINITIONS = [
    {
        "name": "generate_token",
        "description": "Authenticate with Pine Labs Plural API and obtain a Bearer access token. Must be called before any other Pine Labs API call. Returns an access_token and its expiry.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_customer",
        "description": "Create a new customer profile in the Pine Labs Plural system.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Customer's first name"},
                "last_name": {"type": "string", "description": "Customer's last name"},
                "email": {"type": "string", "description": "Customer's email address"},
                "phone": {"type": "string", "description": "Customer's phone number (10 digits)"},
                "merchant_customer_reference": {"type": "string", "description": "Unique merchant-side customer identifier"},
            },
            "required": ["first_name", "last_name", "email", "phone"],
        },
    },
    {
        "name": "create_order",
        "description": "Create a new payment order. Amount is in paisa (100 paisa = ₹1). Returns an order_id needed for payment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Order amount in paisa (100 paisa = ₹1)"},
                "currency": {"type": "string", "description": "Currency code (e.g. INR)", "default": "INR"},
                "merchant_order_reference": {"type": "string", "description": "Unique merchant-side order reference ID"},
                "notes": {"type": "string", "description": "Optional notes for the order"},
                "customer_id": {"type": "string", "description": "Pine Labs customer ID if available"},
                "callback_url": {"type": "string", "description": "URL to receive payment completion callback"},
            },
            "required": ["amount", "currency"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Get the current status and details of an order by its Pine Labs order ID.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Pine Labs order ID"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "create_payment",
        "description": "Execute a payment against an existing order. Supports CARD, UPI, NETBANKING, WALLET, BNPL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Pine Labs order ID to pay against"},
                "payment_method": {"type": "string", "enum": ["CARD", "UPI", "NETBANKING", "WALLET", "BNPL"], "description": "Payment method"},
                "amount": {"type": "integer", "description": "Payment amount in paisa"},
                "currency": {"type": "string", "description": "Currency code", "default": "INR"},
                "upi_vpa": {"type": "string", "description": "Customer's UPI VPA (for UPI collect)"},
                "upi_mode": {"type": "string", "enum": ["COLLECT", "INTENT", "QR"], "description": "UPI mode", "default": "COLLECT"},
                "card_number": {"type": "string", "description": "Card number (for CARD payment)"},
                "card_expiry_month": {"type": "string", "description": "Card expiry month MM"},
                "card_expiry_year": {"type": "string", "description": "Card expiry year YYYY"},
                "card_cvv": {"type": "string", "description": "Card CVV"},
                "card_holder_name": {"type": "string", "description": "Name on card"},
            },
            "required": ["order_id", "payment_method", "amount"],
        },
    },
    {
        "name": "discover_offers",
        "description": "Discover available EMI and BNPL offers for a given amount.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Transaction amount in paisa"},
                "card_number": {"type": "string", "description": "Card number for card-specific offers (optional)"},
                "product_code": {"type": "string", "description": "Product code for filtering (optional)"},
            },
            "required": ["amount"],
        },
    },
    {
        "name": "create_refund",
        "description": "Initiate a full or partial refund for a processed order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Pine Labs order ID to refund"},
                "payment_id": {"type": "string", "description": "Payment ID within the order to refund"},
                "amount": {"type": "integer", "description": "Refund amount in paisa (omit for full refund)"},
                "merchant_refund_reference": {"type": "string", "description": "Unique merchant-side refund reference"},
            },
            "required": ["order_id", "payment_id"],
        },
    },
    {
        "name": "get_settlements",
        "description": "Get settlement information, optionally filtered by UTR or date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "utr": {"type": "string", "description": "UTR number (optional)"},
                "from_date": {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
                "to_date": {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "create_payment_link",
        "description": "Generate a shareable payment link for customers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Payment amount in paisa"},
                "currency": {"type": "string", "description": "Currency code", "default": "INR"},
                "description": {"type": "string", "description": "Purpose of the payment link"},
                "customer_name": {"type": "string", "description": "Customer name"},
                "customer_email": {"type": "string", "description": "Customer email"},
                "customer_phone": {"type": "string", "description": "Customer phone"},
                "expiry_minutes": {"type": "integer", "description": "Link expiry in minutes", "default": 1440},
            },
            "required": ["amount", "description"],
        },
    },
    {
        "name": "manage_subscription",
        "description": "Manage subscriptions: create plan, create subscription, pause, resume, cancel, or get status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_plan", "create_subscription", "pause", "resume", "cancel", "get_status"], "description": "Subscription action"},
                "plan_name": {"type": "string", "description": "Plan name (for create_plan)"},
                "plan_amount": {"type": "integer", "description": "Plan amount in paisa (for create_plan)"},
                "currency": {"type": "string", "description": "Currency code", "default": "INR"},
                "frequency": {"type": "string", "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"], "description": "Billing frequency"},
                "plan_id": {"type": "string", "description": "Plan ID (for create_subscription)"},
                "subscription_id": {"type": "string", "description": "Subscription ID (for management actions)"},
                "customer_id": {"type": "string", "description": "Customer ID (for create_subscription)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "calculate_convenience_fee",
        "description": "Calculate convenience fee for a transaction based on payment method and amount.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Transaction amount in paisa"},
                "payment_method": {"type": "string", "enum": ["CARD", "UPI", "NETBANKING", "WALLET"], "description": "Payment method"},
            },
            "required": ["amount", "payment_method"],
        },
    },
    {
        "name": "currency_conversion",
        "description": "Convert between currencies for international payments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Amount in paisa of the source currency"},
                "source_currency": {"type": "string", "description": "Source currency code (e.g. INR)"},
                "target_currency": {"type": "string", "description": "Target currency code (e.g. USD, EUR)"},
            },
            "required": ["amount", "source_currency", "target_currency"],
        },
    },
    {
        "name": "reconcile_transactions",
        "description": "Cross-reference orders, payments, and settlements to find mismatches. Provide a list of order_ids to check. Returns a reconciliation report with matched, unmatched, and problematic transactions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Pine Labs order IDs to reconcile",
                },
            },
            "required": [],
        },
    },
    {
        "name": "analyze_activity",
        "description": "Analyze transaction activity for patterns, failure rates, popular payment methods, and generate insights. Pass the recent activity data and an optional query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to analyze: 'general', 'failures', 'methods', 'trends'"},
                "activities": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Array of activity entries with event, tool_name, tool_input, tool_result, timestamp",
                },
            },
            "required": ["query"],
        },
    },
]
