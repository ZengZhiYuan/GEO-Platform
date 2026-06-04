"""API 路由聚合。

后续各业务域（keyword、title_inspiration ...）的 router 在此 include。
当前仅提供健康检查接口。
"""

from fastapi import APIRouter

from app.api.endpoints import (
    image_asset,
    image_category,
    keyword,
    title_inspiration,
    writing_rule,
)
from app.core.config import settings
from app.core.response import success

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


# 业务路由聚合
api_router.include_router(keyword.router)
api_router.include_router(title_inspiration.router)
api_router.include_router(image_category.router)
api_router.include_router(image_asset.router)
api_router.include_router(writing_rule.router)
