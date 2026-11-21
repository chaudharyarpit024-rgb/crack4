from fastapi import APIRouter, Depends
from security.dependencies import current_user
from models.family_box import CreateFamilyBoxBody, JoinFamilyBoxBody
from controllers.family_box_controller import (
    create_family_box,
    join_family_box,
    get_my_family_box,
    leave_family_box,
)

router = APIRouter(prefix="/family-box", tags=["family-box"])


@router.post("/create")
async def create_box_endpoint(
    body: CreateFamilyBoxBody,
    user: dict = Depends(current_user)
):
    return await create_family_box(user, body)


@router.post("/join")
async def join_box_endpoint(
    body: JoinFamilyBoxBody,
    user: dict = Depends(current_user)
):
    return await join_family_box(user, body)


@router.get("/my-box")
async def get_my_box_endpoint(
    user: dict = Depends(current_user)
):
    return await get_my_family_box(user)


@router.post("/leave")
async def leave_box_endpoint(
    user: dict = Depends(current_user)
):
    return await leave_family_box(user)