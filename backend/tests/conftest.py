import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://test-redis.invalid:6379/15"
os.environ["DRAMATIQ_BROKER"] = "stub"
os.environ["NACOS_ENABLED"] = "false"


@compiles(BigInteger, "sqlite")
def compile_big_integer_for_sqlite(type_, compiler, **kw):
    return compiler.visit_INTEGER(Integer(), **kw)


@pytest.fixture
def session_factory():
    from app.core.database import Base
    from app.geo_monitoring import models  # noqa: F401

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory) -> Generator[TestClient, None, None]:
    from app.core.database import get_db
    from app.main import app

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def project_id(client) -> int:
    response = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "测试监测项目", "industry": "文旅"},
    )
    assert response.json()["code"] == 0
    return response.json()["data"]["id"]


@pytest.fixture
def target_brand_id(client, project_id) -> int:
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "目标品牌", "brand_type": "target"},
    )
    assert response.json()["code"] == 0
    return response.json()["data"]["id"]
