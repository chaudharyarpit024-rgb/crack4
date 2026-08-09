import httpx
from fastapi import HTTPException
from config.settings import RZP_KEY_ID, RZP_KEY_SECRET, RZP_LIVE, logger


async def razorpay_req(method: str, path: str, **kwargs):
    """Execute authenticated HTTP requests against the Razorpay API."""
    if not RZP_LIVE:
        raise HTTPException(
            503,
            "Razorpay is not configured. Add RAZORPAY_KEY_ID/SECRET/PLAN_ID in backend/.env.",
        )
    async with httpx.AsyncClient(
        base_url="https://api.razorpay.com",
        auth=(RZP_KEY_ID, RZP_KEY_SECRET),
        timeout=20,
    ) as c:
        r = await c.request(method, path, **kwargs)
        if r.is_error:
            logger.error(f"Razorpay {method} {path} failed: {r.status_code} {r.text}")
            raise HTTPException(502, f"Razorpay error: {r.status_code}")
        return r.json()
