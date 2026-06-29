"""采集域契约测试。"""

from app.geo_monitoring.models import AIPlatform, Answer, QueryTask
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.schemas import AnswerCreate
from app.geo_monitoring.services import answers as answer_service
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS


def _disabled_except(*enabled_codes: str) -> set[str]:
    enabled = set(enabled_codes)
    return {
        platform["platform_code"]
        for platform in DEFAULT_PLATFORMS
        if platform["platform_code"] not in enabled
    }


def _seed_platforms(session_factory, disabled: set[str] | None = None) -> None:
    disabled = disabled or set()
    with session_factory() as db:
        db.add_all(
            AIPlatform(
                **platform,
                enabled=platform["platform_code"] not in disabled,
            )
            for platform in DEFAULT_PLATFORMS
        )
        db.commit()


def _active_prompt_setup(client, project_id: int, prompt_count: int = 1) -> dict:
    prompt_set = client.post(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets",
        json={"set_name": "采集契约", "version_no": "v1"},
    ).json()["data"]
    prompt_ids = []
    for index in range(prompt_count):
        prompt = client.post(
            f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
            json={
                "prompt_code": f"prompt_{index + 1}",
                "prompt_text": f"问题 {index + 1}",
                "sort_order": index,
            },
        ).json()["data"]
        prompt_ids.append(prompt["id"])
    activated = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate"
    ).json()["data"]
    return {"prompt_set": activated, "prompt_ids": prompt_ids}


def test_create_run_returns_409_when_no_enabled_platforms(client, project_id):
    _active_prompt_setup(client, project_id)
    response = client.post(
        "/api/geo-monitoring/runs", json={"project_id": project_id}
    ).json()
    assert response["code"] == 40902


def test_create_run_returns_409_when_all_platforms_disabled(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS})
    response = client.post(
        "/api/geo-monitoring/runs", json={"project_id": project_id}
    ).json()
    assert response["code"] == 40902


def test_duplicate_answer_creation_is_idempotent(db):
    task = QueryTask(
        run_id=1,
        prompt_id=1,
        platform_code="qwen",
        idempotency_key="dup-key",
        status="pending",
    )
    db.add(task)
    db.flush()
    payload = AnswerCreate(
        task_id=task.id,
        platform_code="qwen",
        prompt_id=1,
        raw_text="第一次",
    )
    first = answer_service.create_answer(db, payload)
    second = answer_service.create_answer(
        db,
        payload.model_copy(update={"raw_text": "第二次"}),
    )
    assert first.id == second.id
    assert answer_repo.count_by_task_id(db, task.id) == 1


def test_delete_project_referenced_by_run_returns_409(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id)
    _seed_platforms(session_factory)
    run = client.post(
        "/api/geo-monitoring/runs", json={"project_id": project_id}
    ).json()["data"]
    assert run["prompt_set_id"] == setup["prompt_set"]["id"]
    response = client.delete(f"/api/geo-monitoring/projects/{project_id}").json()
    assert response["code"] == 40903


def test_invalid_pagination_returns_422(client, project_id):
    response = client.get(
        "/api/geo-monitoring/runs",
        params={"page": 0, "project_id": project_id},
    ).json()
    assert response["code"] == 422


def test_run_detail_includes_task_counters_and_progress(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id, prompt_count=2)
    _seed_platforms(session_factory, disabled=_disabled_except("doubao", "qwen"))
    run = client.post(
        "/api/geo-monitoring/runs", json={"project_id": project_id}
    ).json()["data"]
    detail = client.get(f"/api/geo-monitoring/runs/{run['id']}").json()["data"]
    assert detail["total_tasks"] == 4
    assert detail["expected_query_count"] == 4
    assert detail["progress_rate"] == "0.0000"
    assert "succeeded_tasks" in detail


def test_run_tasks_alias_matches_query_tasks(client, session_factory, project_id):
    _active_prompt_setup(client, project_id)
    _seed_platforms(session_factory, disabled=_disabled_except("doubao", "qwen"))
    run = client.post(
        "/api/geo-monitoring/runs", json={"project_id": project_id}
    ).json()["data"]
    query_tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/query-tasks"
    ).json()["data"]
    tasks = client.get(f"/api/geo-monitoring/runs/{run['id']}/tasks").json()["data"]
    assert query_tasks == tasks


def test_answer_detail_endpoint_returns_citations_and_brand_results(db, client):
    from app.geo_monitoring.models import AnswerBrandResult, AnswerCitation, MonitorProject, MonitorRun, Prompt, PromptSet

    project = MonitorProject(project_name="答案详情", status="active")
    db.add(project)
    db.flush()
    prompt_set = PromptSet(
        project_id=project.id,
        set_name="集",
        version_no="v1",
        status="active",
    )
    db.add(prompt_set)
    db.flush()
    prompt = Prompt(
        prompt_set_id=prompt_set.id,
        prompt_code="p1",
        prompt_text="问题",
    )
    db.add(prompt)
    db.flush()
    run = MonitorRun(
        run_no="RUN-TEST",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        platform_codes=["qwen"],
        total_tasks=1,
        expected_query_count=1,
    )
    db.add(run)
    db.flush()
    task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="qwen",
        idempotency_key="task-key",
        status="success",
    )
    db.add(task)
    db.flush()
    answer = Answer(
        task_id=task.id,
        platform_code="qwen",
        prompt_id=prompt.id,
        raw_text="回答",
    )
    db.add(answer)
    db.flush()
    db.add(
        AnswerCitation(
            answer_id=answer.id,
            citation_no=1,
            title="引用",
            url="https://example.com",
            domain="example.com",
        )
    )
    db.add(
        AnswerBrandResult(
            answer_id=answer.id,
            brand_id=1,
            is_mentioned=True,
            mention_count=1,
        )
    )
    db.commit()

    listed = client.get(f"/api/geo-monitoring/runs/{run.id}/answers").json()["data"]
    detail = client.get(f"/api/geo-monitoring/answers/{answer.id}").json()["data"]
    assert listed["total"] == 1
    assert detail["raw_text"] == "回答"
    assert len(detail["citations"]) == 1
    assert len(detail["brand_results"]) == 1
