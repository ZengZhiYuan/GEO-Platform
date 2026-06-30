from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.services.platforms import DEFAULT_PLATFORMS

import pytest


def _seed_platforms(session_factory) -> None:
    with session_factory() as db:
        db.add_all(AIPlatform(**platform) for platform in DEFAULT_PLATFORMS)
        db.commit()


def test_platform_endpoints_groups_official_and_molizhishu_codes(client, session_factory):
    _seed_platforms(session_factory)

    payload = client.get("/api/geo-monitoring/platform-endpoints").json()["data"]
    groups = {group["base_platform"]: group for group in payload["groups"]}

    assert "doubao" in groups
    doubao_codes = {item["platform_code"] for item in groups["doubao"]["endpoints"]}
    assert {
        "doubao",
        "molizhishu_doubao_web",
        "molizhishu_doubao_mobile",
    }.issubset(doubao_codes)

    web = next(
        item
        for item in groups["doubao"]["endpoints"]
        if item["platform_code"] == "molizhishu_doubao_web"
    )
    app = next(
        item
        for item in groups["doubao"]["endpoints"]
        if item["platform_code"] == "molizhishu_doubao_mobile"
    )
    assert web["endpoint_type"] == "web"
    assert app["endpoint_type"] == "app"
    assert web["endpoint_label"]
    assert app["endpoint_label"]
    assert web["base_platform"] == "doubao"
    assert app["base_platform"] == "doubao"

    endpoint_types = [item["endpoint_type"] for item in groups["doubao"]["endpoints"]]
    assert endpoint_types.index("web") < endpoint_types.index("app")


def test_platform_endpoints_labels_new_molizhishu_base_platforms(client, session_factory):
    _seed_platforms(session_factory)

    payload = client.get("/api/geo-monitoring/platform-endpoints").json()["data"]
    groups = {group["base_platform"]: group for group in payload["groups"]}

    assert groups["qianwen"]["base_platform_label"] == "通义千问"
    assert groups["quark"]["base_platform_label"] == "夸克 AI"
    assert groups["baiduai"]["base_platform_label"] == "百度 AI+"
    assert groups["weibo_zhisou"]["base_platform_label"] == "微博智搜"
    assert groups["wenxinyiyan"]["base_platform_label"] == "文心一言"


def test_platform_endpoints_respects_extra_config(client, session_factory):
    _seed_platforms(session_factory)
    with session_factory() as db:
        platform = db.query(AIPlatform).filter(AIPlatform.platform_code == "deepseek").one()
        platform.extra_config = {
            "base_platform": "deepseek",
            "endpoint_type": "web",
            "endpoint_label": "DeepSeek 网页端",
            "logo_url": "https://cdn.example/deepseek.png",
            "thinking_mode": "enabled",
        }
        db.commit()

    payload = client.get("/api/geo-monitoring/platform-endpoints").json()["data"]
    deepseek_group = next(
        group for group in payload["groups"] if group["base_platform"] == "deepseek"
    )
    endpoint = next(
        item
        for item in deepseek_group["endpoints"]
        if item["platform_code"] == "deepseek"
    )

    assert endpoint["endpoint_type"] == "web"
    assert endpoint["endpoint_label"] == "DeepSeek 网页端"
    assert endpoint["logo_url"] == "https://cdn.example/deepseek.png"
    assert endpoint["thinking_mode"] == "enabled"


def test_platform_endpoints_enabled_filter(client, session_factory):
    _seed_platforms(session_factory)
    with session_factory() as db:
        platform = db.query(AIPlatform).filter(AIPlatform.platform_code == "kimi").one()
        platform.enabled = False
        db.commit()

    all_payload = client.get("/api/geo-monitoring/platform-endpoints").json()["data"]
    enabled_payload = client.get(
        "/api/geo-monitoring/platform-endpoints", params={"enabled": True}
    ).json()["data"]

    all_codes = {
        item["platform_code"]
        for group in all_payload["groups"]
        for item in group["endpoints"]
    }
    enabled_codes = {
        item["platform_code"]
        for group in enabled_payload["groups"]
        for item in group["endpoints"]
    }

    assert "kimi" in all_codes
    assert "kimi" not in enabled_codes


def test_prompt_types_returns_five_prototype_intents(client):
    payload = client.get("/api/geo-monitoring/prompt-types").json()["data"]

    assert len(payload["items"]) == 5
    codes = {item["code"] for item in payload["items"]}
    assert codes == {
        "brand_sentiment",
        "brand_info",
        "category_sentiment",
        "competitor_comparison",
        "category_recommendation",
    }

    comparison = next(item for item in payload["items"] if item["code"] == "competitor_comparison")
    recommendation = next(
        item for item in payload["items"] if item["code"] == "category_recommendation"
    )
    assert "comparison" in comparison["compatible_values"]
    assert "竞品对比" in comparison["compatible_values"]
    assert "recommendation" in recommendation["compatible_values"]
    assert "品类推荐" in recommendation["compatible_values"]


def test_source_types_returns_display_dictionary_and_storage_mappings(client):
    payload = client.get("/api/geo-monitoring/source-types").json()["data"]

    assert len(payload["items"]) >= 8
    display_codes = {item["code"] for item in payload["items"]}
    assert "official_site" in display_codes
    assert "ecommerce_ota" in display_codes

    storage_values = {item["storage_value"] for item in payload["storage_mappings"]}
    assert storage_values == {"web", "official", "media", "social", "video", "ecommerce"}

    official_mapping = next(
        item for item in payload["storage_mappings"] if item["storage_value"] == "official"
    )
    assert official_mapping["display_code"] == "official_site"
    assert official_mapping["display_label"]


