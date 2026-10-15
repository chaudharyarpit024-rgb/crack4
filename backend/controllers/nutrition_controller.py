import uuid
from typing import Optional, List
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage

from models.nutrition import RecipeItem, RecipeSuggestionsResponse
from config.settings import EMERGENT_LLM_KEY, logger
from utils.json_parser import parse_json
from controllers.food_controller import get_today_food_logs


def _get_fallback_recipes(preference: str, remaining: int) -> List[dict]:
    """Fallback recipes in case AI service is temporarily slow or unreachable."""
    is_veg = "veg" in preference.lower() and "non" not in preference.lower()
    
    if is_veg:
        return [
            {
                "id": f"rec_{uuid.uuid4().hex[:8]}",
                "title": "Paneer & Chickpea Power Bowl",
                "meal_type": "lunch",
                "calories": min(450, max(250, remaining)),
                "protein_g": 28.0,
                "carbs_g": 35.0,
                "fat_g": 16.0,
                "prep_time_minutes": 15,
                "difficulty": "easy",
                "description": "Pan-tossed spiced paneer cubes with boiled chickpeas, fresh spinach, and lemon tahini dressing.",
                "ingredients": [
                    "100g low-fat paneer",
                    "80g boiled chickpeas",
                    "1 cup baby spinach",
                    "1 tbsp olive oil",
                    "Cumin, paprika, salt, and lemon juice"
                ],
                "instructions": [
                    "Heat olive oil in a non-stick skillet over medium heat.",
                    "Sauté paneer cubes and chickpeas with cumin, paprika, and salt for 6-8 minutes until golden.",
                    "Toss with fresh baby spinach and squeeze fresh lemon juice on top before serving."
                ],
                "why_it_fits": "High-protein vegetarian option that provides sustained energy without spiking insulin.",
            },
            {
                "id": f"rec_{uuid.uuid4().hex[:8]}",
                "title": "Greek Yogurt Berry Parfait",
                "meal_type": "snack",
                "calories": min(260, max(180, remaining)),
                "protein_g": 22.0,
                "carbs_g": 26.0,
                "fat_g": 4.0,
                "prep_time_minutes": 5,
                "difficulty": "easy",
                "description": "Thick unsweetened Greek yogurt layered with mixed berries, chia seeds, and a drizzle of honey.",
                "ingredients": [
                    "200g Greek yogurt (0% or low-fat)",
                    "50g mixed fresh berries",
                    "1 tsp chia seeds",
                    "1 tsp honey or stevia"
                ],
                "instructions": [
                    "Add Greek yogurt into a bowl or jar.",
                    "Top with fresh berries, sprinkle chia seeds, and lightly drizzle with honey."
                ],
                "why_it_fits": "Quick protein-packed snack to curb cravings while staying well within daily calorie limits.",
            },
        ]

    return [
        {
            "id": f"rec_{uuid.uuid4().hex[:8]}",
            "title": "Lemon Herb Grilled Chicken & Quinoa",
            "meal_type": "dinner",
            "calories": min(480, max(300, remaining)),
            "protein_g": 42.0,
            "carbs_g": 32.0,
            "fat_g": 11.0,
            "prep_time_minutes": 20,
            "difficulty": "easy",
            "description": "Juicy grilled chicken breast marinated in lemon, garlic, and herbs served alongside steamed quinoa.",
            "ingredients": [
                "150g skinless chicken breast",
                "60g cooked quinoa",
                "1 cup steamed broccoli florets",
                "1 tbsp lemon juice + garlic clove (minced)",
                "Salt, black pepper, oregano"
            ],
            "instructions": [
                "Marinate chicken breast with lemon juice, minced garlic, oregano, salt, and pepper for 10 minutes.",
                "Grill on medium-high heat for 6-7 minutes per side until fully cooked.",
                "Serve with warm quinoa and steamed broccoli."
            ],
            "why_it_fits": "Lean protein powerhouse that aids muscle recovery while leaving room for healthy fats.",
        },
        {
            "id": f"rec_{uuid.uuid4().hex[:8]}",
            "title": "Egg White & Spinach Scramble",
            "meal_type": "breakfast",
            "calories": min(240, max(160, remaining)),
            "protein_g": 26.0,
            "carbs_g": 6.0,
            "fat_g": 5.0,
            "prep_time_minutes": 8,
            "difficulty": "easy",
            "description": "Fluffy egg whites scrambled with baby spinach, cherry tomatoes, and a pinch of black pepper.",
            "ingredients": [
                "4 egg whites + 1 whole egg",
                "1 cup chopped baby spinach",
                "4 cherry tomatoes (halved)",
                "1 tsp olive oil or butter spray",
                "Salt and cracked black pepper"
            ],
            "instructions": [
                "Whisk eggs with a pinch of salt and pepper.",
                "Sauté spinach and tomatoes in a skillet for 2 minutes until wilted.",
                "Pour in whisked eggs and gently scramble on low heat until soft and fluffy."
            ],
            "why_it_fits": "Ultra-low calorie, high-protein breakfast that kickstarts metabolism without heavy carbs.",
        },
    ]


