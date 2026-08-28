from fastapi import HTTPException
from database.mongodb import db
from models.profile import ProfileBody
from utils.nutrition import calorie_target
from config.settings import logger


async def update_user_profile(user: dict, body: ProfileBody) -> dict:
    """Update profile metrics and recalculate daily calorie goal if required parameters are present."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    merged = {**user, **updates}
    if merged.get("goal") and merged.get("weight_kg") and merged.get("height_cm"):
        merged["daily_target"] = calorie_target(
            merged["goal"],
            merged["weight_kg"],
            merged["height_cm"],
            merged.get("age"),
            merged.get("gender"),
        )
        updates["daily_target"] = merged["daily_target"]
    try:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
        updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password": 0})
    except Exception:
        logger.exception("Database error while updating profile for user %s", user.get("id"))
        raise HTTPException(503, "Service temporarily unavailable. Please try again.")
    return updated
