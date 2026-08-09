from fastapi import APIRouter, Depends
from models.profile import ProfileBody
from security.dependencies import current_user
from controllers.profile_controller import update_user_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.put("")
async def update_profile(body: ProfileBody, user: dict = Depends(current_user)):
    return await update_user_profile(user, body)
