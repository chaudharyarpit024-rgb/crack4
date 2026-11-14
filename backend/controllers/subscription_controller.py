import json
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from database.mongodb import db
from config.settings import (
    RZP_KEY_ID,
    RZP_PLAN_ID,
    RZP_ID_RE,
    RZP_LIVE,
    RZP_WEBHOOK_LIVE,
    PUBLIC_API_URL,
    MOBILE_RETURN_URL,
    SUB_AMOUNT_PAISE,
    TRIAL_DAYS,
    logger,
)
from utils.subscription import ensure_trial, sub_public, reset_monthly_usage, is_unlimited_email
from utils.razorpay_client import razorpay_req
from security.signatures import verify_payment_signature, verify_webhook_signature


async def get_my_subscription(user: dict) -> dict:
    """Return public subscription state for the user."""
    is_unlimited = await is_unlimited_email(user.get("email"))
    sub = await ensure_trial(user["id"])
    return sub_public(sub, is_unlimited=is_unlimited)


async def create_checkout_session(user: dict) -> dict:
    """Create a Razorpay subscription with free trial (via start_at)."""
    is_unlimited = await is_unlimited_email(user.get("email"))
    if is_unlimited:
        return {
            "subscription_id": "unlimited_vip",
            "is_unlimited": True,
            "amount_paise": 0,
            "message": "Your account already has permanent unlimited VIP access.",
        }

    if not RZP_LIVE:
        logger.warning("Checkout requested but Razorpay is not configured")
        raise HTTPException(
            503,
            "Payment service is temporarily unavailable. Please try again later.",
        )
    if not RZP_PLAN_ID:
        logger.warning("Checkout requested but RAZORPAY_PLAN_ID is not configured")
        raise HTTPException(503, "Payment service is temporarily unavailable. Please try again later.")

    try:
        existing = await db.subscriptions.find_one({"user_id": user["id"]})
    except Exception:
        logger.exception("Database error checking existing subscription for user %s", user.get("id"))
        raise HTTPException(503, "Service temporarily unavailable. Please try again.")

    now = datetime.now(timezone.utc)

    # If the user already has an active or authenticated paid subscription, reuse it.
    # Otherwise, always create a fresh subscription so payment is charged immediately today.
    if existing and existing.get("razorpay_subscription_id"):
        if existing.get("status") in {"authenticated", "active"}:
            return {
                "subscription_id": existing["razorpay_subscription_id"],
                "key_id": RZP_KEY_ID,
                "amount_paise": SUB_AMOUNT_PAISE,
            }

    # Option A: In-app free trial only.
    # When a user goes to checkout, we do NOT pass 'start_at' in the future.
    # Razorpay bills the full subscription amount (e.g. ₹57) immediately today.
    rzp_sub_payload: dict = {
        "plan_id": RZP_PLAN_ID,
        "quantity": 1,
        "total_count": 12,  # 12 monthly cycles; extend via renewals
        "customer_notify": 1,
        "notes": {"user_id": user["id"]},
    }

    sub = await razorpay_req(
        "POST",
        "/v1/subscriptions",
        json=rzp_sub_payload,
    )

    try:
        update_fields: dict = {
            "razorpay_subscription_id": sub["id"],
            "plan_id": sub["plan_id"],
            "status": sub.get("status", "created"),
            "updated_at": now.isoformat(),
        }
        await db.subscriptions.update_one(
            {"user_id": user["id"]},
            {"$set": update_fields},
            upsert=True,
        )
    except Exception:
        logger.exception("Database error saving subscription %s for user %s", sub.get("id"), user.get("id"))
        raise HTTPException(503, "Service temporarily unavailable. Please try again.")
    return {
        "subscription_id": sub["id"],
        "key_id": RZP_KEY_ID,
        "amount_paise": SUB_AMOUNT_PAISE,
    }


