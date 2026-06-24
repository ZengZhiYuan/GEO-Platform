from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS


def _seed_platforms(session_factory) -> None:
    with session_factory() as db:
        db.add_all(AIPlatform(**platform) for platform in DEFAULT_PLATFORMS)
        db.commit()


def test_platform_list_and_update(client, session_factory):
    _seed_platforms(session_factory)

    listed = client.get(
        "/api/geo-monitoring/platforms", params={"page_size": 50}
    ).json()["data"]
    updated = client.put(
        "/api/geo-monitoring/platforms/deepseek",
        json={
            "model_name": "deepseek-chat",
            "max_concurrency": 4,
            "timeout_seconds": 90,
            "citation_supported": True,
        },
    ).json()["data"]

    assert listed["total"] == len(DEFAULT_PLATFORMS)
    assert {item["platform_code"] for item in listed["items"]} == {
        platform["platform_code"] for platform in DEFAULT_PLATFORMS
    }
    assert updated["model_name"] == "deepseek-chat"
    assert updated["max_concurrency"] == 4
    assert updated["citation_supported"] is True
    detail = client.get("/api/geo-monitoring/platforms/deepseek").json()["data"]
    assert detail["model_name"] == "deepseek-chat"


def test_platform_catalog_includes_aidso_endpoint_platforms(client, session_factory):
    _seed_platforms(session_factory)

    listed = client.get(
        "/api/geo-monitoring/platforms", params={"page_size": 50}
    ).json()["data"]
    codes = {item["platform_code"] for item in listed["items"]}

    assert "aidso_doubao_web" in codes
    assert "aidso_doubao_app" in codes
    assert "aidso_qwen_app" in codes


def test_platform_update_validates_limits(client, session_factory):
    _seed_platforms(session_factory)

    invalid = client.put(
        "/api/geo-monitoring/platforms/deepseek",
        json={"max_concurrency": 0, "timeout_seconds": 0},
    ).json()
    missing = client.put(
        "/api/geo-monitoring/platforms/not-found",
        json={"enabled": False},
    ).json()

    assert invalid["code"] == 422
    assert missing["code"] == 40400
