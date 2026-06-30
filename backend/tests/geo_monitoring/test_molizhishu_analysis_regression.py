"""Task M12：模力指数入库数据在分析、Dashboard、竞品、信源与报告链路的回归测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import select

import app.geo_monitoring.reports.storage  # noqa: F401
import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerBrandResult,
    AnswerCitation,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.reports.pdf_renderer import render_pdf
from app.geo_monitoring.reports.renderer import build_report_context, render_html, render_markdown
from app.geo_monitoring.services.analysis import PlatformAnalysis, SourceStat
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS
from tests.geo_monitoring.analysis_support import patch_fake_llm_for_analyze
from tests.geo_monitoring.agents.test_graph import FakeLLMClient, _seed_run

_MOLIZHISHU_PLATFORM_CODE = "molizhishu_deepseek_web"
_MOLIZHISHU_PLATFORM_META = MOLIZHISHU_PLATFORM_MAPPINGS[_MOLIZHISHU_PLATFORM_CODE]
_SECRET_TOKEN = "secret-molizhishu-token-xyz"


def _molizhishu_raw_response(*, answer_text: str) -> dict[str, Any]:
    return {
        "Authorization": f"Bearer {_SECRET_TOKEN}",
        "proxyIp": "10.0.0.1",
        "submit": {"data": {"taskId": "task-mz-regression"}},
        "result": {
            "success": True,
            "code": 200,
            "data": {
                "status": "completed",
                "answerContent": answer_text,
                "citationList": [
                    {
                        "title": "官方介绍",
                        "url": "https://example.com/intro",
                        "siteName": "Example",
                    },
                    {
                        "title": "行业报道",
                        "url": "https://news.example.com/story",
                        "siteName": "News Example",
                    },
                ],
                "reasoningProcess": {"content": "模力指数思考过程。"},
                "recommendedQuestions": ["相关问题 A"],
            },
        },
    }


def _seed_molizhishu_run(
    db,
    *,
    with_valid_answers: bool = True,
) -> dict[str, Any]:
    project = MonitorProject(
        project_name="模力指数回归测试",
        status="active",
        official_domain="example.com",
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
        brand_name="竞品B",
        brand_type="competitor",
        status="active",
    )
    db.add_all([target, competitor])
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="模力指数集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="mz1",
        prompt_text="哪个文旅品牌更值得推荐？",
    )
    db.add(prompt)
    db.flush()

    db.add(
        AIPlatform(
            platform_code=_MOLIZHISHU_PLATFORM_CODE,
            platform_name=_MOLIZHISHU_PLATFORM_META["platform_name"],
            model_name=f"molizhishu:{_MOLIZHISHU_PLATFORM_META['molizhishu_platform']}",
            adapter_type="molizhishu",
            enabled=True,
            search_enabled=True,
            citation_supported=True,
            extra_config={
                "molizhishu_platform": _MOLIZHISHU_PLATFORM_META["molizhishu_platform"],
                "base_platform": _MOLIZHISHU_PLATFORM_META["base_platform"],
                "endpoint_type": _MOLIZHISHU_PLATFORM_META["endpoint_type"],
                "default_mode": _MOLIZHISHU_PLATFORM_META["default_mode"],
                "supported_modes": list(_MOLIZHISHU_PLATFORM_META["supported_modes"]),
            },
        )
    )

    run = MonitorRun(
        run_no="RUN-MZ-REGRESSION",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        collection_source="molizhishu",
        platform_codes=[_MOLIZHISHU_PLATFORM_CODE],
        provider_mode_by_platform={
            _MOLIZHISHU_PLATFORM_CODE: _MOLIZHISHU_PLATFORM_META["default_mode"],
        },
        status="completed",
        collection_status="completed",
        analysis_status="pending",
        total_tasks=1,
        expected_query_count=1,
        succeeded_tasks=1 if with_valid_answers else 0,
        valid_answer_count=1 if with_valid_answers else 0,
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code=_MOLIZHISHU_PLATFORM_CODE,
        idempotency_key=f"mz-regression-{run.id}",
        status="success" if with_valid_answers else "failed",
        provider_task_id="task-mz-regression",
        provider_subtask_id="subtask-mz-regression",
        completed_at=now if with_valid_answers else None,
        finished_at=now if with_valid_answers else None,
    )
    db.add(task)
    db.flush()

    if with_valid_answers:
        answer_text = "模力指数推荐目标品牌，优于竞品B。"
        answer = Answer(
            task_id=task.id,
            platform_code=_MOLIZHISHU_PLATFORM_CODE,
            prompt_id=prompt.id,
            raw_text=answer_text,
            normalized_text=answer_text,
            model_name=f"molizhishu:{_MOLIZHISHU_PLATFORM_META['molizhishu_platform']}",
            raw_response_json=_molizhishu_raw_response(answer_text=answer_text),
            collected_at=now,
        )
        db.add(answer)
        db.flush()
        db.add_all(
            [
                AnswerBrandResult(
                    answer_id=answer.id,
                    brand_id=target.id,
                    is_mentioned=True,
                    mention_count=1,
                    first_position=0,
                ),
                AnswerBrandResult(
                    answer_id=answer.id,
                    brand_id=competitor.id,
                    is_mentioned=True,
                    mention_count=1,
                    first_position=10,
                ),
                AnswerCitation(
                    answer_id=answer.id,
                    citation_no=1,
                    title="官方介绍",
                    url="https://example.com/intro",
                    domain="example.com",
                    source_type="official",
                ),
                AnswerCitation(
                    answer_id=answer.id,
                    citation_no=2,
                    title="行业报道",
                    url="https://news.example.com/story",
                    domain="news.example.com",
                    source_type="media",
                ),
            ]
        )

    db.commit()
    return {
        "run_id": run.id,
        "project_id": project.id,
        "target_brand_id": target.id,
        "platform_code": _MOLIZHISHU_PLATFORM_CODE,
    }


@pytest.fixture
def molizhishu_analyzed_run(client, session_factory, monkeypatch):
    llm = patch_fake_llm_for_analyze(monkeypatch)
    with session_factory() as db:
        seeded = _seed_molizhishu_run(db)
    response = client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["queued"] is True
    assert data["analysis_status"] == "pending"
    assert data["run_analysis_status"] == "completed"
    return seeded


def _analysis_platform_keys(data: dict[str, Any]) -> set[str]:
    platform = data["platforms"][0]
    return set(platform.keys())


def _dashboard_platform_keys(data: dict[str, Any]) -> set[str]:
    platform = data["platforms"][0]
    return set(platform.keys())


def test_molizhishu_run_triggers_analysis_and_persists_platform_analysis(
    client, molizhishu_analyzed_run, session_factory
):
    run_id = molizhishu_analyzed_run["run_id"]
    response = client.get(f"/api/geo-monitoring/runs/{run_id}/analysis")
    body = response.json()
    assert body["code"] == 0
    platform = body["data"]["platforms"][0]
    assert platform["platform_code"] == _MOLIZHISHU_PLATFORM_CODE
    assert platform["valid_answer_count"] == 1
    assert platform["brand_mention_rate"] is not None
    assert platform["brand_top1_mention_rate"] == "1.0000"

    with session_factory() as db:
        row = db.execute(
            select(PlatformAnalysis).where(
                PlatformAnalysis.run_id == run_id,
                PlatformAnalysis.platform_code == _MOLIZHISHU_PLATFORM_CODE,
            )
        ).scalar_one()
        assert row.status == "completed"


def test_molizhishu_source_analysis_counts_domains_and_types(
    client, molizhishu_analyzed_run, session_factory
):
    project_id = molizhishu_analyzed_run["project_id"]
    run_id = molizhishu_analyzed_run["run_id"]

    with session_factory() as db:
        source_stats = list(
            db.execute(select(SourceStat).where(SourceStat.run_id == run_id))
            .scalars()
            .all()
        )
        assert source_stats

    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_citation_data"] is True
    assert data["kpi"]["citation_count"] >= 2
    assert data["kpi"]["site_count"] >= 2

    column_codes = [item["platform_code"] for item in data["platform_columns"]]
    assert column_codes == [_MOLIZHISHU_PLATFORM_CODE]

    domains = {item["domain"] for item in data["sites"]["items"]}
    assert "example.com" in domains
    assert "news.example.com" in domains

    type_codes = {item["source_type"] for item in data["type_distribution"]}
    assert type_codes


def test_molizhishu_competitor_analysis_boards_and_kpis(
    client, molizhishu_analyzed_run
):
    project_id = molizhishu_analyzed_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/competitor-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_analysis_data"] is True
    assert data["target_brand"]["brand_name"] == "目标品牌"
    assert data["kpis"]["mention_rate"] is not None
    assert data["kpis"]["top1_rate"] == "1.0000"

    for board_name in ("mention_rate", "average_rank", "mention_count"):
        board = data["boards"][board_name]
        assert board
        target_rows = [row for row in board if row["is_target"]]
        assert len(target_rows) == 1


def test_molizhishu_dashboard_uses_platform_catalog_name(
    client, molizhishu_analyzed_run
):
    project_id = molizhishu_analyzed_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/dashboard"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["latest_run"]["platform_codes"] == [_MOLIZHISHU_PLATFORM_CODE]

    platform = data["platforms"][0]
    assert platform["platform_code"] == _MOLIZHISHU_PLATFORM_CODE
    assert platform["platform_name"] == _MOLIZHISHU_PLATFORM_META["platform_name"]
    assert platform["analysis"]["valid_answer_count"] == 1
    assert platform["analysis"]["brand_mention_rate"] is not None


def test_molizhishu_report_renders_without_token_leak(
    session_factory, molizhishu_analyzed_run
):
    run_id = molizhishu_analyzed_run["run_id"]
    with session_factory() as db:
        context = build_report_context(db, run_id)

    assert context["platform_scoreboard"][0]["platform_code"] == _MOLIZHISHU_PLATFORM_CODE
    assert context["top_source_cards"]
    assert context["source_type_distribution"]

    markdown = render_markdown(context)
    html = render_html(context)
    pdf = render_pdf(context)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100

    for content in (markdown, html, str(context)):
        assert _SECRET_TOKEN not in content
        assert "Authorization" not in content
        assert "proxyIp" not in content

    for needle in (_SECRET_TOKEN, "Authorization", "proxyIp"):
        assert needle.encode("utf-8") not in pdf

    assert _MOLIZHISHU_PLATFORM_META["platform_name"] in markdown or _MOLIZHISHU_PLATFORM_CODE in markdown
    assert "Top1(首位)提及率" in markdown
    assert "example.com" in markdown


def test_molizhishu_and_official_run_report_field_structure_match(
    client, session_factory, monkeypatch
):
    llm = patch_fake_llm_for_analyze(monkeypatch)

    with session_factory() as db:
        official = _seed_run(db, platforms=("qwen",))
        molizhishu = _seed_molizhishu_run(db)

    for run_id in (official["run_id"], molizhishu["run_id"]):
        response = client.post(f"/api/geo-monitoring/runs/{run_id}/analyze")
        data = response.json()["data"]
        assert data["queued"] is True
        assert data["analysis_status"] == "pending"
        assert data["run_analysis_status"] == "completed"

    official_analysis = client.get(
        f"/api/geo-monitoring/runs/{official['run_id']}/analysis"
    ).json()["data"]
    molizhishu_analysis = client.get(
        f"/api/geo-monitoring/runs/{molizhishu['run_id']}/analysis"
    ).json()["data"]

    assert _analysis_platform_keys(official_analysis) == _analysis_platform_keys(
        molizhishu_analysis
    )

    official_dashboard = client.get(
        f"/api/geo-monitoring/projects/{official['project_id']}/dashboard"
    ).json()["data"]
    molizhishu_dashboard = client.get(
        f"/api/geo-monitoring/projects/{molizhishu['project_id']}/dashboard"
    ).json()["data"]

    assert _dashboard_platform_keys(official_dashboard) == _dashboard_platform_keys(
        molizhishu_dashboard
    )

    with session_factory() as db:
        official_context = build_report_context(db, official["run_id"])
        molizhishu_context = build_report_context(db, molizhishu["run_id"])

    assert set(official_context.keys()) == set(molizhishu_context.keys())
    assert set(official_context["platform_scoreboard"][0].keys()) == set(
        molizhishu_context["platform_scoreboard"][0].keys()
    )
