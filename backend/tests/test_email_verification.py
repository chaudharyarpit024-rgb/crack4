"""Tests for the email verification flow.

Strategy
--------
The verification flow is end-to-end: signup creates a user, an email is sent
with a 24h JWT, the link is consumed by POST /api/auth/verify, and the JTI
is recorded in `used_verification_jti` to prevent replay.

These tests run the FastAPI app **in-process** via `httpx.AsyncClient` +
`ASGITransport` against an isolated test database (`DB_NAME=crack_test_email_xxx`)
so they don't touch production data. We monkeypatch `utils.email.send_email`
to capture the verification token in memory — no log scraping, no SMTP.

Why synchronous `def test_...` with `anyio.run` inside?
The user env may not have `pytest-asyncio` installed. `anyio` is already a
transitive dep of httpx/fastapi, so we lean on it for the event loop. This file
runs under either `pytest tests/test_email_verification.py` or as a plain
script (`python tests/test_email_verification.py`).

Run with:
    cd backend
    python -m tests.test_email_verification     # ad-hoc run
    pytest tests/test_email_verification.py -v   # if pytest is installed
"""
import os
import re
import sys
import time
import uuid
from typing import List

# Ensure backend root is on sys.path so `from server import app` works whether
# this file is invoked as `python tests/test_email_verification.py` (CWD=backend)
# or as `pytest tests/test_email_verification.py` (CWD=backend).
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Force a unique test database BEFORE app import so init_db hits the right DB.
os.environ.setdefault("DB_NAME", f"crack_test_email_{uuid.uuid4().hex[:8]}")
# SMTP dry-run is moot because we monkeypatch send_email, but keep it on.
os.environ.setdefault("SMTP_DRY_RUN", "1")
# Make sure we have a strong JWT secret for settings import.
os.environ.setdefault("JWT_SECRET", "test-secret-" + uuid.uuid4().hex)


# ---- Captured emails --------------------------------------------------------
class _SentEmail:
    __slots__ = ("to", "subject", "text", "html")

    def __init__(self, to: str, subject: str, text: str, html: str):
        self.to = to
        self.subject = subject
        self.text = text
        self.html = html


_SENT: List[_SentEmail] = []


async def _fake_send_email(to: str, subject: str, html: str, text: str) -> bool:
    _SENT.append(_SentEmail(to, subject, text, html))
    return True


# ---- Test infrastructure ----------------------------------------------------
def _run(coro):
    """Run a coroutine on a fresh event loop. Works without pytest-asyncio."""
    import asyncio
    return asyncio.run(coro)


def _new_email() -> str:
    return f"qa+{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"


def _extract_token(email: _SentEmail) -> str:
    """Pull the verification token out of a captured email (text or html)."""
    match = re.search(r"token=([A-Za-z0-9._\-]+)", email.text) or re.search(
        r"token=([A-Za-z0-9._\-]+)", email.html
    )
    assert match, f"No token in email: {email.text[:200]}"
    return match.group(1)


async def _setup_app():
    """Import app, patch send_email, init the test DB, return (app, client, teardown)."""
    from server import app, init_db, close_db
    import utils.email as email_mod
    import controllers.auth_controller as auth_ctrl

    original_email = email_mod.send_email
    original_ctrl = auth_ctrl.send_email
    email_mod.send_email = _fake_send_email
    auth_ctrl.send_email = _fake_send_email

    await init_db()
    _SENT.clear()
    from security.rate_limiter import rate_limiter
    rate_limiter.reset()

    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)

    async def _teardown():
        email_mod.send_email = original_email
        auth_ctrl.send_email = original_ctrl
        try:
            from database.mongodb import client
            await client.drop_database(os.environ["DB_NAME"])
        except Exception:
            pass
        await close_db()

    return app, transport, _teardown


# =============================================================================
# Tests
# =============================================================================

def test_root_ok():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                r = await client.get("/")
                assert r.status_code == 200, r.text
                assert r.json().get("ok") is True
        finally:
            await teardown()
    _run(_go())


def test_signup_returns_no_auth_token():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                r = await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                assert r.status_code == 200, r.text
                body = r.json()
                assert "token" not in body, "Signup must not issue a token before email is verified"
                assert body.get("ok") is True
                assert body.get("email") == email
                assert "message" in body
                assert _SENT, "Verification email should have been sent on signup"
                assert _SENT[-1].to == email
        finally:
            await teardown()
    _run(_go())


