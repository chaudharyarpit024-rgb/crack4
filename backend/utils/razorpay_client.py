import json
import httpx
from fastapi import HTTPException
from config.settings import RZP_KEY_ID, RZP_KEY_SECRET, RZP_LIVE, logger


async def razorpay_req(method: str, path: str, **kwargs):
    """Execute authenticated HTTP requests against the Razorpay API."""
    if not RZP_LIVE:
        logger.warning("Attempted Razorpay request %s %s but Razorpay is not configured", method, path)
        raise HTTPException(
            503,
            "Payment service is temporarily unavailable. Please try again later.",
        )
    try:
        async with httpx.AsyncClient(
            base_url="https://api.razorpay.com",
            auth=(RZP_KEY_ID, RZP_KEY_SECRET),
            timeout=20,
        ) as c:
            r = await c.request(method, path, **kwargs)
    except httpx.RequestError:
        logger.exception("Network error calling Razorpay %s %s", method, path)
        raise HTTPException(502, "Payment provider unreachable. Please try again later.")

    if r.is_error:
        logger.error("Razorpay %s %s failed: status=%s body=%.500s", method, path, r.status_code, r.text)
        raise HTTPException(502, "Payment provider returned an error. Please try again later.")

    try:
        return r.json()
    except json.JSONDecodeError:
        logger.error("Razorpay %s %s returned non-JSON response: %.200s", method, path, r.text)
        raise HTTPException(502, "Payment provider returned an unexpected response. Please try again later.")
