import json
import os
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, _parse_comma_separated_keys

_ENV_EXAMPLE_KEY_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]*)=")

# Settings 字段名；对应 .env.example 中的部署配置键（DEBUG 映射为 APP_DEBUG）
_SETTINGS_FIELDS_IN_ENV_EXAMPLE = frozenset(
    {
        "APP_ENV",
        "DEBUG",
        "APP_TIMEZONE",
        "BACKEND_HOST",
        "BACKEND_PORT",
        "DATABASE_URL",
        "REDIS_URL",
        "DRAMATIQ_BROKER",
        "NACOS_ENABLED",
        "NACOS_SERVER_ADDRESSES",
        "NACOS_NAMESPACE",
        "NACOS_GROUP",
        "NACOS_USERNAME",
        "NACOS_PASSWORD",
        "NACOS_CONFIG_DATA_ID",
        "COLLECTION_REQUEST_TIMEOUT_SECONDS",
        "COLLECTION_MAX_ATTEMPTS",
        "COLLECTION_RETRY_BASE_SECONDS",
        "COLLECTION_AIDSO_MAX_POLLS",
        "COLLECTION_MAX_CONCURRENCY",
        "COLLECTION_RAW_RESPONSE_ENABLED",
        "DOUBAO_ENABLED",
        "DOUBAO_BASE_URL",
        "DOUBAO_MODEL",
        "DOUBAO_API_KEYS",
        "QWEN_ENABLED",
        "QWEN_BASE_URL",
        "QWEN_MODEL",
        "QWEN_API_KEYS",
        "YUANBAO_ENABLED",
        "YUANBAO_BASE_URL",
        "YUANBAO_MODEL",
        "YUANBAO_CREDENTIALS_JSON",
        "DEEPSEEK_ENABLED",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_API_KEYS",
        "KIMI_ENABLED",
        "KIMI_BASE_URL",
        "KIMI_MODEL",
        "KIMI_API_KEYS",
        "AIDSO_ENABLED",
        "AIDSO_BASE_URL",
        "AIDSO_API_TOKEN",
        "MOLIZHISHU_ENABLED",
        "MOLIZHISHU_BASE_URL",
        "MOLIZHISHU_API_TOKEN",
        "MOLIZHISHU_REQUEST_TIMEOUT_SECONDS",
        "COLLECTION_MOLIZHISHU_MAX_POLLS",
        "COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS",
        "MOLIZHISHU_PROVIDER_BATCH_ENABLED",
        "MOLIZHISHU_PROVIDER_BATCH_MAX_SUBTASKS",
        "MOLIZHISHU_DEFAULT_SCREENSHOT",
        "MOLIZHISHU_CALLBACK_ENABLED",
        "MOLIZHISHU_CALLBACK_TOKEN",
        "MOLIZHISHU_REGIONS_URL",
        "MOLIZHISHU_REGIONS_CACHE_SECONDS",
        "AGENT_LLM_BASE_URL",
        "AGENT_LLM_API_KEY",
        "AGENT_LLM_MODEL",
        "AGENT_LLM_PROVIDER",
        "AGENT_LLM_TIMEOUT_SECONDS",
        "AGENT_LLM_MAX_ATTEMPTS",
        "SCHEDULER_ENABLED",
        "SCHEDULER_TIMEZONE",
        "SCHEDULER_POLL_SECONDS",
        "REPORT_STORAGE_DIR",
        "REPORT_PUBLIC_BASE_URL",
        "REPORT_RETENTION_DAYS",
    }
)


def _env_var_name_for_settings_field(field_name: str) -> str:
    if field_name == "DEBUG":
        return "APP_DEBUG"
    return field_name


def _settings_env_var_names() -> frozenset[str]:
    names = {_env_var_name_for_settings_field(name) for name in Settings.model_fields}
    return frozenset(names)


def _expected_env_example_keys() -> frozenset[str]:
    return frozenset(
        _env_var_name_for_settings_field(name)
        for name in _SETTINGS_FIELDS_IN_ENV_EXAMPLE
    )


def _parse_env_example_keys(text: str) -> frozenset[str]:
    keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_EXAMPLE_KEY_PATTERN.match(stripped)
        if match is None:
            raise AssertionError(f"invalid .env.example line: {line!r}")
        keys.add(match.group(1))
    return frozenset(keys)


