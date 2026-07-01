import pytest

from app.core.exceptions import BusinessException
from app.geo_monitoring.services.platform_collection_options import (
    build_provider_mode_by_platform,
    default_platform_toggles,
    normalize_platform_toggle_maps,
    provider_mode_from_toggles,
    serialize_platform_toggles,
    toggles_from_provider_mode,
)


@pytest.mark.parametrize(
    ("deep_thinking", "search_enabled", "expected"),
    [
        (False, False, "standard"),
        (True, False, "reasoning"),
        (False, True, "search"),
        (True, True, "reasoning_search"),
    ],
)
def test_provider_mode_from_toggles(deep_thinking, search_enabled, expected):
    assert (
        provider_mode_from_toggles(
            deep_thinking=deep_thinking,
            search_enabled=search_enabled,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("standard", (False, False)),
        ("reasoning", (True, False)),
        ("search", (False, True)),
        ("reasoning_search", (True, True)),
    ],
)
def test_toggles_from_provider_mode(mode, expected):
    assert toggles_from_provider_mode(mode) == expected


def test_default_platform_toggles_for_molizhishu_platforms():
    assert default_platform_toggles("molizhishu_doubao_web") == (False, True)
    assert default_platform_toggles("molizhishu_deepseek_web") == (True, True)
    assert default_platform_toggles("qwen") == (True, True)


def test_serialize_platform_toggles_uses_defaults_for_missing_keys():
    deep, search = serialize_platform_toggles(
        ["molizhishu_doubao_web", "molizhishu_deepseek_web"],
        deep_thinking_by_platform={"molizhishu_doubao_web": False},
        search_enabled_by_platform={},
    )
    assert deep == {
        "molizhishu_doubao_web": False,
        "molizhishu_deepseek_web": True,
    }
    assert search == {
        "molizhishu_doubao_web": True,
        "molizhishu_deepseek_web": True,
    }


def test_build_provider_mode_by_platform_from_project_toggles():
    result = build_provider_mode_by_platform(
        ["molizhishu_doubao_web", "molizhishu_deepseek_web"],
        deep_thinking_by_platform={"molizhishu_doubao_web": False},
        search_enabled_by_platform={"molizhishu_deepseek_web": False},
    )
    assert result == {
        "molizhishu_doubao_web": "search",
        "molizhishu_deepseek_web": "reasoning",
    }


def test_normalize_platform_toggle_maps_rejects_outside_selected():
    with pytest.raises(BusinessException) as exc:
        normalize_platform_toggle_maps(
            ["qwen"],
            deep_thinking_by_platform={"deepseek": True},
            search_enabled_by_platform={},
        )
    assert exc.value.code == 40029


def test_normalize_platform_toggle_maps_rejects_unsupported_combination():
    with pytest.raises(BusinessException) as exc:
        normalize_platform_toggle_maps(
            ["molizhishu_doubao_web"],
            deep_thinking_by_platform={"molizhishu_doubao_web": True},
            search_enabled_by_platform={"molizhishu_doubao_web": False},
        )
    assert exc.value.code == 40056
