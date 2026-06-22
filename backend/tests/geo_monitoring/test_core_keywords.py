def test_core_keyword_crud(client, project_id):
    create = client.post(
        f"/api/geo-monitoring/projects/{project_id}/core-keywords",
        json={"keyword": "文旅演艺", "sort_order": 1},
    ).json()
    assert create["code"] == 0
    keyword_id = create["data"]["id"]

    listed = client.get(
        f"/api/geo-monitoring/projects/{project_id}/core-keywords"
    ).json()
    assert listed["code"] == 0
    assert listed["data"]["total"] == 1
    assert listed["data"]["items"][0]["keyword"] == "文旅演艺"

    updated = client.put(
        f"/api/geo-monitoring/core-keywords/{keyword_id}",
        json={"keyword": "沉浸式演艺", "sort_order": 2},
    ).json()
    assert updated["code"] == 0
    assert updated["data"]["keyword"] == "沉浸式演艺"

    duplicate = client.post(
        f"/api/geo-monitoring/projects/{project_id}/core-keywords",
        json={"keyword": "沉浸式演艺"},
    ).json()
    assert duplicate["code"] == 40024

    deleted = client.delete(
        f"/api/geo-monitoring/core-keywords/{keyword_id}"
    ).json()
    assert deleted["code"] == 0


def test_prompt_library_list(client):
    response = client.get("/api/geo-monitoring/prompt-library").json()
    assert response["code"] == 0
    assert response["data"]["total"] >= 1
    assert any(item.get("prompt_text") for item in response["data"]["items"])