def test_signup_duplicate_email_returns_400():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                r1 = await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                assert r1.status_code == 200, r1.text
                r2 = await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                assert r2.status_code == 400, r2.text
        finally:
            await teardown()
    _run(_go())


def test_login_blocked_until_verified():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                r = await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                assert r.status_code == 200
                r = await client.post("/api/auth/login", json={"email": email, "password": "secret123"})
                assert r.status_code == 403, r.text
                assert "verified" in r.json().get("detail", "").lower()
        finally:
            await teardown()
    _run(_go())


def test_verify_with_garbage_token_returns_400():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                r = await client.post("/api/auth/verify", json={"token": "not-a-jwt"})
                assert r.status_code == 400, r.text
        finally:
            await teardown()
    _run(_go())


def test_verify_with_wrong_type_token_returns_400():
    """A regular auth JWT (no `type=verify_email`) must be rejected."""
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from security.jwt import make_token
            wrong_type = make_token("some-user", extra_claims={"jti": uuid.uuid4().hex})
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                r = await client.post("/api/auth/verify", json={"token": wrong_type})
                assert r.status_code == 400, r.text
        finally:
            await teardown()
    _run(_go())


def test_verify_with_expired_token_returns_400():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from datetime import timedelta
            from security.jwt import make_token
            expired = make_token(
                "fake-user",
                extra_claims={"type": "verify_email", "jti": uuid.uuid4().hex},
                ttl=timedelta(minutes=-1),  # already expired
            )
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                r = await client.post("/api/auth/verify", json={"token": expired})
                assert r.status_code == 400, r.text
        finally:
            await teardown()
    _run(_go())


def test_full_signup_then_verify_flow():
    """End-to-end: signup → consume token → login works."""
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                r = await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                assert r.status_code == 200
                sent = _SENT[-1]
                token = _extract_token(sent)

                r = await client.post("/api/auth/verify", json={"token": token})
                assert r.status_code == 200, r.text
                body = r.json()
                assert "token" in body, "Verify must return an auth token on success"
                assert body["user"]["email"] == email
                assert body["user"].get("email_verified") is True

                # Login now works.
                r = await client.post("/api/auth/login", json={"email": email, "password": "secret123"})
                assert r.status_code == 200, r.text
                assert "token" in r.json()
        finally:
            await teardown()
    _run(_go())


def test_jti_cannot_be_reused():
    """Once a verification token is consumed, replaying it must fail."""
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                token = _extract_token(_SENT[-1])

                r1 = await client.post("/api/auth/verify", json={"token": token})
                assert r1.status_code == 200, r1.text
                r2 = await client.post("/api/auth/verify", json={"token": token})
                assert r2.status_code == 400, r2.text
                assert "already" in r2.json().get("detail", "").lower()
        finally:
            await teardown()
    _run(_go())


def test_resend_returns_generic_200_for_unknown_email():
    """Resend must not leak whether an account exists."""
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                before = len(_SENT)
                r = await client.post(
                    "/api/auth/resend-verification",
                    json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"},
                )
                assert r.status_code == 200, r.text
                body = r.json()
                assert body.get("ok") is True
                assert "message" in body
                assert len(_SENT) == before, "No email should be sent for unknown address"
        finally:
            await teardown()
    _run(_go())


def test_resend_for_real_user_sends_email():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                await client.post("/api/auth/signup", json={"email": email, "password": "secret123"})
                before = len(_SENT)
                r = await client.post("/api/auth/resend-verification", json={"email": email})
                assert r.status_code == 200, r.text
                assert len(_SENT) == before + 1
                assert _SENT[-1].to == email
        finally:
            await teardown()
    _run(_go())


# ---------- Ad-hoc runner ----------------------------------------------------
if __name__ == "__main__":
    import inspect
    funcs = [
        (name, obj)
        for name, obj in globals().items()
        if name.startswith("test_") and callable(obj) and obj.__module__ == __name__
    ]
    funcs.sort(key=lambda kv: kv[0])
    passed = 0
    failed = 0
    for name, fn in funcs:
        try:
            fn()
        except Exception as e:
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
            failed += 1
            continue
        print(f"OK    {name}")
        passed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
