import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
from config.settings import JWT_SECRET, JWT_ALGO, JWT_TTL_DAYS


def make_token(user_id: str, extra_claims: Optional[dict] = None, ttl: Optional[timedelta] = None) -> str:
    """Generate a signed JWT token for a given user ID.

    `extra_claims` are merged into the payload (do not include 'sub', 'exp', or 'iat' — they are set here).
    `ttl` overrides the default TTL (used for short-lived tokens like email verification).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + (ttl if ttl is not None else timedelta(days=JWT_TTL_DAYS)),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    """Decode and validate a signed JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
