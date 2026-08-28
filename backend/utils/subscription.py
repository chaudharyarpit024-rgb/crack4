from datetime import datetime, timezone, timedelta
from database.mongodb import db
from config.settings import RZP_PLAN_ID, TRIAL_DAYS, SUB_AMOUNT_PAISE, RZP_LIVE, logger


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
        }



def sub_public(sub: dict) -> dict:
    """Compute derived subscription and trial status fields for the client."""
    status = sub.get("status", "none")
    trial_ends_at = sub.get("trial_ends_at")
    now = datetime.now(timezone.utc)
    days_left = 0
    trial_active = False
    paid_active = status in {"authenticated", "active"}
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
    }
