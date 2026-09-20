"""Test suite for Unlimited Access for specific emails.

Verifies:
1. Environment variable whitelisting (UNLIMITED_ACCESS_EMAILS)
2. Database whitelisting (unlimited_emails collection)
3. Direct user document flag (is_unlimited=True)
4. Permanent active subscription status from /subscription/me
5. Zero paywalls and unlimited AI scan quota bypass via /food/analyze
6. Bypassing trial expiration (expired trial still has unlimited access)
7. Non-unlimited regular users still follow normal trial and quota constraints
8. CLI management script (manage_unlimited.py) functionality
"""
import base64
import os
import sys
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_unlimited_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-unlimited-" + uuid.uuid4().hex)

from server import app, init_db, close_db
from database.mongodb import db
from security.jwt import make_token
import config.settings as settings
import utils.email as email_mod
import controllers.auth_controller as auth_ctrl
import controllers.food_controller as food_ctrl
import routes.food_routes as food_routes
from scripts.manage_unlimited import add_email, remove_email


async def _fake_send_email(to: str, subject: str, html: str, text: str) -> bool:
    return True


async def _fake_analyze_food_image(body):
    return {
        "food_name": "Test Healthy Salad",
        "calories": 250,
        "protein_g": 12,
        "fat_g": 5,
        "carbs_g": 20,
        "serving_size_g": 150,
        "confidence": 0.95,
        "health_rating": 8,
    }


def make_test_image_b64() -> str:
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00" + (b"\x01" * 64)
    return base64.b64encode(fake_jpeg).decode()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest.fixture(autouse=True)
async def setup_test_env():
    email_mod.send_email = _fake_send_email
    auth_ctrl.send_email = _fake_send_email
    food_ctrl.analyze_food_image = _fake_analyze_food_image
    food_routes.analyze_food_image = _fake_analyze_food_image
    await init_db()
    yield
    try:
        from database.mongodb import client
        await client.drop_database(os.environ["DB_NAME"])
    except Exception:
        pass
    await close_db()



async def create_user(email: str, is_unlimited_flag: bool = False) -> dict:
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": email.strip().lower(),
        "password": "hashed_pw",
        "name": "Unlimited Tester",
        "email_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if is_unlimited_flag:
        user_doc["is_unlimited"] = True
    await db.users.insert_one(user_doc)
    token = make_token(user_id)
    return {"id": user_id, "email": email, "token": token}


@pytest.mark.anyio
async def test_env_unlimited_email_subscription_status(transport):
    """Users whose email is in UNLIMITED_ACCESS_EMAILS get permanent unlimited status."""
    vip_email = f"vip_owner_{uuid.uuid4().hex[:6]}@crack.test"
    settings.UNLIMITED_ACCESS_EMAILS.add(vip_email)

    user = await create_user(vip_email)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /subscription/me
        r = await client.get("/api/subscription/me", headers={"Authorization": f"Bearer {user['token']}"})
        assert r.status_code == 200, r.text
        sub = r.json()
        assert sub["is_unlimited"] is True
        assert sub["active"] is True
        assert sub["paid_active"] is True
        assert sub["status"] == "unlimited"
        assert sub["requests_limit"] is None
        assert sub["requests_remaining"] is None

        # Check /subscription/checkout returns VIP payload instead of charging
        r_checkout = await client.post("/api/subscription/checkout", headers={"Authorization": f"Bearer {user['token']}"})
        assert r_checkout.status_code == 200
        d_checkout = r_checkout.json()
        assert d_checkout.get("is_unlimited") is True


