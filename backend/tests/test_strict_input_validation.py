"""Strict input schema validation test suite.

Tests every endpoint against strict schemas (types, bounds, lengths, formats, regexes, extra fields),
ensuring any non-compliant input is rejected (422/400) and not silently sanitized or accepted.
"""
import os
import sys
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_strict_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-strict-" + uuid.uuid4().hex)

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
    return ASGITransport(app=app)


@pytest.fixture
async def verified_user():
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": f"strict_{uuid.uuid4().hex[:6]}@example.com",
        "email_verified": True,
        "created_at": "2026-08-28T00:00:00Z",
    }
    await db.users.insert_one(doc)
    token = make_token(user_id)
    return {"id": user_id, "token": token, "email": doc["email"]}


# ============================================================================
# 1. Auth Schemas & Extra Fields Rejection
# ============================================================================

@pytest.mark.anyio
async def test_signup_extra_fields_rejected_422(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Extra unexpected field 'admin'
        r = await client.post(
            "/api/auth/signup",
            json={"email": "hacker@example.com", "password": "validPassword123", "admin": True},
        )
        assert r.status_code == 422
        assert "extra_forbidden" in r.text or "extra" in r.text.lower()


@pytest.mark.anyio
async def test_signup_invalid_name_format_rejected_422(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Control characters / script injection in name
        r = await client.post(
            "/api/auth/signup",
            json={"email": "test@example.com", "password": "validPassword123", "name": "<script>alert(1)</script>"},
        )
        assert r.status_code == 422


@pytest.mark.anyio
async def test_signup_password_length_bounds(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Too short (< 8 chars)
        r_short = await client.post(
            "/api/auth/signup",
            json={"email": "test_short@example.com", "password": "short7!"},
        )
        assert r_short.status_code == 422

        # Too long (> 128 chars)
        r_long = await client.post(
            "/api/auth/signup",
            json={"email": "test_long@example.com", "password": "A" * 129},
        )
        assert r_long.status_code == 422


@pytest.mark.anyio
async def test_login_extra_fields_rejected_422(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "validPassword123", "role": "superuser"},
        )
        assert r.status_code == 422


# ============================================================================
# 2. Verification Schemas & Token Bounds
# ============================================================================

@pytest.mark.anyio
async def test_verify_body_extra_fields_and_bounds(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Extra field rejected (422)
        r_extra = await client.post(
            "/api/auth/verify",
            json={"token": "valid.jwt.token", "foo": "bar"},
        )
        assert r_extra.status_code == 422

        # Empty token string rejected (422)
        r_empty = await client.post(
            "/api/auth/verify",
            json={"token": ""},
        )
        assert r_empty.status_code == 422

        # Malformed / garbage token rejected with 400
        r_bad_jwt = await client.post(
            "/api/auth/verify",
            json={"token": "not-a-real-jwt"},
        )
        assert r_bad_jwt.status_code == 400


@pytest.mark.anyio
async def test_verify_link_query_param_validation(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Empty query token rejected (422)
        r = await client.get("/api/auth/verify-link?token=")
        assert r.status_code == 422


@pytest.mark.anyio
async def test_reset_password_schema_validation(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # New password too short (< 8 chars) rejected (422)
        r = await client.post(
            "/api/auth/reset-password",
            json={"token": "header.payload.signature", "new_password": "short"},
        )
        assert r.status_code == 422

        # Extra field forbidden (422)
        r_extra = await client.post(
            "/api/auth/reset-password",
            json={"token": "header.payload.signature", "new_password": "validPassword123", "extra": 123},
        )
        assert r_extra.status_code == 422



# ============================================================================
# 3. Profile Metric Bounds & Strict Schema Rejection
# ============================================================================

@pytest.mark.anyio
async def test_profile_bounds_and_literal_validation(transport, verified_user):
    headers = {"Authorization": f"Bearer {verified_user['token']}"}
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Invalid goal literal
        r_goal = await client.put("/api/profile", json={"goal": "fly_to_mars"}, headers=headers)
        assert r_goal.status_code == 422

        # Negative / unrealistic weight (< 20 kg or > 500 kg)
        r_weight_low = await client.put("/api/profile", json={"weight_kg": 5.0}, headers=headers)
        assert r_weight_low.status_code == 422
        r_weight_high = await client.put("/api/profile", json={"weight_kg": 600.0}, headers=headers)
        assert r_weight_high.status_code == 422

        # Height out of bounds (< 50 cm or > 300 cm)
        r_height = await client.put("/api/profile", json={"height_cm": 10.0}, headers=headers)
        assert r_height.status_code == 422

        # Age out of bounds (< 5 or > 130)
        r_age = await client.put("/api/profile", json={"age": 200}, headers=headers)
        assert r_age.status_code == 422

        # Invalid gender literal
        r_gender = await client.put("/api/profile", json={"gender": "alien"}, headers=headers)
        assert r_gender.status_code == 422

        # Extra field forbidden
        r_extra = await client.put("/api/profile", json={"goal": "lose", "is_admin": True}, headers=headers)
        assert r_extra.status_code == 422

        # Valid payload succeeds
        r_valid = await client.put(
            "/api/profile",
            json={"goal": "lose", "weight_kg": 75.5, "height_cm": 180.0, "age": 29, "gender": "male"},
            headers=headers,
        )
        assert r_valid.status_code == 200
        assert r_valid.json()["daily_target"] is not None


# ============================================================================
# 4. Food Log & Analyze Strict Schemas
# ============================================================================

@pytest.mark.anyio
async def test_food_log_schema_validation(transport, verified_user):
    headers = {"Authorization": f"Bearer {verified_user['token']}"}
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Missing required calories or food_name
        r_missing = await client.post("/api/food/log", json={"food_name": "Apple"}, headers=headers)
        assert r_missing.status_code == 422

        # Negative calories
        r_neg_cal = await client.post("/api/food/log", json={"food_name": "Apple", "calories": -50}, headers=headers)
        assert r_neg_cal.status_code == 422

        # Calories exceeding maximum (20,000)
        r_max_cal = await client.post("/api/food/log", json={"food_name": "Feast", "calories": 25000}, headers=headers)
        assert r_max_cal.status_code == 422

        # Macros exceeding reasonable limits (> 1000g)
        r_macro = await client.post(
            "/api/food/log",
            json={"food_name": "Protein Shake", "calories": 500, "protein_g": 1500},
            headers=headers,
        )
        assert r_macro.status_code == 422

        # Invalid source enum
        r_source = await client.post(
            "/api/food/log",
            json={"food_name": "Apple", "calories": 95, "source": "telepathy"},
            headers=headers,
        )
        assert r_source.status_code == 422

        # Extra forbidden field
        r_extra = await client.post(
            "/api/food/log",
            json={"food_name": "Apple", "calories": 95, "untracked_field": "test"},
            headers=headers,
        )
        assert r_extra.status_code == 422

        # Valid food log accepts and persists
        r_valid = await client.post(
            "/api/food/log",
            json={"food_name": "Chicken Breast", "calories": 220, "protein_g": 45, "serving_size_g": 180, "source": "manual"},
            headers=headers,
        )
        assert r_valid.status_code == 200
        assert r_valid.json()["food_name"] == "Chicken Breast"


@pytest.mark.anyio
async def test_food_query_and_path_validation(transport, verified_user):
    headers = {"Authorization": f"Bearer {verified_user['token']}"}
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # History days < 1 or > 365
        r_days_low = await client.get("/api/food/history?days=0", headers=headers)
        assert r_days_low.status_code == 422

        r_days_high = await client.get("/api/food/history?days=500", headers=headers)
        assert r_days_high.status_code == 422

        # History days non-integer
        r_days_type = await client.get("/api/food/history?days=abc", headers=headers)
        assert r_days_type.status_code == 422

        # Delete invalid item_id with illegal path characters
        r_del = await client.delete("/api/food/invalid!item*id", headers=headers)
        assert r_del.status_code == 422


# ============================================================================
# 5. Subscription Query & Form Validation
# ============================================================================

@pytest.mark.anyio
async def test_subscription_checkout_page_query_validation(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Malformed subscription id regex pattern
        r_malformed = await client.get("/api/subscription/checkout-page?subscription_id=not_sub_id")
        assert r_malformed.status_code == 422

        # Empty subscription id
        r_empty = await client.get("/api/subscription/checkout-page?subscription_id=")
        assert r_empty.status_code == 422


@pytest.mark.anyio
async def test_subscription_callback_form_validation(transport):
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Invalid payment id format
        r_bad_pay = await client.post(
            "/api/subscription/callback",
            data={
                "razorpay_payment_id": "invalid_format",
                "razorpay_subscription_id": "sub_test12345",
                "razorpay_signature": "a" * 64,
            },
        )
        assert r_bad_pay.status_code == 422

        # Invalid signature format (non-hex)
        r_bad_sig = await client.post(
            "/api/subscription/callback",
            data={
                "razorpay_payment_id": "pay_test12345",
                "razorpay_subscription_id": "sub_test12345",
                "razorpay_signature": "not_a_hex_signature!",
            },
        )
        assert r_bad_sig.status_code == 422
