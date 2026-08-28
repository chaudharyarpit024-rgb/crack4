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
MONGO_URL = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017"
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

# Food payload limits
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB decoded

# Razorpay configuration
RZP_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RZP_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RZP_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
RZP_PLAN_ID = os.environ.get("RAZORPAY_PLAN_ID", "")
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "")
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

# Logger setup
logger = logging.getLogger("crack")