@pytest.mark.anyio
async def test_env_unlimited_email_bypasses_expired_trial_and_quota(transport):
    """Unlimited email can scan food even when trial is expired and across many requests."""
    vip_email = f"vip_scanner_{uuid.uuid4().hex[:6]}@crack.test"
    settings.UNLIMITED_ACCESS_EMAILS.add(vip_email)
    user = await create_user(vip_email)

    # Manually expire trial in database
    past_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    await db.subscriptions.update_one(
        {"user_id": user["id"]},
        {"$set": {"status": "expired", "trial_ends_at": past_date, "trial_requests_used": 100}},
        upsert=True,
    )

    b64 = make_test_image_b64()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Should not get 402 Payment Required even though trial is expired and 6 requests exceed standard daily limit of 5
        for _ in range(6):
            r = await client.post(
                "/api/food/analyze",
                json={"image_base64": b64},
                headers={"Authorization": f"Bearer {user['token']}"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["food_name"] == "Test Healthy Salad"


@pytest.mark.anyio
async def test_db_unlimited_emails_collection(transport):
    """Adding an email to db.unlimited_emails grants unlimited access."""
    db_vip = f"db_vip_{uuid.uuid4().hex[:6]}@crack.test"
    user = await create_user(db_vip)

    # Insert into unlimited_emails collection
    await db.unlimited_emails.insert_one({"email": db_vip, "reason": "Test promotion"})

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/subscription/me", headers={"Authorization": f"Bearer {user['token']}"})
        assert r.status_code == 200
        assert r.json()["is_unlimited"] is True
        assert r.json()["active"] is True

        # Scan should succeed
        b64 = make_test_image_b64()
        r_scan = await client.post(
            "/api/food/analyze",
            json={"image_base64": b64},
            headers={"Authorization": f"Bearer {user['token']}"},
        )
        assert r_scan.status_code == 200


@pytest.mark.anyio
async def test_user_flag_is_unlimited(transport):
    """Setting is_unlimited=True directly on user document grants unlimited access."""
    flag_user_email = f"flagged_vip_{uuid.uuid4().hex[:6]}@crack.test"
    user = await create_user(flag_user_email, is_unlimited_flag=True)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/subscription/me", headers={"Authorization": f"Bearer {user['token']}"})
        assert r.status_code == 200
        assert r.json()["is_unlimited"] is True


@pytest.mark.anyio
async def test_regular_user_enforces_normal_limits(transport):
    """A regular user without unlimited access is bounded by standard trial & paywall rules."""
    regular_email = f"regular_user_{uuid.uuid4().hex[:6]}@crack.test"
    user = await create_user(regular_email)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/subscription/me", headers={"Authorization": f"Bearer {user['token']}"})
        assert r.status_code == 200
        sub = r.json()
        assert sub["is_unlimited"] is False
        assert sub["trial_active"] is True

        # Expire regular user trial
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        await db.subscriptions.update_one(
            {"user_id": user["id"]},
            {"$set": {"status": "expired", "trial_ends_at": past_date}},
        )

        # /subscription/me reflects expired
        r_exp = await client.get("/api/subscription/me", headers={"Authorization": f"Bearer {user['token']}"})
        assert r_exp.json()["active"] is False

        # /food/analyze should fail with 402
        b64 = make_test_image_b64()
        r_scan = await client.post(
            "/api/food/analyze",
            json={"image_base64": b64},
            headers={"Authorization": f"Bearer {user['token']}"},
        )
        assert r_scan.status_code == 402
        assert "subscription" in r_scan.json()["detail"].lower()


@pytest.mark.anyio
async def test_cli_manage_unlimited_script():
    """Verify add and remove functions from manage_unlimited.py."""
    cli_email = f"cli_managed_{uuid.uuid4().hex[:6]}@crack.test"

    # 1. Add email
    exit_code = await add_email(cli_email, "Beta tester grant")
    assert exit_code == 0

    # 2. Check email
    doc = await db.unlimited_emails.find_one({"email": cli_email})
    assert doc is not None
    assert doc["reason"] == "Beta tester grant"

    # 3. Check helper
    from utils.subscription import is_unlimited_email
    assert await is_unlimited_email(cli_email) is True

    # 4. Remove email
    rm_code = await remove_email(cli_email)
    assert rm_code == 0
    doc_after = await db.unlimited_emails.find_one({"email": cli_email})
    assert doc_after is None
    assert await is_unlimited_email(cli_email) is False
