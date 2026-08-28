from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from security.dependencies import current_user
from security.rate_limiter import rate_limit_public
from controllers.subscription_controller import (
    get_my_subscription,
    create_checkout_session,
    render_checkout_page,
    handle_subscription_callback,
    handle_subscription_webhook,
)

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/me")
async def subscription_me(user: dict = Depends(current_user)):
    return await get_my_subscription(user)


@router.post("/checkout")
async def create_checkout(user: dict = Depends(current_user)):
    return await create_checkout_session(user)


@router.get("/checkout-page", response_class=HTMLResponse, dependencies=[Depends(rate_limit_public)])
async def checkout_page(
    subscription_id: str = Query(..., min_length=8, max_length=64, pattern=r"^sub_[a-zA-Z0-9]+$"),
):
    return await render_checkout_page(subscription_id)


@router.post("/callback", dependencies=[Depends(rate_limit_public)])
async def subscription_callback(
    razorpay_payment_id: str = Form(..., min_length=4, max_length=64, pattern=r"^pay_[a-zA-Z0-9]+$"),
    razorpay_subscription_id: str = Form(..., min_length=4, max_length=64, pattern=r"^sub_[a-zA-Z0-9]+$"),
    razorpay_signature: str = Form(..., min_length=32, max_length=128, pattern=r"^[a-fA-F0-9]+$"),
):
    return await handle_subscription_callback(
        razorpay_payment_id,
        razorpay_subscription_id,
        razorpay_signature,
    )



@router.post("/webhook", dependencies=[Depends(rate_limit_public)])
async def subscription_webhook(request: Request):
    return await handle_subscription_webhook(request)

