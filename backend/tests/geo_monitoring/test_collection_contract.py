"""采集域契约测试。"""

from __future__ import annotations

from app.core.config import Settings
from app.geo_monitoring.adapters.base import PlatformAnswer
from app.geo_monitoring.adapters.errors import AdapterError, ErrorCategory
from app.geo_monitoring.adapters.key_pool import ApiKeyCredential, CredentialKeyPool
from app.geo_monitoring.adapters.registry import AdapterRegistry
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
from app.geo_monitoring.repositories import answers as answer_repo
from app.geo_monitoring.schemas import AnswerCreate
from app.geo_monitoring.services import answers as answer_service
from app.geo_monitoring.services import collection as collection_service
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
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
    ).json()
    assert response["code"] == 40902


def test_create_run_returns_409_when_all_platforms_disabled(
    client, session_factory, project_id
):
    _active_prompt_setup(client, project_id)
    _seed_platforms(session_factory, disabled={p["platform_code"] for p in DEFAULT_PLATFORMS})
    response = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
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
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
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
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
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
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "collection_source": "official"},
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


def _make_collection_runtime(session_factory, tmp_path):
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://test-redis.invalid:6379/15",
        DRAMATIQ_BROKER="stub",
        NACOS_ENABLED=False,
        REPORT_STORAGE_DIR=str(tmp_path),
    )
    registry = AdapterRegistry()
    key_pool = CredentialKeyPool(None)
    return collection_service.CollectionRuntime(
        session_factory=session_factory,
        settings=settings,
        adapter_registry=registry,
        key_pool=key_pool,
    )


def _seed_molizhishu_persist_graph(db) -> dict:
    project = MonitorProject(project_name="模力指数入库", status="active")
    db.add(project)
    db.flush()
    target = Brand(
        project_id=project.id,
        brand_name="目标品牌",
        brand_type="target",
        status="active",
    )
    db.add(target)
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
        prompt_text="哪个品牌更好？",
    )
    db.add(prompt)
    db.flush()
    db.add(
        AIPlatform(
            platform_code="molizhishu_doubao_web",
            platform_name="豆包 Web 端",
            model_name="molizhishu:doubao",
            adapter_type="molizhishu",
            extra_config={"molizhishu_platform": "doubao"},
            enabled=True,
        )
    )
    run = MonitorRun(
        run_no="RUN-M8",
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version="v1",
        collection_source="molizhishu",
        platform_codes=["molizhishu_doubao_web"],
        total_tasks=1,
        expected_query_count=1,
    )
    db.add(run)
    db.flush()
    task = QueryTask(
        run_id=run.id,
        prompt_id=prompt.id,
        platform_code="molizhishu_doubao_web",
        idempotency_key="molizhishu-persist-1",
        status="running",
        request_json={
            "molizhishu_task_id": "task-mlz-1",
            "molizhishu_subtask_id": "sub-1",
            "molizhishu_platform": "doubao",
            "molizhishu_mode": "search",
        },
    )
    db.add(task)
    db.commit()
    return {
        "project_id": project.id,
        "target_brand_id": target.id,
        "task_id": task.id,
        "run_id": run.id,
        "prompt_id": prompt.id,
    }


def _molizhishu_platform_answer(
    *,
    text: str = "普通回答，不含任何品牌提及。",
    citations: list[dict] | None = None,
    result_data: dict | None = None,
) -> PlatformAnswer:
    result_data = result_data or {
        "success": True,
        "code": 200,
        "data": {
            "status": "completed",
            "answerContent": text,
            "citationList": citations or [],
        },
    }
    return PlatformAnswer(
        text=text,
        citations=citations or [],
        model="molizhishu:doubao",
        usage={},
        latency_ms=100,
        provider_request_id="sub-1",
        raw_response={"submit": {"data": {"taskId": "task-mlz-1"}}, "result": result_data},
    )


def _persist_molizhishu_answer(session_factory, tmp_path, seeded: dict, platform_answer: PlatformAnswer):
    runtime = _make_collection_runtime(session_factory, tmp_path)
    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        snapshot = collection_service.TaskSnapshot(
            task_id=task.id,
            run_id=task.run_id,
            prompt_id=task.prompt_id,
            platform_code=task.platform_code,
            idempotency_key=task.idempotency_key,
            prompt_text="哪个品牌更好？",
            model_name="molizhishu:doubao",
            project_id=seeded["project_id"],
            collection_source="molizhishu",
            provider_mode="search",
            provider_screenshot=0,
            region_code=None,
            aidso_thinking_enabled=True,
            request_json=task.request_json,
            reclaim=False,
        )
    collection_service._persist_success(runtime, snapshot, platform_answer)


def test_molizhishu_success_persists_citation_list(session_factory, tmp_path):
    citations = [
        {
            "url": "https://example.com/a",
            "title": "引用标题",
            "quoted_text": "摘要",
            "source_type": "web",
        }
    ]
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
    _persist_molizhishu_answer(
        session_factory,
        tmp_path,
        seeded,
        _molizhishu_platform_answer(citations=citations),
    )
    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        rows = db.execute(
            AnswerCitation.__table__.select().where(AnswerCitation.answer_id == answer.id)
        ).mappings().all()
        assert len(rows) == 1
        assert rows[0]["title"] == "引用标题"
        assert rows[0]["quoted_text"] == "摘要"


