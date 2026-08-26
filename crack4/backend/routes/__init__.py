from fastapi import APIRouter
from .auth_routes import router as auth_router
from .profile_routes import router as profile_router
from .food_routes import router as food_router
from .subscription_routes import router as subscription_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(food_router)
api_router.include_router(subscription_router)


@api_router.get("")
@api_router.get("/")
async def api_root():
    return {"service": "crack", "ok": True}


__all__ = [
    "api_router",
    "auth_router",
    "profile_router",
    "food_router",
    "subscription_router",
]
