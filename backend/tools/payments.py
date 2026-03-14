import uuid
from .pine_client import api_post


async def create_payment(**kwargs) -> dict:
    """Execute a payment against an existing order."""
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
    result = await api_post(f"/api/pay/v1/orders/{order_id}/payments", body)
    return result
