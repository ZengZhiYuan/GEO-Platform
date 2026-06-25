"""平台端元数据与基础字典服务。"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.repositories import platforms as platform_repo
from app.geo_monitoring.schemas import (
    PlatformEndpointsOut,
    PromptTypesOut,
    SourceTypesOut,
)

_ENDPOINT_ORDER = {"web": 0, "app": 1, "other": 2}
_AIDSO_CODE_PATTERN = re.compile(r"^aidso_(?P<base>.+)_(?P<endpoint>web|app)$")

_BASE_PLATFORM_LABELS = {
    "doubao": "豆包",
    "qwen": "通义千问",
    "yuanbao": "腾讯元宝",
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "baidu": "百度 AI",
    "douyin": "抖音 AI",
    "wenxin": "文心一言",
}

_ENDPOINT_TYPE_LABELS = {
    "web": "网页端",
    "app": "手机端",
    "other": "其他端",
}

_PROMPT_TYPES = (
    {
        "code": "brand_sentiment",
        "label": "品牌情绪",
        "compatible_values": ["brand_sentiment", "品牌情绪"],
    },
    {
        "code": "brand_info",
        "label": "品牌信息",
        "compatible_values": ["brand_info", "brand_visibility", "品牌信息", "品牌认知"],
    },
    {
        "code": "category_sentiment",
        "label": "品类情绪",
        "compatible_values": ["category_sentiment", "generic", "品类情绪"],
    },
    {
        "code": "competitor_comparison",
        "label": "竞品对比",
        "compatible_values": ["competitor_comparison", "comparison", "竞品对比", "对比"],
    },
    {
        "code": "category_recommendation",
        "label": "品类推荐",
        "compatible_values": [
            "category_recommendation",
            "recommendation",
            "品类推荐",
            "推荐",
        ],
    },
)

_SOURCE_TYPE_ITEMS = (
    {"code": "official_site", "label": "官网/官方"},
    {"code": "industry_vertical", "label": "独立站/行业垂直"},
    {"code": "authority_media", "label": "官媒/权威媒体"},
    {"code": "social_forum", "label": "社交/论坛"},
    {"code": "video_platform", "label": "视频平台"},
    {"code": "ecommerce_ota", "label": "电商平台/OTA"},
    {"code": "encyclopedia", "label": "百科/知识库"},
    {"code": "other", "label": "其他/未分类"},
)

_SOURCE_STORAGE_MAPPINGS = (
    {
        "storage_value": "web",
        "display_code": "industry_vertical",
        "display_label": "独立站/行业垂直",
    },
    {
        "storage_value": "official",
        "display_code": "official_site",
        "display_label": "官网/官方",
    },
    {
        "storage_value": "media",
        "display_code": "authority_media",
        "display_label": "官媒/权威媒体",
    },
    {
        "storage_value": "social",
        "display_code": "social_forum",
        "display_label": "社交/论坛",
    },
    {
        "storage_value": "video",
        "display_code": "video_platform",
        "display_label": "视频平台",
    },
    {
        "storage_value": "ecommerce",
        "display_code": "ecommerce_ota",
        "display_label": "电商平台/OTA",
    },
)


def _coerce_extra_config(extra_config: dict[str, Any] | None) -> dict[str, Any]:
    return extra_config if isinstance(extra_config, dict) else {}


def _parse_aidso_platform_code(platform_code: str) -> tuple[str | None, str | None]:
    match = _AIDSO_CODE_PATTERN.match(platform_code)
    if not match:
        return None, None
    return match.group("base"), match.group("endpoint")


def _resolve_base_platform(platform: AIPlatform) -> str:
    extra = _coerce_extra_config(platform.extra_config)
    if base_platform := extra.get("base_platform"):
        return str(base_platform).strip()
    parsed_base, _ = _parse_aidso_platform_code(platform.platform_code)
    if parsed_base:
        return parsed_base
    return platform.platform_code


def _resolve_endpoint_type(platform: AIPlatform) -> str:
    extra = _coerce_extra_config(platform.extra_config)
    if endpoint_type := extra.get("endpoint_type"):
        normalized = str(endpoint_type).strip().lower()
        if normalized in {"web", "app"}:
            return normalized
        return "other"
    _, parsed_endpoint = _parse_aidso_platform_code(platform.platform_code)
    if parsed_endpoint:
        return parsed_endpoint
    return "other"


def _resolve_endpoint_label(platform: AIPlatform, *, endpoint_type: str) -> str:
    extra = _coerce_extra_config(platform.extra_config)
    if endpoint_label := extra.get("endpoint_label"):
        return str(endpoint_label).strip()
    if endpoint_type in _ENDPOINT_TYPE_LABELS:
        base_label = _BASE_PLATFORM_LABELS.get(
            _resolve_base_platform(platform), platform.platform_name
        )
        return f"{base_label} {_ENDPOINT_TYPE_LABELS[endpoint_type]}"
    return platform.platform_name


def _resolve_base_platform_label(base_platform: str, endpoints: list[dict[str, Any]]) -> str:
    for endpoint in endpoints:
        if endpoint["base_platform"] == base_platform and endpoint["endpoint_type"] == "other":
            return _BASE_PLATFORM_LABELS.get(base_platform, endpoint["platform_name"])
    return _BASE_PLATFORM_LABELS.get(base_platform, base_platform)


def _serialize_endpoint(platform: AIPlatform) -> dict[str, Any]:
    extra = _coerce_extra_config(platform.extra_config)
    base_platform = _resolve_base_platform(platform)
    endpoint_type = _resolve_endpoint_type(platform)
    return {
        "platform_code": platform.platform_code,
        "platform_name": platform.platform_name,
        "base_platform": base_platform,
        "base_platform_label": _BASE_PLATFORM_LABELS.get(base_platform, platform.platform_name),
        "endpoint_type": endpoint_type,
        "endpoint_label": _resolve_endpoint_label(platform, endpoint_type=endpoint_type),
        "logo_url": extra.get("logo_url"),
        "thinking_mode": extra.get("thinking_mode"),
        "enabled": platform.enabled,
        "adapter_type": platform.adapter_type,
        "search_enabled": platform.search_enabled,
        "citation_supported": platform.citation_supported,
    }


def list_platform_endpoints(
    db: Session,
    *,
    enabled: bool | None = None,
) -> dict[str, Any]:
    platforms = platform_repo.list_all_platforms(db, enabled=enabled)
    endpoints = [_serialize_endpoint(platform) for platform in platforms]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for endpoint in endpoints:
        grouped.setdefault(endpoint["base_platform"], []).append(endpoint)

    groups = []
    for base_platform in sorted(grouped):
        group_endpoints = sorted(
            grouped[base_platform],
            key=lambda item: (
                _ENDPOINT_ORDER.get(item["endpoint_type"], 99),
                item["platform_code"],
            ),
        )
        groups.append(
            {
                "base_platform": base_platform,
                "base_platform_label": _resolve_base_platform_label(
                    base_platform, group_endpoints
                ),
                "endpoints": group_endpoints,
            }
        )
    return PlatformEndpointsOut(groups=groups).model_dump(mode="json")


def list_prompt_types() -> dict[str, Any]:
    return PromptTypesOut(items=[dict(item) for item in _PROMPT_TYPES]).model_dump(
        mode="json"
    )


def list_source_types() -> dict[str, Any]:
    return SourceTypesOut(
        items=[dict(item) for item in _SOURCE_TYPE_ITEMS],
        storage_mappings=[dict(item) for item in _SOURCE_STORAGE_MAPPINGS],
    ).model_dump(mode="json")


_STORAGE_TO_DISPLAY = {
    mapping["storage_value"]: (
        mapping["display_code"],
        mapping["display_label"],
    )
    for mapping in _SOURCE_STORAGE_MAPPINGS
}
_DISPLAY_LABELS = {item["code"]: item["label"] for item in _SOURCE_TYPE_ITEMS}


def resolve_display_source_type(storage_value: str | None) -> tuple[str, str]:
    """将存储层信源类型映射为原型展示字典 code/label。"""
    if storage_value:
        normalized = storage_value.strip().lower()
        if normalized in _STORAGE_TO_DISPLAY:
            return _STORAGE_TO_DISPLAY[normalized]
        if normalized in _DISPLAY_LABELS:
            return normalized, _DISPLAY_LABELS[normalized]
    return "other", _DISPLAY_LABELS["other"]
