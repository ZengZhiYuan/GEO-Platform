"""调度 API 测试。"""


def test_schedule_crud_and_list(client, schedule_setup):
    project_id = schedule_setup["project_id"]

    created = client.post(
        f"/api/geo-monitoring/projects/{project_id}/schedules",
        json={
            "name": "morning",
            "cron_expr": "0 9 * * *",
            "timezone": "Asia/Shanghai",
        },
    ).json()
    schedule_id = created["data"]["id"]

    listed = client.get(
        f"/api/geo-monitoring/projects/{project_id}/schedules"
    ).json()
    detail = client.get(
        f"/api/geo-monitoring/schedules/{schedule_id}"
    ).json()
    updated = client.put(
        f"/api/geo-monitoring/schedules/{schedule_id}",
        json={"name": "morning-updated", "enabled": False},
    ).json()

    assert created["code"] == 0
    assert created["data"]["enabled"] is True
    assert created["data"]["misfire_policy"] == "fire_once"
    assert created["data"]["next_run_at"] is not None
    assert listed["data"]["total"] == 1
    assert detail["data"]["name"] == "morning"
    assert updated["data"]["name"] == "morning-updated"
    assert updated["data"]["enabled"] is False


def test_manual_trigger_creates_schedule_run(client, schedule_setup):
    project_id = schedule_setup["project_id"]
    schedule = client.post(
        f"/api/geo-monitoring/projects/{project_id}/schedules",
        json={"name": "manual", "cron_expr": "0 9 * * *"},
    ).json()["data"]

    triggered = client.post(
        f"/api/geo-monitoring/schedules/{schedule['id']}/trigger"
    ).json()

    assert triggered["code"] == 0
    assert triggered["data"]["trigger_type"] == "schedule"
    assert triggered["data"]["triggered_by"] == schedule["id"]
    assert triggered["data"]["status"] == "collecting"


def test_enable_disable_endpoints(client, schedule_setup):
    project_id = schedule_setup["project_id"]
    schedule = client.post(
        f"/api/geo-monitoring/projects/{project_id}/schedules",
        json={"name": "toggle", "cron_expr": "0 9 * * *", "enabled": True},
    ).json()["data"]

    disabled = client.post(
        f"/api/geo-monitoring/schedules/{schedule['id']}/disable"
    ).json()
    enabled = client.post(
        f"/api/geo-monitoring/schedules/{schedule['id']}/enable"
    ).json()

    assert disabled["data"]["enabled"] is False
    assert enabled["data"]["enabled"] is True


def test_delete_schedule(client, schedule_setup):
    project_id = schedule_setup["project_id"]
    schedule = client.post(
        f"/api/geo-monitoring/projects/{project_id}/schedules",
        json={"name": "temp", "cron_expr": "0 9 * * *"},
    ).json()["data"]

    deleted = client.delete(
        f"/api/geo-monitoring/schedules/{schedule['id']}"
    ).json()
    missing = client.get(
        f"/api/geo-monitoring/schedules/{schedule['id']}"
    ).json()

    assert deleted["code"] == 0
    assert missing["code"] != 0
