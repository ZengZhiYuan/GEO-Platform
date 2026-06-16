import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides) -> Settings:
    values = {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "REDIS_URL": "redis://test-redis.invalid:6379/15",
        "DRAMATIQ_BROKER": "stub",
        "NACOS_ENABLED": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_database_and_redis_urls_are_required_without_env_file(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, APP_ENV="test", DRAMATIQ_BROKER="stub")

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
def test_invalid_connection_urls_are_rejected(field_name, value):
    with pytest.raises(ValidationError):
        make_settings(**{field_name: value})


def test_nacos_can_be_disabled_without_server_addresses():
    settings = make_settings(NACOS_ENABLED=False, NACOS_SERVER_ADDRESSES=None)

    assert settings.NACOS_ENABLED is False
    assert settings.NACOS_SERVER_ADDRESSES is None


def test_nacos_enabled_requires_valid_server_addresses():
    with pytest.raises(ValidationError):
        make_settings(NACOS_ENABLED=True, NACOS_SERVER_ADDRESSES=None)

    with pytest.raises(ValidationError):
        make_settings(
            NACOS_ENABLED=True,
            NACOS_SERVER_ADDRESSES="http://nacos.example.test:8848",
        )

    settings = make_settings(
        NACOS_ENABLED=True,
        NACOS_SERVER_ADDRESSES="nacos.example.test:8848,10.0.0.10:8848",
    )

    assert settings.NACOS_SERVER_ADDRESSES == "nacos.example.test:8848,10.0.0.10:8848"


def test_connection_summary_redacts_credentials_and_tokens():
    settings = make_settings(
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


def test_env_example_uses_placeholders_without_real_connection_values():
    from pathlib import Path

    text = (Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")

    assert "<postgres-host>" in text
    assert "<redis-host>" in text
    assert "<nacos-host>" in text
    assert "121.40.156.97" not in text
    assert "admin123" not in text
    assert "ark-" not in text
    assert "sk-" not in text
