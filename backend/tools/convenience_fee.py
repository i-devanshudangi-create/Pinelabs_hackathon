from .pine_client import api_post


async def calculate_convenience_fee(**kwargs) -> dict:
    """Calculate the convenience fee for a transaction."""
    body = {
        "order_amount": {
            "value": kwargs["amount"],
            "currency": kwargs.get("currency", "INR"),
        },
        "payment_method": kwargs["payment_method"],
    }
    result = await api_post("/pay/v1/convenience-fee/calculate", body)
    return result
