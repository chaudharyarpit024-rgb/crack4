"""Tiered rate limiting engine with configurable thresholds and exponential backoff.

Provides three rate-limiting tiers:
1. Auth Routes (Strictest): Combines per-IP and per-account limits with exponential
   backoff rather than a hard lockout.
2. Public Endpoints (Moderate): Per-IP sliding-window rate limiting.
3. Authenticated User Actions (Looser): Per-user sliding-window rate limiting.

All limits, windows, and backoff parameters are dynamically configurable via environment
variables / settings.py.
"""
import json
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, status

from config.settings import (
    RATE_LIMIT_AUTH_ACCOUNT_BACKOFF_FACTOR,
    RATE_LIMIT_AUTH_ACCOUNT_BASE_BACKOFF,
    RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS,
    RATE_LIMIT_AUTH_ACCOUNT_MAX_BACKOFF,
    RATE_LIMIT_AUTH_ACCOUNT_WINDOW_SECONDS,
    RATE_LIMIT_AUTH_IP_BACKOFF_FACTOR,
    RATE_LIMIT_AUTH_IP_BASE_BACKOFF,
    RATE_LIMIT_AUTH_IP_MAX_BACKOFF,
    RATE_LIMIT_AUTH_IP_REQUESTS,
    RATE_LIMIT_AUTH_IP_WINDOW_SECONDS,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_PUBLIC_REQUESTS,
    RATE_LIMIT_PUBLIC_WINDOW_SECONDS,
    RATE_LIMIT_USER_REQUESTS,
    RATE_LIMIT_USER_WINDOW_SECONDS,
    logger,
)


def mask_email(email: str) -> str:
    """Mask email to prevent writing raw PII to logs."""
    if not email or "@" not in email:
        return email
    parts = email.split("@", 1)
    name = parts[0]
    domain = parts[1]
    if len(name) <= 2:
        masked_name = name[0] + "*" * (len(name) - 1) if name else ""
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"


def get_client_ip(request: Request) -> str:
    """Extract client IP address safely from headers or connection."""
    # Check CF-Connecting-IP (Cloudflare)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Check X-Forwarded-For (can contain comma-separated IPs; client is first)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip

    # Direct client connection host
    if request.client and request.client.host:
        return request.client.host.strip()

    return "127.0.0.1"


