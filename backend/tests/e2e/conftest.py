"""E2E mock test fixtures."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select

from app.geo_monitoring.models import AIPlatform, QueryTask
from app.geo_monitoring.services import collection as collection_service
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS
from tests.geo_monitoring.agents.test_graph import FakeLLMClient


MOCK_QWEN_BASE = "https://qwen-mock.e2e.test/compatible-mode/v1"
MOCK_QWEN_KEY = "sk-e2e-mock-qwen-key"


def seed_qwen_platform(session_factory) -> None:
    with session_factory() as db:
        existing = {
            row.platform_code
            for row in db.execute(select(AIPlatform.platform_code)).scalars().all()
        }
        for platform in DEFAULT_PLATFORMS:
            code = platform["platform_code"]
            if code in existing:
                continue
            db.add(
                AIPlatform(
                    **platform,
                    enabled=code == "qwen",
                )
            )
        for row in db.execute(select(AIPlatform)).scalars().all():
            row.enabled = row.platform_code == "qwen"
        db.commit()


def active_prompt_setup(client, project_id: int, *, prompt_count: int = 1) -> dict[str, Any]:
    prompt_set = client.post(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets",
        json={"set_name": "E2E 提示词集", "version_no": "v1"},
    ).json()["data"]
    prompt_ids: list[int] = []
    for index in range(prompt_count):
        prompt = client.post(
            f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
            json={
                "prompt_code": f"e2e_{index + 1}",
                "prompt_text": f"推荐哪个品牌更好？问题 {index + 1}",
                "sort_order": index,
            },
        ).json()["data"]
        prompt_ids.append(prompt["id"])
    activated = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate"
    ).json()["data"]
    return {"prompt_set": activated, "prompt_ids": prompt_ids}


def configure_molizhishu_collection_runtime(session_factory, monkeypatch) -> None:
    monkeypatch.setenv("MOLIZHISHU_ENABLED", "true")
    monkeypatch.setenv("MOLIZHISHU_API_TOKEN", "test-molizhishu-token")
    from app.core.config import get_settings

    get_settings.cache_clear()
    runtime_settings = get_settings()
    collection_service.configure_runtime(
        collection_service.build_default_runtime(
            session_factory=session_factory,
            runtime_settings=runtime_settings,
        )
    )


def seed_molizhishu_platform(session_factory, *, platform_code: str = "molizhishu_doubao_web") -> None:
    with session_factory() as db:
        existing = set(db.execute(select(AIPlatform.platform_code)).scalars().all())
        for platform in DEFAULT_PLATFORMS:
            code = platform["platform_code"]
            if code in existing:
                continue
            db.add(AIPlatform(**platform, enabled=False))
        for row in db.execute(select(AIPlatform)).scalars().all():
            row.enabled = row.platform_code == platform_code
        db.commit()


def configure_mock_collection_runtime(session_factory, monkeypatch) -> None:
    monkeypatch.setenv("QWEN_ENABLED", "true")
    monkeypatch.setenv("QWEN_MODEL", "qwen-max")
    monkeypatch.setenv("QWEN_API_KEYS", MOCK_QWEN_KEY)
    monkeypatch.setenv("QWEN_BASE_URL", MOCK_QWEN_BASE)
    from app.core.config import get_settings

    get_settings.cache_clear()
    runtime_settings = get_settings()
    collection_service.configure_runtime(
        collection_service.build_default_runtime(
            session_factory=session_factory,
            runtime_settings=runtime_settings,
        )
    )


def register_qwen_success_route(
    *,
    answer_text: str = "推荐目标品牌，官网 https://example.com/docs",
) -> respx.MockRouter:
    payload = {
        "id": "qwen-e2e",
        "model": "qwen-max",
        "choices": [{"message": {"content": answer_text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }
    return respx.post(f"{MOCK_QWEN_BASE}/chat/completions").mock(
        return_value=httpx.Response(200, json=payload)
    )


async def drain_run_collection(session_factory, run_id: int) -> None:
    with session_factory() as db:
        task_ids = list(
            db.execute(
                select(QueryTask.id).where(
                    QueryTask.run_id == run_id,
                    QueryTask.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
    for task_id in task_ids:
        attempts = 0
        while attempts < 5:
            attempts += 1
            result = await collection_service.execute_query_task(task_id)
            if not result.should_retry:
                break


def drain_run_collection_sync(session_factory, run_id: int) -> None:
    asyncio.run(drain_run_collection(session_factory, run_id))


@pytest.fixture
def e2e_project(client, session_factory, monkeypatch):
    configure_mock_collection_runtime(session_factory, monkeypatch)
    seed_qwen_platform(session_factory)

    project = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "E2E 监测项目", "industry": "文旅", "official_domain": "example.com"},
    ).json()["data"]
    project_id = project["id"]

    client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "目标品牌", "brand_type": "target"},
    )
    client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "竞品B", "brand_type": "competitor"},
    )
    prompts = active_prompt_setup(client, project_id, prompt_count=2)
    return {"project_id": project_id, **prompts}


@pytest.fixture
def fake_llm(monkeypatch):
    from tests.geo_monitoring.analysis_support import patch_fake_llm_for_analyze

    return patch_fake_llm_for_analyze(monkeypatch)
