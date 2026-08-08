"""Tests for subscription endpoints (trial, real Razorpay checkout, paywall).

Iteration 3: Razorpay keys are LIVE — checkout should return real subscription_id.
Trial should still be active after checkout (trial precedence over RZP 'created' status).
"""
import base64
import io
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from PIL import Image, ImageDraw
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path("/app/backend/.env"))

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def fresh_user(s):
    email = f"qa+sub_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{API}/auth/signup", json={"email": email, "password": "secret123", "name": "Sub QA"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "token": d["token"], "id": d["user"]["id"]}


def auth_h(t):
    return {"Authorization": f"Bearer {t}"}


def make_food_b64():
    img = Image.new("RGB", (128, 128), (240, 200, 150))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, 118, 118], fill=(255, 255, 220))
    d.ellipse([44, 44, 84, 84], fill=(255, 180, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


# ---- 1. Auto-provisioning trial on signup (rzp_configured=True now) ----
class TestTrialProvisioning:
    def test_signup_creates_10day_trial(self, s, fresh_user):
        r = s.get(f"{API}/subscription/me", headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "trialing"
        assert d["trial_active"] is True
        assert d["active"] is True
        assert d["paid_active"] is False
        assert d["days_left"] in (9, 10), f"days_left={d['days_left']}"
        assert d["rzp_configured"] is True, "Real Razorpay keys expected"
        assert d["amount_paise"] == 3900
        assert d["currency"] == "INR"


# ---- 2. Real Razorpay checkout ----
class TestCheckoutLive:
    def test_checkout_requires_auth(self, s):
        r = s.post(f"{API}/subscription/checkout", timeout=15)
        assert r.status_code == 401

    def test_checkout_returns_real_subscription_id(self, s, fresh_user):
        r = s.post(f"{API}/subscription/checkout", headers=auth_h(fresh_user["token"]), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "subscription_id" in d and d["subscription_id"].startswith("sub_"), d
        assert "key_id" in d and d["key_id"].startswith("rzp_test_"), d
        assert d["amount_paise"] == 3900
        # stash for idempotency check
        pytest.first_sub_id = d["subscription_id"]

    def test_checkout_is_idempotent(self, s, fresh_user):
        r = s.post(f"{API}/subscription/checkout", headers=auth_h(fresh_user["token"]), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["subscription_id"] == pytest.first_sub_id, \
            f"Expected same sub id, got {d['subscription_id']} vs {pytest.first_sub_id}"

    def test_trial_still_active_after_checkout(self, s, fresh_user):
        """Trial precedence: RZP status may be 'created' but trial_ends_at is future → trial_active=True."""
        r = s.get(f"{API}/subscription/me", headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # Razorpay just created → status likely 'created', but trial should still be active
        assert d["trial_active"] is True, f"trial should be active. sub={d}"
        assert d["active"] is True
        assert d["paid_active"] is False
        assert d["days_left"] > 0
        assert d["razorpay_subscription_id"] == pytest.first_sub_id


# ---- 3. /food/today returns macro totals (iteration 3) ----
class TestFoodTodayMacros:
    def test_macro_totals_returned(self, s, fresh_user):
        # Log two foods with known macros
        r = s.post(f"{API}/food/log",
                   json={"food_name": "TEST_MacroA", "calories": 200,
                         "protein_g": 20, "fat_g": 5, "carbs_g": 30, "source": "manual"},
                   headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        item_a = r.json()
        assert item_a["protein_g"] == 20 and item_a["fat_g"] == 5 and item_a["carbs_g"] == 30

        r = s.post(f"{API}/food/log",
                   json={"food_name": "TEST_MacroB", "calories": 150,
                         "protein_g": 10, "fat_g": 3, "carbs_g": 20, "source": "manual"},
                   headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text

        r = s.get(f"{API}/food/today", headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("total_calories", "total_protein_g", "total_fat_g", "total_carbs_g", "items"):
            assert k in d, f"missing {k}"
        assert d["total_calories"] >= 350
        assert d["total_protein_g"] >= 30
        assert d["total_fat_g"] >= 8
        assert d["total_carbs_g"] >= 50
        # each item should retain protein_g
        for item in d["items"]:
            if item["food_name"].startswith("TEST_Macro"):
                assert "protein_g" in item


# ---- 4. Analyze paywall (trial expired scenario) ----
class TestAnalyzeExpiredPaywall:
    def test_expired_trial_returns_402(self, s, fresh_user):
        m = MongoClient(MONGO_URL)
        try:
            past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            # Also mark paid_active=false by using 'expired' status
            res = m[DB_NAME].subscriptions.update_one(
                {"user_id": fresh_user["id"]},
                {"$set": {"status": "expired", "trial_ends_at": past}},
            )
            assert res.matched_count == 1

            r = s.get(f"{API}/subscription/me", headers=auth_h(fresh_user["token"]), timeout=15)
            assert r.status_code == 200
            pub = r.json()
            assert pub["active"] is False
            assert pub["trial_active"] is False
            assert pub["days_left"] == 0

            b64 = make_food_b64()
            r = s.post(f"{API}/food/analyze", json={"image_base64": b64},
                       headers=auth_h(fresh_user["token"]), timeout=30)
            assert r.status_code == 402, r.text
            assert "subscription" in r.json().get("detail", "").lower()

            # Manual entry still works (soft paywall)
            r = s.post(f"{API}/food/log",
                       json={"food_name": "TEST_ManualExpired", "calories": 100, "source": "manual"},
                       headers=auth_h(fresh_user["token"]), timeout=15)
            assert r.status_code == 200, r.text
        finally:
            m.close()


# ---- 5. Webhook / callback signature validation ----
class TestWebhookSecurity:
    def test_webhook_invalid_signature_rejected(self, s):
        r = s.post(f"{BASE_URL}/api/subscription/webhook",
                   data=b'{"event":"subscription.activated"}',
                   headers={"x-razorpay-signature": "deadbeef", "Content-Type": "application/json"},
                   timeout=15)
        assert r.status_code == 400

    def test_callback_invalid_signature_rejected(self, s):
        r = s.post(f"{BASE_URL}/api/subscription/callback",
                   data={"razorpay_payment_id": "pay_x",
                         "razorpay_subscription_id": "sub_x",
                         "razorpay_signature": "bad"},
                   timeout=15,
                   allow_redirects=False)
        assert r.status_code == 400
