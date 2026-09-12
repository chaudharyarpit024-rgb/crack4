import os
import sys
import uuid
import asyncio
from datetime import datetime, date, timedelta, timezone
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_streak_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-streak-" + uuid.uuid4().hex)

from server import app, init_db, close_db
from security.jwt import make_token
from database.mongodb import db
from utils.streak import (
    calculate_longest_streak_from_dates,
    _resolve_reference_date,
    _parse_timestamp_to_date_str,
    compute_user_streak,
)


def run_async(coro):
    return asyncio.run(coro)


async def create_user_and_token():
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": f"streak_user_{uuid.uuid4().hex[:6]}@example.com",
        "name": "Streak Tester",
        "email_verified": True,
        "daily_target": 2000,
        "longest_streak": 0,
    }
    await db.users.insert_one(doc)
    token = make_token(user_id, extra_claims={"email": doc["email"]})
    return {"id": user_id, "token": token, "user": doc}



# --- Unit Tests: Core Streak Functions ---

def test_longest_streak_calculation():
    # Empty
    assert calculate_longest_streak_from_dates(set()) == 0

    # Single day
    assert calculate_longest_streak_from_dates({"2026-09-01"}) == 1

    # 3 consecutive days
    assert calculate_longest_streak_from_dates({"2026-09-01", "2026-09-02", "2026-09-03"}) == 3

    # Broken streaks: [2 days] ... [4 days] ... [1 day] -> Max is 4
    dates = {
        "2026-08-01", "2026-08-02",
        "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13",
        "2026-08-20",
    }
    assert calculate_longest_streak_from_dates(dates) == 4


def test_reference_date_resolution():
    # Explicit valid client date
    res = _resolve_reference_date(client_date="2026-09-15")
    assert res == date(2026, 9, 15)

    # Invalid client date falls back to UTC
    res_invalid = _resolve_reference_date(client_date="not-a-date")
    assert abs((res_invalid - datetime.now(timezone.utc).date()).days) <= 1

    # Timezone resolution
    res_tz = _resolve_reference_date(client_tz="Asia/Kolkata")
    assert isinstance(res_tz, date)


def test_timestamp_parsing():
    ts = "2026-09-12T14:30:00+00:00"
    assert _parse_timestamp_to_date_str(ts) == "2026-09-12"
    assert _parse_timestamp_to_date_str("invalid") is None
    assert _parse_timestamp_to_date_str("") is None


# --- Integration Tests: Full Flow & Edge Cases ---

def test_empty_streak_for_new_user():
    async def _test():
        await init_db()
        try:
            test_user = await create_user_and_token()
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/food/streak",
                    headers={"Authorization": f"Bearer {test_user['token']}"},
                )
                assert res.status_code == 200
                data = res.json()
                assert data["current_streak"] == 0
                assert data["longest_streak"] == 0
                assert data["logged_today"] is False
                assert data["streak_active"] is False
                assert len(data["weekly_activity"]) == 7
                assert all(day["logged"] is False for day in data["weekly_activity"])
        finally:
            await close_db()

    run_async(_test())


def test_streak_increments_on_log_and_is_idempotent_same_day():
    async def _test():
        await init_db()
        try:
            test_user = await create_user_and_token()
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                headers = {"Authorization": f"Bearer {test_user['token']}"}

                # 1. Log first meal today
                log_res = await ac.post(
                    "/api/food/log",
                    json={"food_name": "Oatmeal", "calories": 300, "source": "manual"},
                    headers=headers,
                )
                assert log_res.status_code == 200
                log_data = log_res.json()
                assert "streak" in log_data
                assert log_data["streak"]["current_streak"] == 1
                assert log_data["streak"]["logged_today"] is True

                # 2. Check /food/streak endpoint
                res = await ac.get("/api/food/streak", headers=headers)
                assert res.status_code == 200
                data = res.json()
                assert data["current_streak"] == 1
                assert data["longest_streak"] == 1
                assert data["logged_today"] is True
                assert data["streak_active"] is True
                today_activity = [d for d in data["weekly_activity"] if d["is_today"]]
                assert len(today_activity) == 1
                assert today_activity[0]["logged"] is True

                # 3. Log a second meal on the same day -> streak stays 1 (idempotent for the day)
                log_res_2 = await ac.post(
                    "/api/food/log",
                    json={"food_name": "Chicken Breast", "calories": 400, "source": "manual"},
                    headers=headers,
                )
                assert log_res_2.status_code == 200
                res_2 = await ac.get("/api/food/streak", headers=headers)
                data_2 = res_2.json()
                assert data_2["current_streak"] == 1
                assert data_2["longest_streak"] == 1
        finally:
            await close_db()

    run_async(_test())


