from pydantic import BaseModel, Field
from typing import Optional, Literal


class FoodLogBody(BaseModel):
    food_name: str = Field(min_length=1, max_length=120)
    calories: float = Field(ge=0, le=20000)
    fat_g: Optional[float] = Field(default=0, ge=0, le=1000)
    carbs_g: Optional[float] = Field(default=0, ge=0, le=1000)
    protein_g: Optional[float] = Field(default=0, ge=0, le=1000)
    serving_size_g: Optional[float] = Field(default=None, ge=0, le=10000)
    source: Optional[Literal["ai", "manual"]] = "manual"
    image_b64: Optional[str] = Field(default=None, max_length=250_000)



class AnalyzeBody(BaseModel):
    image_base64: str = Field(min_length=32, max_length=8 * 1024 * 1024)  # ≤ ~6 MB decoded
