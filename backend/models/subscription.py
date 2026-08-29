# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from config.settings import TRIAL_DAILY_MAX_REQUESTS, PAID_MONTHLY_MAX_REQUESTS


class SubscriptionPublic(BaseModel):
    status: str
    active: bool
    trial_active: bool
    paid_active: bool
    trial_ends_at: Optional[str] = None
    days_left: int
    razorpay_subscription_id: Optional[str] = None
    amount_paise: int
    currency: str = "INR"
    rzp_configured: bool
    # Quota tracking — always computed server-side, never stored directly.
    requests_used: int
    requests_limit: int
    requests_remaining: int


def to_subscription_public(sub: dict, **base_fields) -> SubscriptionPublic:
    """
    Single source of truth for turning a raw subscription doc into the public-facing shape.
    Limit / used / remaining are always computed here — never trust a stored 'requests_limit'
    value, since a plan change should instantly change the effective limit without a migration.

    For trial users, if ``trial_usage_date`` is not today the stored count is stale (it only
    resets lazily on the next /analyze call), so we show 0 used to give an accurate banner.
    """
    is_paid = base_fields.get("paid_active", False)
    if is_paid:
        limit = PAID_MONTHLY_MAX_REQUESTS
        used = sub.get("monthly_requests_used", 0)
    else:
        today = datetime.now(timezone.utc).date().isoformat()
        limit = TRIAL_DAILY_MAX_REQUESTS
        used = sub.get("trial_requests_used", 0) if sub.get("trial_usage_date") == today else 0

    return SubscriptionPublic(
        **base_fields,
        requests_used=used,
        requests_limit=limit,
        requests_remaining=max(0, limit - used),
    )


class CheckoutResponse(BaseModel):
    subscription_id: str
    key_id: str
    amount_paise: int
