from config.settings import RZP_KEY_ID
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI, Depends, Header, HTTPException, status
from starlette.middleware.cors import CORSMiddleware

# Configuration & settings (runs boot-guards like JWT secret strength check)
from config.settings import logger
from database.mongodb import client, db, init_db, close_db
from routes import api_router

# Re-exports for backwards compatibility across tests and legacy imports
from models import SignupBody, LoginBody, ProfileBody, FoodLogBody, AnalyzeBody
from security import (
    hash_pw,
    verify_pw,
    make_token,
    decode_token,
    current_user,
    require_active_subscription,
    verify_payment_signature,
    verify_webhook_signature,
    rate_limiter,
    rate_limit_auth,
    rate_limit_public,
    record_auth_success,
    record_auth_failure,
)
from utils import calorie_target, parse_json, razorpay_req, ensure_trial, sub_public
from controllers import (
    signup_user,
    login_user,
    get_me,
    verify_email,
    resend_verification,
    update_user_profile,
    analyze_food_image,
    create_food_log,
    get_today_food_logs,
    get_food_history,
    delete_food_log,
    get_my_subscription,
    create_checkout_session,
    render_checkout_page,
    handle_subscription_callback,
    handle_subscription_webhook,
)

# App instance
app = FastAPI(
    title="CRACK Backend",
    description="Clean, modular, and secure backend API for CRACK diet & nutrition tracking",
    version="1.0.0",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_rate_limit_headers_middleware(request, call_next):
    response = await call_next(request)
    if hasattr(request.state, "rate_limit_headers") and request.state.rate_limit_headers:
        for k, v in request.state.rate_limit_headers.items():
            response.headers[k] = v
    return response


# Mount modular API router
app.include_router(api_router)


@app.get("/", dependencies=[Depends(rate_limit_public)])
async def root():
    """Health check root endpoint."""
    return {"service": "crack", "ok": True}


# Lifecycle hooks
@app.on_event("startup")
async def on_startup():
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()

# Load a  secret key from environment variable if exist

import secrets
from config.settings import WAKEUP_SECRET_KEY

app = FastAPI()

@app.get("/api/awake")
async def awake_checkpoint(x_wakeup_key: str = Header(None)):
    """
    Secure production awakening checkpoint.
    Requires WAKEUP_SECRET_KEY to be configured
    """

    if not WAKEUP_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WakeUp checkpoint is not enabled on this server."
        )
    if (
        not x_wakeup_key 
        or not secrets.compar_digest(
            x_wakeup_key,
            WAKEUP_SECRET_KEY
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing wakeup key."
        )
    return {
            "status": "awake",
            "ok": True
    }


__all__ = [
    "app",
    "client",
    "db",
    "SignupBody",
    "LoginBody",
    "ProfileBody",
    "FoodLogBody",
    "AnalyzeBody",
    "hash_pw",
    "verify_pw",
    "make_token",
    "decode_token",
    "current_user",
    "require_active_subscription",
    "verify_payment_signature",
    "verify_webhook_signature",
    "rate_limiter",
    "rate_limit_auth",
    "rate_limit_public",
    "record_auth_success",
    "record_auth_failure",
    "calorie_target",
    "parse_json",
    "razorpay_req",
    "ensure_trial",
    "sub_public",
    "verify_email",
    "resend_verification",
]
