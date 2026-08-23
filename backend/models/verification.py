from pydantic import BaseModel, EmailStr, Field


class VerifyBody(BaseModel):
    token: str = Field(min_length=10, max_length=4096)


class ResendBody(BaseModel):
    email: EmailStr
