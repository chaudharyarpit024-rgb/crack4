from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import re
import logging
import uuid
import bcrypt
import jwt
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
    image_b64: Optional[str] = None  # small thumbnail for history


class AnalyzeBody(BaseModel):
    image_base64: str  # raw base64 (no data: prefix)


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
    """Mifflin–St Jeor + activity 1.4 + goal adjustment."""
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


def user_public(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password"}


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
    return {"token": make_token(user["id"]), "user": user_public({k: v for k, v in user.items() if k != "_id"})}


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


# ---------- Food AI Analysis ----------
def _parse_json(text: str) -> Optional[dict]:
    # Strip code fences if present
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


@api.post("/food/analyze")
async def analyze_food(body: AnalyzeBody, user=Depends(current_user)):
    # Strip data: prefix if provided
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
    return {"items": items, "total_calories": total}


@api.get("/food/history")
async def history(days: int = 30, user=Depends(current_user)):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = db.food_logs.find(
        {"user_id": user["id"], "timestamp": {"$gte": start}},
        {"_id": 0},
    ).sort("timestamp", -1)
    items = await cursor.to_list(2000)

    # group by date
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
