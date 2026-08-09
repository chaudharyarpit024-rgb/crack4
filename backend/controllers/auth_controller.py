import uuid
from datetime import datetime, timezone
from fastapi import HTTPException

from database.mongodb import db
from models.auth import SignupBody, LoginBody
from security.hashing import hash_pw, verify_pw
from security.jwt import make_token
from utils.subscription import ensure_trial


async def signup_user(body: SignupBody) -> dict:
    """Register a new user account and provision an initial 10-day trial."""
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": user_id,
        "email": email,
        "password": hash_pw(body.password),
        "name": body.name or email.split("@")[0],
        "goal": None,
        "weight_kg": None,
        "height_cm": None,
        "age": None,
        "gender": None,
        "daily_target": None,
        "created_at": now,
    }
    await db.users.insert_one(doc)
    # Auto-provision 10-day free trial
    await ensure_trial(user_id)
    return {
        "token": make_token(user_id),
        "user": {k: v for k, v in doc.items() if k not in ("password", "_id")},
    }


async def login_user(body: LoginBody) -> dict:
    """Authenticate a user and return a signed JWT token."""
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_pw(body.password, user.get("password", "")):
        raise HTTPException(401, "Invalid email or password")
    # Ensure trial exists (for legacy accounts)
    await ensure_trial(user["id"])
    return {
        "token": make_token(user["id"]),
        "user": {k: v for k, v in user.items() if k not in ("password", "_id")},
    }


async def get_me(user: dict) -> dict:
    """Return the profile info for the currently authenticated user."""
    return user
