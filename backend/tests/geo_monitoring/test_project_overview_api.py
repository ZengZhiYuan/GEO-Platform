"""项目概览、暂停恢复与删除检查 API 测试。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.geo_monitoring.models import (
    AIPlatform,
    Brand,
    BrandAlias,
    MonitorProject,
    MonitorRun,
    MonitorSchedule,
    Prompt,
    PromptSet,
)
from app.geo_monitoring.reports.storage import GeoReport
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS


def _seed_platforms(session_factory) -> None:
    with session_factory() as db:
        if not db.query(AIPlatform).count():
            db.add_all(AIPlatform(**platform) for platform in DEFAULT_PLATFORMS)
            db.commit()


def _seed_project_card(
    session_factory,
    *,
    project_name: str = "概览测试项目",
    platform_codes: list[str] | None = None,
    monitoring_paused: bool = False,
    run_no: str | None = None,
) -> dict:
    platform_codes = platform_codes or [
        "doubao",
        "molizhishu_doubao_web",
        "molizhishu_doubao_mobile",
        "qwen",
    ]
    with session_factory() as db:
        project = MonitorProject(
            project_name=project_name,
            status="active",
            monitoring_paused=monitoring_paused,
            default_platform_codes=platform_codes,
        )
        db.add(project)
        db.flush()

        target = Brand(
            project_id=project.id,
            brand_name="目标品牌",
            brand_type="target",
            status="active",
        )
        competitor = Brand(
            project_id=project.id,
            brand_name="竞品A",
            brand_type="competitor",
            status="active",
        )
        db.add_all([target, competitor])
        db.flush()
        db.add_all(
            [
                BrandAlias(
                    brand_id=target.id,
                    alias_name="品牌词1",
                    match_mode="contains",
                    enabled=True,
                ),
                BrandAlias(
                    brand_id=target.id,
                    alias_name="品牌词2",
                    match_mode="contains",
                    enabled=True,
                ),
            ]
        )

        prompt_set = PromptSet(
            project_id=project.id,
            set_name="激活集",
            version_no="v1",
            status="active",
            prompt_count=2,
        )
        db.add(prompt_set)
        db.flush()
        db.add_all(
            [
                Prompt(
                    prompt_set_id=prompt_set.id,
                    prompt_code="Q001",
                    prompt_text="问题1",
                ),
                Prompt(
                    prompt_set_id=prompt_set.id,
                    prompt_code="Q002",
                    prompt_text="问题2",
                ),
            ]
        )

        run = MonitorRun(
            run_no=run_no or f"RUN-OVERVIEW-{project.id}",
            project_id=project.id,
            prompt_set_id=prompt_set.id,
            prompt_set_version="v1",
            platform_codes=["doubao", "qwen"],
            status="completed",
            collection_status="completed",
            analysis_status="completed",
            total_tasks=2,
            expected_query_count=2,
            succeeded_tasks=2,
        )
        db.add(run)
        db.commit()
        return {
            "project_id": project.id,
            "run_id": run.id,
            "competitor_id": competitor.id,
            "prompt_set_id": prompt_set.id,
        }


def test_project_options_returns_lightweight_list(client, session_factory):
    _seed_project_card(session_factory, project_name="选项项目A")
    _seed_project_card(session_factory, project_name="选项项目B")

    response = client.get("/api/geo-monitoring/projects/options")
    body = response.json()

    assert body["code"] == 0
    items = body["data"]["items"]
    assert len(items) >= 2
    sample = items[0]
    assert set(sample) == {"id", "project_name", "status", "monitoring_paused"}
    assert isinstance(sample["monitoring_paused"], bool)


def test_project_overview_returns_card_summary(client, session_factory):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(session_factory)

    response = client.get("/api/geo-monitoring/projects/overview")
    body = response.json()

    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    card = next(
        item for item in body["data"]["items"] if item["id"] == seeded["project_id"]
    )
    assert card["project_name"] == "概览测试项目"
    assert card["target_brand_name"] == "目标品牌"
    assert card["brand_word_count"] == 2
    assert card["brand_words"] == ["品牌词1", "品牌词2"]
    assert card["competitor_count"] == 1
    assert card["competitors"] == [
        {"brand_id": seeded["competitor_id"], "brand_name": "竞品A"}
    ]
    assert card["question_count"] == 2
    assert card["endpoint_count"] == 4
    assert card["platform_count"] == 2
    assert card["monitoring_paused"] is False
    assert card["homepage_badges"] == [{"code": "monitoring", "label": "监测中"}]
    assert card["latest_run"]["run_id"] == seeded["run_id"]
    assert card["latest_run"]["status"] == "completed"
    assert card["last_updated_at"] is not None
    assert len(card["platform_endpoints"]) == 4
    endpoint_codes = {item["platform_code"] for item in card["platform_endpoints"]}
    assert endpoint_codes == {
        "doubao",
        "molizhishu_doubao_web",
        "molizhishu_doubao_mobile",
        "qwen",
    }
    sample_endpoint = next(
        item for item in card["platform_endpoints"] if item["platform_code"] == "doubao"
    )
    assert sample_endpoint["platform_name"] == "豆包"
    assert sample_endpoint["base_platform"] == "doubao"
    assert sample_endpoint["endpoint_type"] == "web"
    assert sample_endpoint["endpoint_label"]
    assert sample_endpoint["enabled"] is True


def test_project_overview_platform_endpoints_match_metadata(client, session_factory):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(
        session_factory,
        platform_codes=["molizhishu_doubao_web", "molizhishu_doubao_mobile"],
    )

    metadata = client.get("/api/geo-monitoring/platform-endpoints").json()["data"]
    metadata_by_code = {
        endpoint["platform_code"]: endpoint
        for group in metadata["groups"]
        for endpoint in group["endpoints"]
    }

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    for endpoint in card["platform_endpoints"]:
        expected = metadata_by_code[endpoint["platform_code"]]
        assert endpoint["platform_name"] == expected["platform_name"]
        assert endpoint["base_platform"] == expected["base_platform"]
        assert endpoint["endpoint_type"] == expected["endpoint_type"]
        assert endpoint["endpoint_label"] == expected["endpoint_label"]
        assert endpoint["logo_url"] == expected["logo_url"]
        assert endpoint["enabled"] == expected["enabled"]


def test_project_overview_homepage_badges_when_paused(client, session_factory):
    seeded = _seed_project_card(session_factory, monitoring_paused=True)

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    assert card["homepage_badges"] == [{"code": "paused", "label": "已暂停"}]


def test_project_overview_last_updated_at_prefers_run_completed_at(
    client, session_factory
):
    _seed_platforms(session_factory)
    completed_at = datetime(2026, 6, 26, 12, 0, tzinfo=UTC)
    seeded = _seed_project_card(session_factory)

    with session_factory() as db:
        run = db.get(MonitorRun, seeded["run_id"])
        run.completed_at = completed_at
        db.commit()

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    assert card["last_updated_at"].startswith("2026-06-26T12:00:00")


def test_project_overview_last_updated_at_falls_back_to_project_updated_at(
    client, session_factory
):
    response = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "无运行项目", "industry": "文旅"},
    )
    project_id = response.json()["data"]["id"]

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == project_id
    )

    assert card["latest_run"] is None
    assert card["last_updated_at"] == card["updated_at"]


def test_project_overview_last_updated_at_uses_latest_completed_at_not_latest_run_id(
    client, session_factory
):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(session_factory)
    earlier_completed = datetime(2026, 6, 26, 10, 0, tzinfo=UTC)
    later_completed = datetime(2026, 6, 26, 15, 0, tzinfo=UTC)

    with session_factory() as db:
        first_run = db.get(MonitorRun, seeded["run_id"])
        first_run.completed_at = earlier_completed
        second_run = MonitorRun(
            run_no=f"RUN-OVERVIEW-{seeded['project_id']}-2",
            project_id=seeded["project_id"],
            prompt_set_id=seeded["prompt_set_id"],
            prompt_set_version="v1",
            platform_codes=["doubao"],
            status="completed",
            collection_status="completed",
            analysis_status="completed",
            total_tasks=1,
            expected_query_count=1,
            succeeded_tasks=1,
            completed_at=later_completed,
        )
        db.add(second_run)
        db.commit()
        second_run_id = second_run.id

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    assert card["latest_run"]["run_id"] == second_run_id
    assert card["last_updated_at"].startswith("2026-06-26T15:00:00")


def test_project_overview_last_updated_at_uses_completed_run_when_latest_run_pending(
    client, session_factory
):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(session_factory)
    completed_at = datetime(2026, 6, 26, 11, 30, tzinfo=UTC)

    with session_factory() as db:
        first_run = db.get(MonitorRun, seeded["run_id"])
        first_run.completed_at = completed_at
        pending_run = MonitorRun(
            run_no=f"RUN-OVERVIEW-{seeded['project_id']}-pending",
            project_id=seeded["project_id"],
            prompt_set_id=seeded["prompt_set_id"],
            prompt_set_version="v1",
            platform_codes=["doubao"],
            status="pending",
            collection_status="pending",
            analysis_status="pending",
            total_tasks=1,
            expected_query_count=1,
            succeeded_tasks=0,
            completed_at=None,
        )
        db.add(pending_run)
        db.commit()
        pending_run_id = pending_run.id

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    assert card["latest_run"]["run_id"] == pending_run_id
    assert card["latest_run"]["completed_at"] is None
    assert card["last_updated_at"].startswith("2026-06-26T11:30:00")


def test_project_overview_competitor_count_excludes_disabled_competitors(
    client, session_factory
):
    seeded = _seed_project_card(session_factory)

    with session_factory() as db:
        db.add(
            Brand(
                project_id=seeded["project_id"],
                brand_name="已停用竞品",
                brand_type="competitor",
                status="disabled",
            )
        )
        db.commit()

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    assert card["competitor_count"] == 1
    assert card["competitors"] == [
        {"brand_id": seeded["competitor_id"], "brand_name": "竞品A"}
    ]


def test_project_overview_platform_count_dedupes_base_platform(client, session_factory):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(
        session_factory,
        platform_codes=["doubao", "molizhishu_doubao_web", "molizhishu_doubao_mobile"],
    )

    response = client.get("/api/geo-monitoring/projects/overview")
    card = next(
        item
        for item in response.json()["data"]["items"]
        if item["id"] == seeded["project_id"]
    )

    assert card["endpoint_count"] == 3
    assert card["platform_count"] == 1


def test_pause_and_resume_project(client, session_factory):
    seeded = _seed_project_card(session_factory, monitoring_paused=False)
    project_id = seeded["project_id"]

    pause = client.post(f"/api/geo-monitoring/projects/{project_id}/pause")
    assert pause.json()["code"] == 0
    assert pause.json()["data"]["monitoring_paused"] is True

    resume = client.post(f"/api/geo-monitoring/projects/{project_id}/resume")
    assert resume.json()["code"] == 0
    assert resume.json()["data"]["monitoring_paused"] is False


def test_paused_project_blocks_new_run(client, session_factory):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(session_factory)
    project_id = seeded["project_id"]

    pause = client.post(f"/api/geo-monitoring/projects/{project_id}/pause")
    assert pause.json()["code"] == 0

    create_run = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id},
    )
    body = create_run.json()
    assert body["code"] != 0
    assert "暂停" in body["message"]


def test_delete_check_reports_related_counts(client, session_factory):
    seeded = _seed_project_card(session_factory)
    project_id = seeded["project_id"]

    with session_factory() as db:
        db.add(
            MonitorSchedule(
                project_id=project_id,
                name="每日监测",
                cron_expr="0 9 * * *",
                enabled=True,
            )
        )
        db.add(
            GeoReport(
                project_id=project_id,
                run_id=seeded["run_id"],
                status="completed",
                format="pdf",
                file_name="report.pdf",
                relative_storage_path=f"reports/{project_id}/report.pdf",
            )
        )
        db.commit()

    response = client.get(f"/api/geo-monitoring/projects/{project_id}/delete-check")
    body = response.json()

    assert body["code"] == 0
    data = body["data"]
    assert data["project_id"] == project_id
    assert data["run_count"] == 1
    assert data["report_count"] == 1
    assert data["schedule_count"] == 1
    assert data["can_delete"] is False
    assert data["blocking_reasons"] == ["项目已有 1 次监测运行"]


def test_delete_check_schedule_only_project_can_still_delete(client, session_factory):
    response = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "仅有调度项目", "industry": "文旅"},
    )
    project_id = response.json()["data"]["id"]

    with session_factory() as db:
        db.add(
            MonitorSchedule(
                project_id=project_id,
                name="每日监测",
                cron_expr="0 9 * * *",
                enabled=True,
            )
        )
        db.commit()

    data = client.get(
        f"/api/geo-monitoring/projects/{project_id}/delete-check"
    ).json()["data"]

    assert data["run_count"] == 0
    assert data["schedule_count"] == 1
    assert data["can_delete"] is True
    assert data["blocking_reasons"] == []


def test_project_overview_question_count_excludes_disabled_prompts(
    client, session_factory
):
    _seed_platforms(session_factory)
    seeded = _seed_project_card(session_factory)
    project_id = seeded["project_id"]

    with session_factory() as db:
        prompt = (
            db.query(Prompt)
            .filter(Prompt.prompt_code == "Q002")
            .one()
        )
        prompt.enabled = False
        db.commit()

    card = next(
        item
        for item in client.get("/api/geo-monitoring/projects/overview").json()["data"]["items"]
        if item["id"] == project_id
    )
    assert card["question_count"] == 1


def test_project_options_matches_project_list_total(client, session_factory):
    _seed_project_card(session_factory, project_name="选项对齐A")
    _seed_project_card(session_factory, project_name="选项对齐B")

    options = client.get("/api/geo-monitoring/projects/options").json()["data"]["items"]
    listed = client.get(
        "/api/geo-monitoring/projects",
        params={"page": 1, "page_size": 100},
    ).json()["data"]

    assert len(options) == listed["total"]


def test_delete_check_allows_clean_project(client, session_factory):
    response = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "可删除项目", "industry": "文旅"},
    )
    project_id = response.json()["data"]["id"]

    check = client.get(f"/api/geo-monitoring/projects/{project_id}/delete-check")
    data = check.json()["data"]

    assert data["run_count"] == 0
    assert data["report_count"] == 0
    assert data["schedule_count"] == 0
    assert data["can_delete"] is True
    assert data["blocking_reasons"] == []
