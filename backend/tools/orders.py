import uuid
from .pine_client import api_post, api_get


async def create_order(**kwargs) -> dict:
    """Create a new payment order."""
    body = {
        "merchant_order_reference": kwargs.get("merchant_order_reference", str(uuid.uuid4())),
        "order_amount": {
            "value": kwargs["amount"],
            "currency": kwargs.get("currency", "INR"),
        },
        "notes": kwargs.get("notes", ""),
    }
    if kwargs.get("customer_id"):
        body["purchase_details"] = {
            "customer": {"customer_id": kwargs["customer_id"]}
        }
    if kwargs.get("callback_url"):
        body["callback_url"] = kwargs["callback_url"]

    result = await api_post("/pay/v1/orders", body)
    return result


async def get_order_status(**kwargs) -> dict:
    """Get the current status of an order."""
    order_id = kwargs["order_id"]
    result = await api_get(f"/pay/v1/orders/{order_id}")
    return result
