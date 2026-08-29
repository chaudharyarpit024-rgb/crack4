from datetime import datetime, timezone, timedelta
from typing import Optional
from database.mongodb import db
from config.settings import (
    RZP_PLAN_ID,
    TRIAL_DAYS,
    SUB_AMOUNT_PAISE,
    RZP_LIVE,
    TRIAL_DAILY_MAX_REQUESTS,
    PAID_MONTHLY_MAX_REQUESTS,
    logger,
)

# Razorpay statuses that mean the user has an active paid subscription.
# Keep this in sync with the status_map in subscription_controller.py.
_PAID_ACTIVE_STATUSES = {"authenticated", "active"}


async def ensure_trial(user_id: str) -> dict:
    """Create a 10-day free trial subscription record on first read if not present."""
    try:
        sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
        if sub:
            return sub
        now = datetime.now(timezone.utc)
        sub = {
            "user_id": user_id,
            "razorpay_subscription_id": None,
            "plan_id": RZP_PLAN_ID or None,
            "status": "trialing",
            "trial_ends_at": (now + timedelta(days=TRIAL_DAYS)).isoformat(),
            "current_end": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            # Quota counters — initialised to zero on first provision
            "trial_requests_used": 0,
            "trial_usage_date": None,
            "monthly_requests_used": 0,
            "usage_cycle_start": now.isoformat(),
        }
        await db.subscriptions.insert_one(dict(sub))
        return sub
    except Exception:
        logger.exception("Database error ensuring trial subscription for user %s", user_id)
        now = datetime.now(timezone.utc)
        return {
            "user_id": user_id,
            "razorpay_subscription_id": None,
            "plan_id": RZP_PLAN_ID or None,
            "status": "trialing",
            "trial_ends_at": (now + timedelta(days=TRIAL_DAYS)).isoformat(),
            "current_end": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "trial_requests_used": 0,
            "trial_usage_date": None,
            "monthly_requests_used": 0,
            "usage_cycle_start": now.isoformat(),
        }


def sub_public(sub: dict) -> dict:
    """Compute derived subscription and trial status fields for the client."""
    status = sub.get("status", "none")
    trial_ends_at = sub.get("trial_ends_at")
    now = datetime.now(timezone.utc)
    days_left = 0
    trial_active = False
    paid_active = status in _PAID_ACTIVE_STATUSES
    if trial_ends_at:
        try:
            end = datetime.fromisoformat(trial_ends_at)
            if end > now:
                # Trial is active until end_at, regardless of RZP status
                # (as long as user hasn't been marked paid_active)
                trial_active = not paid_active
                delta = end - now
                days_left = max(0, delta.days + (1 if delta.seconds > 0 else 0))
        except Exception:
            pass

    # Compute quota fields
    is_paid = paid_active
    if is_paid:
        limit = PAID_MONTHLY_MAX_REQUESTS
        used = sub.get("monthly_requests_used", 0)
    else:
        today = now.date().isoformat()
        limit = TRIAL_DAILY_MAX_REQUESTS
        used = sub.get("trial_requests_used", 0) if sub.get("trial_usage_date") == today else 0

    active = paid_active or trial_active
    return {
        "status": status,
        "active": active,
        "trial_active": trial_active,
        "paid_active": paid_active,
        "trial_ends_at": trial_ends_at,
        "days_left": days_left,
        "razorpay_subscription_id": sub.get("razorpay_subscription_id"),
        "amount_paise": SUB_AMOUNT_PAISE,
        "currency": "INR",
        "rzp_configured": RZP_LIVE,
        "requests_used": used,
        "requests_limit": limit,
        "requests_remaining": max(0, limit - used),
    }


# ---------------------------------------------------------------------------
# Quota helpers
# ---------------------------------------------------------------------------

def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def try_consume_trial_request(user_id: str, limit: int) -> Optional[dict]:
    """
    Atomic daily-quota consume. Single round trip — no read-then-write race.

    The filter matches only when:
      • it's a new day  (trial_usage_date != today)  → always allowed, resets counter to 1
      • it's today AND  trial_requests_used < limit   → normal increment

    Because the filter already gates eligibility, we don't need to re-check
    the limit inside the update pipeline.
    """
    today = _today_str()

    return await db.subscriptions.find_one_and_update(
        {
            "user_id": user_id,
            "$or": [
                {"trial_usage_date": {"$ne": today}},
                {"trial_usage_date": today, "trial_requests_used": {"$lt": limit}},
            ],
        },
        [
            {
                "$set": {
                    "trial_requests_used": {
                        "$cond": [
                            {"$ne": ["$trial_usage_date", today]},
                            1,
                            {"$add": ["$trial_requests_used", 1]},
                        ]
                    },
                    "trial_usage_date": today,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        ],
        return_document=True,
    )


async def refund_trial_request(user_id: str) -> None:
    """
    Decrement the trial counter by 1 for infra-side failures only.
    Same-day guard prevents refunding across a day boundary.
    """
    today = _today_str()
    await db.subscriptions.update_one(
        {"user_id": user_id, "trial_usage_date": today, "trial_requests_used": {"$gt": 0}},
        {"$inc": {"trial_requests_used": -1}},
    )


async def try_consume_paid_request(user_id: str, limit: int) -> Optional[dict]:
    """
    Atomic monthly-quota consume for paid users. Returns the updated document,
    or None if ANY of the following are true (service must stop):
      • subscription status is not active/authenticated  (lapsed, cancelled, halted)
      • current billing period has ended  (current_end timestamp has passed)
      • monthly_requests_used >= limit   (500 scans exhausted)

    All three conditions are evaluated in a single server-side MongoDB filter,
    so there is no TOCTOU window between reading state and writing the increment.
    """
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return await db.subscriptions.find_one_and_update(
        {
            "user_id": user_id,
            # 1. Must be in an active paid state
            "status": {"$in": list(_PAID_ACTIVE_STATUSES)},
            # 2. Billing period must not have ended (current_end is a Unix timestamp
            #    written by Razorpay webhooks; None/missing passes through — edge case
            #    for users in 'authenticated' state before first charge)
            "$or": [
                {"current_end": None},
                {"current_end": {"$gt": now_ts}},
            ],
            # 3. Monthly quota not exhausted
            "monthly_requests_used": {"$lt": limit},
        },
        {
            "$inc": {"monthly_requests_used": 1},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
        return_document=True,
    )


async def refund_paid_request(user_id: str) -> None:
    """Decrement the monthly counter by 1 for infra-side failures."""
    await db.subscriptions.update_one(
        {"user_id": user_id, "monthly_requests_used": {"$gt": 0}},
        {"$inc": {"monthly_requests_used": -1}},
    )


async def reset_monthly_usage(user_id: str) -> None:
    """Called from the Razorpay subscription.charged webhook on each successful renewal."""
    await db.subscriptions.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "monthly_requests_used": 0,
                "usage_cycle_start": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )