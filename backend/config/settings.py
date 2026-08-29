import os
import sys
import re
import logging
from pathlib import Path
from dotenv import load_dotenv 

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load .env from backend directory and current working directory
load_dotenv(BACKEND_DIR / ".env")
load_dotenv()

# Database settings
MONGO_URL = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
DB_NAME = os.environ.get("DB_NAME", "crack")

# LLM integration
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# JWT Auth settings
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGO = "HS256"
JWT_TTL_DAYS = 7

# Fail fast on weak or placeholder JWT secret
if not JWT_SECRET or len(JWT_SECRET) < 32 or "placeholder" in JWT_SECRET.lower():
    raise RuntimeError("JWT_SECRET must be a strong random value of >= 32 chars")

# Regex pattern for subscription ID validation (defensive against reflected XSS)
RZP_ID_RE = re.compile(r"^sub_[A-Za-z0-9]{6,32}$")

# Food payload limits.
# Frontend compresses to 640px / JPEG 0.5 → ~100–300 KB decoded.
# We allow up to 400 KB to give a comfortable margin, and reject anything
# larger with HTTP 413 before it reaches the LLM — protecting token budget
# and preventing quota-slot abuse via oversized crafted payloads.
MAX_IMAGE_BYTES = 400 * 1024  # 400 KB decoded

# Razorpay configuration
RZP_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RZP_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RZP_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
RZP_PLAN_ID = os.environ.get("RAZORPAY_PLAN_ID", "")
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "")
if not PUBLIC_API_URL:
    import logging
    logging.getLogger("crack").warning(
        "PUBLIC_API_URL is not set. Email verification and password-reset links "
        "will fail at runtime. Set PUBLIC_API_URL in your .env file."
    )
MOBILE_RETURN_URL = os.environ.get("MOBILE_RETURN_URL", "crack://razorpay-complete")
SUB_AMOUNT_PAISE = int(os.environ.get("SUBSCRIPTION_AMOUNT_PAISE", 3900))
TRIAL_DAYS = int(os.environ.get("SUBSCRIPTION_TRIAL_DAYS", 10))
RZP_LIVE = bool(RZP_KEY_ID) and not RZP_KEY_ID.endswith("placeholder")
RZP_WEBHOOK_LIVE = bool(RZP_WEBHOOK_SECRET) and "placeholder" not in RZP_WEBHOOK_SECRET.lower()

# Email / SMTP / Brevo configuration
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@crack.app")

# If BREVO_API_KEY is present, default dry-run to False so emails are sent automatically
_default_dry_run = "0" if (BREVO_API_KEY or SMTP_HOST) else "1"
SMTP_DRY_RUN = os.environ.get("SMTP_DRY_RUN", _default_dry_run).lower() in ("1", "true", "yes")

# Email verification settings
EMAIL_VERIFY_TTL_HOURS = int(os.environ.get("EMAIL_VERIFY_TTL_HOURS", "24"))
RESEND_MIN_INTERVAL_SECONDS = int(os.environ.get("RESEND_MIN_INTERVAL_SECONDS", "60"))

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "1").lower() in ("1", "true", "yes")

# Auth routes rate limits (strictest: IP limits + per-account limits with exponential backoff)
RATE_LIMIT_AUTH_IP_REQUESTS = int(os.environ.get("RATE_LIMIT_AUTH_IP_REQUESTS", "20"))
RATE_LIMIT_AUTH_IP_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_AUTH_IP_WINDOW_SECONDS", "60"))
RATE_LIMIT_AUTH_IP_BASE_BACKOFF = float(os.environ.get("RATE_LIMIT_AUTH_IP_BASE_BACKOFF", "2.0"))
RATE_LIMIT_AUTH_IP_BACKOFF_FACTOR = float(os.environ.get("RATE_LIMIT_AUTH_IP_BACKOFF_FACTOR", "2.0"))
RATE_LIMIT_AUTH_IP_MAX_BACKOFF = float(os.environ.get("RATE_LIMIT_AUTH_IP_MAX_BACKOFF", "300.0"))

RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS = int(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS", "5"))
RATE_LIMIT_AUTH_ACCOUNT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_WINDOW_SECONDS", "300"))
RATE_LIMIT_AUTH_ACCOUNT_BASE_BACKOFF = float(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_BASE_BACKOFF", "5.0"))
RATE_LIMIT_AUTH_ACCOUNT_BACKOFF_FACTOR = float(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_BACKOFF_FACTOR", "2.0"))
RATE_LIMIT_AUTH_ACCOUNT_MAX_BACKOFF = float(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_MAX_BACKOFF", "900.0"))

# Public endpoints rate limits (moderate limits per IP)
RATE_LIMIT_PUBLIC_REQUESTS = int(os.environ.get("RATE_LIMIT_PUBLIC_REQUESTS", "60"))
RATE_LIMIT_PUBLIC_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_PUBLIC_WINDOW_SECONDS", "60"))

# Authenticated user actions rate limits (looser limits per authenticated user)
RATE_LIMIT_USER_REQUESTS = int(os.environ.get("RATE_LIMIT_USER_REQUESTS", "300"))
RATE_LIMIT_USER_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_USER_WINDOW_SECONDS", "60"))

# Awakening checkpoint secret
WAKEUP_SECRET_KEY = os.environ.get("WAKEUP_SECRET_KEY", "").strip()

# Ensure it meets minimum length if set
if WAKEUP_SECRET_KEY and len(WAKEUP_SECRET_KEY) < 16:
    raise RuntimeError("WAKEUP_SECRET_KEY must be at least 16 characters long if configured.")

# CORS Configuration
# Comma-separated list of allowed origins. Defaults to standard local development origins.
CORS_ORIGINS_RAW = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://localhost:8081,http://localhost:19006,http://127.0.0.1:3000,http://127.0.0.1:8080,http://127.0.0.1:8081,http://127.0.0.1:19006",
)
ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_RAW.split(",") if origin.strip()]

# Usage quotas
# Free-trial users: 5 AI scans per calendar day (UTC). Resets automatically on the next day.
# Paid users: 500 AI scans per billing month. Resets on subscription.charged webhook.
TRIAL_DAILY_MAX_REQUESTS = int(os.environ.get("TRIAL_DAILY_MAX_REQUESTS", "5"))
PAID_MONTHLY_MAX_REQUESTS = int(os.environ.get("PAID_MONTHLY_MAX_REQUESTS", "500"))

# Logger setup
logger = logging.getLogger("crack")

