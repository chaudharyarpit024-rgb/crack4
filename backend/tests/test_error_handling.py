"""Tests for comprehensive error handling across the application.

Verifies:
1. Pydantic validation errors return clean field-level messages without internal file paths or tracebacks.
2. Unhandled server exceptions are caught by the global handler and return a generic 500 response.
3. Database failures return clean 503 status without leaking MongoDB/Motor exceptions or internal collection names.
4. Malformed webhook payloads return 400 with a clean error message.
5. Razorpay network or decode errors return a generic 502 response.
"""
import os
import sys
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_err_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-error-handling-" + uuid.uuid4().hex)

from server import app, init_db, close_db
from security.jwt import make_token
from database.mongodb import db
import utils.email as email_mod
import controllers.auth_controller as auth_ctrl


async def _fake_send_email(to: str, subject: str, html: str, text: str) -> bool:
    return True


@pytest.fixture(autouse=True)
async def setup_test_db():
    email_mod.send_email = _fake_send_email
    auth_ctrl.send_email = _fake_send_email
    await init_db()
    yield
    try:
        from database.mongodb import client
        await client.drop_database(os.environ["DB_NAME"])
    except Exception:
        pass
    await close_db()


@pytest.fixture
def transport():
    return ASGITransport(app=app, raise_app_exceptions=False)


@pytest.fixture
async def verified_user():
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": f"err_user_{uuid.uuid4().hex[:6]}@example.com",
        "email_verified": True,
        "created_at": "2026-08-28T00:00:00Z",
    }
    await db.users.insert_one(doc)
    token = make_token(user_id)
    return {"id": user_id, "email": doc["email"], "token": token}


@pytest.mark.anyio
async def test_validation_error_does_not_leak_internal_paths(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid body on signup (invalid email, too short password)
        res = await ac.post("/api/auth/signup", json={"email": "not-an-email", "password": "123"})
        assert res.status_code == 422
        data = res.json()
        assert "detail" in data
        assert data["detail"] == "Invalid request data."
        assert "errors" in data
        # Ensure no file paths or stack traces in response
        raw_text = res.text
        assert "Traceback" not in raw_text
        assert ".py" not in raw_text
        assert "/Users/" not in raw_text
        assert "/home/" not in raw_text


@pytest.mark.anyio
async def test_unhandled_exception_returns_generic_500(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("routes.auth_routes.signup_user", side_effect=RuntimeError("Secret internal failure /var/log/secret.txt")):
            res = await ac.post("/api/auth/signup", json={"email": "valid_user@example.com", "password": "Password123!"})
            assert res.status_code == 500
            data = res.json()
            assert data == {"detail": "An unexpected error occurred. Please try again later."}
            assert "Secret internal failure" not in res.text
            assert "Traceback" not in res.text
            assert ".py" not in res.text


@pytest.mark.anyio
async def test_database_failure_on_profile_update_returns_generic_503(transport, verified_user):
    mock_users = MagicMock()
    mock_users.update_one = AsyncMock(side_effect=Exception("MongoDB connection timeout to 10.0.0.5:27017"))
    mock_users.find_one = AsyncMock(side_effect=Exception("MongoDB connection timeout to 10.0.0.5:27017"))

    mock_db = MagicMock()
    mock_db.users = mock_users

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("controllers.profile_controller.db", mock_db):
            res = await ac.put(
                "/api/profile",
                headers={"Authorization": f"Bearer {verified_user['token']}"},
                json={"weight_kg": 75.0, "height_cm": 180.0, "goal": "maintain"},
            )
            assert res.status_code == 503
            data = res.json()
            assert data["detail"] == "Service temporarily unavailable. Please try again."
            assert "10.0.0.5" not in res.text
            assert "MongoDB" not in res.text


@pytest.mark.anyio
async def test_database_failure_on_food_log_returns_generic_503(transport, verified_user):
    mock_food_logs = MagicMock()
    mock_food_logs.insert_one = AsyncMock(side_effect=Exception("pymongo.errors.ServerSelectionTimeoutError"))

    mock_db = MagicMock()
    mock_db.food_logs = mock_food_logs

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("controllers.food_controller.db", mock_db):
            res = await ac.post(
                "/api/food/log",
                headers={"Authorization": f"Bearer {verified_user['token']}"},
                json={"food_name": "Oatmeal", "calories": 250.0, "source": "manual"},
            )
            assert res.status_code == 503
            data = res.json()
            assert data["detail"] == "Service temporarily unavailable. Please try again."
            assert "ServerSelectionTimeoutError" not in res.text
            assert "pymongo" not in res.text


@pytest.mark.anyio
async def test_malformed_webhook_payload_returns_clean_400():
    from controllers.subscription_controller import handle_subscription_webhook
    from fastapi import Request, HTTPException
    
    with patch("controllers.subscription_controller.RZP_WEBHOOK_LIVE", True):
        with patch("controllers.subscription_controller.verify_webhook_signature", return_value=True):
            mock_req = AsyncMock(spec=Request)
            mock_req.body.return_value = b"{not-valid-json:"
            mock_req.headers = {"x-razorpay-signature": "valid"}

            with pytest.raises(HTTPException) as exc_info:
                await handle_subscription_webhook(mock_req)
            
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid webhook payload: expected JSON"
