from app.geo_monitoring.models import AIPlatform


PLATFORMS = (
    ("deepseek", "DeepSeek"),
    ("doubao", "豆包"),
    ("qwen", "通义千问"),
    ("kimi", "Kimi"),
    ("wenxin", "文心一言"),
)


def _seed_platforms(session_factory) -> None:
    with session_factory() as db:
        db.add_all(
            AIPlatform(platform_code=code, platform_name=name)
            for code, name in PLATFORMS
        )
        db.commit()


def test_platform_list_and_update(client, session_factory):
    _seed_platforms(session_factory)

    listed = client.get("/api/geo-monitoring/platforms").json()["data"]
    updated = client.put(
        "/api/geo-monitoring/platforms/deepseek",
        json={
            "model_name": "deepseek-chat",
            "max_concurrency": 4,
            "timeout_seconds": 90,
            "citation_supported": True,
        },
    ).json()["data"]

    assert listed["total"] == 5
    assert {item["platform_code"] for item in listed["items"]} == {
        code for code, _ in PLATFORMS
    }
    assert updated["model_name"] == "deepseek-chat"
    assert updated["max_concurrency"] == 4
    assert updated["citation_supported"] is True


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
