from .pine_client import api_get


async def get_settlements(**kwargs) -> dict:
    """Get settlement information, optionally filtered by UTR or date range."""
    params = {}
    if kwargs.get("utr"):
        path = f"/pay/v1/settlements/utr/{kwargs['utr']}"
        result = await api_get(path)
        return result

    if kwargs.get("from_date"):
        params["from_date"] = kwargs["from_date"]
    if kwargs.get("to_date"):
        params["to_date"] = kwargs["to_date"]

    result = await api_get("/pay/v1/settlements", params=params if params else None)
    return result
