"""Task P2-2：创建向导草稿 API 测试。"""


def _draft_payload(
    *,
    draft_key: str = "wizard-session-1",
    current_step: int = 1,
    project_name: str = "草稿项目",
) -> dict:
    return {
        "draft_key": draft_key,
        "current_step": current_step,
        "project": {
            "project_name": project_name,
            "industry": "文旅演艺",
            "official_domain": "https://example.com",
        },
        "monitor_setup": {
            "brand": {
                "brand_name": "宋城演艺",
                "brand_words": ["宋城", "宋城演艺"],
            },
            "selected_platform_codes": ["qwen"],
        },
    }


def test_create_project_draft(client):
    response = client.post(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(),
    ).json()
    assert response["code"] == 0, response
    data = response["data"]
    assert data["id"] > 0
    assert data["draft_key"] == "wizard-session-1"
    assert data["current_step"] == 1
    assert data["project"]["project_name"] == "草稿项目"
    assert data["monitor_setup"]["brand"]["brand_name"] == "宋城演艺"
    assert data["monitor_setup"]["selected_platform_codes"] == ["qwen"]


def test_update_project_draft(client):
    created = client.post(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(current_step=1),
    ).json()["data"]
    draft_id = created["id"]

    updated = client.put(
        f"/api/geo-monitoring/project-drafts/{draft_id}",
        params={"draft_key": "wizard-session-1"},
        json={
            "current_step": 2,
            "monitor_setup": {
                "competitors": [
                    {"brand_name": "竞品A", "competitor_words": ["竞品A"]},
                ],
            },
        },
    ).json()
    assert updated["code"] == 0, updated
    data = updated["data"]
    assert data["id"] == draft_id
    assert data["current_step"] == 2
    assert data["project"]["project_name"] == "草稿项目"
    assert len(data["monitor_setup"]["competitors"]) == 1
    assert data["monitor_setup"]["brand"]["brand_name"] == "宋城演艺"


def test_get_project_draft_by_id(client):
    created = client.post(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(),
    ).json()["data"]

    loaded = client.get(
        f"/api/geo-monitoring/project-drafts/{created['id']}",
        params={"draft_key": "wizard-session-1"},
    ).json()
    assert loaded["code"] == 0, loaded
    assert loaded["data"]["id"] == created["id"]
    assert loaded["data"]["project"]["project_name"] == "草稿项目"


def test_get_current_project_draft_by_draft_key(client):
    client.post(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(draft_key="session-a", current_step=1),
    )
    client.put(
        "/api/geo-monitoring/project-drafts/current",
        json={
            "draft_key": "session-a",
            "current_step": 3,
            "project": {"project_name": "更新后的草稿"},
        },
    )

    loaded = client.get(
        "/api/geo-monitoring/project-drafts/current",
        params={"draft_key": "session-a"},
    ).json()
    assert loaded["code"] == 0, loaded
    data = loaded["data"]
    assert data["draft_key"] == "session-a"
    assert data["current_step"] == 3
    assert data["project"]["project_name"] == "更新后的草稿"


def test_put_project_drafts_upsert_by_draft_key(client):
    upserted = client.put(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(draft_key="session-b", current_step=2),
    ).json()
    assert upserted["code"] == 0, upserted
    assert upserted["data"]["draft_key"] == "session-b"
    assert upserted["data"]["current_step"] == 2

    updated = client.put(
        "/api/geo-monitoring/project-drafts",
        json={
            "draft_key": "session-b",
            "current_step": 3,
            "project": {"project_name": "PUT shorthand 更新"},
        },
    ).json()
    assert updated["code"] == 0, updated
    assert updated["data"]["id"] == upserted["data"]["id"]
    assert updated["data"]["current_step"] == 3
    assert updated["data"]["project"]["project_name"] == "PUT shorthand 更新"


def test_get_missing_project_draft_returns_not_found(client):
    response = client.get(
        "/api/geo-monitoring/project-drafts/99999",
        params={"draft_key": "wizard-session-1"},
    ).json()
    assert response["code"] == 40400


def test_get_current_project_draft_without_key_returns_not_found(client):
    response = client.get(
        "/api/geo-monitoring/project-drafts/current",
        params={"draft_key": "missing-session"},
    ).json()
    assert response["code"] == 40400


def test_draft_key_mismatch_returns_not_found(client):
    created = client.post(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(draft_key="owner-session"),
    ).json()["data"]

    response = client.get(
        f"/api/geo-monitoring/project-drafts/{created['id']}",
        params={"draft_key": "other-session"},
    ).json()
    assert response["code"] == 40400

    update_response = client.put(
        f"/api/geo-monitoring/project-drafts/{created['id']}",
        params={"draft_key": "other-session"},
        json={"current_step": 2},
    ).json()
    assert update_response["code"] == 40400


def test_blank_draft_key_upsert_returns_validation_error(client):
    response = client.put(
        "/api/geo-monitoring/project-drafts",
        json={"draft_key": "   ", "current_step": 1},
    ).json()
    assert response["code"] == 422


def test_current_step_out_of_range_returns_validation_error(client):
    response = client.post(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(current_step=4),
    ).json()
    assert response["code"] == 422


def test_same_draft_key_multiple_updates_return_latest_draft(client):
    first = client.put(
        "/api/geo-monitoring/project-drafts",
        json=_draft_payload(draft_key="session-c", current_step=1),
    ).json()["data"]

    second = client.put(
        "/api/geo-monitoring/project-drafts/current",
        json={
            "draft_key": "session-c",
            "current_step": 2,
            "project": {"project_name": "第二次更新"},
        },
    ).json()["data"]

    assert second["id"] == first["id"]
    assert second["current_step"] == 2
    assert second["project"]["project_name"] == "第二次更新"

    loaded = client.get(
        "/api/geo-monitoring/project-drafts/current",
        params={"draft_key": "session-c"},
    ).json()["data"]
    assert loaded["id"] == first["id"]
    assert loaded["project"]["project_name"] == "第二次更新"
