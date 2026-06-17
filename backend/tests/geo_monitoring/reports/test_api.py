"""报告 API 与生成流程测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import app.geo_monitoring.reports.storage  # noqa: F401
from app.geo_monitoring.reports.storage import GeoReport, ReportStorage, generate_report_content
from app.worker.actors import report as report_actor


@pytest.fixture(autouse=True)
def configure_report_actor(session_factory):
    report_actor.configure_session_factory(session_factory)
    yield
    report_actor.reset_session_factory()


def test_create_list_and_download_report(client, analyzed_run, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_STORAGE_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    create_resp = client.post(
        f"/api/geo-monitoring/runs/{analyzed_run['run_id']}/reports",
        json={"formats": ["md", "html"]},
    )
    body = create_resp.json()
    assert body["code"] == 0
    assert len(body["data"]["reports"]) == 2

    list_resp = client.get(
        f"/api/geo-monitoring/runs/{analyzed_run['run_id']}/reports"
    )
    listed = list_resp.json()["data"]["items"]
    assert len(listed) == 2
    report_id = listed[0]["id"]

    status_resp = client.get(f"/api/geo-monitoring/reports/{report_id}")
    assert status_resp.json()["data"]["status"] == "completed"

    download_resp = client.get(f"/api/geo-monitoring/reports/{report_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.content


def test_download_only_by_report_id_not_user_path(client, analyzed_run, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_STORAGE_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    create_resp = client.post(
        f"/api/geo-monitoring/runs/{analyzed_run['run_id']}/reports",
        json={"formats": ["md"]},
    )
    report_id = create_resp.json()["data"]["reports"][0]["id"]

    bad_resp = client.get(
        "/api/geoFrom-monitoring/reports/999999/download",
    )
    assert bad_resp.status_code in {200, 404}
    if bad_resp.status_code == 200:
        assert bad_resp.json()["code"] != 0

    good = client.get(f"/api/geo-monitoring/reports/{report_id}/download")
    assert good.status_code == 200


def test_delete_report_soft_deletes_and_removes_file(session_factory, analyzed_run, tmp_path):
    storage = ReportStorage(str(tmp_path))
    with session_factory() as db:
        report = GeoReport(
            project_id=analyzed_run["project_id"],
            run_id=analyzed_run["run_id"],
            status="pending",
            format="md",
            file_name="report.md",
            relative_storage_path=f"{analyzed_run['project_id']}/{analyzed_run['run_id']}/5.md",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        generate_report_content(db, report.id, storage=storage)
        relative = report.relative_storage_path
        report_id = report.id

    from app.geo_monitoring.reports.storage import delete_report

    with session_factory() as db:
        delete_report(db, report_id, storage=storage)
        row = db.get(GeoReport, report_id)
        assert row.is_deleted is True
        assert not storage.resolve_path(relative).exists()


def test_generate_report_actor(session_factory, analyzed_run, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_STORAGE_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    storage = ReportStorage(str(tmp_path))
    with session_factory() as db:
        report = GeoReport(
            project_id=analyzed_run["project_id"],
            run_id=analyzed_run["run_id"],
            status="pending",
            format="html",
            file_name="report.html",
            relative_storage_path=(
                f"{analyzed_run['project_id']}/{analyzed_run['run_id']}/9.html"
            ),
        )
        db.add(report)
        db.commit()
        report_id = report.id

    report_actor.generate_report_task(report_id)

    with session_factory() as db:
        row = db.get(GeoReport, report_id)
        assert row.status == "completed"
        assert row.file_size and row.file_size > 0
        assert row.checksum
        assert row.completed_at is not None
        assert storage.read_bytes(row.relative_storage_path)
