from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class FoodLogBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    food_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        pattern=r"^[\w\s\-\.,'\"&()%/+!#]+$",
    )
    calories: float = Field(..., ge=0.0, le=20000.0)
    fat_g: Optional[float] = Field(default=0.0, ge=0.0, le=1000.0)
    carbs_g: Optional[float] = Field(default=0.0, ge=0.0, le=1000.0)
    protein_g: Optional[float] = Field(default=0.0, ge=0.0, le=1000.0)
    serving_size_g: Optional[float] = Field(default=None, ge=0.1, le=10000.0)
    source: Optional[Literal["ai", "manual"]] = "manual"
    image_b64: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=250000,
        pattern=r"^(?:data:image\/[a-zA-Z0-9\+\-\.]+;base64,)?[A-Za-z0-9+/=]+$",
    )


class AnalyzeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    image_base64: str = Field(
        ...,
        min_length=32,
        max_length=8 * 1024 * 1024,
        pattern=r"^(?:data:image\/[a-zA-Z0-9\+\-\.]+;base64,)?[A-Za-z0-9+/=\s]+$",
    )
    
    user_hint: Optional[str] = Field(
        default=None,
        max_length=120,
        pattern=r"^[\w\s\-\.,'\"&()%/+!#]+$",
        description="Optional user hint to help identify the food",)
    
        


class AiAnalyzeResult(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    food_name: str = Field(default="Unknown food", min_length=1, max_length=120)
    serving_size_g: float = Field(default=150.0, ge=0.0, le=10000.0)
    calories: float = Field(default=0.0, ge=0.0, le=20000.0)
    fat_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    carbs_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    protein_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    verdict: Literal["good", "bad", "ok"] = "ok"
    reason: str = Field(default="", max_length=500)

