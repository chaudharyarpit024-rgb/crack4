from fastapi import APIRouter, Depends, Query, Path
from models.food import AnalyzeBody, FoodLogBody
from security.dependencies import current_user, require_active_subscription
from controllers.food_controller import (
    analyze_food_image,
    create_food_log,
    get_today_food_logs,
    get_food_history,
    delete_food_log,
)

router = APIRouter(prefix="/food", tags=["food"])


@router.post("/analyze")
async def analyze_food(
    body: AnalyzeBody,
    user: dict = Depends(require_active_subscription),
):
    return await analyze_food_image(body)


@router.post("/log")
async def log_food(
    body: FoodLogBody,
    user: dict = Depends(current_user),
):
    return await create_food_log(user, body)


@router.get("/today")
async def today_logs(user: dict = Depends(current_user)):
    return await get_today_food_logs(user)


@router.get("/history")
async def history(
    days: int = Query(default=30, ge=1, le=365, description="Number of historical days to retrieve"),
    user: dict = Depends(current_user),
):
    return await get_food_history(user, days)


@router.delete("/{item_id}")
async def delete_log(
    item_id: str = Path(..., min_length=1, max_length=128, pattern=r"^[\w\-]+$"),
    user: dict = Depends(current_user),
):
    return await delete_food_log(user, item_id)

