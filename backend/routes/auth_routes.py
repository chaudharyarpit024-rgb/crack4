from fastapi import APIRouter, Depends
from models.auth import SignupBody, LoginBody
from models.verification import (
    VerifyBody,
    ResendBody,
    ForgotPasswordBody,
    ResetPasswordBody,
)
from security.dependencies import current_user
from controllers.auth_controller import (
    signup_user,
    login_user,
    get_me,
    verify_email,
    verify_email_link,
    resend_verification,
    forgot_password,
    reset_password,
    reset_password_web,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(body: SignupBody):
    return await signup_user(body)


@router.post("/login")
async def login(body: LoginBody):
    return await login_user(body)


@router.post("/verify")
async def verify(body: VerifyBody):
    return await verify_email(body)


@router.get("/verify-link")
async def verify_link(token: str):
    return await verify_email_link(token)


@router.post("/resend-verification")
async def resend(body: ResendBody):
    return await resend_verification(body)


@router.post("/forgot-password")
async def handle_forgot_password(body: ForgotPasswordBody):
    return await forgot_password(body)


@router.post("/reset-password")
async def handle_reset_password(body: ResetPasswordBody):
    return await reset_password(body)


@router.get("/reset-password-web")
async def handle_reset_password_web(token: str):
    return await reset_password_web(token)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return await get_me(user)

