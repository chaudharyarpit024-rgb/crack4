from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import re
import hmac
import hashlib
import logging
import uuid
import bcrypt
import jwt
import httpx
from pathlib import Path
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
JWT_TTL_DAYS = 30

# Razorpay
RZP_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RZP_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RZP_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
RZP_PLAN_ID = os.environ.get("RAZORPAY_PLAN_ID", "")
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "")
MOBILE_RETURN_URL = os.environ.get("MOBILE_RETURN_URL", "crack://razorpay-complete")
SUB_AMOUNT_PAISE = int(os.environ.get("SUBSCRIPTION_AMOUNT_PAISE", 3900))
TRIAL_DAYS = int(os.environ.get("SUBSCRIPTION_TRIAL_DAYS", 10))
RZP_LIVE = bool(RZP_KEY_ID) and not RZP_KEY_ID.endswith("placeholder")


client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI()
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crack")


# ---------- Models ----------
class SignupBody(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ProfileBody(BaseModel):
    name: Optional[str] = None
    goal: Optional[Literal["gain", "lose", "maintain"]] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[Literal["male", "female", "other"]] = None


class FoodLogBody(BaseModel):
    food_name: str
    calories: float
    fat_g: Optional[float] = 0
    carbs_g: Optional[float] = 0
    protein_g: Optional[float] = 0
    source: Optional[Literal["ai", "manual"]] = "manual"
    image_b64: Optional[str] = None


class AnalyzeBody(BaseModel):
    image_base64: str


# ---------- Helpers ----------
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_TTL_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


def calorie_target(goal: str, weight_kg: float, height_cm: float,
                   age: Optional[int], gender: Optional[str]) -> int:
    age = age or 25
    if gender == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    tdee = bmr * 1.4
    if goal == "lose":
        tdee -= 400
    elif goal == "gain":
        tdee += 400
    return max(1200, int(round(tdee)))


# ---------- Subscription helpers ----------
async def ensure_trial(user_id: str) -> dict:
    """Create a 10-day free trial subscription record on first read."""
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    if sub:
        return sub
    now = datetime.now(timezone.utc)
    sub = {
        "user_id": user_id,
        "razorpay_subscription_id": None,
        "plan_id": RZP_PLAN_ID or None,
        "status": "trialing",
        "trial_ends_at": (now + timedelta(days=TRIAL_DAYS)).isoformat(),
        "current_end": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.subscriptions.insert_one(dict(sub))
    return sub


def sub_public(sub: dict) -> dict:
    """Compute derived fields for client."""
    status = sub.get("status", "none")
    trial_ends_at = sub.get("trial_ends_at")
    now = datetime.now(timezone.utc)
    days_left = 0
    trial_active = False
    paid_active = status in {"authenticated", "active"}
    if trial_ends_at:
        try:
            end = datetime.fromisoformat(trial_ends_at)
            if end > now:
                # Trial is active until end_at, regardless of RZP status
                # (as long as user hasn't been marked paid_active)
                trial_active = not paid_active
                delta = end - now
                days_left = max(0, delta.days + (1 if delta.seconds > 0 else 0))
        except Exception:
            pass
    active = paid_active or trial_active
    return {
        "status": status,
        "active": active,
        "trial_active": trial_active,
        "paid_active": paid_active,
        "trial_ends_at": trial_ends_at,
        "days_left": days_left,
        "razorpay_subscription_id": sub.get("razorpay_subscription_id"),
        "amount_paise": SUB_AMOUNT_PAISE,
        "currency": "INR",
        "rzp_configured": RZP_LIVE,
    }


async def require_active_subscription(user=Depends(current_user)):
    sub = await ensure_trial(user["id"])
    pub = sub_public(sub)
    if not pub["active"]:
        raise HTTPException(402, "Subscription required. Your free trial has ended.")
    return user


async def razorpay_req(method: str, path: str, **kwargs):
    if not RZP_LIVE:
        raise HTTPException(503, "Razorpay is not configured. Add RAZORPAY_KEY_ID/SECRET/PLAN_ID in backend/.env.")
    async with httpx.AsyncClient(
        base_url="https://api.razorpay.com",
        auth=(RZP_KEY_ID, RZP_KEY_SECRET),
        timeout=20,
    ) as c:
        r = await c.request(method, path, **kwargs)
        if r.is_error:
            logger.error(f"Razorpay {method} {path} failed: {r.status_code} {r.text}")
            raise HTTPException(502, f"Razorpay error: {r.status_code}")
        return r.json()


# ---------- Auth ----------
@api.post("/auth/signup")
async def signup(body: SignupBody):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": user_id,
        "email": email,
        "password": hash_pw(body.password),
        "name": body.name or email.split("@")[0],
        "goal": None,
        "weight_kg": None,
        "height_cm": None,
        "age": None,
        "gender": None,
        "daily_target": None,
        "created_at": now,
    }
    await db.users.insert_one(doc)
    # Auto-provision 10-day free trial
    await ensure_trial(user_id)
    return {
        "token": make_token(user_id),
        "user": {k: v for k, v in doc.items() if k not in ("password", "_id")},
    }


@api.post("/auth/login")
async def login(body: LoginBody):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_pw(body.password, user.get("password", "")):
        raise HTTPException(401, "Invalid email or password")
    # Ensure trial exists (for legacy accounts)
    await ensure_trial(user["id"])
    return {
        "token": make_token(user["id"]),
        "user": {k: v for k, v in user.items() if k not in ("password", "_id")},
    }


@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return user


# ---------- Profile ----------
@api.put("/profile")
async def update_profile(body: ProfileBody, user=Depends(current_user)):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    merged = {**user, **updates}
    if merged.get("goal") and merged.get("weight_kg") and merged.get("height_cm"):
        merged["daily_target"] = calorie_target(
            merged["goal"], merged["weight_kg"], merged["height_cm"],
            merged.get("age"), merged.get("gender"),
        )
        updates["daily_target"] = merged["daily_target"]
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password": 0})
    return updated


# ---------- Subscription ----------
@api.get("/subscription/me")
async def subscription_me(user=Depends(current_user)):
    sub = await ensure_trial(user["id"])
    return sub_public(sub)


@api.post("/subscription/checkout")
async def create_checkout(user=Depends(current_user)):
    """Create a Razorpay subscription with 10-day free trial (via start_at)."""
    if not RZP_LIVE:
        raise HTTPException(
            503,
            "Payment is not configured yet. Please ask the admin to add Razorpay keys in backend/.env."
        )
    if not RZP_PLAN_ID:
        raise HTTPException(503, "RAZORPAY_PLAN_ID is not set.")

    existing = await db.subscriptions.find_one({"user_id": user["id"]})
    if existing and existing.get("razorpay_subscription_id") and existing.get("status") in {"authenticated", "active", "pending", "created"}:
        return {
            "subscription_id": existing["razorpay_subscription_id"],
            "key_id": RZP_KEY_ID,
            "amount_paise": SUB_AMOUNT_PAISE,
        }

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=TRIAL_DAYS)
    sub = await razorpay_req("POST", "/v1/subscriptions", json={
        "plan_id": RZP_PLAN_ID,
        "quantity": 1,
        "total_count": 12,  # 12 monthly cycles; extend via renewals
        "start_at": int(trial_end.timestamp()),
        "customer_notify": 1,
        "notes": {"user_id": user["id"]},
    })

    await db.subscriptions.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "razorpay_subscription_id": sub["id"],
            "plan_id": sub["plan_id"],
            "status": sub.get("status", "created"),
            "trial_ends_at": trial_end.isoformat(),
            "updated_at": now.isoformat(),
        }},
        upsert=True,
    )
    return {
        "subscription_id": sub["id"],
        "key_id": RZP_KEY_ID,
        "amount_paise": SUB_AMOUNT_PAISE,
    }


