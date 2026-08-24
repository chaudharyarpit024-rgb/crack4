import uuid
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException

from config.settings import PUBLIC_API_URL, logger
from database.mongodb import db
from models.auth import SignupBody, LoginBody
from models.verification import VerifyBody, ResendBody
from security.hashing import hash_pw, verify_pw
from security.jwt import make_token
from utils.email import send_email
from utils.email_templates import verification_email_html, verification_email_text
from utils.subscription import ensure_trial
from utils.verification import (
    can_resend,
    decode_verification_token,
    make_verification_token,
    mark_and_check_jti,
)


def _verify_url(token: str) -> str:
    """Build an HTTPS web verification URL for email links."""
    base = PUBLIC_API_URL.rstrip('/') if PUBLIC_API_URL else "https://crack4-uljj.onrender.com"
    return f"{base}/api/auth/verify-link?token={token}"


def _render_verify_html(success: bool, message: str) -> str:
    icon = "✓" if success else "✕"
    icon_color = "#4caf50" if success else "#ff4d4d"
    title = "Email Verified!" if success else "Verification Failed"
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - CRACK</title>
    <style>
        body {{ background-color: #0b0b0f; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
        .card {{ background: #15151c; max-width: 420px; width: 100%; border-radius: 16px; border: 1px solid #2a2a33; padding: 40px 28px; text-align: center; box-shadow: 0 12px 32px rgba(0,0,0,0.5); }}
        .logo {{ color: #ff6a3d; font-size: 26px; font-weight: 900; letter-spacing: 3px; margin: 0 0 4px 0; }}
        .tagline {{ color: #7c8189; font-size: 12px; margin: 0 0 28px 0; text-transform: uppercase; letter-spacing: 1px; }}
        .icon-circle {{ width: 64px; height: 64px; border-radius: 50%; background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; margin: 0 auto 20px auto; font-size: 32px; color: {icon_color}; }}
        h1 {{ font-size: 22px; font-weight: 700; margin: 0 0 12px 0; color: #ffffff; }}
        p {{ color: #a0a5b1; font-size: 14px; line-height: 1.6; margin: 0 0 24px 0; }}
        .btn {{ display: inline-block; background: #ff6a3d; color: #ffffff; text-decoration: none; font-weight: 600; padding: 14px 28px; border-radius: 10px; font-size: 15px; transition: background 0.2s; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">CRACK</div>
        <div class="tagline">Track It First</div>
        <div class="icon-circle">{icon}</div>
        <h1>{title}</h1>
        <p>{message}</p>
        <a href="crack://login" class="btn">Open CRACK App</a>
    </div>
</body>
</html>"""


async def _send_verification_email(user_id: str, email: str) -> None:
    token = make_verification_token(user_id)
    url = _verify_url(token)
    await send_email(
        email,
        "Verify your CRACK email",
        verification_email_html(url),
        verification_email_text(url),
    )


async def signup_user(body: SignupBody) -> dict:
    """Register a new user and send a verification email. Does NOT issue a token.

    The user must click the link in the verification email before they can log in.
    """
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
        "email_verified": False,
        "created_at": now,
    }
    await db.users.insert_one(doc)
    # Provision trial so a returning verified user doesn't hit a cold-start.
    await ensure_trial(user_id)
    # Send verification email. Failures are logged but don't break signup — user can resend.
    try:
        await _send_verification_email(user_id, email)
    except Exception:
        logger.exception(f"Failed to send verification email to {email}")
    return {
        "ok": True,
        "message": "Check your email for a verification link.",
        "email": email,
    }


async def login_user(body: LoginBody) -> dict:
    """Authenticate a verified user and return a signed JWT token.

    Unverified users (including legacy users after the migration) receive 403.
    """
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_pw(body.password, user.get("password", "")):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("email_verified", False):
        raise HTTPException(403, "Email not verified. Check your inbox for the verification link.")
    await ensure_trial(user["id"])
    return {
        "token": make_token(user["id"]),
        "user": {k: v for k, v in user.items() if k not in ("password", "_id")},
    }


async def verify_email(body: VerifyBody) -> dict:
    """Validate a verification token and issue an auth token.

    Replay-protected via the unique `used_verification_jti` collection.
    """
    try:
        payload = decode_verification_token(body.token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Verification link expired. Please request a new one.")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid verification link.")

    user_id = payload["sub"]
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(400, "Invalid verification link.")

    if not await mark_and_check_jti(jti):
        raise HTTPException(400, "This verification link has already been used.")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found.")

    await db.users.update_one({"id": user_id}, {"$set": {"email_verified": True}})
    return {
        "token": make_token(user_id),
        "user": {k: v for k, v in user.items() if k not in ("password", "_id")},
    }


async def resend_verification(body: ResendBody) -> dict:
    """Resend a verification email if the account exists and is not yet verified.

    Rate-limited per email. Always returns a generic 200 to avoid leaking
    whether an account exists for the given email.
    """
    email = body.email.lower().strip()
    if not can_resend(email):
        return {"ok": True, "message": "If an account exists for that email, a new link has been sent."}

    user = await db.users.find_one({"email": email})
    if user and not user.get("email_verified", False):
        try:
            await _send_verification_email(user["id"], email)
        except Exception:
            logger.exception(f"Failed to resend verification email to {email}")

    return {"ok": True, "message": "If an account exists for that email, a new link has been sent."}


async def verify_email_link(token: str) -> HTMLResponse:
    """Web endpoint triggered when clicking email verification link in any browser.

    Decodes verification token, marks user as verified in DB, and returns a confirmation webpage.
    """
    try:
        payload = decode_verification_token(token)
    except jwt.ExpiredSignatureError:
        return HTMLResponse(_render_verify_html(False, "Verification link expired. Please request a new link from the app."))
    except Exception:
        return HTMLResponse(_render_verify_html(False, "Invalid or corrupt verification link."))

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        return HTMLResponse(_render_verify_html(False, "Invalid verification link."))

    if not await mark_and_check_jti(jti):
        return HTMLResponse(_render_verify_html(True, "Your email is already verified! You can return to the app and log in."))

    user = await db.users.find_one({"id": user_id})
    if not user:
        return HTMLResponse(_render_verify_html(False, "User account not found."))

    await db.users.update_one({"id": user_id}, {"$set": {"email_verified": True}})
    return HTMLResponse(_render_verify_html(True, "Your email has been verified successfully! You can now return to the app and log in."))


async def get_me(user: dict) -> dict:
    """Return the profile info for the currently authenticated user."""
    return user
