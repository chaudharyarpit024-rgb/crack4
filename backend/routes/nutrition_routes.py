import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from security.dependencies import enforce_recipe_quota
from controllers.nutrition_controller import get_recipe_suggestions

logger = logging.getLogger(__name__)

# Prefix "/nutrition" means this router handles paths starting with /api/nutrition
router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.get("/recipes")
async def get_recipes(
    meal_type: Optional[str] = Query(
        default=None,
        pattern=r"^(breakfast|lunch|dinner|snack)$",
        description="Filter by meal type: breakfast, lunch, dinner, or snack",
    ),
    diet_pref: Optional[str] = Query(
        default=None,
        max_length=50,
        description="Optional diet preference override (e.g., vegetarian, vegan, high-protein)",
    ),
    user: dict = Depends(enforce_recipe_quota),
):
    """
    Generate personalized meal recommendations based on today's remaining calories.
    Requires an active trial, subscription, or unlimited VIP access.
    """
    return await get_recipe_suggestions(
        user=user,
        meal_type=meal_type,
        diet_preference=diet_pref,
    )