async def get_recipe_suggestions(
    user: dict,
    meal_type: Optional[str] = None,
    diet_preference: Optional[str] = None,
) -> dict:
    """Generate personalized recipe recommendations based on today's remaining calories and user goals."""
    today_data = await get_today_food_logs(user)
    consumed_calories = int(today_data.get("total_calories", 0))
    daily_target = int(user.get("daily_target") or 2000)
    remaining_calories = max(0, daily_target - consumed_calories)

    active_pref = (
        diet_preference
        or user.get("food_preference")
        or user.get("dietary_preference")
        or "Balanced"
    )
    user_goal = user.get("goal") or "maintain"

    system_prompt = (
        "You are an elite sports nutritionist and executive chef. "
        "Given the user's remaining calories for today, daily target, and diet preference, "
        "generate 3 to 4 realistic, delicious, high-satiety recipe recommendations. "
        "You must respond with STRICT JSON matching this schema: "
        '{"recipes": ['
        '  {'
        '    "id": string,'
        '    "title": string,'
        '    "meal_type": "breakfast"|"lunch"|"dinner"|"snack",'
        '    "calories": integer,'
        '    "protein_g": number,'
        '    "carbs_g": number,'
        '    "fat_g": number,'
        '    "prep_time_minutes": integer,'
        '    "difficulty": "easy"|"medium"|"hard",'
        '    "description": string,'
        '    "ingredients": [string],'
        '    "instructions": [string],'
        '    "why_it_fits": string'
        '  }'
        ']}'
    )

    meal_clause = f"Meal type preference: '{meal_type}'. " if meal_type else ""
    user_prompt = (
        f"User daily target: {daily_target} kcal. Already consumed today: {consumed_calories} kcal. "
        f"Remaining calories budget: {remaining_calories} kcal. "
        f"Fitness goal: {user_goal}. Diet preference: {active_pref}. "
        f"{meal_clause}"
        "Create 3 to 4 varied, practical recipes that fit within their remaining budget. "
        "Focus on high protein and realistic ingredients. Return JSON only."
    )

    recipes_list = []
    if EMERGENT_LLM_KEY:
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"recipes-{uuid.uuid4()}",
                system_message=system_prompt,
            ).with_model("gemini", "gemini-3.1-flash-lite")

            msg = UserMessage(text=user_prompt)
            raw = await chat.send_message(msg)
            parsed = parse_json(raw)
            if parsed and isinstance(parsed.get("recipes"), list):
                for item in parsed["recipes"]:
                    if not item.get("id"):
                        item["id"] = f"rec_{uuid.uuid4().hex[:8]}"
                    try:
                        validated_item = RecipeItem.model_validate(item)
                        recipes_list.append(validated_item)
                    except Exception as val_err:
                        logger.warning("Recipe validation skipped item: %s", val_err)
        except Exception as e:
            logger.warning("Gemini recipe generation fallback triggered: %s", e)

    # Use fallback recipes if AI generation returned empty or failed
    if not recipes_list:
        fallback_raw = _get_fallback_recipes(active_pref, remaining_calories)
        recipes_list = [RecipeItem.model_validate(r) for r in fallback_raw]

    response = RecipeSuggestionsResponse(
        remaining_calories=remaining_calories,
        daily_target=daily_target,
        calories_consumed_today=consumed_calories,
        dietary_preference=active_pref,
        recipes=recipes_list,
    )
    return response.model_dump()