class RateLimiterStore:
    """Thread-safe in-memory store for sliding-window and exponential-backoff rate limits."""

    def __init__(self):
        self._lock = threading.Lock()
        # Sliding-window timestamps: key -> list of float timestamps
        self._ip_records: Dict[str, List[float]] = {}
        self._account_records: Dict[str, List[float]] = {}
        self._user_records: Dict[str, List[float]] = {}

        # Exponential backoff state: key -> {"cooldown_until": float, "excess": int}
        self._ip_backoffs: Dict[str, Dict[str, Any]] = {}
        self._account_backoffs: Dict[str, Dict[str, Any]] = {}

        self._last_cleanup = time.time()

    def _cleanup_stale(self, now: float):
        """Purge records older than 1 hour to prevent memory leaks."""
        if now - self._last_cleanup < 300:  # Run at most every 5 minutes
            return
        self._last_cleanup = now
        cutoff = now - 3600

        for store in (self._ip_records, self._account_records, self._user_records):
            stale_keys = [k for k, v in store.items() if not v or v[-1] < cutoff]
            for k in stale_keys:
                del store[k]

        for b_store in (self._ip_backoffs, self._account_backoffs):
            stale_b = [k for k, v in b_store.items() if v.get("cooldown_until", 0) < cutoff]
            for k in stale_b:
                del b_store[k]

    def reset(self):
        """Clear all stored rate limiting data (useful for test fixtures)."""
        with self._lock:
            self._ip_records.clear()
            self._account_records.clear()
            self._user_records.clear()
            self._ip_backoffs.clear()
            self._account_backoffs.clear()

    def record_auth_success(self, account: Optional[str] = None, ip: Optional[str] = None):
        """Reset exponential backoff penalty on successful authentication."""
        with self._lock:
            if account:
                acc_key = account.lower().strip()
                self._account_backoffs.pop(acc_key, None)
                self._account_records.pop(acc_key, None)
            if ip:
                ip_key = ip.strip()
                self._ip_backoffs.pop(ip_key, None)

    def record_auth_failure(self, account: Optional[str] = None, ip: Optional[str] = None):
        """Log auth failure; attempt is already tracked by check_auth_rate_limit."""
        if account:
            logger.info("Recorded authentication failure for account: %s", mask_email(account))
        elif ip:
            logger.info(f"Recorded authentication failure for IP: {ip}")

    def check_auth_rate_limit(
        self,
        ip: str,
        account: Optional[str] = None,
        custom_ip_limit: Optional[int] = None,
        custom_ip_window: Optional[int] = None,
        custom_acc_limit: Optional[int] = None,
        custom_acc_window: Optional[int] = None,
    ) -> Tuple[bool, int, Dict[str, str]]:
        """Check rate limits for authentication endpoints using dual IP + account exponential backoff.

        Returns: (allowed: bool, retry_after_seconds: int, headers: dict)
        """
        import os
        from config.settings import RATE_LIMIT_ENABLED as CURRENT_ENABLED

        enabled = os.environ.get("RATE_LIMIT_ENABLED", str(CURRENT_ENABLED)).lower() in ("1", "true", "yes")
        if not enabled:
            return True, 0, {}

        ip_limit = custom_ip_limit or int(os.environ.get("RATE_LIMIT_AUTH_IP_REQUESTS", RATE_LIMIT_AUTH_IP_REQUESTS))
        ip_window = custom_ip_window or int(os.environ.get("RATE_LIMIT_AUTH_IP_WINDOW_SECONDS", RATE_LIMIT_AUTH_IP_WINDOW_SECONDS))
        ip_base_backoff = float(os.environ.get("RATE_LIMIT_AUTH_IP_BASE_BACKOFF", RATE_LIMIT_AUTH_IP_BASE_BACKOFF))
        ip_factor = float(os.environ.get("RATE_LIMIT_AUTH_IP_BACKOFF_FACTOR", RATE_LIMIT_AUTH_IP_BACKOFF_FACTOR))
        ip_max_backoff = float(os.environ.get("RATE_LIMIT_AUTH_IP_MAX_BACKOFF", RATE_LIMIT_AUTH_IP_MAX_BACKOFF))

        acc_limit = custom_acc_limit or int(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS", RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS))
        acc_window = custom_acc_window or int(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_WINDOW_SECONDS", RATE_LIMIT_AUTH_ACCOUNT_WINDOW_SECONDS))
        acc_base_backoff = float(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_BASE_BACKOFF", RATE_LIMIT_AUTH_ACCOUNT_BASE_BACKOFF))
        acc_factor = float(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_BACKOFF_FACTOR", RATE_LIMIT_AUTH_ACCOUNT_BACKOFF_FACTOR))
        acc_max_backoff = float(os.environ.get("RATE_LIMIT_AUTH_ACCOUNT_MAX_BACKOFF", RATE_LIMIT_AUTH_ACCOUNT_MAX_BACKOFF))

        now = time.time()
        with self._lock:
            self._cleanup_stale(now)
            ip_key = ip.strip()

            # 1. Check IP active backoff cooldown
            ip_backoff = self._ip_backoffs.get(ip_key)
            if ip_backoff and now < ip_backoff.get("cooldown_until", 0):
                retry_after = max(1, math.ceil(ip_backoff["cooldown_until"] - now))
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(ip_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(ip_backoff["cooldown_until"])),
                }
                return False, retry_after, headers

            # 2. Check Account active backoff cooldown (if account identifier supplied)
            acc_key = account.lower().strip() if account else None
            if acc_key:
                acc_backoff = self._account_backoffs.get(acc_key)
                if acc_backoff and now < acc_backoff.get("cooldown_until", 0):
                    retry_after = max(1, math.ceil(acc_backoff["cooldown_until"] - now))
                    headers = {
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(acc_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(acc_backoff["cooldown_until"])),
                    }
                    return False, retry_after, headers

            # 3. Slide IP window and check threshold
            ip_history = self._ip_records.setdefault(ip_key, [])
            ip_history = [t for t in ip_history if t > now - ip_window]
            self._ip_records[ip_key] = ip_history

            if len(ip_history) >= ip_limit:
                excess = len(ip_history) - ip_limit + 1
                delay = min(ip_max_backoff, ip_base_backoff * (ip_factor ** (excess - 1)))
                cooldown_until = now + delay
                self._ip_backoffs[ip_key] = {"cooldown_until": cooldown_until, "excess": excess}
                ip_history.append(now)  # Count attempt
                retry_after = max(1, math.ceil(delay))
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(ip_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(cooldown_until)),
                }
                return False, retry_after, headers

            # 4. Slide Account window and check threshold
            if acc_key:
                acc_history = self._account_records.setdefault(acc_key, [])
                acc_history = [t for t in acc_history if t > now - acc_window]
                self._account_records[acc_key] = acc_history

                if len(acc_history) >= acc_limit:
                    excess = len(acc_history) - acc_limit + 1
                    delay = min(acc_max_backoff, acc_base_backoff * (acc_factor ** (excess - 1)))
                    cooldown_until = now + delay
                    self._account_backoffs[acc_key] = {"cooldown_until": cooldown_until, "excess": excess}
                    acc_history.append(now)  # Count attempt
                    retry_after = max(1, math.ceil(delay))
                    headers = {
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(acc_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(cooldown_until)),
                    }
                    return False, retry_after, headers

            # 5. Allowed: record request
            ip_history.append(now)
            if acc_key:
                self._account_records[acc_key].append(now)

            remaining = max(0, ip_limit - len(ip_history))
            reset_ts = int(now + ip_window)
            headers = {
                "X-RateLimit-Limit": str(ip_limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_ts),
            }
            return True, 0, headers

    def check_public_rate_limit(
        self,
        ip: str,
        custom_limit: Optional[int] = None,
        custom_window: Optional[int] = None,
    ) -> Tuple[bool, int, Dict[str, str]]:
        """Check sliding-window rate limit for moderate public endpoints (per IP)."""
        import os
        from config.settings import RATE_LIMIT_ENABLED as CURRENT_ENABLED

        enabled = os.environ.get("RATE_LIMIT_ENABLED", str(CURRENT_ENABLED)).lower() in ("1", "true", "yes")
        if not enabled:
            return True, 0, {}

        limit = custom_limit or int(os.environ.get("RATE_LIMIT_PUBLIC_REQUESTS", RATE_LIMIT_PUBLIC_REQUESTS))
        window = custom_window or int(os.environ.get("RATE_LIMIT_PUBLIC_WINDOW_SECONDS", RATE_LIMIT_PUBLIC_WINDOW_SECONDS))

        now = time.time()
        with self._lock:
            self._cleanup_stale(now)
            ip_key = ip.strip()
            history = self._ip_records.setdefault(ip_key, [])
            history = [t for t in history if t > now - window]
            self._ip_records[ip_key] = history

            if len(history) >= limit:
                oldest = history[0]
                retry_after = max(1, math.ceil(oldest + window - now))
                reset_ts = int(oldest + window)
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_ts),
                }
                return False, retry_after, headers

            history.append(now)
            remaining = max(0, limit - len(history))
            reset_ts = int(now + window)
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_ts),
            }
            return True, 0, headers

    def check_user_rate_limit(
        self,
        user_id: str,
        custom_limit: Optional[int] = None,
        custom_window: Optional[int] = None,
    ) -> Tuple[bool, int, Dict[str, str]]:
        """Check sliding-window rate limit for authenticated user actions (per user ID)."""
        import os
        from config.settings import RATE_LIMIT_ENABLED as CURRENT_ENABLED

        enabled = os.environ.get("RATE_LIMIT_ENABLED", str(CURRENT_ENABLED)).lower() in ("1", "true", "yes")
        if not enabled:
            return True, 0, {}

        limit = custom_limit or int(os.environ.get("RATE_LIMIT_USER_REQUESTS", RATE_LIMIT_USER_REQUESTS))
        window = custom_window or int(os.environ.get("RATE_LIMIT_USER_WINDOW_SECONDS", RATE_LIMIT_USER_WINDOW_SECONDS))

        now = time.time()
        with self._lock:
            self._cleanup_stale(now)
            u_key = user_id.strip()
            history = self._user_records.setdefault(u_key, [])
            history = [t for t in history if t > now - window]
            self._user_records[u_key] = history

            if len(history) >= limit:
                oldest = history[0]
                retry_after = max(1, math.ceil(oldest + window - now))
                reset_ts = int(oldest + window)
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_ts),
                }
                return False, retry_after, headers

            history.append(now)
            remaining = max(0, limit - len(history))
            reset_ts = int(now + window)
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_ts),
            }
            return True, 0, headers