def make_settings(**overrides) -> Settings:
    values = {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "REDIS_URL": "redis://test-redis.invalid:6379/15",
        "DRAMATIQ_BROKER": "stub",
        "NACOS_ENABLED": False,
        "REPORT_STORAGE_DIR": overrides.pop(
            "REPORT_STORAGE_DIR",
            str(Path(__file__).parent / "_tmp_reports"),
        ),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_database_and_redis_urls_are_required_without_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            APP_ENV="test",
            DRAMATIQ_BROKER="stub",
            REPORT_STORAGE_DIR=str(tmp_path),
        )

    errors = {error["loc"][0] for error in exc_info.value.errors()}
    assert {"DATABASE_URL", "REDIS_URL"} <= errors


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("DATABASE_URL", "not-a-url"),
        ("REDIS_URL", "http://redis.example.test:6379/0"),
        ("REDIS_URL", "redisx://redis.example.test:6379/0"),
    ],
)
def test_invalid_connection_urls_are_rejected(tmp_path, field_name, value):
    with pytest.raises(ValidationError):
        make_settings(REPORT_STORAGE_DIR=str(tmp_path), **{field_name: value})


def test_nacos_can_be_disabled_without_server_addresses(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        NACOS_ENABLED=False,
        NACOS_SERVER_ADDRESSES=None,
    )

    assert settings.NACOS_ENABLED is False
    assert settings.NACOS_SERVER_ADDRESSES is None


def test_global_debug_environment_variable_does_not_override_app_debug(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.setenv("APP_DEBUG", "false")

    settings = make_settings(REPORT_STORAGE_DIR=str(tmp_path))

    assert settings.DEBUG is False


def test_nacos_enabled_requires_valid_server_addresses(tmp_path):
    with pytest.raises(ValidationError):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            NACOS_ENABLED=True,
            NACOS_SERVER_ADDRESSES=None,
        )

    with pytest.raises(ValidationError):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            NACOS_ENABLED=True,
            NACOS_SERVER_ADDRESSES="http://nacos.example.test:8848",
        )

    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        NACOS_ENABLED=True,
        NACOS_SERVER_ADDRESSES="nacos.example.test:8848,10.0.0.10:8848",
    )

    assert settings.NACOS_SERVER_ADDRESSES == "nacos.example.test:8848,10.0.0.10:8848"


@pytest.mark.parametrize(
    ("prefix", "model_field", "keys_field"),
    [
        ("DOUBAO", "DOUBAO_MODEL", "DOUBAO_API_KEYS"),
        ("QWEN", "QWEN_MODEL", "QWEN_API_KEYS"),
        ("DEEPSEEK", "DEEPSEEK_MODEL", "DEEPSEEK_API_KEYS"),
        ("KIMI", "KIMI_MODEL", "KIMI_API_KEYS"),
    ],
)
def test_enabled_platform_requires_model_and_api_keys(
    tmp_path, prefix, model_field, keys_field
):
    with pytest.raises(ValidationError, match=f"{prefix}_MODEL"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            **{f"{prefix}_ENABLED": True, model_field: "", keys_field: "key-a"},
        )

    with pytest.raises(ValidationError, match=f"{prefix}_API_KEYS"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            **{f"{prefix}_ENABLED": True, model_field: "model-a", keys_field: ""},
        )


def test_enabled_yuanbao_requires_credentials_and_model(tmp_path):
    with pytest.raises(ValidationError, match="YUANBAO_MODEL"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            YUANBAO_ENABLED=True,
            YUANBAO_MODEL="",
            YUANBAO_CREDENTIALS_JSON=[
                {"secret_id": "sid", "secret_key": "skey"},
            ],
        )

    with pytest.raises(ValidationError, match="YUANBAO_CREDENTIALS_JSON"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            YUANBAO_ENABLED=True,
            YUANBAO_MODEL="hunyuan-model",
            YUANBAO_CREDENTIALS_JSON=[],
        )


def test_enabled_aidso_requires_token(tmp_path):
    with pytest.raises(ValidationError, match="AIDSO_API_TOKEN"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            AIDSO_ENABLED=True,
            AIDSO_API_TOKEN="",
        )


def test_enabled_molizhishu_requires_token(tmp_path):
    with pytest.raises(ValidationError, match="MOLIZHISHU_API_TOKEN"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            MOLIZHISHU_ENABLED=True,
            MOLIZHISHU_API_TOKEN="",
        )


def test_molizhishu_disabled_without_token_starts_ok(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        MOLIZHISHU_ENABLED=False,
        MOLIZHISHU_API_TOKEN="",
    )

    assert settings.MOLIZHISHU_ENABLED is False
    assert settings.MOLIZHISHU_API_TOKEN == ""


@pytest.mark.parametrize("screenshot_value", [-1, 3, 99])
def test_molizhishu_default_screenshot_rejects_invalid_values(
    tmp_path, screenshot_value
):
    with pytest.raises(ValidationError, match="MOLIZHISHU_DEFAULT_SCREENSHOT"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            MOLIZHISHU_DEFAULT_SCREENSHOT=screenshot_value,
        )


