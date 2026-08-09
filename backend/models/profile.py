from pydantic import BaseModel
from typing import Optional, Literal


class ProfileBody(BaseModel):
    name: Optional[str] = None
    goal: Optional[Literal["gain", "lose", "maintain"]] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[Literal["male", "female", "other"]] = None
