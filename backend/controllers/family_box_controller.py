import secrets
from database.mongodb import db
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from models.family_box import CreateFamilyBoxBody, JoinFamilyBoxBody


async def _generate_invite_code() -> str:
     
    """Generate a clean, collision-free invite code"""
     
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for i in range(10):
        code = "FAM-" + "".join(secrets.choice(alphabet) for _ in range(4))
        exists = await db.family_boxes.find_one({"invite_code": code}, {"_id": 1})
        if not exists:
            return code
    return "FAM-" + secrets.token_hex(3).upper()

async def create_family_box(user: dict, body: CreateFamilyBoxBody) -> dict:
    
    # 1. Rule Check: Is the user already in a box?
    existing = await db.family_boxes.find_one({"member_ids": user["id"]})
    if existing:
        raise HTTPException(
            400,
              f"You are already a member of '{existing.get('name')}'. Leave your current box before creating a new one."
        )
        
    # 2. Generate unique invite code & IDs
    invite_code = await _generate_invite_code()
    box_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # 3. Create the document blueprint
    doc = {
        "id": box_id,
        "name": body.name.strip(),
        "creator_id": user["id"],
        "invite_code": invite_code,
        "member_ids": [user["id"]],
        "created_at": now,
        "updated_at": now,
    }
    
    # 4. Save into MongoDB
    await db.family_boxes.insert_one(doc)
    
    return {
        "ok": True,
        "message": f"Family Box '{doc['name']}' created successfully!",
        "box": {
            "id": doc["id"],
            "name": doc["name"],
            "invite_code": doc["invite_code"],
            "creator_id": doc["creator_id"], 
            "member_count": 1,
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],  
        },
    }
    
async def get_my_family_box(user: dict) -> dict:
    """Fetch current user's family box and the live competitive leaderboard."""
    # 1. Find the box this user belongs to
    box = await db.family_boxes.find_one({"member_ids": user["id"]})
    if not box:
        return {"box": None, "leaderboard": []}

    member_ids = box.get("member_ids", [])
    if not member_ids:
        return {"box": box, "leaderboard": []}

    # 2. Fetch profiles of all members
    members_cursor = db.users.find(
        {"id": {"$in": member_ids}},
        {"_id": 0, "id": 1, "name": 1, "goal": 1, "daily_target": 1}
    )
    members_list = await members_cursor.to_list(100)
    members_map = {m["id"]: m for m in members_list}

    # 3. Sum up calories consumed today for each member
    start_of_today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    calories_by_user = {}
    logs_cursor = db.food_logs.find(
        {"user_id": {"$in": member_ids}, "timestamp": {"$gte": start_of_today}},
        {"_id": 0, "user_id": 1, "calories": 1}
    )
    async for log in logs_cursor:
        uid = log.get("user_id")
        calories_by_user[uid] = calories_by_user.get(uid, 0.0) + float(log.get("calories", 0.0))

    # 4. Calculate adherence percentage and points
    leaderboard = []
    for uid in member_ids:
        prof = members_map.get(uid, {})
        name = prof.get("name") or "Family Member"
        goal = prof.get("goal") or "maintain"
        daily_target = int(prof.get("daily_target") or 2000)
        consumed = int(round(calories_by_user.get(uid, 0.0)))

        # Percentage adherence (capped at 100% for fair points)
        target_pct = min(100, int(round((consumed / daily_target) * 100))) if daily_target > 0 else 0
        score = target_pct * 10

        leaderboard.append({
            "user_id": uid,
            "name": name,
            "goal": goal,
            "calories_consumed": consumed,
            "daily_target": daily_target,
            "target_percentage": target_pct,
            "score": score,
            "is_me": (uid == user["id"]),
        })

    # 5. Sort descending by score and assign ranks
    leaderboard.sort(key=lambda m: m["score"], reverse=True)
    for rank_idx, member in enumerate(leaderboard, start=1):
        member["rank"] = rank_idx

    return {
        "box": {
            "id": box.get("id"),
            "name": box.get("name"),
            "invite_code": box.get("invite_code"),
            "creator_id": box.get("creator_id"),
            "member_count": len(member_ids),
        },
        "leaderboard": leaderboard,
    }

async def join_family_box(user: dict, body: JoinFamilyBoxBody) -> dict:
    """Join an existing family box using an invite code."""
    # 1. Check if user is already in any box
    existing = await db.family_boxes.find_one({"member_ids": user["id"]})
    if existing:
        raise HTTPException(
            400,
            f"You are already a member of '{existing.get('name')}'. Leave your current box before joining a new one."
        )

    # 2. Find box by invite code (case-insensitive clean up)
    clean_code = body.invite_code.strip().upper()
    box = await db.family_boxes.find_one({"invite_code": clean_code})
    if not box:
        raise HTTPException(404, "Invalid invite code. Please check with your family organizer.")

    # 3. Add user to the box using $addToSet to avoid duplicates
    now = datetime.now(timezone.utc).isoformat()
    await db.family_boxes.update_one(
        {"id": box["id"]},
        {
            "$addToSet": {"member_ids": user["id"]},
            "$set": {"updated_at": now}
        }
    )

    return {
        "ok": True,
        "message": f"Successfully joined '{box['name']}'!",
        "box": {
            "id": box["id"],
            "name": box["name"],
            "invite_code": box["invite_code"],
        }
    }


async def leave_family_box(user: dict) -> dict:
    """Leave the current family box."""
    box = await db.family_boxes.find_one({"member_ids": user["id"]})
    if not box:
        raise HTTPException(400, "You are not a member of any family box.")

    # Remove user from members
    updated_members = [m for m in box.get("member_ids", []) if m != user["id"]]
    
    if not updated_members:
        # If no one is left, delete the empty box
        await db.family_boxes.delete_one({"id": box["id"]})
    else:
        now = datetime.now(timezone.utc).isoformat()
        await db.family_boxes.update_one(
            {"id": box["id"]},
            {
                "$set": {
                    "member_ids": updated_members,
                    "updated_at": now
                }
            }
        )

    return {"ok": True, "message": f"You have left '{box['name']}'."}