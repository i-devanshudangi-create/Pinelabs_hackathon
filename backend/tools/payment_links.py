import uuid
from .pine_client import api_post


async def create_payment_link(**kwargs) -> dict:
    """Generate a shareable payment link."""
    body = {
        "merchant_payment_link_reference": str(uuid.uuid4()),
        "payment_link_amount": {
            "value": kwargs["amount"],
            "currency": kwargs.get("currency", "INR"),
        },
        "description": kwargs.get("description", "Payment"),
    }
    if kwargs.get("customer_name"):
        body["customer"] = {
            "name": kwargs["customer_name"],
        }
        if kwargs.get("customer_email"):
            body["customer"]["email_id"] = kwargs["customer_email"]
        if kwargs.get("customer_phone"):
            body["customer"]["mobile_number"] = kwargs["customer_phone"]

    if kwargs.get("expiry_minutes"):
        body["expiry_in_minutes"] = kwargs["expiry_minutes"]

    result = await api_post("/pay/v1/payment-links", body)
    return result
