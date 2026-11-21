import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DB_NAME", f"crack_test_fam_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("SMTP_DRY_RUN", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-family-" + uuid.uuid4().hex)

from server import app, init_db, close_db
from security.jwt import make_token
from database.mongodb import db


def run_async(coro):
    return asyncio.run(coro)


async def create_user_and_token(name: str, goal: str, daily_target: int):
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": f"{name.lower()}_{uuid.uuid4().hex[:6]}@example.com",
        "name": name,
        "goal": goal,
        "email_verified": True,
        "daily_target": daily_target,
    }
    await db.users.insert_one(doc)
    token = make_token(user_id, extra_claims={"email": doc["email"]})
    return {"id": user_id, "token": token, "user": doc}


def test_family_box_full_lifecycle_and_leaderboard():
    """Verify creating a box, joining, competitive percentage points, ranking, and leaving."""
    async def _test():
        await init_db()
        try:
            # 1. Setup 3 members with different goals and targets
            rohan = await create_user_and_token(name="Rohan", goal="lose", daily_target=1500)
            pooja = await create_user_and_token(name="Pooja", goal="maintain", daily_target=2000)
            amit = await create_user_and_token(name="Amit", goal="gain", daily_target=2500)

            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                rohan_headers = {"Authorization": f"Bearer {rohan['token']}"}
                pooja_headers = {"Authorization": f"Bearer {pooja['token']}"}
                amit_headers = {"Authorization": f"Bearer {amit['token']}"}

                # 2. Rohan checks box before joining any -> should return None
                res = await ac.get("/api/family-box/my-box", headers=rohan_headers)
                assert res.status_code == 200
                assert res.json()["box"] is None
                assert res.json()["leaderboard"] == []

                # 3. Rohan creates Family Box
                create_res = await ac.post(
                    "/api/family-box/create",
                    json={"name": "Lodhi Champions"},
                    headers=rohan_headers,
                )
                assert create_res.status_code == 200
                box_data = create_res.json()["box"]
                assert box_data["name"] == "Lodhi Champions"
                assert box_data["member_count"] == 1
                invite_code = box_data["invite_code"]
                assert invite_code.startswith("FAM-")

                # Rohan cannot create a second box while already in one
                dup_res = await ac.post(
                    "/api/family-box/create",
                    json={"name": "Second Box"},
                    headers=rohan_headers,
                )
                assert dup_res.status_code == 400

                # 4. Pooja joins with valid invite code
                join_pooja = await ac.post(
                    "/api/family-box/join",
                    json={"invite_code": invite_code},
                    headers=pooja_headers,
                )
                assert join_pooja.status_code == 200
                assert join_pooja.json()["ok"] is True

                # Amit joins with lowercase/spaced code (tests auto-sanitization)
                join_amit = await ac.post(
                    "/api/family-box/join",
                    json={"invite_code": f"  {invite_code.lower()}  "},
                    headers=amit_headers,
                )
                assert join_amit.status_code == 200
                assert join_amit.json()["ok"] is True

                # Invalid code test
                bad_join = await ac.post(
                    "/api/family-box/join",
                    json={"invite_code": "FAM-INVALID"},
                    headers=rohan_headers,
                )
                assert bad_join.status_code in (400, 404)

                # 5. Log meals for today
                # Rohan eats 1200 kcal out of 1500 (80% -> 800 pts)
                await ac.post(
                    "/api/food/log",
                    json={"food_name": "Rohan Lunch", "calories": 1200, "source": "manual"},
                    headers=rohan_headers,
                )
                # Pooja eats 1900 kcal out of 2000 (95% -> 950 pts)
                await ac.post(
                    "/api/food/log",
                    json={"food_name": "Pooja Dinner", "calories": 1900, "source": "manual"},
                    headers=pooja_headers,
                )
                # Amit eats 1500 kcal out of 2500 (60% -> 600 pts)
                await ac.post(
                    "/api/food/log",
                    json={"food_name": "Amit Snack", "calories": 1500, "source": "manual"},
                    headers=amit_headers,
                )

                # 6. Fetch Leaderboard from Rohan's perspective
                lb_res = await ac.get("/api/family-box/my-box", headers=rohan_headers)
                assert lb_res.status_code == 200
                payload = lb_res.json()
                assert payload["box"]["member_count"] == 3
                leaderboard = payload["leaderboard"]
                assert len(leaderboard) == 3

                # Assert Rank 1: Pooja (950 pts)
                assert leaderboard[0]["name"] == "Pooja"
                assert leaderboard[0]["rank"] == 1
                assert leaderboard[0]["target_percentage"] == 95
                assert leaderboard[0]["score"] == 950
                assert leaderboard[0]["is_me"] is False

                # Assert Rank 2: Rohan (800 pts, is_me=True)
                assert leaderboard[1]["name"] == "Rohan"
                assert leaderboard[1]["rank"] == 2
                assert leaderboard[1]["target_percentage"] == 80
                assert leaderboard[1]["score"] == 800
                assert leaderboard[1]["is_me"] is True

                # Assert Rank 3: Amit (600 pts)
                assert leaderboard[2]["name"] == "Amit"
                assert leaderboard[2]["rank"] == 3
                assert leaderboard[2]["target_percentage"] == 60
                assert leaderboard[2]["score"] == 600
                assert leaderboard[2]["is_me"] is False

                # 7. Amit leaves the family box
                leave_res = await ac.post("/api/family-box/leave", headers=amit_headers)
                assert leave_res.status_code == 200

                # Verify box now has 2 members
                lb_after = await ac.get("/api/family-box/my-box", headers=rohan_headers)
                assert lb_after.json()["box"]["member_count"] == 2
                assert len(lb_after.json()["leaderboard"]) == 2
                names = [m["name"] for m in lb_after.json()["leaderboard"]]
                assert "Amit" not in names
                assert "Pooja" in names
                assert "Rohan" in names

        finally:
            await close_db()

    run_async(_test())
