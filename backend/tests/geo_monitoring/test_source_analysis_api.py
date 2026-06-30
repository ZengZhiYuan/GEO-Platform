"""Task P0-4：信源引用分析页面级接口测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

import app.geo_monitoring.services.analysis as analysis_module  # noqa: F401
from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    AnswerCitation,
    Brand,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.services.analysis import SourceStat
from tests.geo_monitoring.analysis_support import patch_fake_llm_for_analyze
from tests.geo_monitoring.agents.test_graph import FakeLLMClient


def _seed_source_analysis_run(
    db,
    *,
    platforms: tuple[str, ...] = ("qwen", "deepseek"),
    with_answer_citations: bool = True,
    with_source_stats: bool = True,
) -> dict[str, Any]:
    project = MonitorProject(
        project_name="信源分析测试",
        status="active",
        official_domain="example.com",
    )
    db.add(project)
    db.flush()

    db.add(
        Brand(
            project_id=project.id,
            brand_name="目标品牌",
            brand_type="target",
            status="active",
        )
    )
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="信源集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()

    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q1",
        prompt_text="哪个文旅品牌更值得推荐？",
        prompt_type="brand_recommendation",
    )
    db.add(prompt)
    db.flush()

    for code in platforms:
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )

    run = MonitorRun(
        run_no="RUN-SRC-1",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=list(platforms),
        status="completed",
        collection_status="completed",
        analysis_status="completed",
        total_tasks=len(platforms),
        expected_query_count=len(platforms),
        succeeded_tasks=len(platforms),
        valid_answer_count=len(platforms),
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    for platform_code in platforms:
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code=platform_code,
            idempotency_key=f"src-{run.id}-{platform_code}",
            status="success",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()

        text = f"{platform_code} 推荐目标品牌。"
        answer = Answer(
            task_id=task.id,
            platform_code=platform_code,
            prompt_id=prompt.id,
            raw_text=text,
            normalized_text=text,
            model_name=f"{platform_code}-model",
            collected_at=now,
        )
        db.add(answer)
        db.flush()

        if with_answer_citations and platform_code == "qwen":
            db.add(
                AnswerCitation(
                    answer_id=answer.id,
                    citation_no=1,
                    title="官方介绍",
                    url="https://example.com/intro",
                    domain="example.com",
                    source_type="official",
                )
            )
            db.add(
                AnswerCitation(
                    answer_id=answer.id,
                    citation_no=2,
                    title="行业报道",
                    url="https://news.example.com/story",
                    domain="news.example.com",
                    source_type="media",
                )
            )

    if with_source_stats and with_answer_citations:
        db.add_all(
            [
                SourceStat(
                    run_id=run.id,
                    platform_code="qwen",
                    domain="example.com",
                    source_name="Example",
                    source_type="official",
                    citation_count=2,
                    brand_related_count=1,
                    share_rate="0.6667",
                    rank_no=1,
                ),
                SourceStat(
                    run_id=run.id,
                    platform_code="qwen",
                    domain="news.example.com",
                    source_name="News Example",
                    source_type="media",
                    citation_count=1,
                    brand_related_count=1,
                    share_rate="0.3333",
                    rank_no=2,
                ),
                SourceStat(
                    run_id=run.id,
                    platform_code="deepseek",
                    domain="blog.example.com",
                    source_name="Blog Example",
                    source_type="social",
                    citation_count=4,
                    brand_related_count=1,
                    share_rate="1.0000",
                    rank_no=1,
                ),
            ]
        )

    db.commit()
    return {
        "project_id": project.id,
        "run_id": run.id,
        "platforms": platforms,
    }


@pytest.fixture
def source_analysis_run(client, session_factory):
    with session_factory() as db:
        return _seed_source_analysis_run(db)


@pytest.fixture
def analyzed_source_run(client, session_factory, monkeypatch):
    llm = patch_fake_llm_for_analyze(monkeypatch)
    with session_factory() as db:
        seeded = _seed_source_analysis_run(db, with_source_stats=False)
    response = client.post(f"/api/geo-monitoring/runs/{seeded['run_id']}/analyze")
    assert response.json()["code"] == 0
    return seeded


def test_source_analysis_empty_when_no_citation_data(client, session_factory):
    with session_factory() as db:
        seeded = _seed_source_analysis_run(
            db,
            with_answer_citations=False,
            with_source_stats=False,
        )

    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/source-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["run_id"] == seeded["run_id"]
    assert data["has_citation_data"] is False
    assert data["kpi"]["citation_count"] == 0
    assert data["kpi"]["site_count"] == 0
    assert data["kpi"]["article_count"] == 0
    assert data["kpi"]["citation_rate"] is None
    assert data["type_distribution"] == []
    assert data["sites"]["items"] == []
    assert data["sites"]["total"] == 0


def test_source_analysis_returns_platform_matrix_columns(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_citation_data"] is True
    assert data["kpi"]["citation_count"] == 7
    assert data["kpi"]["site_count"] == 3
    assert data["kpi"]["article_count"] == 2

    column_codes = [item["platform_code"] for item in data["platform_columns"]]
    assert column_codes == ["qwen", "deepseek"]

    qwen_column = next(
        item for item in data["platform_columns"] if item["platform_code"] == "qwen"
    )
    deepseek_column = next(
        item for item in data["platform_columns"] if item["platform_code"] == "deepseek"
    )
    assert qwen_column["has_citation_data"] is True
    assert deepseek_column["has_citation_data"] is True

    sites = data["sites"]["items"]
    assert data["sites"]["total"] == 3
    blog_row = next(item for item in sites if item["domain"] == "blog.example.com")
    assert blog_row["link_count"] == 4
    assert len(blog_row["platform_values"]) == 2
    blog_deepseek = next(
        item for item in blog_row["platform_values"] if item["platform_code"] == "deepseek"
    )
    assert blog_deepseek["link_count"] == 4
    assert blog_deepseek["has_citation_data"] is True


def test_source_analysis_source_type_filter(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"source_type": "official_site"},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["kpi"]["citation_count"] == 2
    assert data["kpi"]["site_count"] == 1
    assert data["sites"]["total"] == 1
    assert data["sites"]["items"][0]["domain"] == "example.com"
    assert data["type_distribution"][0]["source_type"] == "official_site"


def test_source_analysis_keyword_filter(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"keyword": "news"},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["kpi"]["site_count"] == 1
    assert data["sites"]["items"][0]["domain"] == "news.example.com"


def test_source_analysis_metric_switch(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    links_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"metric": "links"},
    )
    rate_response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"metric": "rate"},
    )
    links_data = links_response.json()["data"]
    rate_data = rate_response.json()["data"]
    assert links_data["metric"] == "links"
    assert rate_data["metric"] == "rate"

    top_site = links_data["sites"]["items"][0]
    assert top_site["display_value"] == str(top_site["link_count"])
    rate_top_site = next(
        item for item in rate_data["sites"]["items"] if item["domain"] == top_site["domain"]
    )
    assert rate_top_site["display_value"] == rate_top_site["citation_rate"]


def test_source_analysis_platform_codes_filter(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"platform_codes": ["qwen"]},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["kpi"]["citation_count"] == 3
    assert data["kpi"]["site_count"] == 2
    assert [item["platform_code"] for item in data["platform_columns"]] == ["qwen"]
    assert all(
        len(item["platform_values"]) == 1 for item in data["sites"]["items"]
    )


def test_source_analysis_populates_from_analyze(client, analyzed_source_run):
    project_id = analyzed_source_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis"
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_citation_data"] is True
    assert data["kpi"]["citation_count"] >= 1


def test_source_analysis_time_range_excludes_all_citations(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    future_start = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"start_at": future_start},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["has_citation_data"] is False
    assert data["kpi"]["citation_count"] == 0
    assert data["kpi"]["site_count"] == 0
    assert data["type_distribution"] == []
    assert data["sites"]["items"] == []
    assert data["sites"]["total"] == 0


def test_source_analysis_same_domain_different_source_name(client, session_factory):
    with session_factory() as db:
        seeded = _seed_source_analysis_run(db)
        blog_stat = (
            db.query(SourceStat)
            .filter(
                SourceStat.run_id == seeded["run_id"],
                SourceStat.domain == "blog.example.com",
            )
            .one()
        )
        blog_stat.domain = "example.com"
        blog_stat.source_name = "Example Mirror"
        blog_stat.source_type = "official"
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/source-analysis",
        params={"page_size": 100},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    example_rows = [
        item for item in data["sites"]["items"] if item["domain"] == "example.com"
    ]
    assert len(example_rows) == 2
    source_names = {item["source_name"] for item in example_rows}
    assert source_names == {"Example", "Example Mirror"}


def test_source_analysis_run_id_belongs_to_other_project(client, session_factory):
    with session_factory() as db:
        seeded_a = _seed_source_analysis_run(db)
        project_b = MonitorProject(
            project_name="其他项目",
            status="active",
            official_domain="other.com",
        )
        db.add(project_b)
        db.commit()

    response = client.get(
        f"/api/geo-monitoring/projects/{project_b.id}/source-analysis",
        params={"run_id": seeded_a["run_id"]},
    )
    body = response.json()
    assert body["code"] == 40400


def test_source_analysis_pagination(client, source_analysis_run):
    project_id = source_analysis_run["project_id"]
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/source-analysis",
        params={"page": 2, "page_size": 2},
    )
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["sites"]["total"] == 3
    assert data["sites"]["page"] == 2
    assert data["sites"]["page_size"] == 2
    assert len(data["sites"]["items"]) == 1
