# backend/routes/webhooks.py (or wherever Razorpay webhooks already land)

from backend.utils.subscription import reset_monthly_usage

@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    event = verify_and_parse_razorpay_signature(request)  # your existing signature verification — do not skip

    if event["event"] == "subscription.charged":
        user_id = resolve_user_id_from_subscription(event["payload"])
        await reset_monthly_usage(user_id)

    # ...existing event handling
    return {"status": "ok"}