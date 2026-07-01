"""监测项目平台采集选项：深度思考与联网开关与 provider_mode 互转。"""

from __future__ import annotations

from app.core.exceptions import BusinessException
from app.geo_monitoring.services.platforms import (
    MOLIZHISHU_PLATFORM_MAPPINGS,
    MolizhishuPlatformMapping,
)

_PROVIDER_MODE_TO_TOGGLES: dict[str, tuple[bool, bool]] = {
    "standard": (False, False),
    "reasoning": (True, False),
    "search": (False, True),
    "reasoning_search": (True, True),
}


def provider_mode_from_toggles(*, deep_thinking: bool, search_enabled: bool) -> str:
    if deep_thinking and search_enabled:
        return "reasoning_search"
    if deep_thinking:
        return "reasoning"
    if search_enabled:
        return "search"
    return "standard"


def toggles_from_provider_mode(mode: str) -> tuple[bool, bool]:
    return _PROVIDER_MODE_TO_TOGGLES.get(mode, (False, True))


def default_platform_toggles(
    platform_code: str,
    *,
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> tuple[bool, bool]:
    mappings = molizhishu_mappings or MOLIZHISHU_PLATFORM_MAPPINGS
    mapping = mappings.get(platform_code)
    if mapping is None:
        return True, True
    return toggles_from_provider_mode(str(mapping["default_mode"]))


def resolve_platform_toggles(
    platform_code: str,
    *,
    deep_thinking_by_platform: dict[str, bool],
    search_enabled_by_platform: dict[str, bool],
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> tuple[bool, bool]:
    default_deep, default_search = default_platform_toggles(
        platform_code, molizhishu_mappings=molizhishu_mappings
    )
    deep = deep_thinking_by_platform.get(platform_code, default_deep)
    search = search_enabled_by_platform.get(platform_code, default_search)
    return bool(deep), bool(search)


def serialize_platform_toggles(
    platform_codes: list[str],
    *,
    deep_thinking_by_platform: dict[str, bool],
    search_enabled_by_platform: dict[str, bool],
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> tuple[dict[str, bool], dict[str, bool]]:
    deep_out: dict[str, bool] = {}
    search_out: dict[str, bool] = {}
    for code in platform_codes:
        deep, search = resolve_platform_toggles(
            code,
            deep_thinking_by_platform=deep_thinking_by_platform,
            search_enabled_by_platform=search_enabled_by_platform,
            molizhishu_mappings=molizhishu_mappings,
        )
        deep_out[code] = deep
        search_out[code] = search
    return deep_out, search_out


def validate_platform_toggle_combinations(
    platform_codes: list[str],
    *,
    deep_thinking_by_platform: dict[str, bool],
    search_enabled_by_platform: dict[str, bool],
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> None:
    mappings = molizhishu_mappings or MOLIZHISHU_PLATFORM_MAPPINGS
    for code in platform_codes:
        mapping = mappings.get(code)
        if mapping is None:
            continue
        deep, search = resolve_platform_toggles(
            code,
            deep_thinking_by_platform=deep_thinking_by_platform,
            search_enabled_by_platform=search_enabled_by_platform,
            molizhishu_mappings=mappings,
        )
        mode = provider_mode_from_toggles(deep_thinking=deep, search_enabled=search)
        if mode not in mapping["supported_modes"]:
            raise BusinessException(
                message=(
                    f"平台 {code} 不支持深度思考={deep}、联网={search} 的组合"
                ),
                code=40056,
            )


def normalize_platform_toggle_maps(
    selected_platform_codes: list[str],
    *,
    deep_thinking_by_platform: dict[str, bool],
    search_enabled_by_platform: dict[str, bool],
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> tuple[dict[str, bool], dict[str, bool]]:
    selected = set(selected_platform_codes)
    for field_name, toggle_map in (
        ("deep_thinking_enabled_by_platform", deep_thinking_by_platform),
        ("search_enabled_by_platform", search_enabled_by_platform),
    ):
        outside = sorted(set(toggle_map) - selected)
        if outside:
            raise BusinessException(
                message=f"{field_name} 只能配置已选平台: {', '.join(outside)}",
                code=40029,
            )

    validate_platform_toggle_combinations(
        selected_platform_codes,
        deep_thinking_by_platform=deep_thinking_by_platform,
        search_enabled_by_platform=search_enabled_by_platform,
        molizhishu_mappings=molizhishu_mappings,
    )

    stored_deep = {
        code: value
        for code, value in deep_thinking_by_platform.items()
        if code in selected
    }
    stored_search = {
        code: value
        for code, value in search_enabled_by_platform.items()
        if code in selected
    }
    return stored_deep, stored_search


def build_provider_mode_by_platform(
    platform_codes: list[str],
    *,
    deep_thinking_by_platform: dict[str, bool],
    search_enabled_by_platform: dict[str, bool],
    molizhishu_mappings: dict[str, MolizhishuPlatformMapping] | None = None,
) -> dict[str, str]:
    mappings = molizhishu_mappings or MOLIZHISHU_PLATFORM_MAPPINGS
    result: dict[str, str] = {}
    for code in platform_codes:
        mapping = mappings.get(code)
        if mapping is None:
            continue
        deep, search = resolve_platform_toggles(
            code,
            deep_thinking_by_platform=deep_thinking_by_platform,
            search_enabled_by_platform=search_enabled_by_platform,
            molizhishu_mappings=mappings,
        )
        mode = provider_mode_from_toggles(deep_thinking=deep, search_enabled=search)
        if mode not in mapping["supported_modes"]:
            raise BusinessException(
                message=(
                    f"平台 {code} 不支持深度思考={deep}、联网={search} 的组合"
                ),
                code=40056,
            )
        result[code] = mode
    return result
