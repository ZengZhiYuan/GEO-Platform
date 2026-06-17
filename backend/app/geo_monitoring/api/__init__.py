"""AI 应用监测 API 路由聚合。"""

from fastapi import APIRouter

from app.geo_monitoring.api.analysis import router as analysis_router
from app.geo_monitoring.api.answers import router as answers_router
from app.geo_monitoring.api.brands import router as brands_router
from app.geo_monitoring.api.dashboard import router as dashboard_router
from app.geo_monitoring.api.platforms import router as platforms_router
from app.geo_monitoring.api.projects import router as projects_router
from app.geo_monitoring.api.prompts import router as prompts_router
from app.geo_monitoring.api.runs import router as runs_router

_SUB_ROUTERS = (
    projects_router,
    brands_router,
    prompts_router,
    platforms_router,
    runs_router,
    answers_router,
    analysis_router,
    dashboard_router,
)


def build_router(*, prefix: str, tags: list[str]) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=tags)
    for sub_router in _SUB_ROUTERS:
        router.include_router(sub_router)
    return router


router = build_router(prefix="/geo-monitoring", tags=["AI 应用监测"])
legacy_router = build_router(
    prefix="/v1/geo-monitoring",
    tags=["AI 应用监测 (v1 兼容)"],
)
