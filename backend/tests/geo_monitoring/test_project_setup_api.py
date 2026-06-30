"""Task P2-1：一步创建完整项目 API 测试。"""


def _seed_platforms(session_factory, *, enabled_codes: list[str] | None = None) -> None:
    from app.geo_monitoring.models import AIPlatform
    from app.geo_monitoring.services.platforms import AIDSO_PLATFORMS, DEFAULT_PLATFORMS

    with session_factory() as db:
        db.add_all(AIPlatform(**platform) for platform in DEFAULT_PLATFORMS)
        if enabled_codes is not None:
            enabled = set(enabled_codes)
            extra_codes = enabled - {platform["platform_code"] for platform in DEFAULT_PLATFORMS}
            if extra_codes:
                aidso_by_code = {platform["platform_code"]: platform for platform in AIDSO_PLATFORMS}
                db.add_all(
                    AIPlatform(**aidso_by_code[code])
                    for code in sorted(extra_codes)
                    if code in aidso_by_code
                )
            for row in db.query(AIPlatform).all():
                row.enabled = row.platform_code in enabled
        db.commit()


def _setup_payload(*, project_name: str = "一步创建项目", platform_codes: list[str] | None = None):
    return {
        "project": {
            "project_name": project_name,
            "industry": "文旅演艺",
            "description": "创建向导一步提交",
        },
        "monitor_setup": {
            "brand": {
                "brand_name": "宋城演艺",
                "official_domain": "https://www.songcn.com",
                "brand_words": ["宋城", "宋城演艺"],
            },
            "competitors": [
                {"brand_name": "竞品A", "competitor_words": ["竞品A"]},
            ],
            "core_keywords": [{"keyword": "文旅演艺", "sort_order": 1}],
            "ai_questions": [
                {
                    "core_keyword": "文旅演艺",
                    "prompt_text": "推荐国内有哪些值得看的文旅演艺项目？",
                }
            ],
            "selected_platform_codes": platform_codes or ["qwen"],
            "activate_prompt_set": True,
        },
        "run_after_create": False,
    }


def test_project_setup_activate_prompt_set_with_ai_questions_under_autoflush_false(
    client, session_factory
):
    """回归：autoflush=False 时 persist 后须 flush，否则 activate 查不到新 Prompt。"""
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    response = client.post(
        "/api/geo-monitoring/projects:setup",
        json=_setup_payload(),
    ).json()
    assert response["code"] == 0, response
    data = response["data"]
    assert data["monitor_setup"]["active_prompt_set_id"] is not None
    assert len(data["monitor_setup"]["ai_questions"]) == 1

    from app.geo_monitoring.models import Prompt, PromptSet

    with session_factory() as db:
        prompt_set = db.get(PromptSet, data["monitor_setup"]["active_prompt_set_id"])
        assert prompt_set is not None
        assert prompt_set.status == "active"
        prompts = (
            db.query(Prompt)
            .filter(
                Prompt.prompt_set_id == prompt_set.id,
                Prompt.is_deleted.is_(False),
            )
            .all()
        )
        assert len(prompts) == 1
        assert prompts[0].enabled is True


def test_project_setup_creates_project_and_monitor_setup(client, session_factory):
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    response = client.post(
        "/api/geo-monitoring/projects:setup",
        json=_setup_payload(),
    ).json()
    assert response["code"] == 0, response
    data = response["data"]
    assert data["project"]["project_name"] == "一步创建项目"
    assert data["project"]["status"] == "active"
    assert data["monitor_setup"]["brand"]["brand_name"] == "宋城演艺"
    assert len(data["monitor_setup"]["competitors"]) == 1
    assert len(data["monitor_setup"]["ai_questions"]) == 1
    assert data["monitor_setup"]["selected_platform_codes"] == ["qwen"]
    assert data["monitor_setup"]["active_prompt_set_id"] is not None
    assert data.get("run") is None

    project_id = data["project"]["id"]
    loaded = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()["data"]
    assert loaded["brand"]["brand_name"] == "宋城演艺"


def test_project_setup_rolls_back_on_monitor_setup_failure(client, session_factory):
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    before = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    payload = _setup_payload(
        project_name="应回滚的项目",
        platform_codes=["invalid_platform"],
    )
    response = client.post("/api/geo-monitoring/projects:setup", json=payload).json()
    assert response["code"] == 40025

    after = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    assert after == before


def test_project_setup_run_after_create(client, session_factory):
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    payload = _setup_payload(project_name="创建并运行")
    payload["run_after_create"] = True
    response = client.post("/api/geo-monitoring/projects:setup", json=payload).json()
    assert response["code"] == 0, response
    data = response["data"]
    assert data["run"] is not None
    assert data["run"]["project_id"] == data["project"]["id"]
    assert data["run"]["status"] in {"pending", "collecting"}


def test_project_setup_run_after_create_requires_activate_prompt_set(
    client, session_factory
):
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    before = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    payload = _setup_payload(project_name="未激活不应创建")
    payload["monitor_setup"]["activate_prompt_set"] = False
    payload["run_after_create"] = True
    response = client.post("/api/geo-monitoring/projects:setup", json=payload).json()
    assert response["code"] == 40055

    after = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    assert after == before


def test_project_setup_run_after_create_requires_questions(client, session_factory):
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    before = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    payload = _setup_payload(project_name="无问题不应创建")
    payload["monitor_setup"]["ai_questions"] = []
    payload["run_after_create"] = True
    response = client.post("/api/geo-monitoring/projects:setup", json=payload).json()
    assert response["code"] == 40901

    after = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    assert after == before


def test_project_setup_run_after_create_rejects_aidso_platform_with_official_run(
    client, session_factory
):
    _seed_platforms(session_factory, enabled_codes=["aidso_doubao_web"])

    before = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    payload = _setup_payload(
        project_name="Aidso平台不应半成功",
        platform_codes=["aidso_doubao_web"],
    )
    payload["run_after_create"] = True
    response = client.post("/api/geo-monitoring/projects:setup", json=payload).json()
    assert response["code"] == 40031

    after = client.get("/api/geo-monitoring/projects").json()["data"]["total"]
    assert after == before


def test_project_setup_available_on_v1_prefix(client, session_factory):
    _seed_platforms(session_factory, enabled_codes=["qwen"])

    response = client.post(
        "/api/v1/geo-monitoring/projects:setup",
        json=_setup_payload(project_name="v1前缀创建"),
    ).json()
    assert response["code"] == 0, response
    assert response["data"]["project"]["project_name"] == "v1前缀创建"