def test_molizhishu_success_persists_reference_list_as_citations(session_factory, tmp_path):
    citations = [
        {
            "url": "https://example.com/ref",
            "title": "参考标题",
            "quoted_text": "参考摘要",
            "source_type": "web",
        }
    ]
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
    _persist_molizhishu_answer(
        session_factory,
        tmp_path,
        seeded,
        _molizhishu_platform_answer(citations=citations),
    )
    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        row = db.execute(
            AnswerCitation.__table__.select().where(AnswerCitation.answer_id == answer.id)
        ).mappings().one()
        assert row["title"] == "参考标题"
        assert row["quoted_text"] == "参考摘要"


def test_molizhishu_success_without_citations_still_persists_answer(session_factory, tmp_path):
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
    _persist_molizhishu_answer(
        session_factory,
        tmp_path,
        seeded,
        _molizhishu_platform_answer(text="无引用回答"),
    )
    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        assert answer.raw_text == "无引用回答"
        citations = db.execute(
            AnswerCitation.__table__.select().where(AnswerCitation.answer_id == answer.id)
        ).mappings().all()
        assert citations == []


def test_molizhishu_provider_brand_fields_do_not_override_local_brand_metrics(
    session_factory, tmp_path
):
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
    _persist_molizhishu_answer(
        session_factory,
        tmp_path,
        seeded,
        _molizhishu_platform_answer(
            result_data={
                "success": True,
                "code": 200,
                "data": {
                    "status": "completed",
                    "answerContent": "普通回答，不含任何品牌提及。",
                    "mentionPosition": 1,
                    "mentionContext": "provider context",
                    "sentiment": "positive",
                    "competitorRankings": [{"brand": "竞品", "rank": 1}],
                    "allRankings": [{"brand": "目标品牌", "rank": 1}],
                },
            }
        ),
    )
    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        brand_result = db.execute(
            AnswerBrandResult.__table__.select().where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == seeded["target_brand_id"],
            )
        ).mappings().one()
        assert brand_result["is_mentioned"] is False
        assert brand_result["mention_count"] == 0
        assert brand_result["first_position"] is None
        context = brand_result["context_json"]
        assert context["provider_mention_position"] == 1
        assert context["provider_sentiment"] == "positive"
        assert context["provider_competitor_rankings"] == [{"brand": "竞品", "rank": 1}]


def test_molizhishu_provider_brand_context_is_sanitized_for_api(session_factory, tmp_path):
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
    long_context = "x" * 3000
    _persist_molizhishu_answer(
        session_factory,
        tmp_path,
        seeded,
        _molizhishu_platform_answer(
            result_data={
                "success": True,
                "code": 200,
                "data": {
                    "status": "completed",
                    "answerContent": "普通回答，不含任何品牌提及。",
                    "mentionContext": long_context,
                    "sentiment": "positive",
                    "competitorRankings": [
                        {"brand": "竞品", "rank": 1, "token": "secret", "debug": "internal"},
                    ]
                    + [{"brand": f"品牌{i}", "rank": i} for i in range(25)],
                },
            }
        ),
    )
    with session_factory() as db:
        answer = answer_repo.get_by_task_id(db, seeded["task_id"])
        brand_result = db.execute(
            AnswerBrandResult.__table__.select().where(
                AnswerBrandResult.answer_id == answer.id,
                AnswerBrandResult.brand_id == seeded["target_brand_id"],
            )
        ).mappings().one()
        context = brand_result["context_json"]
        assert len(context["provider_mention_context"]) == 2000
        assert context["provider_competitor_rankings"] == [
            {"brand": "竞品", "rank": 1},
            *[{"brand": f"品牌{i}", "rank": i} for i in range(0, 19)],
        ]
        assert "token" not in str(context)
        assert "debug" not in str(context)


def test_molizhishu_success_syncs_provider_task_fields(session_factory, tmp_path):
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
    _persist_molizhishu_answer(
        session_factory,
        tmp_path,
        seeded,
        _molizhishu_platform_answer(),
    )
    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "success"
        assert task.provider_name == "molizhishu"
        assert task.provider_task_id == "task-mlz-1"
        assert task.provider_subtask_id == "sub-1"
        assert task.provider_platform_code == "doubao"
        assert task.provider_mode == "search"
        assert task.provider_status == "completed"
        assert task.provider_result_json["answerContent"] == "普通回答，不含任何品牌提及。"


def test_molizhishu_failure_sets_provider_error_message(session_factory, tmp_path):
    runtime = _make_collection_runtime(session_factory, tmp_path)
    with session_factory() as db:
        seeded = _seed_molizhishu_persist_graph(db)
        task = db.get(QueryTask, seeded["task_id"])
        task.status = "running"
        db.commit()
        error = AdapterError(
            "molizhishu subtask failed: provider timeout",
            category=ErrorCategory.INVALID_REQUEST,
            provider_error_message="provider timeout",
        )
        collection_service._handle_adapter_failure(runtime, task.id, error)
    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "failed"
        assert task.provider_error_message == "provider timeout"
