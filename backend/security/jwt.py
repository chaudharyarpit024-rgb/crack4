import jwt
from datetime import datetime, timezone, timedelta
from config.settings import JWT_SECRET, JWT_ALGO, JWT_TTL_DAYS


def make_token(user_id: str) -> str:
    """Generate a signed JWT token for a given user ID."""
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_TTL_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    """Decode and validate a signed JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