# Global store instance
rate_limiter = RateLimiterStore()


# --- Account Extractor Helpers ---

async def extract_email_from_body(request: Request) -> Optional[str]:
    """Safely extract email from JSON body without consuming the request stream."""
    try:
        raw_body = await request.body()
        if not raw_body:
            return None
        data = json.loads(raw_body.decode("utf-8"))
        if isinstance(data, dict):
            email = data.get("email")
            if email and isinstance(email, str):
                return email.strip().lower()
    except Exception:
        pass
    return None


async def extract_token_from_body(request: Request) -> Optional[str]:
    """Safely extract token from JSON body without consuming the request stream."""
    try:
        raw_body = await request.body()
        if not raw_body:
            return None
        data = json.loads(raw_body.decode("utf-8"))
        if isinstance(data, dict):
            token = data.get("token")
            if token and isinstance(token, str):
                return token.strip()
    except Exception:
        pass
    return None


# --- FastAPI Dependency Providers ---

def rate_limit_auth(
    account_extractor: Optional[Callable[[Request], Any]] = None,
    custom_ip_limit: Optional[int] = None,
    custom_acc_limit: Optional[int] = None,
):
    """Factory creating a FastAPI dependency for strict auth rate limiting with exponential backoff."""

    async def _auth_dependency(request: Request):
        ip = get_client_ip(request)
        account = None
        if account_extractor:
            try:
                account = await account_extractor(request)
            except Exception:
                account = None

        allowed, retry_after, headers = rate_limiter.check_auth_rate_limit(
            ip=ip,
            account=account,
            custom_ip_limit=custom_ip_limit,
            custom_acc_limit=custom_acc_limit,
        )
        if hasattr(request, "state"):
            request.state.rate_limit_headers = headers

        if not allowed:
            target = f"account '{mask_email(account)}'" if account else f"IP '{ip}'"
            logger.warning(f"Auth rate limit exceeded for {target}. Backoff retry-after: {retry_after}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many authentication attempts. Please try again in {retry_after} seconds.",
                headers=headers,
            )

    return _auth_dependency


async def rate_limit_public(request: Request):
    """FastAPI dependency for moderate public endpoint rate limiting."""
    ip = get_client_ip(request)
    allowed, retry_after, headers = rate_limiter.check_public_rate_limit(ip=ip)
    if hasattr(request, "state"):
        request.state.rate_limit_headers = headers

    if not allowed:
        logger.warning(f"Public rate limit exceeded for IP '{ip}'. Retry-after: {retry_after}s")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please try again in {retry_after} seconds.",
            headers=headers,
        )


def record_auth_success(account: Optional[str] = None, ip: Optional[str] = None):
    """Exposed helper to reset exponential backoff after successful auth."""
    rate_limiter.record_auth_success(account=account, ip=ip)


def record_auth_failure(account: Optional[str] = None, ip: Optional[str] = None):
    """Exposed helper to register failed auth attempt for exponential backoff."""
    rate_limiter.record_auth_failure(account=account, ip=ip)
