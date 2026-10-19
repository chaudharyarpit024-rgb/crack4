"""Tests for GET /api/nutrition/recipes endpoint.

Validates:
1. Unauthorized / missing token -> 401 or 403.
2. Unsubscribed user without active trial -> 403 paywall.
3. Subscribed / trial user -> 200 with valid recipe list and calorie counts.
4. Query validation: invalid meal_type regex rejection -> 422.
"""
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import ASGITransport, AsyncClient

# Ensure backend directory is in python path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Use isolated test database
os.environ.setdefault("DB_NAME", f"crack_test_recipes_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-recipes-" + uuid.uuid4().hex)

from server import app, init_db, close_db
from security.jwt import make_token
from database.mongodb import db


@pytest.fixture
def anyio_backend():
    """Tells AnyIO plugin to use Python's asyncio event loop."""
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Setup and teardown database for each test run."""
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
    """ASGI in-memory transport to test FastAPI without launching a separate web server."""
    return ASGITransport(app=app)


async def create_user(is_subscribed: bool = True):
    """Helper to insert a user into MongoDB and return an auth token."""
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    doc = {
        "id": user_id,
        "email": f"chef_{uuid.uuid4().hex[:6]}@example.com",
        "name": "Recipe Tester",
        "email_verified": True,
        "daily_target": 2200,
        "food_preference": "Vegetarian",
        "goal": "fat_loss",
        "created_at": now.isoformat(),
    }
    
    if is_subscribed:
        # Give user an active 21-day trial in db.subscriptions
        await db.subscriptions.insert_one({
            "user_id": user_id,
            "status": "trialing",
            "trial_ends_at": (now + timedelta(days=21)).isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
    else:
        # Expired trial in db.subscriptions
        past = (now - timedelta(days=5)).isoformat()
        await db.subscriptions.insert_one({
            "user_id": user_id,
            "status": "expired",
            "trial_ends_at": past,
            "created_at": past,
            "updated_at": past,
        })

    await db.users.insert_one(doc)
    token = make_token(user_id, extra_claims={"email": doc["email"]})
    return {"id": user_id, "token": token, "doc": doc}


# --- Tests ---

@pytest.mark.anyio
async def test_recipes_unauthenticated(transport):
    """Calling without a token must fail."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/nutrition/recipes")
        assert res.status_code == 401


@pytest.mark.anyio
async def test_recipes_paywalled_for_unsubscribed(transport):
    """User without active trial or subscription must get 403."""
    user = await create_user(is_subscribed=False)
    headers = {"Authorization": f"Bearer {user['token']}"}
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/nutrition/recipes", headers=headers)
        assert res.status_code == 402
        assert "subscription" in res.json().get("detail", "").lower()


@pytest.mark.anyio
async def test_recipes_invalid_meal_type_rejected(transport):
    """Passing an invalid meal_type query param (e.g. 'brunch') must trigger 422."""
    user = await create_user(is_subscribed=True)
    headers = {"Authorization": f"Bearer {user['token']}"}
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/nutrition/recipes?meal_type=brunch", headers=headers)
        assert res.status_code == 422


@pytest.mark.anyio
async def test_recipes_success_with_active_subscription(transport):
    """Active user should receive valid recipe suggestions matching schema."""
    user = await create_user(is_subscribed=True)
    headers = {"Authorization": f"Bearer {user['token']}"}
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/nutrition/recipes?meal_type=lunch", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Check top-level metadata
        assert "remaining_calories" in data
        assert "daily_target" in data
        assert data["daily_target"] == 2200
        assert isinstance(data.get("recipes"), list)
        assert len(data["recipes"]) > 0

        # Check fields of the first recipe
        first_recipe = data["recipes"][0]
        assert "title" in first_recipe
        assert "calories" in first_recipe
        assert "protein_g" in first_recipe
        assert "prep_time_minutes" in first_recipe
        assert isinstance(first_recipe.get("ingredients"), list)
        assert isinstance(first_recipe.get("instructions"), list)
