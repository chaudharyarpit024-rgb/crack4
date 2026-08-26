"""Helpers for email verification: short-lived JWT tokens + replay protection.

Verification tokens are JWTs signed with the same JWT_SECRET as auth tokens,
but with `type="verify_email"` and a `jti` (JWT ID). On verification, the
`jti` is atomically inserted into `used_verification_jti` (unique index) to
prevent replay. A TTL index on `used_at` (2 days) cleans up old records.
"""
import time
import uuid
from datetime import timedelta
from typing import Dict

import jwt
from pymongo.errors import DuplicateKeyError

from config.settings import (
    EMAIL_VERIFY_TTL_HOURS,
    RESEND_MIN_INTERVAL_SECONDS,
)
from database.mongodb import db
from security.jwt import make_token, decode_token


VERIFICATION_TOKEN_TYPE = "verify_email"
PASSWORD_RESET_TOKEN_TYPE = "reset_password"
PASSWORD_RESET_TTL_MINUTES = 15


def make_verification_token(user_id: str) -> str:
    """Generate a signed 24h JWT for email verification."""
    return make_token(
        user_id,
        extra_claims={"type": VERIFICATION_TOKEN_TYPE, "jti": uuid.uuid4().hex},
        ttl=timedelta(hours=EMAIL_VERIFY_TTL_HOURS),
    )


def decode_verification_token(token: str) -> dict:
    """Decode a verification JWT and confirm it has the right type.

    Raises:
        jwt.ExpiredSignatureError: if exp passed.
        jwt.InvalidTokenError: if signature invalid, malformed, or wrong type.
    """
    payload = decode_token(token)
    if payload.get("type") != VERIFICATION_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


async def mark_and_check_jti(jti: str) -> bool:
    """Atomically record a used verification jti. Returns True if newly marked, False if already used."""
    try:
        await db.used_verification_jti.insert_one({"jti": jti, "used_at": _now()})
        return True
    except DuplicateKeyError:
        return False


def make_password_reset_token(user_id: str) -> str:
    """Generate a signed 15-minute JWT for password reset."""
    return make_token(
        user_id,
        extra_claims={"type": PASSWORD_RESET_TOKEN_TYPE, "jti": uuid.uuid4().hex},
        ttl=timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
    )


def decode_password_reset_token(token: str) -> dict:
    """Decode a password reset JWT and confirm it has the right type.

    Raises:
        jwt.ExpiredSignatureError: if exp passed.
        jwt.InvalidTokenError: if signature invalid, malformed, or wrong type.
    """
    payload = decode_token(token)
    if payload.get("type") != PASSWORD_RESET_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


async def mark_and_check_reset_jti(jti: str) -> bool:
    """Atomically record a used reset jti. Returns True if newly marked, False if already used."""
    try:
        await db.used_reset_jti.insert_one({"jti": jti, "used_at": _now()})
        return True
    except DuplicateKeyError:
        return False


_last_resend: Dict[str, float] = {}
_last_forgot_password: Dict[str, float] = {}


def _now() -> "datetime":  # local helper so we don't import datetime at module top
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def check_resend_allowed(email: str) -> tuple[bool, int]:
    """Check if resend is permitted. Returns (allowed, seconds_remaining)."""
    now_mono = time.monotonic()
    last = _last_resend.get(email, 0.0)
    elapsed = now_mono - last
    if elapsed < RESEND_MIN_INTERVAL_SECONDS:
        return False, max(1, int(RESEND_MIN_INTERVAL_SECONDS - elapsed))
    _last_resend[email] = now_mono
    return True, 0


def can_resend(email: str) -> bool:
    """Return True if a resend is allowed for this email right now."""
    allowed, _ = check_resend_allowed(email)
    return allowed


def check_forgot_password_allowed(email: str) -> tuple[bool, int]:
    """Check if forgot-password request is permitted. Returns (allowed, seconds_remaining)."""
    now_mono = time.monotonic()
    last = _last_forgot_password.get(email, 0.0)
    elapsed = now_mono - last
    if elapsed < RESEND_MIN_INTERVAL_SECONDS:
        return False, max(1, int(RESEND_MIN_INTERVAL_SECONDS - elapsed))
    _last_forgot_password[email] = now_mono
    return True, 0

