"""报告模块测试夹具。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import app.geo_monitoring.reports.storage  # noqa: F401 — register GeoReport ORM
import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import Answer, MonitorProject, MonitorRun, QueryTask
from app.geo_monitoring.reports.storage import GeoReport, ReportStorage, RETAIN_MARKER
from app.geo_monitoring.services.analysis import PlatformAnalysis, run_analysis
from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run


@pytest.fixture
def report_storage(tmp_path) -> ReportStorage:
    return ReportStorage(str(tmp_path))


@pytest.fixture
def analyzed_run(session_factory, monkeypatch):
    llm = FakeLLMClient()
    monkeypatch.setattr(
        "app.geo_monitoring.api.analysis.create_agent_llm_client",
        lambda *_args, **_kwargs: llm,
    )
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
    with session_factory() as db:
        run_analysis(db, seeded["run_id"], llm_client=llm)
    return seeded


@pytest.fixture
def xss_analyzed_run(session_factory):
    llm = FakeLLMClient()
    with session_factory() as db:
        seeded = _seed_run(db, platforms=("qwen",))
        answer = db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Answer)
            .join(QueryTask, QueryTask.id == Answer.task_id)
            .where(QueryTask.run_id == seeded["run_id"])
        ).scalar_one()
        malicious = '<script>alert("xss")</script> 推荐目标品牌'
        answer.raw_text = malicious
        answer.normalized_text = malicious
        db.commit()
    with session_factory() as db:
        run_analysis(db, seeded["run_id"], llm_client=llm)
    return seeded


def _insert_report(
    db,
    *,
    project_id: int,
    run_id: int,
    report_id: int | None = None,
    fmt: str = "md",
    status: str = "completed",
    relative_storage_path: str | None = None,
    created_at: datetime | None = None,
    retained: bool = False,
) -> GeoReport:
    report = GeoReport(
        project_id=project_id,
        run_id=run_id,
        status=status,
        format=fmt,
        file_name=f"report-{run_id}.{fmt}",
        relative_storage_path=relative_storage_path
        or f"{project_id}/{run_id}/{report_id or 1}.{fmt}",
        file_size=12,
        checksum="abc123",
        completed_at=datetime.now(timezone.utc) if status == "completed" else None,
        created_by=RETAIN_MARKER if retained else None,
    )
    if report_id is not None:
        report.id = report_id
    db.add(report)
    db.flush()
    if created_at is not None:
        report.created_at = created_at
    db.commit()
    db.refresh(report)
    return report