def test_molizhishu_default_screenshot_accepts_zero_one_two(tmp_path):
    for value in (0, 1, 2):
        settings = make_settings(
            REPORT_STORAGE_DIR=str(tmp_path / str(value)),
            MOLIZHISHU_DEFAULT_SCREENSHOT=value,
        )
        assert settings.MOLIZHISHU_DEFAULT_SCREENSHOT == value


def test_api_keys_are_trimmed_deduped_and_empty_values_removed():
    assert _parse_comma_separated_keys(" key-a , key-b, key-a , , key-c ") == [
        "key-a",
        "key-b",
        "key-c",
    ]


def test_yuanbao_credentials_json_parses_and_validates(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        YUANBAO_CREDENTIALS_JSON=json.dumps(
            [
                {"secret_id": " sid-1 ", "secret_key": " skey-1 "},
                {"secret_id": "sid-2", "secret_key": "skey-2"},
            ]
        ),
    )

    credentials = settings.parsed_yuanbao_credentials()
    assert credentials[0].secret_id == "sid-1"
    assert credentials[0].secret_key == "skey-1"

    with pytest.raises(ValidationError, match="YUANBAO_CREDENTIALS_JSON"):
        make_settings(
            REPORT_STORAGE_DIR=str(tmp_path),
            YUANBAO_ENABLED=True,
            YUANBAO_MODEL="hunyuan-model",
            YUANBAO_CREDENTIALS_JSON='[{"secret_id":"sid"}]',
        )


def test_yuanbao_default_base_url_matches_tc3_hunyuan_api(tmp_path):
    settings = make_settings(REPORT_STORAGE_DIR=str(tmp_path))

    assert settings.YUANBAO_BASE_URL == "https://hunyuan.tencentcloudapi.com"