def test_streak_alive_when_logged_yesterday_not_today():
    async def _test():
        await init_db()
        try:
            test_user = await create_user_and_token()
            yesterday_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            await db.food_logs.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": test_user["id"],
                "food_name": "Salad",
                "calories": 250,
                "timestamp": yesterday_ts,
            })

            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                headers = {"Authorization": f"Bearer {test_user['token']}"}
                res = await ac.get("/api/food/streak", headers=headers)
                assert res.status_code == 200
                data = res.json()
                assert data["current_streak"] == 1
                assert data["logged_today"] is False
                assert data["streak_active"] is True
                assert "Keep your 1-day streak alive" in data["message"]

                # Log today -> streak extends to 2!
                await ac.post(
                    "/api/food/log",
                    json={"food_name": "Eggs", "calories": 200, "source": "manual"},
                    headers=headers,
                )
                res_after = await ac.get("/api/food/streak", headers=headers)
                data_after = res_after.json()
                assert data_after["current_streak"] == 2
                assert data_after["longest_streak"] == 2
                assert data_after["logged_today"] is True
        finally:
            await close_db()

    run_async(_test())


def test_streak_resets_after_gap_day():
    async def _test():
        await init_db()
        try:
            test_user = await create_user_and_token()
            three_days_ago_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
            four_days_ago_ts = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()

            await db.food_logs.insert_many([
                {"id": str(uuid.uuid4()), "user_id": test_user["id"], "food_name": "Meal 1", "calories": 300, "timestamp": four_days_ago_ts},
                {"id": str(uuid.uuid4()), "user_id": test_user["id"], "food_name": "Meal 2", "calories": 300, "timestamp": three_days_ago_ts},
            ])

            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                headers = {"Authorization": f"Bearer {test_user['token']}"}
                res = await ac.get("/api/food/streak", headers=headers)
                assert res.status_code == 200
                data = res.json()
                assert data["current_streak"] == 0
                assert data["streak_active"] is False
                assert data["longest_streak"] == 2

                # Log today -> restarts at 1, but longest streak preserved as 2
                await ac.post(
                    "/api/food/log",
                    json={"food_name": "Fresh Start Meal", "calories": 500, "source": "manual"},
                    headers=headers,
                )
                res_after = await ac.get("/api/food/streak", headers=headers)
                data_after = res_after.json()
                assert data_after["current_streak"] == 1
                assert data_after["longest_streak"] == 2
        finally:
            await close_db()

    run_async(_test())


def test_self_healing_on_food_log_deletion():
    async def _test():
        await init_db()
        try:
            test_user = await create_user_and_token()
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                headers = {"Authorization": f"Bearer {test_user['token']}"}

                log_res = await ac.post(
                    "/api/food/log",
                    json={"food_name": "Snack to delete", "calories": 150, "source": "manual"},
                    headers=headers,
                )
                log_id = log_res.json()["id"]

                res1 = await ac.get("/api/food/streak", headers=headers)
                assert res1.json()["current_streak"] == 1

                # Delete the meal
                del_res = await ac.delete(f"/api/food/{log_id}", headers=headers)
                assert del_res.status_code == 200

                # Streak recalculation self-heals back to 0
                res2 = await ac.get("/api/food/streak", headers=headers)
                assert res2.json()["current_streak"] == 0
                assert res2.json()["logged_today"] is False
        finally:
            await close_db()

    run_async(_test())
