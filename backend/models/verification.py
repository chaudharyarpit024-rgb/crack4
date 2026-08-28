from pydantic import BaseModel, EmailStr, Field


class VerifyBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class ResendBody(BaseModel):
    email: EmailStr


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    new_password: str = Field(min_length=8, max_length=128)
