from .pine_client import api_post


async def currency_conversion(**kwargs) -> dict:
    """Convert between currencies for international payments."""
    body = {
        "amount": {
            "value": kwargs["amount"],
            "currency": kwargs["source_currency"],
        },
        "target_currency": kwargs["target_currency"],
    }
    result = await api_post("/pay/v1/international/currency-conversion", body)
    return result
