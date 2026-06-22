"""调度测试夹具。"""

import pytest

from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS


def seed_platforms(session_factory, disabled: set[str] | None = None) -> None:
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


def active_prompt_setup(client, project_id: int, prompt_count: int = 1) -> dict:
    prompt_set = client.post(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets",
        json={"set_name": "调度提示词", "version_no": "v1"},
    ).json()["data"]
    prompt_ids = []
    for index in range(prompt_count):
        prompt = client.post(
            f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
            json={
                "prompt_code": f"schedule_prompt_{index + 1}",
                "prompt_text": f"调度问题 {index + 1}",
                "sort_order": index,
            },
        ).json()["data"]
        prompt_ids.append(prompt["id"])
    activated = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate"
    ).json()["data"]
    return {"prompt_set": activated, "prompt_ids": prompt_ids}


@pytest.fixture
def schedule_setup(client, session_factory, project_id):
    seed_platforms(session_factory, disabled={"yuanbao", "deepseek", "kimi", "doubao"})
    prompts = active_prompt_setup(client, project_id, prompt_count=1)
    return {"project_id": project_id, **prompts}
