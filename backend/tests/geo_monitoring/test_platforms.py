from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.services.platforms import (
    DEFAULT_PLATFORMS,
    MOLIZHISHU_PLATFORM_MAPPINGS,
    MOLIZHISHU_PLATFORMS,
    OFFICIAL_PLATFORMS,
)


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


def test_default_platform_catalog_counts_official_and_molizhishu():
    assert len(OFFICIAL_PLATFORMS) == 5
    assert len(MOLIZHISHU_PLATFORM_MAPPINGS) == 11
    assert len(MOLIZHISHU_PLATFORMS) == 11
    assert len(DEFAULT_PLATFORMS) == 16

    codes = [platform["platform_code"] for platform in DEFAULT_PLATFORMS]
    assert len(codes) == len(set(codes))

    expected_molizhishu_codes = {
        "molizhishu_deepseek_web",
        "molizhishu_deepseek_mobile",
        "molizhishu_doubao_web",
        "molizhishu_doubao_mobile",
        "molizhishu_yuanbao_web",
        "molizhishu_kimi_web",
        "molizhishu_qianwen_web",
        "molizhishu_quark_web",
        "molizhishu_baiduai_web",
        "molizhishu_weibo_zhisou_web",
        "molizhishu_wenxinyiyan_web",
    }
    assert set(MOLIZHISHU_PLATFORM_MAPPINGS) == expected_molizhishu_codes


def test_molizhishu_platform_mappings_use_exact_provider_codes():
    assert MOLIZHISHU_PLATFORM_MAPPINGS["molizhishu_qianwen_web"]["molizhishu_platform"] == "qianwen"
    assert (
        MOLIZHISHU_PLATFORM_MAPPINGS["molizhishu_baiduai_web"]["molizhishu_platform"]
        == "baiduai"
    )
    assert (
        MOLIZHISHU_PLATFORM_MAPPINGS["molizhishu_weibo_zhisou_web"]["molizhishu_platform"]
        == "weibo_zhisou"
    )
    assert (
        MOLIZHISHU_PLATFORM_MAPPINGS["molizhishu_doubao_mobile"]["molizhishu_platform"]
        == "doubao_mobile"
    )


def test_molizhishu_platform_seed_fields(client, session_factory):
    _seed_platforms(session_factory)

    listed = client.get(
        "/api/geo-monitoring/platforms", params={"page_size": 50}
    ).json()["data"]
    by_code = {item["platform_code"]: item for item in listed["items"]}

    platform = by_code["molizhishu_deepseek_web"]
    assert platform["adapter_type"] == "molizhishu"
    assert platform["model_name"] == "molizhishu:deepseek"
    assert platform["search_enabled"] is True
    assert platform["citation_supported"] is True

    extra = platform["extra_config"]
    assert extra["molizhishu_platform"] == "deepseek"
    assert extra["base_platform"] == "deepseek"
    assert extra["endpoint_type"] == "web"
    assert extra["default_mode"] == "reasoning_search"
    assert "reasoning_search" in extra["supported_modes"]


def test_platform_catalog_includes_molizhishu_endpoint_platforms(client, session_factory):
    _seed_platforms(session_factory)

    listed = client.get(
        "/api/geo-monitoring/platforms", params={"page_size": 50}
    ).json()["data"]
    codes = {item["platform_code"] for item in listed["items"]}

    assert "molizhishu_doubao_web" in codes
    assert "molizhishu_doubao_mobile" in codes
    assert "molizhishu_qianwen_web" in codes
    assert "aidso_doubao_web" not in codes


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
