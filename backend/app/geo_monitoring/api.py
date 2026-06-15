"""AI 应用监测 API。"""

from fastapi import APIRouter

from app.core.response import success

router = APIRouter(prefix="/geo-monitoring", tags=["AI 应用监测"])


@router.get("/platforms", summary="分页查询 AI 平台")
def list_platforms_placeholder() -> dict:
    """临时边界端点，后续由平台 Service 替换。"""
    return success({"items": [], "total": 0, "page": 1, "page_size": 10})
