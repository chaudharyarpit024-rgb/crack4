from pydantic import BaseModel
from typing import Optional


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


class CheckoutResponse(BaseModel):
    subscription_id: str
    key_id: str
    amount_paise: int
