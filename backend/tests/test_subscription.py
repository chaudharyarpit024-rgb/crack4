"""Tests for subscription endpoints (trial, checkout gated by placeholder keys, paywall)."""
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

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://nutrition-simple-7.preview.emergentagent.com").rstrip("/")
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


# ---- 1. Auto-provisioning trial on signup ----
class TestTrialProvisioning:
    def test_signup_creates_10day_trial(self, s, fresh_user):
        r = s.get(f"{API}/subscription/me", headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "trialing"
        assert d["trial_active"] is True
        assert d["active"] is True
        assert d["paid_active"] is False
        # trial_ends_at ~10 days ahead → days_left 9 or 10 depending on rounding
        assert d["days_left"] in (9, 10), f"days_left={d['days_left']}"
        assert d["rzp_configured"] is False  # placeholder keys
        assert d["amount_paise"] == 3900
        assert d["currency"] == "INR"


# ---- 2. Checkout gated on placeholder keys ----
class TestCheckoutGated:
    def test_checkout_returns_503_with_placeholder_keys(self, s, fresh_user):
        r = s.post(f"{API}/subscription/checkout", headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 503, r.text
        detail = r.json().get("detail", "").lower()
        assert "not configured" in detail or "razorpay" in detail

    def test_checkout_requires_auth(self, s):
        r = s.post(f"{API}/subscription/checkout", timeout=15)
        assert r.status_code == 401


# ---- 3. Food analyze allowed during trial ----
class TestAnalyzeDuringTrial:
    def test_analyze_works_while_trial_active(self, s, fresh_user):
        b64 = make_food_b64()
        r = s.post(f"{API}/food/analyze", json={"image_base64": b64},
                   headers=auth_h(fresh_user["token"]), timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("food_name", "calories", "fat_g", "carbs_g", "protein_g", "verdict", "reason"):
            assert k in d, f"missing field {k}"


# ---- 4. Analyze blocked when trial expired (soft paywall) ----
class TestAnalyzeExpiredPaywall:
    def test_expired_trial_returns_402(self, s, fresh_user):
        # Mutate the subscriptions doc directly to expire the trial
        m = MongoClient(MONGO_URL)
        try:
            past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            res = m[DB_NAME].subscriptions.update_one(
                {"user_id": fresh_user["id"]},
                {"$set": {"status": "expired", "trial_ends_at": past}},
            )
            assert res.matched_count == 1

            # Verify /subscription/me reflects inactive
            r = s.get(f"{API}/subscription/me", headers=auth_h(fresh_user["token"]), timeout=15)
            assert r.status_code == 200
            pub = r.json()
            assert pub["active"] is False
            assert pub["trial_active"] is False
            assert pub["days_left"] == 0

            # Analyze must now be gated with 402
            b64 = make_food_b64()
            r = s.post(f"{API}/food/analyze", json={"image_base64": b64},
                       headers=auth_h(fresh_user["token"]), timeout=30)
            assert r.status_code == 402, r.text
            assert "subscription" in r.json().get("detail", "").lower()

            # Manual entry must still work (soft paywall)
            r = s.post(f"{API}/food/log",
                       json={"food_name": "TEST_ManualExpired", "calories": 100, "source": "manual"},
                       headers=auth_h(fresh_user["token"]), timeout=15)
            assert r.status_code == 200, r.text
        finally:
            m.close()


# ---- 5. Webhook rejects invalid signature ----
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
