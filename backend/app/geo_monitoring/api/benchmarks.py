"""行业基准 API。"""

from fastapi import APIRouter, Query

from app.core.response import ResponseModel, success
from app.geo_monitoring.schemas import BenchmarkDetailOut, BenchmarkListOut
from app.geo_monitoring.services import benchmarks as benchmarks_service

router = APIRouter()


@router.get(
    "/benchmarks",
    summary="获取行业基准参照指标",
    response_model=ResponseModel[BenchmarkListOut | BenchmarkDetailOut],
)
def list_benchmarks(
    industry: str | None = Query(None, description="行业名称；不传时返回全部行业基准列表"),
) -> dict:
    data = benchmarks_service.get_benchmarks(industry=industry)
    return success(data)
