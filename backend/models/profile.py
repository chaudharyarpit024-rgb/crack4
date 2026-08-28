from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class ProfileBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[\w\s'.-]+$",
    )
    goal: Optional[Literal["gain", "lose", "maintain"]] = None
    weight_kg: Optional[float] = Field(default=None, ge=20.0, le=500.0)
    height_cm: Optional[float] = Field(default=None, ge=50.0, le=300.0)
    age: Optional[int] = Field(default=None, ge=5, le=130)
    gender: Optional[Literal["male", "female", "other"]] = None

