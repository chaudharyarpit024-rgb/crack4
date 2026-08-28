from pydantic import BaseModel, ConfigDict, EmailStr, Field


class VerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    token: str = Field(
        ...,
        min_length=1,
        max_length=4096,
    )


class ResendBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr = Field(..., max_length=255)


class ForgotPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr = Field(..., max_length=255)


class ResetPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    token: str = Field(
        ...,
        min_length=1,
        max_length=4096,
    )
    new_password: str = Field(..., min_length=8, max_length=128)