async def render_checkout_page(subscription_id: str) -> HTMLResponse:
    """Hosted checkout page loaded inside WebView on mobile app with strict XSS defenses and CSP."""
    # Strict allowlist prevents reflected XSS by rejecting anything that isn't a plain Razorpay id.
    if not RZP_ID_RE.match(subscription_id or ""):
        raise HTTPException(400, "Invalid subscription id")
    # Verify subscription belongs to a real record; also protects against enumerating arbitrary ids.
    try:
        exists = await db.subscriptions.find_one({"razorpay_subscription_id": subscription_id})
    except Exception:
        logger.exception("Database error checking subscription %s in checkout page", subscription_id)
        raise HTTPException(503, "Service temporarily unavailable. Please try again.")
    if not exists:
        raise HTTPException(404, "Subscription not found")

    # Values are now guaranteed alphanumeric-only, but we still JSON-encode and swap the "</"
    # sequence to be defense-in-depth against future edits.
    def js_str(v: str) -> str:
        return json.dumps(v).replace("</", "<\\/")

    price_str = f"{SUB_AMOUNT_PAISE // 100}" if SUB_AMOUNT_PAISE % 100 == 0 else f"{SUB_AMOUNT_PAISE / 100:.2f}"

    sub_line = f"Billed today · ₹{price_str}/month · UPI Autopay"
    desc_line = f"Premium — Rs.{price_str}/month"

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta http-equiv="Content-Security-Policy" content="default-src 'self' https://checkout.razorpay.com https://*.razorpay.com; script-src 'self' 'unsafe-inline' https://checkout.razorpay.com; style-src 'self' 'unsafe-inline'; img-src * data: blob:; connect-src https://checkout.razorpay.com https://*.razorpay.com; frame-src https://*.razorpay.com;" />
<meta http-equiv="X-Content-Type-Options" content="nosniff"/>
<title>CRACK — Subscribe</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #fff; margin:0; padding: 32px; color:#111827; text-align:center; }}
  .brand {{ font-weight: 900; font-size: 42px; color: #E05D36; letter-spacing: 3px; }}
  .tag {{ color: #6B7280; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; margin-top: 6px; }}
  .price {{ font-size: 42px; font-weight: 900; margin: 28px 0 4px; }}
  .sub {{ color: #6B7280; font-size: 14px; }}
  button {{ background:#E05D36; color:#fff; border:none; padding: 14px 28px; border-radius: 12px; font-size:16px; font-weight:700; margin-top:24px; }}
</style>
</head>
<body>
<div class="brand">CRACK</div>
<div class="tag">Premium</div>
<div class="price">₹{price_str}<span style="font-size:16px;color:#6B7280;">/month</span></div>
<div class="sub">{sub_line}</div>
<button id="pay">Continue to payment</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
  document.getElementById('pay').addEventListener('click', function() {{
    var options = {{
      key: {js_str(RZP_KEY_ID)},
      subscription_id: {js_str(subscription_id)},
      name: 'CRACK',
      description: {js_str(desc_line)},
      callback_url: {js_str((PUBLIC_API_URL or '') + '/api/subscription/callback')},
      theme: {{ color: '#E05D36' }}
    }};
    var rzp = new Razorpay(options);
    rzp.open();
  }});
</script>
</body>
</html>"""
    return HTMLResponse(
        html,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "no-store",
        },
    )


async def handle_subscription_callback(
    razorpay_payment_id: str,
    razorpay_subscription_id: str,
    razorpay_signature: str,
) -> RedirectResponse:
    """Handle Razorpay redirect callback and verify HMAC signature."""
    if not verify_payment_signature(razorpay_payment_id, razorpay_subscription_id, razorpay_signature):
        raise HTTPException(400, "Invalid payment signature")

    try:
        await db.subscriptions.update_one(
            {"razorpay_subscription_id": razorpay_subscription_id},
            {
                "$set": {
                    "auth_payment_id": razorpay_payment_id,
                    "status": "authenticated",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    except Exception:
        logger.exception("Database error updating subscription %s in callback", razorpay_subscription_id)
        raise HTTPException(503, "Service temporarily unavailable. Please try again.")
    return RedirectResponse(MOBILE_RETURN_URL, status_code=303)


async def handle_subscription_webhook(request: Request) -> dict:
    """Handle and idempotently process Razorpay webhooks."""
    # Fail closed if the webhook secret hasn't been configured yet.
    if not RZP_WEBHOOK_LIVE:
        raise HTTPException(503, "Webhook not configured")

    raw = await request.body()
    received = request.headers.get("x-razorpay-signature", "")
    if not verify_webhook_signature(raw, received):
        raise HTTPException(400, "Invalid webhook signature")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Received malformed (non-JSON) webhook payload — body length: %d", len(raw))
        raise HTTPException(400, "Invalid webhook payload: expected JSON")

    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw).hexdigest()
    try:
        await db.rzp_events.insert_one(
            {
                "event_id": event_id,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        return {"ok": True}  # duplicate event

    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    rid = entity.get("id")
    status_map = {
        "subscription.authenticated": "authenticated",
        "subscription.activated": "active",
        "subscription.charged": "active",
        "subscription.pending": "pending",
        "subscription.halted": "halted",
        "subscription.cancelled": "cancelled",
        "subscription.completed": "completed",
    }
    if rid and event in status_map:
        try:
            update_payload: dict = {
                "status": status_map[event],
                "current_start": entity.get("current_start"),
                "current_end": entity.get("current_end"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.subscriptions.update_one(
                {"razorpay_subscription_id": rid},
                {"$set": update_payload},
            )
        except Exception:
            logger.exception("Database error updating subscription %s in webhook event %s", rid, event)

        # On successful renewal, reset the monthly AI-scan quota for this user
        if event == "subscription.charged":
            try:
                sub_doc = await db.subscriptions.find_one({"razorpay_subscription_id": rid}, {"_id": 0, "user_id": 1})
                if sub_doc and sub_doc.get("user_id"):
                    await reset_monthly_usage(sub_doc["user_id"])
                    logger.info("Monthly quota reset for user_id=%s on subscription.charged", sub_doc["user_id"])
            except Exception:
                logger.exception("Failed to reset monthly quota for subscription %s", rid)
    return {"ok": True}
