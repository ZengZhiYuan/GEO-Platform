"""报告文件存储、元数据 ORM 与生命周期管理。"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import get_settings
from app.core.exceptions import BusinessException
from app.geo_monitoring.models import MonitorRun
from app.geo_monitoring.reports.renderer import (
    build_report_context,
    render_html,
    render_markdown,
)
from app.geo_monitoring.reports.pdf_renderer import render_pdf
from app.geo_monitoring.services.runs import get_run
from app.geo_monitoring.services.tenant_access import (
    ensure_project_tenant_access,
    stamp_tenant_fields,
)
from app.models.base import BaseModel

RETAIN_MARKER = -1
_VALID_FORMATS = frozenset({"md", "html", "pdf"})


class PathTraversalError(ValueError):
    """相对路径非法或试图穿越存储根目录。"""


class GeoReport(BaseModel):
    __tablename__ = "geo_report"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'generating', 'completed', 'failed')",
            name="ck_geo_report_status",
        ),
        CheckConstraint(
            "format IN ('md', 'html', 'pdf')",
            name="ck_geo_report_format",
        ),
        Index("uq_geo_report_relative_storage_path", "relative_storage_path", unique=True),
        Index("ix_geo_report_project_run", "project_id", "run_id"),
        Index("ix_geo_report_tenant", "tenant_id"),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )


class ReportStorage:
    # 初始化报告本地存储根目录并确保目录存在。
    def __init__(self, root_dir: str | Path) -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # 按项目/运行/报告 ID 生成相对存储路径。
    def build_relative_path(
        self,
        *,
        project_id: int,
        run_id: int,
        report_id: int,
        ext: str,
    ) -> str:
        normalized_ext = ext.lstrip(".")
        return f"{project_id}/{run_id}/{report_id}.{normalized_ext}"

    # 将相对路径解析为绝对路径并校验防目录穿越。
    def resolve_path(self, relative_path: str) -> Path:
        normalized = relative_path.replace("\\", "/").strip()
        if not normalized:
            raise PathTraversalError("empty relative path")
        if normalized.startswith("/") or normalized.startswith("\\\\"):
            raise PathTraversalError("absolute path is not allowed")
        if len(normalized) >= 2 and normalized[1] == ":":
            raise PathTraversalError("absolute path is not allowed")
        parts = [part for part in normalized.split("/") if part not in {"", "."}]
        if any(part == ".." for part in parts):
            raise PathTraversalError("path traversal is not allowed")
        candidate = self.root.joinpath(*parts).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise PathTraversalError("path escapes storage root")
        return candidate

    # 读取相对路径对应报告文件的二进制内容。
    def read_bytes(self, relative_path: str) -> bytes:
        path = self.resolve_path(relative_path)
        return path.read_bytes()

    # 删除相对路径对应的报告文件（存在时）。
    def delete_file(self, relative_path: str) -> None:
        path = self.resolve_path(relative_path)
        if path.exists():
            path.unlink()


# 原子写入报告文件并返回文件大小与 SHA256 校验和。
def write_report_file(
    storage: ReportStorage,
    relative_path: str,
    content: bytes,
) -> tuple[int, str]:
    target = storage.resolve_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # 先写临时文件再原子替换，避免生成不完整报告
    temp_path = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_bytes(content)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    checksum = hashlib.sha256(content).hexdigest()
    return len(content), checksum


# 判断报告是否被标记为永久保留（不参与过期清理）。
def is_report_retained(report: GeoReport) -> bool:
    return report.created_by == RETAIN_MARKER


# 将报告标记为永久保留。
def mark_report_retained(report: GeoReport) -> None:
    report.created_by = RETAIN_MARKER


# 使用全局配置创建默认报告存储实例。
def _default_storage() -> ReportStorage:
    return ReportStorage(get_settings().REPORT_STORAGE_DIR)


# 为已完成分析的运行创建待生成的报告元数据记录。
def create_run_reports(
    db: Session,
    run_id: int,
    *,
    formats: list[str],
) -> list[GeoReport]:
    run = get_run(db, run_id)
    if run.analysis_status not in {"completed", "partial_success"}:
        raise BusinessException(
            message="分析尚未完成，暂不可生成报告",
            code=40920,
            status_code=409,
        )

    normalized_formats = []
    for fmt in formats:
        value = fmt.strip().lower()
        if value not in _VALID_FORMATS:
            raise BusinessException(message=f"不支持的报告格式: {fmt}", code=40060)
        if value not in normalized_formats:
            normalized_formats.append(value)

    reports: list[GeoReport] = []
    for fmt in normalized_formats:
        report = GeoReport(
            project_id=run.project_id,
            run_id=run.id,
            status="pending",
            format=fmt,
            file_name=f"report-{run.run_no}.{fmt}",
            relative_storage_path="pending",
        )
        stamp_tenant_fields(report)
        db.add(report)
        db.flush()
        # flush 后获得 report.id，再确定最终存储路径
        report.relative_storage_path = (
            f"{run.project_id}/{run.id}/{report.id}.{fmt}"
        )
        reports.append(report)

    run.report_status = "running"
    db.commit()
    for report in reports:
        db.refresh(report)
    return reports


# 渲染指定报告内容、写入文件并更新状态与运行报告进度。
def generate_report_content(
    db: Session,
    report_id: int,
    *,
    storage: ReportStorage | None = None,
) -> GeoReport:
    storage = storage or _default_storage()
    report = db.get(GeoReport, report_id)
    if report is None or report.is_deleted:
        raise BusinessException(message="报告不存在", code=40420, status_code=404)

    report.status = "generating"
    db.commit()

    try:
        context = build_report_context(db, report.run_id)
        # 按格式选择 Markdown、HTML 或 PDF 渲染
        if report.format == "md":
            content = render_markdown(context).encode("utf-8")
        elif report.format == "html":
            content = render_html(context).encode("utf-8")
        elif report.format == "pdf":
            content = render_pdf(context)
        else:
            raise BusinessException(message=f"不支持的报告格式: {report.format}", code=40060)

        file_size, checksum = write_report_file(
            storage,
            report.relative_storage_path,
            content,
        )
        report.status = "completed"
        report.file_size = file_size
        report.checksum = checksum
        report.completed_at = datetime.now(timezone.utc)
        report.error_message = None

        run = db.get(MonitorRun, report.run_id)
        if run is not None:
            # 同运行下无其他待生成报告时标记报告阶段完成
            sibling_pending = db.scalar(
                select(func.count())
                .select_from(GeoReport)
                .where(
                    GeoReport.run_id == report.run_id,
                    GeoReport.is_deleted.is_(False),
                    GeoReport.status.in_({"pending", "generating"}),
                    GeoReport.id != report.id,
                )
            )
            if not sibling_pending:
                run.report_status = "completed"
    except Exception as exc:
        report.status = "failed"
        report.error_message = str(exc)
        run = db.get(MonitorRun, report.run_id)
        if run is not None:
            run.report_status = "failed"
        db.commit()
        raise

    db.commit()
    db.refresh(report)
    return report


# 软删除报告记录并移除本地存储文件。
def delete_report(
    db: Session,
    report_id: int,
    *,
    storage: ReportStorage | None = None,
) -> GeoReport:
    storage = storage or _default_storage()
    report = db.get(GeoReport, report_id)
    if report is None or report.is_deleted:
        raise BusinessException(message="报告不存在", code=40420, status_code=404)

    if report.relative_storage_path and report.relative_storage_path != "pending":
        try:
            storage.delete_file(report.relative_storage_path)
        except PathTraversalError:
            pass

    report.is_deleted = True
    report.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return report


# 清理超过保留期且未标记保留的已完成报告。
def purge_expired_reports(
    db: Session,
    storage: ReportStorage,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    moment = now or datetime.now(timezone.utc)
    cutoff = moment - timedelta(days=retention_days)
    rows = list(
        db.execute(
            select(GeoReport).where(
                GeoReport.is_deleted.is_(False),
                GeoReport.status == "completed",
                GeoReport.created_at < cutoff,
            )
        )
        .scalars()
        .all()
    )

    removed = 0
    for report in rows:
        if is_report_retained(report):
            continue
        if report.relative_storage_path and report.relative_storage_path != "pending":
            try:
                storage.delete_file(report.relative_storage_path)
            except PathTraversalError:
                pass
        report.is_deleted = True
        report.deleted_at = moment
        removed += 1

    if removed:
        db.commit()
    return removed


# 按 ID 获取有效报告记录，不存在时抛出业务异常。
def get_report(db: Session, report_id: int) -> GeoReport:
    report = db.get(GeoReport, report_id)
    if report is None or report.is_deleted:
        raise BusinessException(message="报告不存在", code=40420, status_code=404)
    ensure_project_tenant_access(db, report.project_id)
    return report


# 分页查询指定运行下的报告列表。
def list_run_reports(
    db: Session,
    run_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[GeoReport], int]:
    get_run(db, run_id)
    conditions = [
        GeoReport.run_id == run_id,
        GeoReport.is_deleted.is_(False),
    ]
    total = db.scalar(select(func.count()).select_from(GeoReport).where(*conditions)) or 0
    items = list(
        db.execute(
            select(GeoReport)
            .where(*conditions)
            .order_by(GeoReport.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


# 读取已完成报告文件的二进制内容。
def read_report_bytes(report: GeoReport, storage: ReportStorage | None = None) -> bytes:
    if report.status != "completed":
        raise BusinessException(message="报告尚未生成完成", code=40921, status_code=409)
    storage = storage or _default_storage()
    return storage.read_bytes(report.relative_storage_path)

