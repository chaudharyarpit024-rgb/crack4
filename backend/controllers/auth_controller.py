import uuid
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from config.settings import PUBLIC_API_URL, logger
from database.mongodb import db
from models.auth import SignupBody, LoginBody
from models.verification import (
    VerifyBody,
    ResendBody,
    ForgotPasswordBody,
    ResetPasswordBody,
)
from security.hashing import hash_pw, verify_pw
from security.jwt import make_token
from utils.email import send_email
from utils.email_templates import (
    verification_email_html,
    verification_email_text,
    password_reset_email_html,
    password_reset_email_text,
)
from utils.subscription import ensure_trial
from utils.verification import (
    can_resend,
    check_resend_allowed,
    check_forgot_password_allowed,
    decode_verification_token,
    make_verification_token,
    mark_and_check_jti,
    make_password_reset_token,
    decode_password_reset_token,
    mark_and_check_reset_jti,
)


def _verify_url(token: str) -> str:
    """Build an HTTPS web verification URL for email links."""
    base = PUBLIC_API_URL.rstrip('/') if PUBLIC_API_URL else "https://crack4-avoa.onrender.com"
    return f"{base}/api/auth/verify-link?token={token}"


def _reset_password_url(token: str) -> str:
    """Build an HTTPS web password reset URL for email links."""
    base = PUBLIC_API_URL.rstrip('/') if PUBLIC_API_URL else "https://crack4-avoa.onrender.com"
    return f"{base}/api/auth/reset-password-web?token={token}"


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


