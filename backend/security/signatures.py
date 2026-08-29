import hmac
import hashlib
from config.settings import RZP_KEY_SECRET, RZP_WEBHOOK_SECRET


def verify_payment_signature(payment_id: str, subscription_id: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature for Razorpay payment callback."""
    message = f"{payment_id}|{subscription_id}".encode()
    expected = hmac.new(RZP_KEY_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, received_signature: str) -> bool:
    """Verify HMAC-SHA256 signature for Razorpay webhook payloads.

    Raises ValueError if the webhook secret is not configured — an empty secret
    would let anyone forge a valid HMAC, so we refuse to operate rather than
    silently accepting forged payloads.
    """
    if not RZP_WEBHOOK_SECRET:
        raise ValueError("RAZORPAY_WEBHOOK_SECRET is not configured — refusing to verify webhook")
    expected = hmac.new(RZP_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_signature)
