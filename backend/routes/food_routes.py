import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from models.food import AnalyzeBody, FoodLogBody
from security.dependencies import current_user, enforce_quota
from utils.subscription import refund_trial_request, refund_paid_request
from controllers.food_controller import (
    analyze_food_image,
    create_food_log,
    get_today_food_logs,
    get_food_history,
    delete_food_log,
    get_user_streak,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/food", tags=["food"])


@router.post("/analyze")
async def analyze_food(
    body: AnalyzeBody,
    request: Request,
    user: dict = Depends(enforce_quota),
):
    """
    Quota is reserved by enforce_quota BEFORE this handler runs (not after success),
    so concurrent requests can't all slip through before any of them registers a count.

    If the AI upstream fails (infra error → HTTP 502), we refund the reservation so
    the user is not penalised for our infrastructure problems.
    If it's a user-input problem (unreadable image → HTTP 4xx), we do NOT refund.
    """
    try:
        return await analyze_food_image(body)
    except HTTPException as exc:
        # 502 = upstream AI failure on our side → refund the reservation so
        # the user is not penalised for our infrastructure problems.
        # 4xx = user-input problem (bad image etc.) → do NOT refund; it still counts.
        if exc.status_code == 502:
            try:
                # Use getattr with defaults: enforce_quota always sets these before
                # the route body runs, but be defensive against future refactors.
                is_paid = getattr(request.state, "is_paid", False)
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    if is_paid:
                        await refund_paid_request(user_id)
                    else:
                        await refund_trial_request(user_id)
            except Exception:
                # Refund failure must not mask the original error the client sees.
                user_id_str = str(getattr(request.state, "user_id", "unknown")).replace("\n", "\\n").replace("\r", "\\r")
                logger.warning("Refund failed for user_id=%s after 502", user_id_str)
        raise


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


@router.get("/streak")
async def get_streak(
    client_date: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Client local date YYYY-MM-DD"),
    timezone: Optional[str] = Query(default=None, max_length=64, description="Client IANA timezone name (e.g. Asia/Kolkata)"),
    user: dict = Depends(current_user),
):
    return await get_user_streak(user, client_date=client_date, client_tz=timezone)

