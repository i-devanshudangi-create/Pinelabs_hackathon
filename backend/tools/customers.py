import uuid
from .pine_client import api_post


async def create_customer(**kwargs) -> dict:
    """Create a new customer in Pine Labs Plural."""
    body = {
        "merchant_customer_reference": kwargs.get("merchant_customer_reference", str(uuid.uuid4())),
        "first_name": kwargs["first_name"],
        "last_name": kwargs["last_name"],
        "email_id": kwargs["email"],
        "mobile_number": kwargs["phone"],
        "country_code": "91",
    }
    result = await api_post("/pay/v1/customers", body)
    return result