async def _send_verification_email(user_id: str, email: str) -> bool:
    token = make_verification_token(user_id)
    url = _verify_url(token)
    logger.info(f"Dispatching verification email to {email} with URL: {url}")
    return await send_email(
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
        sent = await _send_verification_email(user_id, email)
        if not sent:
            logger.warning(f"Initial signup verification email could not be sent to {email}")
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
    if not user_id or not jti:
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

    Rate-limited per email with clear feedback.
    """
    email = body.email.lower().strip()
    allowed, seconds_left = check_resend_allowed(email)
    if not allowed:
        return {
            "ok": True,
            "cooldown": True,
            "retry_after": seconds_left,
            "message": f"Please wait {seconds_left}s before requesting a new verification link.",
        }

    user = await db.users.find_one({"email": email})
    if user and not user.get("email_verified", False):
        try:
            sent = await _send_verification_email(user["id"], email)
            if not sent:
                logger.warning(f"Resend verification email could not be dispatched to {email}")
        except Exception:
            logger.exception(f"Failed to resend verification email to {email}")

    return {
        "ok": True,
        "cooldown": False,
        "message": "If an account exists for that email, a new link has been sent.",
    }


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


def _render_reset_web_html(token: str, error: str = "") -> str:
    err_block = f'<p class="msg err">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Password - CRACK</title>
    <style>
        body {{ background-color: #0b0b0f; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
        .card {{ background: #15151c; max-width: 420px; width: 100%; border-radius: 16px; border: 1px solid #2a2a33; padding: 40px 28px; box-shadow: 0 12px 32px rgba(0,0,0,0.5); }}
        .logo {{ color: #ff6a3d; font-size: 26px; font-weight: 900; letter-spacing: 3px; margin: 0 0 4px 0; text-align: center; }}
        .tagline {{ color: #7c8189; font-size: 12px; margin: 0 0 24px 0; text-transform: uppercase; letter-spacing: 1px; text-align: center; }}
        h1 {{ font-size: 22px; font-weight: 700; margin: 0 0 8px 0; color: #ffffff; text-align: center; }}
        p {{ color: #a0a5b1; font-size: 14px; line-height: 1.5; margin: 0 0 20px 0; text-align: center; }}
        .form-group {{ margin-bottom: 16px; }}
        label {{ display: block; font-size: 13px; font-weight: 600; color: #cfcfd4; margin-bottom: 6px; }}
        input {{ width: 100%; box-sizing: border-box; background: #1e1e28; border: 1px solid #33333f; border-radius: 10px; padding: 14px 16px; color: #ffffff; font-size: 15px; outline: none; }}
        input:focus {{ border-color: #ff6a3d; }}
        .btn {{ display: block; width: 100%; box-sizing: border-box; background: #ff6a3d; color: #ffffff; border: none; font-weight: 700; padding: 14px; border-radius: 10px; font-size: 16px; cursor: pointer; text-align: center; text-decoration: none; margin-top: 20px; transition: background 0.2s; }}
        .btn:hover {{ background: #ff5722; }}
        .btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
        .msg {{ font-size: 13px; margin-top: 14px; text-align: center; }}
        .msg.err {{ color: #ff4d4d; }}
        .msg.ok {{ color: #4caf50; font-weight: 600; }}
        .app-link {{ display: block; text-align: center; color: #7c8189; font-size: 13px; margin-top: 20px; text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">CRACK</div>
        <div class="tagline">Track It First</div>
        <h1>Reset Password</h1>
        <p>Choose a new password for your account (at least 8 characters).</p>
        {err_block}
        <form id="resetForm">
            <div class="form-group">
                <label for="password">New Password</label>
                <input type="password" id="password" placeholder="At least 8 characters" required minlength="8" />
            </div>
            <div class="form-group">
                <label for="confirmPassword">Confirm New Password</label>
                <input type="password" id="confirmPassword" placeholder="Repeat new password" required minlength="8" />
            </div>
            <button type="submit" id="submitBtn" class="btn">Update Password</button>
            <div id="statusMsg" class="msg"></div>
        </form>
        <a href="crack://reset-password?token={token}" class="app-link">Open in CRACK App instead</a>
    </div>

    <script>
        const form = document.getElementById('resetForm');
        const submitBtn = document.getElementById('submitBtn');
        const statusMsg = document.getElementById('statusMsg');
        const token = "{token}";

        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            if (password.length < 8) {{
                statusMsg.className = 'msg err';
                statusMsg.textContent = 'Password must be at least 8 characters.';
                return;
            }}

            if (password !== confirmPassword) {{
                statusMsg.className = 'msg err';
                statusMsg.textContent = 'Passwords do not match.';
                return;
            }}

            submitBtn.disabled = true;
            statusMsg.className = 'msg';
            statusMsg.textContent = 'Updating password...';

            try {{
                const res = await fetch('/api/auth/reset-password', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ token: token, new_password: password }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    statusMsg.className = 'msg ok';
                    statusMsg.textContent = 'Password updated successfully! You can now open the app and log in.';
                    form.reset();
                    submitBtn.style.display = 'none';
                }} else {{
                    statusMsg.className = 'msg err';
                    statusMsg.textContent = data.detail || data.message || 'Reset failed. The link may have expired.';
                    submitBtn.disabled = false;
                }}
            }} catch (err) {{
                statusMsg.className = 'msg err';
                statusMsg.textContent = 'Network error. Please try again.';
                submitBtn.disabled = false;
            }}
        }});
    </script>
</body>
</html>"""


async def forgot_password(body: ForgotPasswordBody) -> dict:
    """Send a password reset email if the account exists.

    Rate-limited and returns a generic 200 to prevent email enumeration.
    """
    email = body.email.lower().strip()
    allowed, seconds_left = check_forgot_password_allowed(email)
    if not allowed:
        return {
            "ok": True,
            "cooldown": True,
            "retry_after": seconds_left,
            "message": f"Please wait {seconds_left}s before requesting another reset link.",
        }

    user = await db.users.find_one({"email": email})
    if user:
        token = make_password_reset_token(user["id"])
        url = _reset_password_url(token)
        logger.info(f"Dispatching password reset email to {email}")
        try:
            await send_email(
                email,
                "Reset your CRACK password",
                password_reset_email_html(url),
                password_reset_email_text(url),
            )
        except Exception:
            logger.exception(f"Failed to send password reset email to {email}")

    return {
        "ok": True,
        "cooldown": False,
        "message": "If an account exists with that email, a password reset link has been sent.",
    }


async def reset_password(body: ResetPasswordBody) -> dict:
    """Validate password reset token and update user's password.

    Replay-protected via unique `used_reset_jti` collection.
    """
    try:
        payload = decode_password_reset_token(body.token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Password reset link expired. Please request a new one.")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid password reset link.")

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        raise HTTPException(400, "Invalid password reset link.")

    if not await mark_and_check_reset_jti(jti):
        raise HTTPException(400, "This password reset link has already been used.")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User account not found.")

    new_hash = hash_pw(body.new_password)
    # Update password and mark email verified (since clicking the email link proves ownership)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password": new_hash, "email_verified": True}},
    )
    logger.info(f"Password reset successfully completed for user {user_id}")
    return {
        "ok": True,
        "message": "Password updated successfully. You can now log in with your new password.",
    }


async def reset_password_web(token: str) -> HTMLResponse:
    """Render the password reset web form in browser."""
    try:
        decode_password_reset_token(token)
        return HTMLResponse(_render_reset_web_html(token))
    except jwt.ExpiredSignatureError:
        return HTMLResponse(_render_verify_html(False, "Password reset link expired. Please request a new link from the CRACK app."))
    except Exception:
        return HTMLResponse(_render_verify_html(False, "Invalid or corrupt password reset link."))


async def get_me(user: dict) -> dict:
    """Return the profile info for the currently authenticated user."""
    return user

