"""Task P2-3：高频评价标签聚类接口测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.geo_monitoring.models import (
    AIPlatform,
    Answer,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.geo_monitoring.schemas import EvaluationTagsOut


def _seed_prompt_with_tagged_answers(db) -> dict[str, Any]:
    project = MonitorProject(
        project_name="评价标签测试",
        industry="文旅演艺",
        status="active",
    )
    db.add(project)
    db.flush()

    prompt_set = PromptSet(
        project_id=project.id,
        set_name="标签集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()

    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="q1",
        prompt_text="宋城演艺怎么样？",
        prompt_type="brand_sentiment",
    )
    db.add(prompt)
    db.flush()

    for code in ("qwen", "deepseek"):
        db.add(
            AIPlatform(
                platform_code=code,
                platform_name=code,
                model_name=f"{code}-model",
                enabled=True,
            )
        )

    run = MonitorRun(
        run_no="RUN-TAGS",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=["qwen", "deepseek"],
        status="completed",
        collection_status="completed",
        analysis_status="completed",
        total_tasks=2,
        expected_query_count=2,
        succeeded_tasks=2,
        valid_answer_count=2,
    )
    db.add(run)
    db.flush()

    now = datetime.now(timezone.utc)
    answer_texts = (
        "宋城演艺演出非常精彩，舞台视觉效果震撼，票价性价比也不错。",
        "交通很方便，演出质量高，适合全家一起观看，沉浸体验很好。",
    )
    for index, (platform_code, text) in enumerate(
        zip(("qwen", "deepseek"), answer_texts, strict=True)
    ):
        task = QueryTask(
            run_id=run.id,
            prompt_id=prompt.id,
            platform_code=platform_code,
            idempotency_key=f"tags-{run.id}-{index}",
            status="success",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()
        db.add(
            Answer(
                task_id=task.id,
                platform_code=platform_code,
                prompt_id=prompt.id,
                raw_text=text,
                normalized_text=text,
                model_name=f"{platform_code}-model",
                collected_at=now,
            )
        )
    db.commit()
    return {"project_id": project.id, "prompt_id": prompt.id, "run_id": run.id}


def test_evaluation_tags_clusters_rule_based_tags(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    response = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
    )
    payload = response.json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["run_id"] == seeded["run_id"]
    assert data["prompt_id"] == seeded["prompt_id"]
    assert data["cluster_method"] == "rule"
    assert data["answer_count"] == 2
    tags = {item["tag"]: item for item in data["items"]}
    assert "演出质量" in tags
    assert "性价比" in tags
    assert "交通便利" in tags
    assert tags["演出质量"]["count"] >= 2
    assert tags["演出质量"]["share_rate"] is not None


def test_evaluation_tags_respects_limit(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"limit": 2},
    ).json()
    assert payload["code"] == 0, payload
    assert len(payload["data"]["items"]) <= 2


def test_evaluation_tags_unknown_prompt_returns_404(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        "conversation-questions/999999/evaluation-tags",
    ).json()
    assert payload["code"] == 40400


def test_evaluation_tags_platform_codes_filter(client, session_factory):
    seeded = _seed_prompt_with_tagged_answers(session_factory())
    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"platform_codes": ["qwen"]},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["answer_count"] == 1
    tags = {item["tag"] for item in data["items"]}
    assert "演出质量" in tags
    assert "性价比" in tags
    assert "交通便利" not in tags
    EvaluationTagsOut.model_validate(data)


def test_evaluation_tags_run_id_filter(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        older_run = db.get(MonitorRun, seeded["run_id"])
        older_run.status = "completed"
        older_run.analysis_status = "completed"
        older_run.completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        newer_run = MonitorRun(
            run_no="RUN-TAGS-NEW",
            project_id=seeded["project_id"],
            prompt_set_id=older_run.prompt_set_id,
            prompt_set_version="v1",
            platform_codes=["qwen"],
            status="completed",
            collection_status="completed",
            analysis_status="completed",
            total_tasks=1,
            expected_query_count=1,
            succeeded_tasks=1,
            valid_answer_count=1,
            completed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        db.add(newer_run)
        db.flush()
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        task = QueryTask(
            run_id=newer_run.id,
            prompt_id=seeded["prompt_id"],
            platform_code="qwen",
            idempotency_key=f"tags-new-{newer_run.id}",
            status="success",
            completed_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()
        db.add(
            Answer(
                task_id=task.id,
                platform_code="qwen",
                prompt_id=seeded["prompt_id"],
                raw_text="交通便利，停车方便。",
                normalized_text="交通便利，停车方便。",
                model_name="qwen-model",
                collected_at=now,
            )
        )
        db.commit()
        newer_run_id = newer_run.id

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"run_id": newer_run_id},
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["run_id"] == newer_run_id
    assert data["answer_count"] == 1
    assert {item["tag"] for item in data["items"]} == {"交通便利"}


def test_evaluation_tags_run_id_belongs_to_other_project(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        other_project = MonitorProject(
            project_name="其他项目",
            status="active",
        )
        db.add(other_project)
        db.commit()

    payload = client.get(
        f"/api/geo-monitoring/projects/{other_project.id}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={"run_id": seeded["run_id"]},
    ).json()
    assert payload["code"] == 40400


def test_evaluation_tags_time_range_filter(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        answers = db.query(Answer).filter(Answer.prompt_id == seeded["prompt_id"]).all()
        by_platform = {answer.platform_code: answer for answer in answers}
        early_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        late_time = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
        by_platform["qwen"].collected_at = early_time
        by_platform["deepseek"].collected_at = late_time
        db.commit()

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
        params={
            "start_at": early_time.isoformat(),
            "end_at": (early_time + timedelta(hours=1)).isoformat(),
        },
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["answer_count"] == 1
    assert "交通便利" not in {item["tag"] for item in data["items"]}


def test_evaluation_tags_no_matching_tags_returns_empty_items(client, session_factory):
    with session_factory() as db:
        seeded = _seed_prompt_with_tagged_answers(db)
        for answer in db.query(Answer).filter(Answer.prompt_id == seeded["prompt_id"]):
            answer.raw_text = "没有任何评价关键词的普通回复。"
            answer.normalized_text = answer.raw_text
        db.commit()

    payload = client.get(
        f"/api/geo-monitoring/projects/{seeded['project_id']}/"
        f"conversation-questions/{seeded['prompt_id']}/evaluation-tags",
    ).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["answer_count"] == 2
    assert data["items"] == []
    assert data["total"] == 0

