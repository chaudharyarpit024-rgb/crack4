import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

from database.mongodb import db
from models.food import AnalyzeBody, FoodLogBody
from config.settings import EMERGENT_LLM_KEY, MAX_IMAGE_BYTES, logger
from utils.json_parser import parse_json


async def analyze_food_image(body: AnalyzeBody) -> dict:
    """Analyze a food photo using Gemini Vision via emergentintegrations."""
    img_b64 = body.image_base64
    if img_b64.startswith("data:"):
        img_b64 = img_b64.split(",", 1)[1]

    # Reject payloads whose decoded size exceeds the limit
    try:
        approx_bytes = (len(img_b64) * 3) // 4
    except Exception:
        approx_bytes = 0
    if approx_bytes > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large")

    system = (
        "You are a nutrition estimator. Given a food photo, respond with STRICT JSON "
        "matching this schema and no extra text: "
        '{"food_name": string, "serving_size_g": number, "calories": number, "fat_g": number, '
        '"carbs_g": number, "protein_g": number, "verdict": "good"|"bad"|"ok", '
        '"reason": string}. '
        "Estimate for a typical single serving and include estimated portion weight in grams as serving_size_g (e.g. 150). "
        "If not food, set food_name to 'Not food', serving_size_g to 0, and calories 0 with verdict 'bad'."
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"food-{uuid.uuid4()}",
        system_message=system,
    ).with_model("gemini", "gemini-3.1-flash-lite")

    msg = UserMessage(
        text="Analyze this food photo. Return the JSON object only.",
        file_contents=[ImageContent(image_base64=img_b64)],
    )
    try:
        raw = await chat.send_message(msg)
    except Exception:
        logger.exception("Gemini analyze failed")
        # Do not leak provider error details to clients
        raise HTTPException(502, "AI analysis failed. Please try again.")

    data = parse_json(raw) or {}
    serving_g = 150.0
    try:
        if data.get("serving_size_g") is not None and float(data.get("serving_size_g")) > 0:
            serving_g = float(data.get("serving_size_g"))
    except (ValueError, TypeError):
        serving_g = 150.0

    return {
        "food_name": data.get("food_name") or "Unknown food",
        "serving_size_g": serving_g,
        "calories": float(data.get("calories") or 0),
        "fat_g": float(data.get("fat_g") or 0),
        "carbs_g": float(data.get("carbs_g") or 0),
        "protein_g": float(data.get("protein_g") or 0),
        "verdict": data.get("verdict") or "ok",
        "reason": data.get("reason") or "",
    }


async def create_food_log(user: dict, body: FoodLogBody) -> dict:
    """Create a new food log entry, safely sanitizing image thumbnails."""
    # Never persist raw meal photos in the log; keep only a small thumbnail if provided.
    thumb = body.image_b64
    if thumb and len(thumb) > 200_000:
        thumb = None
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "food_name": body.food_name[:120],
        "calories": float(body.calories),
        "fat_g": float(body.fat_g or 0),
        "carbs_g": float(body.carbs_g or 0),
        "protein_g": float(body.protein_g or 0),
        "serving_size_g": float(body.serving_size_g) if body.serving_size_g is not None else None,
        "source": body.source or "manual",
        "image_b64": thumb,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.food_logs.insert_one(entry)
    return {k: v for k, v in entry.items() if k != "_id"}


async def get_today_food_logs(user: dict) -> dict:
    """Retrieve today's food logs and aggregated nutritional totals."""
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


async def get_food_history(user: dict, days: int = 30) -> dict:
    """Retrieve historical food logs and daily calorie summaries."""
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


async def delete_food_log(user: dict, item_id: str) -> dict:
    """Delete a food log entry with user ownership enforcement (prevents IDOR)."""
    r = await db.food_logs.delete_one({"id": item_id, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}
