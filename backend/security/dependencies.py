import logging
from fastapi import HTTPException, Header, Depends, Request
from typing import Optional
from database.mongodb import db
from config.settings import (
    TRIAL_DAILY_MAX_REQUESTS,
    PAID_MONTHLY_MAX_REQUESTS,
    TRIAL_DAILY_MAX_RECIPES,
    PAID_MONTHLY_MAX_RECIPES,
)
from security.jwt import decode_token
from utils.subscription import (
    ensure_trial,
    sub_public,
    try_consume_trial_request,
    try_consume_paid_request,
    try_consume_trial_recipe,
    try_consume_paid_recipe,
    is_unlimited_email,
)

logger = logging.getLogger(__name__)


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
    
    if not user.get("email_verified", False):
        raise HTTPException(403, "Email not verified. Please verify your email to continue.")

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


async def require_active_subscription(
    request: Request,
    user: dict = Depends(current_user),
) -> dict:
    """
    FastAPI dependency ensuring the authenticated user has an active trial or paid subscription,
    or permanent unlimited VIP access.

    Stores the raw subscription doc on request.state so that enforce_quota (which is always
    chained after this dependency) can re-use it without a second database round trip.
    """
    is_unlimited = await is_unlimited_email(user.get("email"))
    sub = await ensure_trial(user["id"])
    pub = sub_public(sub, is_unlimited=is_unlimited)
    if not pub["active"]:
        raise HTTPException(402, "Subscription required. Your free trial has ended.")

    # Cache on request.state so downstream dependencies don't re-fetch.
    request.state.sub = sub
    request.state.sub_pub = pub
    request.state.is_unlimited = is_unlimited
    return user


async def enforce_quota(
    request: Request,
    user: dict = Depends(require_active_subscription),
) -> dict:
    """
    Reserves one AI scan request against the user's quota BEFORE the expensive
    analysis work runs, so concurrent requests can't all slip through before any
    of them registers a count.

    Users with unlimited access bypass quota enforcement completely.

    Security properties:
      • user["id"] comes only from the verified JWT — a client cannot spoof another
        user's ID to consume from a different quota.
      • The DB update is atomic (find_one_and_update) — no TOCTOU window.
      • Fails CLOSED: any DB exception blocks the request rather than granting free access.
      • request.state.{user_id, is_paid} are always set before the route body runs,
        so refund logic in the route always has valid state to read.

    For paid users, the underlying try_consume_paid_request also verifies:
      • subscription status == active/authenticated (blocks lapsed/cancelled users)
      • current billing period has not ended (blocks users who haven't renewed)
    """
    is_unlimited = getattr(request.state, "is_unlimited", False)
    if not is_unlimited:
        is_unlimited = await is_unlimited_email(user.get("email"))

    if is_unlimited:
        request.state.user_id = user["id"]
        request.state.is_paid = True
        request.state.is_unlimited = True
        return user

    # Re-use the subscription fetched by require_active_subscription — no second DB hit.
    sub = getattr(request.state, "sub", None)
    pub = getattr(request.state, "sub_pub", None)

    if sub is None or pub is None:
        # Fallback: should not happen in normal flow, but be defensive.
        sub = await ensure_trial(user["id"])
        pub = sub_public(sub)

    is_paid = pub["paid_active"]

    # Initialise refund-context BEFORE the DB call so the route's except block
    # always has valid state even if the call below raises.
    request.state.user_id = user["id"]
    request.state.is_paid = is_paid

    try:
        if is_paid:
            updated = await try_consume_paid_request(user["id"], PAID_MONTHLY_MAX_REQUESTS)
        else:
            updated = await try_consume_trial_request(user["id"], TRIAL_DAILY_MAX_REQUESTS)
    except Exception:
        # Fail CLOSED: a DB error must not silently grant unmetered access.
        logger.exception("Quota check failed for user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Service temporarily unavailable, try again")

    if updated is None:
        if is_paid:
            # Could mean: quota exhausted, OR subscription lapsed, OR billing period ended.
            # Return 402 (payment required) to prompt the user to renew.
            raise HTTPException(
                status_code=402,
                detail=(
                    "Service unavailable: your monthly scan quota is exhausted or your subscription "
                    "has lapsed. Please renew your subscription to continue."
                ),
            )
        raise HTTPException(
            status_code=402,
            detail="Free daily limit reached (5/5). Try again tomorrow or upgrade to Premium.",
        )

    return user


async def enforce_recipe_quota(
    request: Request,
    user: dict = Depends(require_active_subscription),
) -> dict:
    """
    Enforces recipe suggestion quotas:
      • Free trial: 3 requests per calendar day (UTC)
      • Paid subscribers: 100 requests per billing month
      • Permanent VIP / Unlimited accounts: unrestricted
    """
    is_unlimited = getattr(request.state, "is_unlimited", False)
    if not is_unlimited:
        is_unlimited = await is_unlimited_email(user.get("email"))

    if is_unlimited:
        request.state.user_id = user["id"]
        request.state.is_paid = True
        request.state.is_unlimited = True
        return user

    sub = getattr(request.state, "sub", None)
    pub = getattr(request.state, "sub_pub", None)
    if sub is None or pub is None:
        sub = await ensure_trial(user["id"])
        pub = sub_public(sub)

    is_paid = pub["paid_active"]
    request.state.user_id = user["id"]
    request.state.is_paid = is_paid

    try:
        if is_paid:
            updated = await try_consume_paid_recipe(user["id"], PAID_MONTHLY_MAX_RECIPES)
        else:
            updated = await try_consume_trial_recipe(user["id"], TRIAL_DAILY_MAX_RECIPES)
    except Exception:
        logger.exception("Recipe quota check failed for user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Service temporarily unavailable, try again")

    if updated is None:
        if is_paid:
            raise HTTPException(
                status_code=402,
                detail="Monthly recipe suggestions quota exhausted (100/100). Resets on your next billing date.",
            )
        raise HTTPException(
            status_code=402,
            detail="Daily free trial recipe limit reached (3/3). Try again tomorrow or upgrade to Premium.",
        )

    return user