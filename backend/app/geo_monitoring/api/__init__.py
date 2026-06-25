"""AI 应用监测 API 路由聚合。"""

from fastapi import APIRouter

from app.geo_monitoring.api.ai_generation import router as ai_generation_router
from app.geo_monitoring.api.analysis import router as analysis_router
from app.geo_monitoring.api.answers import router as answers_router
from app.geo_monitoring.api.brands import router as brands_router
from app.geo_monitoring.api.competitor_analysis import router as competitor_analysis_router
from app.geo_monitoring.api.conversations import router as conversations_router
from app.geo_monitoring.api.core_keywords import router as core_keywords_router
from app.geo_monitoring.api.dashboard import router as dashboard_router
from app.geo_monitoring.api.metadata import router as metadata_router
from app.geo_monitoring.api.monitor_setup import router as monitor_setup_router
from app.geo_monitoring.api.platforms import router as platforms_router
from app.geo_monitoring.api.projects import router as projects_router
from app.geo_monitoring.api.prompt_library import router as prompt_library_router
from app.geo_monitoring.api.prompts import router as prompts_router
from app.geo_monitoring.api.reports import router as reports_router
from app.geo_monitoring.api.runs import router as runs_router
from app.geo_monitoring.api.schedules import router as schedules_router
from app.geo_monitoring.api.source_analysis import router as source_analysis_router

_SUB_ROUTERS = (
    ai_generation_router,
    projects_router,
    brands_router,
    core_keywords_router,
    prompts_router,
    prompt_library_router,
    monitor_setup_router,
    metadata_router,
    platforms_router,
    runs_router,
    schedules_router,
    answers_router,
    conversations_router,
    competitor_analysis_router,
    source_analysis_router,
    analysis_router,
    dashboard_router,
    reports_router,
)


# 组装监测域子路由并挂载到指定前缀
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
