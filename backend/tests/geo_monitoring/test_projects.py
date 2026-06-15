def test_project_crud_and_soft_delete(client):
    created_response = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "景区监测", "industry": "文旅"},
    )
    assert created_response.status_code == 200
    created = created_response.json()["data"]
    assert created["status"] == "active"

    listed = client.get("/api/geo-monitoring/projects").json()["data"]
    assert listed["total"] == 1

    updated = client.put(
        f"/api/geo-monitoring/projects/{created['id']}",
        json={"report_title": "AI 可见度监测报告"},
    ).json()["data"]
    assert updated["report_title"] == "AI 可见度监测报告"

    deleted = client.delete(
        f"/api/geo-monitoring/projects/{created['id']}"
    ).json()
    assert deleted["code"] == 0

    missing = client.get(
        f"/api/geo-monitoring/projects/{created['id']}"
    ).json()
    assert missing["code"] == 40400


def test_project_list_supports_name_and_status_filters(client):
    client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "华东景区", "industry": "文旅"},
    )
    second = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "华南景区", "industry": "文旅"},
    ).json()["data"]
    client.put(
        f"/api/geo-monitoring/projects/{second['id']}",
        json={"status": "disabled"},
    )

    by_name = client.get(
        "/api/geo-monitoring/projects", params={"project_name": "华东"}
    ).json()["data"]
    by_status = client.get(
        "/api/geo-monitoring/projects", params={"status": "disabled"}
    ).json()["data"]

    assert [item["project_name"] for item in by_name["items"]] == ["华东景区"]
    assert [item["id"] for item in by_status["items"]] == [second["id"]]
