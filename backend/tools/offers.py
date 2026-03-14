from .pine_client import api_post


async def discover_offers(**kwargs) -> dict:
    """Discover EMI and BNPL offers for a given amount."""
    body = {
        "order_amount": {
            "value": kwargs["amount"],
            "currency": kwargs.get("currency", "INR"),
        },
    }
    if kwargs.get("card_number"):
        body["card_number"] = kwargs["card_number"]
    if kwargs.get("product_code"):
        body["product_code"] = kwargs["product_code"]

    result = await api_post("/pay/v1/affordability/offer-discovery", body)
    return result
