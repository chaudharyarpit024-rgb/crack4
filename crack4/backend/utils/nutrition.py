from typing import Optional


def calorie_target(
    goal: str,
    weight_kg: float,
    height_cm: float,
    age: Optional[int] = None,
    gender: Optional[str] = None,
) -> int:
    """Calculate baseline daily calorie target using Mifflin-St Jeor formula."""
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
