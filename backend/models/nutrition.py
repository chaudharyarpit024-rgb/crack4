from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class RecipeItem(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(description="Unique identifier for the recipe")
    title: str = Field(min_length=2, max_length=120, description="Name of the recipe")
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = Field(
        description="Appropriate meal category"
    )
    calories: int = Field(ge=0, le=5000, description="Estimated total calories")
    protein_g: float = Field(ge=0, le=300, description="Protein in grams")
    carbs_g: float = Field(ge=0, le=500, description="Carbohydrates in grams")
    fat_g: float = Field(ge=0, le=300, description="Fat in grams")
    prep_time_minutes: int = Field(ge=1, le=180, description="Estimated preparation time")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="easy")
    description: str = Field(max_length=300, description="Short appetizing summary")
    ingredients: List[str] = Field(description="List of ingredients with measurements")
    instructions: List[str] = Field(description="Step-by-step preparation steps")
    why_it_fits: str = Field(
        max_length=300,
        description="Explanation of how this meal fits the user's calorie and macro targets",
    )


class RecipeSuggestionsResponse(BaseModel):
    remaining_calories: int = Field(description="Calories remaining for today")
    daily_target: int = Field(description="User's total daily calorie target")
    calories_consumed_today: int = Field(description="Calories already logged today")
    dietary_preference: Optional[str] = Field(
        default=None, description="User's dietary preference (e.g., veg, non-veg)"
    )
    recipes: List[RecipeItem] = Field(description="Curated list of AI recommended recipes")
