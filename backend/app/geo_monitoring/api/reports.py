"""监测报告 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.response import paginate, success
from app.geo_monitoring.reports.storage import (
    GeoReport,
    ReportStorage,
    create_run_reports,
    delete_report,
    generate_report_content,
    get_report,
    list_run_reports,
    read_report_bytes,
)
router = APIRouter()

_CONTENT_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
}


class ReportCreateRequest(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["md", "html"])


# 将报告 ORM 行序列化为 API 响应字段
def _report_payload(report: GeoReport) -> dict:
    return {
        "id": report.id,
        "project_id": report.project_id,
        "run_id": report.run_id,
        "status": report.status,
        "format": report.format,
        "file_name": report.file_name,
        "relative_storage_path": report.relative_storage_path,
        "file_size": report.file_size,
        "checksum": report.checksum,
        "error_message": report.error_message,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


# 基于配置创建报告文件存储实例
def _storage() -> ReportStorage:
    return ReportStorage(get_settings().REPORT_STORAGE_DIR)


@router.post("/runs/{run_id}/reports", summary="创建并生成监测报告")
# 为运行创建报告记录并同步生成文件内容
def create_run_report(
    payload: ReportCreateRequest,
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    reports = create_run_reports(db, run_id, formats=payload.formats)
    storage = _storage()
    completed: list[GeoReport] = []
    # 逐份生成并写入存储
    for report in reports:
        row = generate_report_content(db, report.id, storage=storage)
        completed.append(row)
    return success({"run_id": run_id, "reports": [_report_payload(item) for item in completed]})


@router.get("/runs/{run_id}/reports", summary="分页查询运行报告")
# 分页查询指定运行下的报告列表
def list_reports_for_run(
    run_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = list_run_reports(db, run_id, page=page, page_size=page_size)
    data = [_report_payload(item) for item in items]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.get("/reports/{report_id}", summary="获取报告状态与元数据")
# 按 ID 获取报告状态与元数据
def get_report_detail(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    report = get_report(db, report_id)
    return success(_report_payload(report))


@router.get("/reports/{report_id}/download", summary="按报告 ID 下载文件")
# 下载报告文件二进制内容
def download_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Response:
    report = get_report(db, report_id)
    content = read_report_bytes(report, storage=_storage())
    media_type = _CONTENT_TYPES.get(report.format, "application/octet-stream")
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{report.file_name}"',
        },
    )


@router.delete("/reports/{report_id}", summary="删除报告")
# 删除报告记录及对应存储文件
def remove_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> dict:
    report = delete_report(db, report_id, storage=_storage())
    return success(_report_payload(report))
