def test_get_monitor_setup_empty(client, project_id):
    response = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()
    assert response["code"] == 0
    data = response["data"]
    assert data["brand"] is None
    assert data["competitors"] == []
    assert data["core_keywords"] == []
    assert data["ai_questions"] == []
    assert "available_platforms" in data
    assert data["selected_platform_codes"] == []


def test_save_and_get_monitor_setup(client, project_id, session_factory):
    from app.geo_monitoring.models import AIPlatform
    from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS

    with session_factory() as db:
        db.add_all(AIPlatform(**platform) for platform in DEFAULT_PLATFORMS)
        db.commit()

    payload = {
        "brand": {
            "brand_name": "宋城演艺",
            "official_domain": "https://www.songcn.com",
            "description": "文旅演艺集团",
            "brand_words": ["宋城", "宋城演艺"],
        },
        "competitors": [
            {
                "brand_name": "竞品A",
                "competitor_words": ["竞品A", "CompA"],
            }
        ],
        "core_keywords": [
            {"keyword": "文旅演艺", "sort_order": 1},
            {"keyword": "主题乐园", "sort_order": 2},
        ],
        "ai_questions": [
            {
                "core_keyword": "文旅演艺",
                "prompt_text": "推荐国内有哪些值得看的文旅演艺项目？",
            },
            {
                "library_prompt_code": "LIB_RECOMMEND_001",
                "core_keyword": "文旅演艺",
            },
        ],
        "selected_platform_codes": ["qwen", "deepseek"],
        "activate_prompt_set": True,
    }
    saved = client.put(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup",
        json=payload,
    ).json()
    assert saved["code"] == 0
    data = saved["data"]
    assert data["brand"]["brand_name"] == "宋城演艺"
    assert len(data["brand"]["brand_words"]) == 2
    assert len(data["competitors"]) == 1
    assert data["competitors"][0]["competitor_words"] == ["竞品A", "CompA"]
    assert len(data["core_keywords"]) == 2
    assert len(data["ai_questions"]) == 2
    assert data["ai_questions"][0]["prompt_type"] == "recommendation"
    assert data["selected_platform_codes"] == ["qwen", "deepseek"]
    assert data["active_prompt_set_id"] is not None

    loaded = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()["data"]
    assert loaded["brand"]["brand_name"] == "宋城演艺"
    assert loaded["competitors"][0]["brand_name"] == "竞品A"
    assert len(loaded["ai_questions"]) == 2


def test_monitor_setup_without_competitors(client, project_id, session_factory):
    from app.geo_monitoring.models import AIPlatform
    from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS

    with session_factory() as db:
        db.add_all(AIPlatform(**platform) for platform in DEFAULT_PLATFORMS)
        for row in db.query(AIPlatform).all():
            row.enabled = row.platform_code == "qwen"
        db.commit()

    payload = {
        "brand": {
            "brand_name": "目标品牌",
            "brand_words": ["目标"],
        },
        "competitors": [],
        "core_keywords": [{"keyword": "文旅"}],
        "ai_questions": [
            {"core_keyword": "文旅", "prompt_text": "国内有哪些文旅演艺项目？"}
        ],
        "selected_platform_codes": ["qwen"],
    }
    response = client.put(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup",
        json=payload,
    ).json()
    assert response["code"] == 0
    assert response["data"]["competitors"] == []
