from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[\w\s'.-]+$",
    )


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

