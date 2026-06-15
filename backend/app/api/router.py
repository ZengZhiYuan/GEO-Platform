"""应用 API 路由聚合。"""

from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success
from app.geo_monitoring.api import router as geo_monitoring_router

api_router = APIRouter()


@api_router.get("/health", summary="健康检查")
async def health() -> dict:
    return success(
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
        }
    )


api_router.include_router(geo_monitoring_router)
