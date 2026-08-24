"""Tests for the forgot password and password reset flow.

Strategy
--------
1. POST /api/auth/forgot-password sends a 15-minute password reset JWT via email.
2. POST /api/auth/reset-password consumes the token, checks JTI replay protection,
   and updates the user's password hash.
3. User can subsequently log in with their new password.
"""
import os
import re
import sys
import time
import uuid
from typing import List

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_forgot_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-" + uuid.uuid4().hex)


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


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def _new_email() -> str:
    return f"qa+forgot_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"


def _extract_token(email: _SentEmail) -> str:
    match = re.search(r"token=([A-Za-z0-9._\-]+)", email.text) or re.search(
        r"token=([A-Za-z0-9._\-]+)", email.html
    )
    assert match, f"No token in email: {email.text[:200]}"
    return match.group(1)


async def _setup_app():
    from server import app, init_db, close_db
    import utils.email as email_mod
    import controllers.auth_controller as auth_ctrl

    original_email = email_mod.send_email
    original_ctrl = auth_ctrl.send_email
    email_mod.send_email = _fake_send_email
    auth_ctrl.send_email = _fake_send_email

    await init_db()
    _SENT.clear()

    from httpx import ASGITransport
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


def test_forgot_password_unknown_email_returns_200():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                r = await client.post("/api/auth/forgot-password", json={"email": "nonexistent@example.com"})
                assert r.status_code == 200
                assert r.json().get("ok") is True
                assert len(_SENT) == 0, "No email sent for non-existent user"
        finally:
            await teardown()
    _run(_go())


def test_forgot_password_and_reset_flow():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                # 1. Sign up & verify
                r = await client.post("/api/auth/signup", json={"email": email, "password": "oldPassword123"})
                assert r.status_code == 200
                verify_tok = _extract_token(_SENT[-1])
                await client.post("/api/auth/verify", json={"token": verify_tok})

                # 2. Forgot password request
                _SENT.clear()
                r = await client.post("/api/auth/forgot-password", json={"email": email})
                assert r.status_code == 200
                assert len(_SENT) == 1
                assert _SENT[0].to == email
                reset_tok = _extract_token(_SENT[0])

                # 3. Reset password
                r = await client.post("/api/auth/reset-password", json={"token": reset_tok, "new_password": "newPassword123"})
                assert r.status_code == 200
                assert r.json().get("ok") is True

                # 4. Old password fails
                r = await client.post("/api/auth/login", json={"email": email, "password": "oldPassword123"})
                assert r.status_code == 401

                # 5. New password succeeds
                r = await client.post("/api/auth/login", json={"email": email, "password": "newPassword123"})
                assert r.status_code == 200
                assert "token" in r.json()
        finally:
            await teardown()
    _run(_go())


def test_reset_password_jti_replay_protection():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                await client.post("/api/auth/signup", json={"email": email, "password": "oldPassword123"})
                verify_tok = _extract_token(_SENT[-1])
                await client.post("/api/auth/verify", json={"token": verify_tok})

                _SENT.clear()
                await client.post("/api/auth/forgot-password", json={"email": email})
                reset_tok = _extract_token(_SENT[0])

                # Use token first time
                r1 = await client.post("/api/auth/reset-password", json={"token": reset_tok, "new_password": "newPassword1"})
                assert r1.status_code == 200

                # Reusing same token must be rejected (400)
                r2 = await client.post("/api/auth/reset-password", json={"token": reset_tok, "new_password": "newPassword2"})
                assert r2.status_code == 400
                assert "already been used" in r2.text
        finally:
            await teardown()
    _run(_go())


def test_reset_password_web_page():
    async def _go():
        app, transport, teardown = await _setup_app()
        try:
            from httpx import AsyncClient
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                email = _new_email()
                await client.post("/api/auth/signup", json={"email": email, "password": "oldPassword123"})
                await client.post("/api/auth/forgot-password", json={"email": email})
                reset_tok = _extract_token(_SENT[-1])

                r = await client.get(f"/api/auth/reset-password-web?token={reset_tok}")
                assert r.status_code == 200
                assert "text/html" in r.headers["content-type"]
                assert "Reset Password" in r.text
        finally:
            await teardown()
    _run(_go())
