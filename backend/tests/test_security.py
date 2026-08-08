"""Security audit remediation tests (SEC-001..004 + new signup min password).

SEC-001: /subscription/checkout-page rejects malformed subscription_id (XSS payloads),
         404s on nonexistent, and sends CSP header on a real record.
SEC-002: JWT_SECRET rotated — tokens signed by the old weak secret must be rejected.
         Signup with a new user must produce a working token.
         server.py boot-guard: JWT_SECRET placeholder / <32 chars raises RuntimeError.
SEC-003: /subscription/webhook rejects forged signatures with 400 (fail-closed 503 if
         secret were placeholder — verified by reading code path).
         rzp_events has unique index on event_id.
SEC-004: /food/analyze rejects too-large payloads (422 for >8MB base64, 413 for
         approx >5MB decoded). Gemini error is generic (no provider details).
         /food/log Pydantic caps: food_name>120 => 422, calories>20000 => 422,
         image_b64 >250,000 chars => 422.
New:    signup with password shorter than 8 chars returns 422.
"""
import os
import time
import uuid
import base64

import jwt
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]


def auth_h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def fresh_user(s):
    email = f"qa+sec_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{API}/auth/signup",
               json={"email": email, "password": "secret123", "name": "Sec QA"},
               timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "token": d["token"], "id": d["user"]["id"]}


# ---------------- SEC-001: XSS on checkout-page ----------------
class TestSec001CheckoutPageXSS:
    XSS_PAYLOADS = [
        "%3C%2Fscript%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E",
        "</script><script>alert(1)</script>",
        "sub_../../etc",
        "sub_' onerror='alert(1)",
        "",
        "sub_短",  # non-ascii
        "SUB_ABCDEFG",  # wrong case for prefix
        "sub_" + "A" * 33,  # too long
        "sub_ABCDE",  # too short (5 chars after prefix, min is 6)
    ]

    @pytest.mark.parametrize("bad", XSS_PAYLOADS)
    def test_malformed_ids_rejected_400(self, s, bad):
        r = s.get(f"{BASE_URL}/api/subscription/checkout-page",
                  params={"subscription_id": bad}, timeout=15,
                  allow_redirects=False)
        assert r.status_code == 400, f"payload={bad!r} status={r.status_code} body={r.text[:200]}"
        # ensure no reflected script tag anywhere
        assert "<script>alert" not in r.text
        assert "</script><script>" not in r.text

    def test_valid_shaped_but_missing_returns_404(self, s):
        # Well-formed but not in DB
        r = s.get(f"{BASE_URL}/api/subscription/checkout-page",
                  params={"subscription_id": "sub_" + "X" * 20},
                  timeout=15, allow_redirects=False)
        assert r.status_code == 404, r.text

    def test_valid_sub_returns_html_with_csp_and_no_reflected_close_script(self, s, fresh_user):
        # Create a real subscription via checkout
        r = s.post(f"{API}/subscription/checkout",
                   headers=auth_h(fresh_user["token"]), timeout=30)
        assert r.status_code == 200, r.text
        sub_id = r.json()["subscription_id"]
        assert sub_id.startswith("sub_")

        r = s.get(f"{BASE_URL}/api/subscription/checkout-page",
                  params={"subscription_id": sub_id}, timeout=15,
                  allow_redirects=False)
        assert r.status_code == 200, r.text
        # CSP must be present — either as HTTP header (preferred) or meta tag (defense-in-depth).
        csp_header = r.headers.get("Content-Security-Policy") or ""
        csp_meta_present = 'http-equiv="Content-Security-Policy"' in r.text
        assert csp_header or csp_meta_present, \
            f"No CSP found. headers={dict(r.headers)}"
        # Whichever source, it must reference razorpay
        csp_effective = csp_header if csp_header else r.text
        assert "checkout.razorpay.com" in csp_effective
        # X-Content-Type-Options
        assert r.headers.get("X-Content-Type-Options", "").lower() == "nosniff"
        # No unexpected `</` inside JS-inlined values — only one legit `</script>`
        # for the closing tag(s). The subscription_id (alphanumeric) shouldn't produce any `</`.
        body = r.text
        # subscription_id is alphanumeric so raw injection impossible; check anyway.
        assert "</script><script>alert" not in body
        # The subscription_id must be embedded as a properly JSON-quoted string
        # (js_str wraps in quotes and escapes </). Verify quoting is present.
        assert f'"{sub_id}"' in body, "subscription_id not JSON-quoted in JS block"


