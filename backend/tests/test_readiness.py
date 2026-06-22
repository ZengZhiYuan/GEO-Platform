from app.core.readiness import check_database_ready, check_nacos_ready, check_redis_ready


class FakeConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        self.statements.append(str(statement))


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def connect(self):
        return self.connection


class FakeRedis:
    def __init__(self, url):
        self.url = url
        self.closed = False
        self.pinged = False

    def ping(self):
        self.pinged = True

    def close(self):
        self.closed = True


def test_database_readiness_executes_probe_and_returns_target_summary():
    engine = FakeEngine()

    result = check_database_ready(
        engine=engine,
        database_url="postgresql+psycopg2://user:password@db.example.test:5432/app",
    )

    assert result == {
        "ok": True,
        "target": "postgresql+psycopg2://db.example.test:5432/app",
    }
    assert engine.connection.statements == ["SELECT 1"]


def test_redis_readiness_pings_configured_target_without_leaking_password():
    created = []

    def client_factory(url, socket_connect_timeout, socket_timeout):
        client = FakeRedis(url)
        created.append((client, socket_connect_timeout, socket_timeout))
        return client

    result = check_redis_ready(
        redis_url="redis://:secret@redis.example.test:6379/0",
        client_factory=client_factory,
    )

    assert result == {
        "ok": True,
        "target": "redis://redis.example.test:6379/0",
    }
    assert created[0][0].pinged is True
    assert created[0][0].closed is True
    assert "secret" not in repr(result)


def test_nacos_readiness_is_independent_and_non_blocking_when_disabled():
    result = check_nacos_ready(
        enabled=False,
        server_addresses=None,
        client_factory=lambda: (_ for _ in ()).throw(AssertionError("network call")),
    )

    assert result == {"ok": True, "enabled": False, "target": None}
