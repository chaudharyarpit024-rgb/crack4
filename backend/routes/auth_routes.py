from fastapi import APIRouter, Depends
from models.auth import SignupBody, LoginBody
from models.verification import VerifyBody, ResendBody
from security.dependencies import current_user
from controllers.auth_controller import (
    signup_user,
    login_user,
    get_me,
    verify_email,
    resend_verification,
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


@router.post("/resend-verification")
async def resend(body: ResendBody):
    return await resend_verification(body)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return await get_me(user)
