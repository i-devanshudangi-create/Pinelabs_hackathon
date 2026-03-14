from config import PINE_LABS_CLIENT_ID, PINE_LABS_CLIENT_SECRET
from .pine_client import api_post, cache_token


async def generate_token(**kwargs) -> dict:
    """Authenticate with Pine Labs and obtain a Bearer access token."""
    body = {
        "client_id": PINE_LABS_CLIENT_ID,
        "client_secret": PINE_LABS_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    result = await api_post("/auth/v1/token", body)

    if "access_token" in result:
        cache_token(result["access_token"], result.get("expires_at", ""))
        return {
            "success": True,
            "message": "Authentication successful",
            "expires_at": result.get("expires_at", ""),
        }
    return {"success": False, "error": result}