def test_platform_endpoints_returns_all_platforms_without_truncation(client, session_factory):
    _seed_platforms(session_factory)
    with session_factory() as db:
        extra_platforms = [
            AIPlatform(
                platform_code=f"extra_platform_{index:04d}",
                platform_name=f"Extra Platform {index}",
                adapter_type="openai_compatible",
            )
            for index in range(501)
        ]
        db.add_all(extra_platforms)
        db.commit()

    payload = client.get("/api/geo-monitoring/platform-endpoints").json()["data"]
    returned_codes = {
        item["platform_code"]
        for group in payload["groups"]
        for item in group["endpoints"]
    }

    assert len(returned_codes) == len(DEFAULT_PLATFORMS) + 501
    assert "extra_platform_0500" in returned_codes


@pytest.mark.parametrize(
    ("path", "expected_key"),
    [
        ("/api/v1/geo-monitoring/platform-endpoints", "groups"),
        ("/api/v1/geo-monitoring/prompt-types", "items"),
        ("/api/v1/geo-monitoring/source-types", "storage_mappings"),
        ("/api/v1/geo-monitoring/providers/molizhishu/regions", "items"),
    ],
)
def test_metadata_routes_available_on_v1_prefix(client, path, expected_key, monkeypatch):
    if "molizhishu/regions" in path:
        monkeypatch.setattr(
            "app.geo_monitoring.services.metadata._fetch_molizhishu_regions_upstream",
            lambda: _sample_molizhishu_regions_upstream(),
        )
        from app.geo_monitoring.services import metadata as metadata_service

        metadata_service.clear_molizhishu_regions_cache()
    payload = client.get(path).json()["data"]
    assert expected_key in payload


def _sample_molizhishu_regions_upstream() -> dict:
    return {
        "success": True,
        "code": 200,
        "message": "ok",
        "data": [
            {"province": "北京市", "regionCode": ["110000"]},
            {"province": "上海市", "regionCode": ["310000"]},
        ],
    }


def test_molizhishu_regions_returns_normalized_list(client, monkeypatch):
    from app.geo_monitoring.services import metadata as metadata_service

    metadata_service.clear_molizhishu_regions_cache()
    monkeypatch.setattr(
        "app.geo_monitoring.services.metadata._fetch_molizhishu_regions_upstream",
        lambda: _sample_molizhishu_regions_upstream(),
    )

    payload = client.get("/api/geo-monitoring/providers/molizhishu/regions").json()

    assert payload["code"] == 0
    items = payload["data"]["items"]
    assert items == [
        {"province": "北京市", "region_code": "110000"},
        {"province": "上海市", "region_code": "310000"},
    ]


def test_molizhishu_regions_uses_local_cache(client, monkeypatch):
    from app.geo_monitoring.services import metadata as metadata_service

    metadata_service.clear_molizhishu_regions_cache()
    calls = {"count": 0}

    def _fetch() -> dict:
        calls["count"] += 1
        return _sample_molizhishu_regions_upstream()

    monkeypatch.setattr(
        "app.geo_monitoring.services.metadata._fetch_molizhishu_regions_upstream",
        _fetch,
    )

    client.get("/api/geo-monitoring/providers/molizhishu/regions")
    client.get("/api/geo-monitoring/providers/molizhishu/regions")

    assert calls["count"] == 1


def test_molizhishu_regions_returns_clear_error_when_upstream_unavailable(
    client, monkeypatch
):
    from app.core.exceptions import BusinessException
    from app.geo_monitoring.services import metadata as metadata_service

    metadata_service.clear_molizhishu_regions_cache()

    def _raise() -> dict:
        raise BusinessException(
            code=50210,
            message="模力指数区域列表暂不可用，请稍后重试",
        )

    monkeypatch.setattr(
        "app.geo_monitoring.services.metadata._fetch_molizhishu_regions_upstream",
        _raise,
    )

    payload = client.get("/api/geo-monitoring/providers/molizhishu/regions").json()

    assert payload["code"] == 50210
    assert "区域列表" in payload["message"]


def test_molizhishu_regions_cache_expires_after_ttl(client, monkeypatch):
    from app.core.config import settings
    from app.geo_monitoring.services import metadata as metadata_service

    metadata_service.clear_molizhishu_regions_cache()
    calls = {"count": 0}
    clock = {"now": 100.0}

    def _fetch() -> dict:
        calls["count"] += 1
        return _sample_molizhishu_regions_upstream()

    monkeypatch.setattr(
        "app.geo_monitoring.services.metadata.time.monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr(settings, "MOLIZHISHU_REGIONS_CACHE_SECONDS", 60)
    monkeypatch.setattr(
        "app.geo_monitoring.services.metadata._fetch_molizhishu_regions_upstream",
        _fetch,
    )

    client.get("/api/geo-monitoring/providers/molizhishu/regions")
    clock["now"] = 161.0
    client.get("/api/geo-monitoring/providers/molizhishu/regions")

    assert calls["count"] == 2


def test_molizhishu_regions_skips_cache_when_ttl_zero(client, monkeypatch):
    from app.core.config import settings
    from app.geo_monitoring.services import metadata as metadata_service

    metadata_service.clear_molizhishu_regions_cache()
    calls = {"count": 0}

    def _fetch() -> dict:
        calls["count"] += 1
        return _sample_molizhishu_regions_upstream()

    monkeypatch.setattr(settings, "MOLIZHISHU_REGIONS_CACHE_SECONDS", 0)
    monkeypatch.setattr(
        "app.geo_monitoring.services.metadata._fetch_molizhishu_regions_upstream",
        _fetch,
    )

    client.get("/api/geo-monitoring/providers/molizhishu/regions")
    client.get("/api/geo-monitoring/providers/molizhishu/regions")

    assert calls["count"] == 2
