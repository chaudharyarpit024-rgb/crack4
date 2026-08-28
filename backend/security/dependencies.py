from fastapi import HTTPException, Header, Depends, Request
from typing import Optional
from database.mongodb import db
from security.jwt import decode_token
from utils.subscription import ensure_trial, sub_public


async def current_user(
    request: Request = None,
    authorization: Optional[str] = Header(None),
) -> dict:
    """FastAPI dependency to extract and validate current authenticated user from Bearer JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(401, "User not found")

    from security.rate_limiter import rate_limiter
    allowed, retry_after, headers = rate_limiter.check_user_rate_limit(user["id"])
    if request and hasattr(request, "state"):
        request.state.rate_limit_headers = headers

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please try again in {retry_after} seconds.",
            headers=headers,
        )

    return user


async def require_active_subscription(user: dict = Depends(current_user)) -> dict:
    """FastAPI dependency ensuring the authenticated user has an active trial or paid subscription."""
    sub = await ensure_trial(user["id"])
    pub = sub_public(sub)
    if not pub["active"]:
        raise HTTPException(402, "Subscription required. Your free trial has ended.")
    return user
