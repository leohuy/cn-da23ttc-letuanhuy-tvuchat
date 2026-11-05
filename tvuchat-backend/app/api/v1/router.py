from fastapi import APIRouter
from app.api.v1 import admin, chat, auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Student Authentication"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Workspace"])
api_router.include_router(chat.router, prefix="/chat", tags=["Student Chat Service"])