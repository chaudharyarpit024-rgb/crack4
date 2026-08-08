"""Backend tests for CRACK diet tracking app.

Covers: auth (signup/login/me), profile update, food log/today/history/delete,
and AI analyze endpoint (Gemini 3 Flash via emergentintegrations).
"""
import base64
import io
import os
import time
import uuid
import pytest
import requests
from PIL import Image, ImageDraw

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://nutrition-simple-7.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

EXISTING_EMAIL = "test1@example.com"
EXISTING_PASSWORD = "secret123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def new_user(s):
    email = f"qa+{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{API}/auth/signup", json={"email": email, "password": "secret123", "name": "QA Bot"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and "user" in data
    return {"email": email, "password": "secret123", "token": data["token"], "user": data["user"]}


@pytest.fixture(scope="session")
def existing_user(s):
    r = s.post(f"{API}/auth/login", json={"email": EXISTING_EMAIL, "password": EXISTING_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    return {"token": data["token"], "user": data["user"]}


def auth_h(token):
    return {"Authorization": f"Bearer {token}"}


def make_food_jpeg_b64():
    """Create a realistic-looking food JPEG (colorful shapes with texture)."""
    img = Image.new("RGB", (256, 256), (245, 220, 180))
    d = ImageDraw.Draw(img)
    # Plate
    d.ellipse([20, 20, 236, 236], fill=(255, 250, 240), outline=(180, 180, 180), width=4)
    # Fried egg (yellow yolk on white)
    d.ellipse([60, 60, 200, 200], fill=(255, 255, 235))
    d.ellipse([110, 110, 160, 160], fill=(255, 200, 40))
    # Some greens
    for i, (x, y) in enumerate([(50, 180), (180, 55), (200, 180), (55, 55)]):
        d.ellipse([x, y, x + 25, y + 25], fill=(60 + i * 10, 150, 60))
    # Texture lines
    for i in range(0, 256, 8):
        d.line([(0, i), (256, i)], fill=(230, 210, 170), width=1)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# ---------- Health ----------
class TestHealth:
    def test_root(self, s):
        r = s.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------- Auth ----------
class TestAuth:
    def test_signup_returns_token_and_user(self, new_user):
        assert new_user["token"]
        u = new_user["user"]
        assert u["email"] == new_user["email"]
        assert "id" in u and "password" not in u

    def test_signup_duplicate_email_rejected(self, s, new_user):
        r = s.post(f"{API}/auth/signup", json={"email": new_user["email"], "password": "x"}, timeout=15)
        assert r.status_code == 400

    def test_login_valid(self, s, new_user):
        r = s.post(f"{API}/auth/login", json={"email": new_user["email"], "password": new_user["password"]}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["token"] and d["user"]["email"] == new_user["email"]

    def test_login_invalid(self, s):
        r = s.post(f"{API}/auth/login", json={"email": EXISTING_EMAIL, "password": "wrongpass"}, timeout=15)
        assert r.status_code == 401

    def test_me_with_token(self, s, new_user):
        r = s.get(f"{API}/auth/me", headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == new_user["email"]

    def test_me_without_token(self, s):
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# ---------- Profile ----------
class TestProfile:
    def test_update_profile_computes_daily_target(self, s, new_user):
        payload = {"goal": "lose", "weight_kg": 70, "height_cm": 175, "age": 28, "gender": "male"}
        r = s.put(f"{API}/profile", json=payload, headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["goal"] == "lose"
        assert d["weight_kg"] == 70
        assert d["height_cm"] == 175
        # Mifflin: 10*70 + 6.25*175 - 5*28 + 5 = 700 + 1093.75 - 140 + 5 = 1658.75
        # TDEE = 1658.75 * 1.4 = 2322.25; lose -> 1922.25 => 1922
        assert d["daily_target"] == 1922

    def test_profile_persists_on_me(self, s, new_user):
        r = s.get(f"{API}/auth/me", headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["daily_target"] == 1922


# ---------- Food log / today / history / delete ----------
class TestFoodLog:
    def test_log_manual_food(self, s, new_user):
        payload = {"food_name": "TEST_Apple", "calories": 95, "carbs_g": 25, "source": "manual"}
        r = s.post(f"{API}/food/log", json=payload, headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["food_name"] == "TEST_Apple"
        assert d["calories"] == 95
        assert d["source"] == "manual"
        assert "id" in d
        pytest.food_id = d["id"]

    def test_today_returns_item_and_total(self, s, new_user):
        r = s.get(f"{API}/food/today", headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert any(i["food_name"] == "TEST_Apple" for i in d["items"])
        assert d["total_calories"] >= 95

    def test_history_returns_days_aggregation(self, s, new_user):
        r = s.get(f"{API}/food/history?days=30", headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["items"], list) and isinstance(d["days"], list)
        assert len(d["items"]) >= 1
        assert d["days"][0]["total_calories"] >= 95

    def test_delete_only_own_food(self, s, new_user, existing_user):
        # Other user can't delete our item
        r = s.delete(f"{API}/food/{pytest.food_id}", headers=auth_h(existing_user["token"]), timeout=15)
        assert r.status_code == 404
        # Owner can delete
        r = s.delete(f"{API}/food/{pytest.food_id}", headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Second delete -> 404
        r = s.delete(f"{API}/food/{pytest.food_id}", headers=auth_h(new_user["token"]), timeout=15)
        assert r.status_code == 404


# ---------- AI analyze ----------
class TestAnalyze:
    def test_analyze_returns_expected_fields(self, s, new_user):
        b64 = make_food_jpeg_b64()
        r = s.post(f"{API}/food/analyze", json={"image_base64": b64}, headers=auth_h(new_user["token"]), timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("food_name", "calories", "fat_g", "carbs_g", "protein_g", "verdict", "reason"):
            assert k in d, f"missing {k}"
        assert isinstance(d["calories"], (int, float))
        assert d["verdict"] in ("good", "bad", "ok")

    def test_analyze_requires_auth(self, s):
        r = s.post(f"{API}/food/analyze", json={"image_base64": "abc"}, timeout=15)
        assert r.status_code == 401
