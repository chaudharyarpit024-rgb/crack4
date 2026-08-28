from fastapi import APIRouter, Depends, Query
from models.auth import SignupBody, LoginBody
from models.verification import (
    VerifyBody,
    ResendBody,
    ForgotPasswordBody,
    ResetPasswordBody,
)
from security.dependencies import current_user
from security.rate_limiter import (
    rate_limit_auth,
    rate_limit_public,
    extract_email_from_body,
    extract_token_from_body,
)
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


@router.post("/signup", dependencies=[Depends(rate_limit_auth(extract_email_from_body))])
async def signup(body: SignupBody):
    return await signup_user(body)


@router.post("/login", dependencies=[Depends(rate_limit_auth(extract_email_from_body))])
async def login(body: LoginBody):
    return await login_user(body)


@router.post("/verify", dependencies=[Depends(rate_limit_auth())])
async def verify(body: VerifyBody):
    return await verify_email(body)


@router.get("/verify-link", dependencies=[Depends(rate_limit_public)])
async def verify_link(
    token: str = Query(..., min_length=1, max_length=4096),
):
    return await verify_email_link(token)


@router.post("/resend-verification", dependencies=[Depends(rate_limit_auth(extract_email_from_body))])
async def resend(body: ResendBody):
    return await resend_verification(body)


@router.post("/forgot-password", dependencies=[Depends(rate_limit_auth(extract_email_from_body))])
async def handle_forgot_password(body: ForgotPasswordBody):
    return await forgot_password(body)


@router.post("/reset-password", dependencies=[Depends(rate_limit_auth())])
async def handle_reset_password(body: ResetPasswordBody):
    return await reset_password(body)


@router.get("/reset-password-web", dependencies=[Depends(rate_limit_public)])
async def handle_reset_password_web(
    token: str = Query(..., min_length=1, max_length=4096),
):
    return await reset_password_web(token)




@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return await get_me(user)