# ---------------- SEC-002: JWT secret rotation ----------------
class TestSec002JwtRotation:
    def test_token_signed_with_old_weak_secret_rejected(self, s):
        # Common placeholder/weak secrets from prior audit
        for weak in ["placeholder", "secret", "changeme", "dev-secret", "crack-secret"]:
            bad_token = jwt.encode(
                {"sub": "any-uuid", "exp": int(time.time()) + 3600},
                weak, algorithm="HS256"
            )
            r = s.get(f"{API}/auth/me", headers=auth_h(bad_token), timeout=15)
            assert r.status_code == 401, f"weak={weak!r} status={r.status_code}"

    def test_current_secret_is_strong(self):
        assert len(JWT_SECRET) >= 32
        assert "placeholder" not in JWT_SECRET.lower()
        assert JWT_SECRET.lower() not in ("secret", "changeme", "dev-secret")

    def test_fresh_signup_token_works(self, s, fresh_user):
        r = s.get(f"{API}/auth/me", headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == fresh_user["email"]

    def test_existing_user_login_still_works(self, s):
        r = s.post(f"{API}/auth/login",
                   json={"email": "test1@example.com", "password": "secret123"},
                   timeout=15)
        assert r.status_code == 200, r.text
        # re-issued token works
        r2 = s.get(f"{API}/auth/me", headers=auth_h(r.json()["token"]), timeout=15)
        assert r2.status_code == 200


# ---------------- SEC-003: Razorpay webhook secret ----------------
class TestSec003WebhookSecret:
    def test_webhook_secret_not_placeholder(self):
        secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
        assert secret and "placeholder" not in secret.lower()
        assert len(secret) >= 32

    def test_webhook_forged_signature_rejected_400(self, s):
        r = s.post(f"{BASE_URL}/api/subscription/webhook",
                   data=b'{"event":"subscription.activated"}',
                   headers={"x-razorpay-signature": "deadbeef",
                            "Content-Type": "application/json"},
                   timeout=15)
        assert r.status_code == 400

    def test_webhook_no_signature_rejected_400(self, s):
        r = s.post(f"{BASE_URL}/api/subscription/webhook",
                   data=b'{"event":"subscription.activated"}',
                   headers={"Content-Type": "application/json"},
                   timeout=15)
        assert r.status_code == 400

    def test_rzp_events_has_unique_event_id_index(self):
        m = MongoClient(MONGO_URL)
        try:
            indexes = m[DB_NAME].rzp_events.index_information()
            unique_on_event_id = any(
                info.get("unique") and info.get("key") == [("event_id", 1)]
                for info in indexes.values()
            )
            assert unique_on_event_id, f"indexes={indexes}"
        finally:
            m.close()


# ---------------- SEC-004: Image payload limits + generic AI errors ----------------
class TestSec004ImagePayload:
    def test_analyze_rejects_too_long_base64_422(self, s, fresh_user):
        # 8 MB + 1 char triggers Pydantic max_length=8*1024*1024
        big = "A" * (8 * 1024 * 1024 + 1)
        r = s.post(f"{API}/food/analyze", json={"image_base64": big},
                   headers=auth_h(fresh_user["token"]), timeout=60)
        assert r.status_code == 422, f"got {r.status_code} body[:200]={r.text[:200]}"

    def test_analyze_rejects_decoded_over_5mb_413(self, s, fresh_user):
        # Under Pydantic 8MB cap (7 MB chars) but decodes to ~5.25 MB > MAX_IMAGE_BYTES (5MB)
        length = 7 * 1024 * 1024
        big = "A" * length
        # sanity: approx = len*3//4 => 5.25 MB > 5 MB
        assert (length * 3) // 4 > 5 * 1024 * 1024
        r = s.post(f"{API}/food/analyze", json={"image_base64": big},
                   headers=auth_h(fresh_user["token"]), timeout=60)
        assert r.status_code == 413, f"got {r.status_code} body[:200]={r.text[:200]}"

    def test_analyze_ai_error_generic_no_provider_leak(self, s, fresh_user):
        # Send a small but likely invalid image (32 bytes of random base64 chars)
        # Gemini will likely error out; error message must not mention "gemini" or "google"
        b64 = base64.b64encode(b"\x00" * 40).decode()
        r = s.post(f"{API}/food/analyze", json={"image_base64": b64},
                   headers=auth_h(fresh_user["token"]), timeout=60)
        # Either 200 with defaults OR 502 with generic message; must never leak provider details
        assert r.status_code in (200, 502), r.text
        text = r.text.lower()
        for leak in ("gemini", "google", "traceback", "api key", "vertex"):
            assert leak not in text, f"provider leak: '{leak}' in response body"

    def test_food_log_name_over_120_rejected_422(self, s, fresh_user):
        r = s.post(f"{API}/food/log",
                   json={"food_name": "A" * 121, "calories": 100},
                   headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 422, r.text

    def test_food_log_calories_over_20000_rejected_422(self, s, fresh_user):
        r = s.post(f"{API}/food/log",
                   json={"food_name": "TEST_HighCal", "calories": 20001},
                   headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 422, r.text

    def test_food_log_calories_negative_rejected_422(self, s, fresh_user):
        r = s.post(f"{API}/food/log",
                   json={"food_name": "TEST_NegCal", "calories": -1},
                   headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 422, r.text

    def test_food_log_image_b64_too_long_rejected_422(self, s, fresh_user):
        r = s.post(f"{API}/food/log",
                   json={"food_name": "TEST_BigImg", "calories": 100,
                         "image_b64": "A" * 250_001},
                   headers=auth_h(fresh_user["token"]), timeout=30)
        assert r.status_code == 422, r.text[:200]

    def test_food_log_valid_small_payload_accepts(self, s, fresh_user):
        r = s.post(f"{API}/food/log",
                   json={"food_name": "TEST_Sec004Small", "calories": 42,
                         "protein_g": 1.5},
                   headers=auth_h(fresh_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["food_name"] == "TEST_Sec004Small"


# ---------------- New: signup password minimum length ----------------
class TestSignupPasswordPolicy:
    def test_signup_short_password_rejected_422(self, s):
        email = f"qa+shortpw_{int(time.time())}_{uuid.uuid4().hex[:4]}@example.com"
        r = s.post(f"{API}/auth/signup",
                   json={"email": email, "password": "short7!"},  # 7 chars
                   timeout=15)
        assert r.status_code == 422, r.text

    def test_signup_8char_password_ok(self, s):
        email = f"qa+eightpw_{int(time.time())}_{uuid.uuid4().hex[:4]}@example.com"
        r = s.post(f"{API}/auth/signup",
                   json={"email": email, "password": "abcdefgh"},  # exactly 8
                   timeout=15)
        assert r.status_code == 200, r.text
