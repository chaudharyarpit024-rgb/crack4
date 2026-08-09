from fastapi import APIRouter, Depends
from models.auth import SignupBody, LoginBody
from security.dependencies import current_user
from controllers.auth_controller import signup_user, login_user, get_me

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(body: SignupBody):
    return await signup_user(body)


@router.post("/login")
async def login(body: LoginBody):
    return await login_user(body)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return await get_me(user)