def test_report_storage_dir_must_be_creatable(tmp_path, monkeypatch):
    target = tmp_path / "reports"

    def fail_mkdir(self, *args, **kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(ValidationError, match="REPORT_STORAGE_DIR is not creatable"):
        make_settings(REPORT_STORAGE_DIR=str(target))


def test_connection_summary_redacts_credentials_and_tokens(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        DATABASE_URL=(
            "postgresql+psycopg2://db_user:db_password@db.example.test:5432/app"
        ),
        REDIS_URL="redis://:redis_password@redis.example.test:6379/0",
        NACOS_ENABLED=True,
        NACOS_SERVER_ADDRESSES="nacos.example.test:8848",
        NACOS_USERNAME="nacos_user",
        NACOS_PASSWORD="nacos_password",
        NACOS_ACCESS_TOKEN="nacos_token",
    )

    summary = settings.connection_targets_summary()
    rendered = repr(summary)

    assert "db.example.test:5432" in rendered
    assert "redis.example.test:6379" in rendered
    assert "nacos.example.test:8848" in rendered
    assert "db_user" not in rendered
    assert "db_password" not in rendered
    assert "redis_password" not in rendered
    assert "nacos_user" not in rendered
    assert "nacos_password" not in rendered
    assert "nacos_token" not in rendered


def test_runtime_summary_redacts_all_secrets(tmp_path):
    settings = make_settings(
        REPORT_STORAGE_DIR=str(tmp_path),
        DATABASE_URL=(
            "postgresql+psycopg2://db_user:db_password@db.example.test:5432/app"
        ),
        REDIS_URL="redis://:redis_password@redis.example.test:6379/0",
        DOUBAO_ENABLED=False,
        DOUBAO_API_KEYS="doubao-key-1,doubao-key-2",
        QWEN_API_KEYS="qwen-key",
        DEEPSEEK_API_KEYS="deepseek-key",
        KIMI_API_KEYS="kimi-key",
        YUANBAO_CREDENTIALS_JSON=[
            {"secret_id": "yuanbao-id", "secret_key": "yuanbao-secret"},
        ],
        AIDSO_ENABLED=True,
        AIDSO_API_TOKEN="aidso-secret-token",
        MOLIZHISHU_ENABLED=True,
        MOLIZHISHU_API_TOKEN="molizhishu-secret-token",
        MOLIZHISHU_CALLBACK_ENABLED=True,
        MOLIZHISHU_CALLBACK_TOKEN="molizhishu-callback-secret",
        AGENT_LLM_API_KEY="agent-secret-key",
    )

    rendered = repr(settings.runtime_summary())

    assert "doubao-key" not in rendered
    assert "qwen-key" not in rendered
    assert "deepseek-key" not in rendered
    assert "kimi-key" not in rendered
    assert "yuanbao-id" not in rendered
    assert "yuanbao-secret" not in rendered
    assert "aidso-secret-token" not in rendered
    assert "molizhishu-secret-token" not in rendered
    assert "molizhishu-callback-secret" not in rendered
    assert "agent-secret-key" not in rendered
    assert settings.runtime_summary()["platforms"]["doubao"]["api_key_count"] == 2
    assert settings.runtime_summary()["platforms"]["aidso"]["enabled"] is True
    assert settings.runtime_summary()["platforms"]["aidso"]["has_token"] is True
    molizhishu_summary = settings.runtime_summary()["platforms"]["molizhishu"]
    assert molizhishu_summary == {
        "enabled": True,
        "base_url": settings.MOLIZHISHU_BASE_URL,
        "has_token": True,
    }
    assert "molizhishu-secret-token" not in repr(molizhishu_summary)
    assert "molizhishu-callback-secret" not in rendered
    assert settings.runtime_summary()["collection"]["aidso_max_polls"] == 120
    assert settings.runtime_summary()["collection"]["molizhishu_max_polls"] == 360
    assert settings.runtime_summary()["collection"]["molizhishu_poll_delay_seconds"] == 8
    assert settings.runtime_summary()["agent_llm"]["has_api_key"] is True


def test_agent_llm_provider_accepts_supported_values():
    openai_settings = make_settings(AGENT_LLM_PROVIDER="openai_compatible")
    dashscope_settings = make_settings(AGENT_LLM_PROVIDER="dashscope")

    assert openai_settings.AGENT_LLM_PROVIDER == "openai_compatible"
    assert dashscope_settings.AGENT_LLM_PROVIDER == "dashscope"


def test_agent_llm_provider_rejects_unknown_value():
    with pytest.raises(ValidationError):
        make_settings(AGENT_LLM_PROVIDER="unknown")


def test_app_timezone_defaults_to_asia_shanghai(tmp_path):
    settings = make_settings(REPORT_STORAGE_DIR=str(tmp_path))

    assert settings.APP_TIMEZONE == "Asia/Shanghai"


def test_app_timezone_rejects_invalid_value(tmp_path):
    with pytest.raises(ValidationError, match="timezone is invalid"):
        make_settings(REPORT_STORAGE_DIR=str(tmp_path), APP_TIMEZONE="Invalid/Zone")


def test_configure_process_timezone_sets_env_and_returns_zoneinfo():
    from app.core.timezone import configure_process_timezone

    tz = configure_process_timezone("Asia/Shanghai")

    assert tz.key == "Asia/Shanghai"
    assert os.environ["TZ"] == "Asia/Shanghai"


def test_env_example_uses_placeholders_without_real_connection_values():
    text = (Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")

    assert "<server-host>" in text
    assert "<user>" in text
    assert "<password>" in text
    assert "121.40.156.97" not in text
    assert "admin123" not in text
    assert "ark-" not in text
    assert "sk-" not in text
    assert "AGENT_LLM_PROVIDER=openai_compatible" in text
    assert "APP_TIMEZONE=Asia/Shanghai" in text
    assert "MOLIZHISHU_ENABLED=false" in text
    assert "MOLIZHISHU_BASE_URL=" in text
    assert "MOLIZHISHU_API_TOKEN=" in text
    assert "COLLECTION_MOLIZHISHU_MAX_POLLS=360" in text
    assert "COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS=8" in text
    assert "MOLIZHISHU_PROVIDER_BATCH_ENABLED=true" in text
    assert "MOLIZHISHU_PROVIDER_BATCH_MAX_SUBTASKS=100" in text
    assert "MOLIZHISHU_DEFAULT_SCREENSHOT=0" in text
    assert "MOLIZHISHU_CALLBACK_ENABLED=false" in text
    assert "MOLIZHISHU_CALLBACK_TOKEN=" in text
    assert "MOLIZHISHU_REQUEST_TIMEOUT_SECONDS=30" in text
    assert "MOLIZHISHU_REGIONS_URL=" in text
    assert "MOLIZHISHU_REGIONS_CACHE_SECONDS=300" in text
    assert "COLLECTION_AIDSO_MAX_POLLS=120" in text


def test_env_example_keys_match_settings_deployment_whitelist():
    text = (Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")
    parsed_keys = _parse_env_example_keys(text)
    expected_keys = _expected_env_example_keys()

    assert parsed_keys == expected_keys, (
        "missing="
        f"{sorted(expected_keys - parsed_keys)!r}, "
        f"extra={sorted(parsed_keys - expected_keys)!r}"
    )


def test_env_example_keys_map_to_settings_fields():
    text = (Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")
    parsed_keys = _parse_env_example_keys(text)
    settings_keys = _settings_env_var_names()

    unknown_keys = parsed_keys - settings_keys
    assert not unknown_keys, f"unknown .env.example keys: {sorted(unknown_keys)!r}"
