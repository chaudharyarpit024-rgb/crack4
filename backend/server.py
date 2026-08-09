import sys
from pathlib import Path

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
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
)
from utils import calorie_target, parse_json, razorpay_req, ensure_trial, sub_public
from controllers import (
    signup_user,
    login_user,
    get_me,
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

# Mount modular API router
app.include_router(api_router)


@app.get("/")
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
    "calorie_target",
    "parse_json",
    "razorpay_req",
    "ensure_trial",
    "sub_public",
]
