import uuid
from .pine_client import api_post


async def create_refund(**kwargs) -> dict:
    """Initiate a refund for a processed order."""
    body = {
        "order_id": kwargs["order_id"],
        "payment_id": kwargs["payment_id"],
        "merchant_refund_reference": kwargs.get("merchant_refund_reference", str(uuid.uuid4())),
    }
    if kwargs.get("amount"):
        body["refund_amount"] = {
            "value": kwargs["amount"],
            "currency": kwargs.get("currency", "INR"),
        }

    result = await api_post("/pay/v1/refunds", body)
    return result
