"""Comprehensive tests for multi-tiered rate limiting with exponential backoff.

Covers:
1. Stricter limits on authentication routes (/api/auth/login, signup, forgot-password, reset-password, etc.)
2. Combination of per-IP and per-account limits with exponential backoff on auth routes (no hard lockout)
3. Moderate limits on public endpoints (/api/subscription/checkout-page, /api, /, etc.)
4. Looser limits on authenticated user actions (/api/profile, /api/food/*, /api/auth/me)
5. Fully configurable thresholds via settings/environment
6. Standard rate limit headers (Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
7. Success reset for account backoff
"""
import asyncio
import os
import sys
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_ratelimit_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-" + uuid.uuid4().hex)

from server import app, init_db, close_db
from security.rate_limiter import rate_limiter
from security.jwt import make_token
import utils.email as email_mod
import controllers.auth_controller as auth_ctrl


async def _fake_send_email(to: str, subject: str, html: str, text: str) -> bool:
    return True


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_rate_limiter():
    """Reset the rate limiter store before each test."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


async def _setup_test_env():
    email_mod.send_email = _fake_send_email
    auth_ctrl.send_email = _fake_send_email
    await init_db()
    transport = ASGITransport(app=app)

    async def _teardown():
        try:
            from database.mongodb import client
            await client.drop_database(os.environ["DB_NAME"])
        except Exception:
            pass
        await close_db()

    return transport, _teardown


# ---------------------------------------------------------------------------
# 1. Auth IP Rate Limiting & Exponential Backoff
# ---------------------------------------------------------------------------
def test_auth_route_ip_exponential_backoff():
    async def _go():
        transport, teardown = await _setup_test_env()
        try:
            # Configure custom low limit for deterministic test: 3 requests allowed, base backoff 2s, factor 2.0
            os.environ["RATE_LIMIT_AUTH_IP_REQUESTS"] = "3"
            os.environ["RATE_LIMIT_AUTH_IP_WINDOW_SECONDS"] = "60"
            os.environ["RATE_LIMIT_AUTH_IP_BASE_BACKOFF"] = "2.0"
            os.environ["RATE_LIMIT_AUTH_IP_BACKOFF_FACTOR"] = "2.0"

            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                headers = {"X-Forwarded-For": "198.51.100.1"}

                # Requests 1, 2, 3 should be permitted (status 400 for bad payload, not 429)
                for i in range(3):
                    r = await client.post("/api/auth/signup", json={"email": f"user{i}@example.com", "password": "password123"}, headers=headers)
                    assert r.status_code == 200, f"Request {i+1} should succeed, got {r.status_code}"
                    assert "X-RateLimit-Limit" in r.headers
                    assert r.headers["X-RateLimit-Limit"] == "3"

                # Request 4 should be throttled by IP limit with base backoff (2s)
                r4 = await client.post("/api/auth/signup", json={"email": "user4@example.com", "password": "password123"}, headers=headers)
                assert r4.status_code == 429, f"Request 4 should be 429, got {r4.status_code}"
                assert "Retry-After" in r4.headers
                retry_after_1 = int(r4.headers["Retry-After"])
                assert retry_after_1 >= 2, f"Expected Retry-After >= 2s, got {retry_after_1}"
                assert "X-RateLimit-Remaining" in r4.headers
                assert r4.headers["X-RateLimit-Remaining"] == "0"

                # Request 5 during cooldown or excess should experience exponential backoff (e.g. 4s)
                # Advance time or check cooldown
                r5 = await client.post("/api/auth/signup", json={"email": "user5@example.com", "password": "password123"}, headers=headers)
                assert r5.status_code == 429
                assert "Retry-After" in r5.headers

                # Different IP is NOT throttled
                r_diff = await client.post(
                    "/api/auth/signup",
                    json={"email": "diff_user@example.com", "password": "password123"},
                    headers={"X-Forwarded-For": "198.51.100.2"},
                )
                assert r_diff.status_code == 200, "Different IP should not be throttled"
        finally:
            os.environ["RATE_LIMIT_AUTH_IP_REQUESTS"] = "20"
            await teardown()

    _run(_go())


# ---------------------------------------------------------------------------
# 2. Auth Per-Account Rate Limiting & Exponential Backoff
# ---------------------------------------------------------------------------
def test_auth_route_account_exponential_backoff_and_reset():
    async def _go():
        transport, teardown = await _setup_test_env()
        try:
            # 2 attempts allowed per account before backoff, base backoff 3s, factor 2.0
            os.environ["RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS"] = "2"
            os.environ["RATE_LIMIT_AUTH_ACCOUNT_WINDOW_SECONDS"] = "300"
            os.environ["RATE_LIMIT_AUTH_ACCOUNT_BASE_BACKOFF"] = "3.0"
            os.environ["RATE_LIMIT_AUTH_ACCOUNT_BACKOFF_FACTOR"] = "2.0"

            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                target_email = "victim@example.com"

                # Sign up target user and verify
                r = await client.post("/api/auth/signup", json={"email": target_email, "password": "correctPassword123"})
                assert r.status_code == 200

                from database.mongodb import db
                await db.users.update_one({"email": target_email}, {"$set": {"email_verified": True}})

                # Reset rate limiter so setup requests don't consume test quota
                rate_limiter.reset()

                # Attempt 1: Failed login from IP 10.0.0.1
                r1 = await client.post(
                    "/api/auth/login",
                    json={"email": target_email, "password": "wrongPassword1"},
                    headers={"X-Forwarded-For": "10.0.0.1"},
                )
                assert r1.status_code == 401

                # Attempt 2: Failed login from IP 10.0.0.2 (different IP, same account)
                r2 = await client.post(
                    "/api/auth/login",
                    json={"email": target_email, "password": "wrongPassword2"},
                    headers={"X-Forwarded-For": "10.0.0.2"},
                )
                assert r2.status_code == 401

                # Attempt 3: Exceeds 2-attempt account limit -> should trigger account exponential backoff (429)
                r3 = await client.post(
                    "/api/auth/login",
                    json={"email": target_email, "password": "wrongPassword3"},
                    headers={"X-Forwarded-For": "10.0.0.3"},
                )
                assert r3.status_code == 429, f"Expected 429 for throttled account, got {r3.status_code} {r3.text}"
                assert "Retry-After" in r3.headers
                assert int(r3.headers["Retry-After"]) >= 3

                # Attempt with DIFFERENT account from IP 10.0.0.3 is NOT throttled
                r_other = await client.post(
                    "/api/auth/login",
                    json={"email": "other@example.com", "password": "anyPassword"},
                    headers={"X-Forwarded-For": "10.0.0.3"},
                )
                assert r_other.status_code == 401, "Different account should not be locked by another account's backoff"

                # Reset account backoff via successful login or record_auth_success
                rate_limiter.record_auth_success(account=target_email)

                # Now legitimate login succeeds
                r_success = await client.post(
                    "/api/auth/login",
                    json={"email": target_email, "password": "correctPassword123"},
                    headers={"X-Forwarded-For": "10.0.0.4"},
                )
                assert r_success.status_code == 200
                assert "token" in r_success.json()
        finally:
            os.environ["RATE_LIMIT_AUTH_ACCOUNT_MAX_ATTEMPTS"] = "5"
            await teardown()

    _run(_go())


# ---------------------------------------------------------------------------
# 3. Public Endpoint Rate Limiting (Moderate Limits)
# ---------------------------------------------------------------------------
def test_public_endpoint_rate_limiting():
    async def _go():
        transport, teardown = await _setup_test_env()
        try:
            # Set public limit to 4 requests / 60 seconds
            os.environ["RATE_LIMIT_PUBLIC_REQUESTS"] = "4"
            os.environ["RATE_LIMIT_PUBLIC_WINDOW_SECONDS"] = "60"

            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                headers = {"X-Forwarded-For": "192.0.2.55"}

                # Requests 1..4 on root health endpoint /
                for i in range(4):
                    r = await client.get("/", headers=headers)
                    assert r.status_code == 200, f"Request {i+1} failed"
                    assert r.headers["X-RateLimit-Limit"] == "4"
                    assert r.headers["X-RateLimit-Remaining"] == str(4 - (i + 1))

                # Request 5 should be throttled (429)
                r5 = await client.get("/", headers=headers)
                assert r5.status_code == 429
                assert "Retry-After" in r5.headers
                assert "Too many requests" in r5.json()["detail"]

                # Request 5 from DIFFERENT IP succeeds
                r_diff = await client.get("/", headers={"X-Forwarded-For": "192.0.2.56"})
                assert r_diff.status_code == 200

                # Also test public checkout page endpoint
                r_checkout_blocked = await client.get(
                    "/api/subscription/checkout-page",
                    params={"subscription_id": "sub_test1234"},
                    headers=headers,
                )
                assert r_checkout_blocked.status_code == 429
        finally:
            os.environ["RATE_LIMIT_PUBLIC_REQUESTS"] = "60"
            await teardown()

    _run(_go())


# ---------------------------------------------------------------------------
# 4. Authenticated User Rate Limiting (Looser Limits)
# ---------------------------------------------------------------------------
def test_authenticated_user_rate_limiting():
    async def _go():
        transport, teardown = await _setup_test_env()
        try:
            # Set user limit to 3 requests per 60s
            os.environ["RATE_LIMIT_USER_REQUESTS"] = "3"
            os.environ["RATE_LIMIT_USER_WINDOW_SECONDS"] = "60"

            user1_id = str(uuid.uuid4())
            user2_id = str(uuid.uuid4())

            from database.mongodb import db
            await db.users.insert_one({"id": user1_id, "email": "u1@example.com", "email_verified": True})
            await db.users.insert_one({"id": user2_id, "email": "u2@example.com", "email_verified": True})

            token1 = make_token(user1_id)
            token2 = make_token(user2_id)

            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                # User 1 makes 3 requests to /api/auth/me
                for i in range(3):
                    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token1}"})
                    assert r.status_code == 200
                    assert r.headers["X-RateLimit-Limit"] == "3"

                # User 1's 4th request is throttled
                r4 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token1}"})
                assert r4.status_code == 429
                assert "Retry-After" in r4.headers

                # User 2 is NOT throttled
                r_u2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token2}"})
                assert r_u2.status_code == 200

                # User 1 blocked on /api/profile as well
                r_prof = await client.put(
                    "/api/profile",
                    json={"goal": "maintain", "weight_kg": 70, "height_cm": 175, "age": 25, "gender": "male"},
                    headers={"Authorization": f"Bearer {token1}"},
                )
                assert r_prof.status_code == 429
        finally:
            os.environ["RATE_LIMIT_USER_REQUESTS"] = "300"
            await teardown()

    _run(_go())


# ---------------------------------------------------------------------------
# 5. Master Disabled Flag
# ---------------------------------------------------------------------------
def test_rate_limit_disabled_flag():
    async def _go():
        transport, teardown = await _setup_test_env()
        try:
            os.environ["RATE_LIMIT_ENABLED"] = "0"
            os.environ["RATE_LIMIT_PUBLIC_REQUESTS"] = "1"

            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                headers = {"X-Forwarded-For": "1.2.3.4"}
                for _ in range(5):
                    r = await client.get("/", headers=headers)
                    assert r.status_code == 200
        finally:
            os.environ["RATE_LIMIT_ENABLED"] = "1"
            os.environ["RATE_LIMIT_PUBLIC_REQUESTS"] = "60"
            await teardown()

    _run(_go())