@app.get("/api/subscription/checkout-page", response_class=HTMLResponse)
async def checkout_page(subscription_id: str):
    """Hosted checkout page loaded inside WebView on the mobile app."""
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CRACK — Subscribe</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #fff; margin:0; padding: 32px; color:#111827; text-align:center; }}
  .brand {{ font-weight: 900; font-size: 42px; color: #E05D36; letter-spacing: 3px; }}
  .tag {{ color: #6B7280; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; margin-top: 6px; }}
  .price {{ font-size: 42px; font-weight: 900; margin: 28px 0 4px; }}
  .sub {{ color: #6B7280; font-size: 14px; }}
  button {{ background:#E05D36; color:#fff; border:none; padding: 14px 28px; border-radius: 12px; font-size:16px; font-weight:700; margin-top:24px; }}
</style>
</head>
<body>
<div class="brand">CRACK</div>
<div class="tag">Premium</div>
<div class="price">₹39<span style="font-size:16px;color:#6B7280;">/month</span></div>
<div class="sub">10 days free · billed after trial · UPI Autopay</div>
<button id="pay">Continue to payment</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
  document.getElementById('pay').addEventListener('click', function() {{
    var options = {{
      key: {json.dumps(RZP_KEY_ID)},
      subscription_id: {json.dumps(subscription_id)},
      name: 'CRACK',
      description: 'Premium — 10-day free trial, then Rs.39/month',
      callback_url: {json.dumps((PUBLIC_API_URL or '') + '/api/subscription/callback')},
      theme: {{ color: '#E05D36' }}
    }};
    var rzp = new Razorpay(options);
    rzp.open();
  }});
</script>
</body>
</html>"""
    return HTMLResponse(html)


@app.post("/api/subscription/callback")
async def subscription_callback(
    razorpay_payment_id: str = Form(...),
    razorpay_subscription_id: str = Form(...),
    razorpay_signature: str = Form(...),
):
    message = f"{razorpay_payment_id}|{razorpay_subscription_id}".encode()
    expected = hmac.new(RZP_KEY_SECRET.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, razorpay_signature):
        raise HTTPException(400, "Invalid payment signature")

    await db.subscriptions.update_one(
        {"razorpay_subscription_id": razorpay_subscription_id},
        {"$set": {
            "auth_payment_id": razorpay_payment_id,
            "status": "authenticated",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return RedirectResponse(MOBILE_RETURN_URL, status_code=303)


@app.post("/api/subscription/webhook")
async def subscription_webhook(request: Request):
    raw = await request.body()
    received = request.headers.get("x-razorpay-signature", "")
    expected = hmac.new(RZP_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(400, "Invalid webhook signature")

    payload = json.loads(raw)
    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw).hexdigest()
    try:
        await db.rzp_events.insert_one({
            "event_id": event_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        return {"ok": True}  # duplicate

    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    rid = entity.get("id")
    status_map = {
        "subscription.authenticated": "authenticated",
        "subscription.activated": "active",
        "subscription.charged": "active",
        "subscription.pending": "pending",
        "subscription.halted": "halted",
        "subscription.cancelled": "cancelled",
        "subscription.completed": "completed",
    }
    if rid and event in status_map:
        await db.subscriptions.update_one(
            {"razorpay_subscription_id": rid},
            {"$set": {
                "status": status_map[event],
                "current_start": entity.get("current_start"),
                "current_end": entity.get("current_end"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    return {"ok": True}


# ---------- Food AI Analysis ----------
def _parse_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


@api.post("/food/analyze")
async def analyze_food(body: AnalyzeBody, user=Depends(require_active_subscription)):
    img_b64 = body.image_base64
    if img_b64.startswith("data:"):
        img_b64 = img_b64.split(",", 1)[1]

    system = (
        "You are a nutrition estimator. Given a food photo, respond with STRICT JSON "
        "matching this schema and no extra text: "
        "{\"food_name\": string, \"calories\": number, \"fat_g\": number, "
        "\"carbs_g\": number, \"protein_g\": number, \"verdict\": \"good\"|\"bad\"|\"ok\", "
        "\"reason\": string}. "
        "Estimate for a typical single serving. If not food, set food_name to 'Not food' "
        "and calories 0 with verdict 'bad'."
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"food-{uuid.uuid4()}",
        system_message=system,
    ).with_model("gemini", "gemini-3-flash-preview")

    msg = UserMessage(
        text="Analyze this food photo. Return the JSON object only.",
        file_contents=[ImageContent(image_base64=img_b64)],
    )
    try:
        raw = await chat.send_message(msg)
    except Exception as e:
        logger.exception("Gemini analyze failed")
        raise HTTPException(502, f"AI analysis failed: {e}")

    data = _parse_json(raw) or {}
    return {
        "food_name": data.get("food_name") or "Unknown food",
        "calories": float(data.get("calories") or 0),
        "fat_g": float(data.get("fat_g") or 0),
        "carbs_g": float(data.get("carbs_g") or 0),
        "protein_g": float(data.get("protein_g") or 0),
        "verdict": data.get("verdict") or "ok",
        "reason": data.get("reason") or "",
    }


# ---------- Food Log ----------
@api.post("/food/log")
async def log_food(body: FoodLogBody, user=Depends(current_user)):
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "food_name": body.food_name,
        "calories": float(body.calories),
        "fat_g": float(body.fat_g or 0),
        "carbs_g": float(body.carbs_g or 0),
        "protein_g": float(body.protein_g or 0),
        "source": body.source or "manual",
        "image_b64": body.image_b64,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.food_logs.insert_one(entry)
    return {k: v for k, v in entry.items() if k != "_id"}


@api.get("/food/today")
async def today_logs(user=Depends(current_user)):
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    cursor = db.food_logs.find(
        {"user_id": user["id"], "timestamp": {"$gte": start}},
        {"_id": 0},
    ).sort("timestamp", -1)
    items = await cursor.to_list(500)
    total = sum(i.get("calories", 0) for i in items)
    total_protein = sum(i.get("protein_g", 0) or 0 for i in items)
    total_fat = sum(i.get("fat_g", 0) or 0 for i in items)
    total_carbs = sum(i.get("carbs_g", 0) or 0 for i in items)
    return {
        "items": items,
        "total_calories": total,
        "total_protein_g": total_protein,
        "total_fat_g": total_fat,
        "total_carbs_g": total_carbs,
    }


@api.get("/food/history")
async def history(days: int = 30, user=Depends(current_user)):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = db.food_logs.find(
        {"user_id": user["id"], "timestamp": {"$gte": start}},
        {"_id": 0},
    ).sort("timestamp", -1)
    items = await cursor.to_list(2000)

    daily: dict = {}
    for it in items:
        d = it["timestamp"][:10]
        daily.setdefault(d, {"date": d, "total_calories": 0, "count": 0})
        daily[d]["total_calories"] += it.get("calories", 0)
        daily[d]["count"] += 1
    days_list = sorted(daily.values(), key=lambda x: x["date"], reverse=True)
    return {"items": items, "days": days_list}


@api.delete("/food/{item_id}")
async def delete_log(item_id: str, user=Depends(current_user)):
    r = await db.food_logs.delete_one({"id": item_id, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@api.get("/")
async def root():
    return {"service": "crack", "ok": True}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
