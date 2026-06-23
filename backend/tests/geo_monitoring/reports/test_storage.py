"""报告存储与生命周期测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.geo_monitoring.reports.storage import (
    GeoReport,
    PathTraversalError,
    ReportStorage,
    purge_expired_reports,
    write_report_file,
)
from tests.geo_monitoring.reports.conftest import _insert_report


def test_relative_path_uses_project_run_report_pattern(report_storage):
    path = report_storage.build_relative_path(project_id=7, run_id=42, report_id=99, ext="md")
    assert path == "7/42/99.md"


def test_relative_path_supports_pdf_extension(report_storage):
    path = report_storage.build_relative_path(project_id=7, run_id=42, report_id=99, ext="pdf")
    assert path == "7/42/99.pdf"


def test_resolve_path_rejects_traversal(report_storage):
    with pytest.raises(PathTraversalError):
        report_storage.resolve_path("../../etc/passwd")


def test_resolve_path_rejects_absolute_like(report_storage):
    with pytest.raises(PathTraversalError):
        report_storage.resolve_path("/etc/passwd")


def test_write_atomic_rename_and_checksum(report_storage):
    relative = report_storage.build_relative_path(
        project_id=1, run_id=2, report_id=3, ext="md"
    )
    payload = b"# hello report\n"
    file_size, checksum = write_report_file(report_storage, relative, payload)

    assert file_size == len(payload)
    assert len(checksum) == 64
    assert report_storage.read_bytes(relative) == payload
    assert not report_storage.resolve_path(f"{relative}.tmp").exists()


def test_purge_expired_reports_skips_retained(session_factory, report_storage, tmp_path):
    old_time = datetime.now(timezone.utc) - timedelta(days=120)
    with session_factory() as db:
        expired = _insert_report(
            db,
            project_id=1,
            run_id=10,
            report_id=1,
            created_at=old_time,
        )
        retained = _insert_report(
            db,
            project_id=1,
            run_id=10,
            report_id=2,
            fmt="html",
            relative_storage_path="1/10/2.html",
            created_at=old_time,
            retained=True,
        )
        write_report_file(report_storage, expired.relative_storage_path, b"old")
        write_report_file(report_storage, retained.relative_storage_path, b"keep")

    with session_factory() as db:
        removed = purge_expired_reports(
            db,
            report_storage,
            retention_days=90,
            now=datetime.now(timezone.utc),
        )
        assert removed == 1
        assert db.get(GeoReport, expired.id).is_deleted is True
        assert db.get(GeoReport, retained.id).is_deleted is False
        assert report_storage.read_bytes(retained.relative_storage_path) == b"keep"
        assert not report_storage.resolve_path(expired.relative_storage_path).exists()
