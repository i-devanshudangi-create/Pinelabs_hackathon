import uuid
from .pine_client import api_post, api_get


async def manage_subscription(**kwargs) -> dict:
    """Manage subscriptions: create plan, create subscription, pause, resume, cancel, or get status."""
    action = kwargs["action"]

    if action == "create_plan":
        body = {
            "merchant_plan_reference": str(uuid.uuid4()),
            "plan_name": kwargs.get("plan_name", "Default Plan"),
            "plan_amount": {
                "value": kwargs.get("plan_amount", 0),
                "currency": kwargs.get("currency", "INR"),
            },
            "frequency": kwargs.get("frequency", "MONTHLY"),
        }
        return await api_post("/pay/v1/subscriptions/plans", body)

    elif action == "create_subscription":
        body = {
            "merchant_subscription_reference": str(uuid.uuid4()),
            "plan_id": kwargs.get("plan_id", ""),
        }
        if kwargs.get("customer_id"):
            body["customer_id"] = kwargs["customer_id"]
        return await api_post("/pay/v1/subscriptions", body)

    elif action == "pause":
        sub_id = kwargs.get("subscription_id", "")
        return await api_post(f"/pay/v1/subscriptions/{sub_id}/pause", {})

    elif action == "resume":
        sub_id = kwargs.get("subscription_id", "")
        return await api_post(f"/pay/v1/subscriptions/{sub_id}/resume", {})

    elif action == "cancel":
        sub_id = kwargs.get("subscription_id", "")
        return await api_post(f"/pay/v1/subscriptions/{sub_id}/cancel", {})

    elif action == "get_status":
        sub_id = kwargs.get("subscription_id", "")
        return await api_get(f"/pay/v1/subscriptions/{sub_id}")

    return {"error": f"Unknown subscription action: {action}"}
