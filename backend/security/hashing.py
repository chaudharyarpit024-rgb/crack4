import bcrypt


def hash_pw(pw: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    """Verify a raw password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False
