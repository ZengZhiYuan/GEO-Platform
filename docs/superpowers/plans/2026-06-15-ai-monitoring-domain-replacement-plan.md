# AI Monitoring Domain Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing content-generation product with a tested AI application monitoring backend foundation and a minimal React administration shell.

**Architecture:** Keep the shared FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis/Dramatiq, response, exception, and React infrastructure. Move all new business code into an isolated `app.geo_monitoring` domain package, expose it under `/api/geo-monitoring`, rebuild Alembic as a single clean baseline, and retain only a monitoring placeholder page in the frontend.

**Tech Stack:** Python 3, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, Redis 7, Dramatiq, pytest, FastAPI TestClient, React 18, TypeScript, Vite 5, Ant Design 5.

**Design:** `docs/superpowers/specs/2026-06-15-ai-monitoring-domain-replacement-design.md`

---

## File Map

### Backend files to create

- `backend/tests/conftest.py`: shared in-memory database and TestClient fixtures.
- `backend/tests/test_app_boundary.py`: health route, new route prefix, and removed-route assertions.
- `backend/tests/geo_monitoring/test_projects.py`: project CRUD and soft-delete behavior.
- `backend/tests/geo_monitoring/test_brands.py`: target-brand and alias invariants.
- `backend/tests/geo_monitoring/test_prompts.py`: PromptSet lifecycle and Prompt mutability rules.
- `backend/tests/geo_monitoring/test_platforms.py`: seeded platform listing and update validation.
- `backend/tests/geo_monitoring/test_runs.py`: run creation, Cartesian task generation, and rollback behavior.
- `backend/app/geo_monitoring/__init__.py`: domain exports.
- `backend/app/geo_monitoring/api.py`: `/geo-monitoring` router and HTTP handlers.
- `backend/app/geo_monitoring/models.py`: eight SQLAlchemy models.
- `backend/app/geo_monitoring/schemas.py`: request, response, enum, and filter schemas.
- `backend/app/geo_monitoring/services/__init__.py`: service exports.
- `backend/app/geo_monitoring/services/projects.py`: project operations.
- `backend/app/geo_monitoring/services/brands.py`: Brand and BrandAlias operations.
- `backend/app/geo_monitoring/services/prompts.py`: PromptSet and Prompt operations.
- `backend/app/geo_monitoring/services/platforms.py`: AIPlatform operations.
- `backend/app/geo_monitoring/services/runs.py`: MonitorRun and QueryTask operations.
- `backend/alembic/versions/20260615_0001-ai_monitoring_baseline.py`: single clean baseline.
- `backend/requirements-dev.txt`: pytest and HTTP test dependencies.

### Backend files to modify

- `backend/app/api/router.py`: retain health and include only the monitoring router.
- `backend/app/core/config.py`: remove content-generation settings and rename defaults.
- `backend/app/models/__init__.py`: register only BaseModel and monitoring models.
- `backend/app/workers/broker.py`: retain generic broker setup without article-specific commentary or middleware assumptions.
- `backend/app/workers/worker.py`: retain an empty worker bootstrap without old actors.
- `backend/alembic/env.py`: continue loading the new model metadata.
- `backend/requirements.txt`: retain runtime infrastructure dependencies only.

### Backend files to delete

- `backend/app/api/endpoints/`
- Old business files under `backend/app/models/`, except `base.py` and rewritten `__init__.py`.
- Old business files under `backend/app/schemas/` and `backend/app/services/`.
- `backend/app/tasks/`
- Old files under `backend/app/services/ai_generation/`.
- Every existing revision under `backend/alembic/versions/` before adding the new baseline.

### Frontend files to create

- `frontend/src/pages/MonitoringHomePage.tsx`: monitoring placeholder page.
- `frontend/scripts/test-routes.mjs`: verifies old route literals are gone and `/monitoring` exists.

### Frontend files to modify

- `frontend/package.json`: add `test` script.
- `frontend/src/router/index.tsx`: retain only monitoring and 404 routes.
- `frontend/src/layout/MainLayout.tsx`: monitoring-only menu and product copy.
- `frontend/src/pages/NotFoundPage.tsx`: return to `/monitoring`.
- `frontend/index.html`: update the page title.

### Frontend files to delete

- `frontend/src/pages/material/`
- `frontend/src/pages/workspace/`
- `frontend/src/pages/PlaceholderPage.tsx`
- All old business API files under `frontend/src/api/`, retaining only `client.ts`.
- `frontend/src/types/material.ts`, `frontend/src/types/workspace.ts`, and obsolete exports.
- `frontend/src/utils/enums.ts` and other utilities used only by deleted pages.

### Documentation files

- Delete all old files under `docs/`, excluding this plan and the approved spec.
- Rewrite `CLAUDE.md` for the monitoring-only product.
- Update `README.md` and `.env.example` to remove content-generation and Mock writer instructions.

---

### Task 1: Establish the Backend Test Harness and Product Boundary

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_app_boundary.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/core/config.py`
- Delete: `backend/app/api/endpoints/`

- [ ] **Step 1: Add test-only dependencies**

Create `backend/requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.2,<9
httpx>=0.27,<1
```

- [ ] **Step 2: Write the failing boundary tests**

Create `backend/tests/conftest.py`:

```python
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


@compiles(BigInteger, "sqlite")
def compile_big_integer_for_sqlite(type_, compiler, **kw):
    return compiler.visit_INTEGER(Integer(), **kw)


@pytest.fixture
def session_factory():
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
```

Create `backend/tests/test_app_boundary.py`:

```python
OLD_PATHS = (
    "/api/keywords",
    "/api/title-inspirations",
    "/api/image-categories",
    "/api/image-assets",
    "/api/brand-knowledges",
    "/api/writing-rules",
    "/api/content-categories",
    "/api/writing-tasks",
    "/api/articles",
)


def test_health_uses_monitoring_product_name(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["app"] == "ai-application-monitoring"


def test_old_business_routes_are_removed(client):
    for path in OLD_PATHS:
        assert client.get(path).status_code == 404


def test_monitoring_router_is_registered(client):
    response = client.get("/api/geo-monitoring/platforms")
    assert response.status_code != 404
```

- [ ] **Step 3: Run tests and verify the expected RED state**

Run:

```powershell
cd backend
python -m pytest tests/test_app_boundary.py -v
```

Expected: the health product name assertion fails, old routes still respond, and `/api/geo-monitoring/platforms` returns 404.

- [ ] **Step 4: Replace route aggregation with the new domain boundary**

Rewrite `backend/app/api/router.py`:

```python
from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success
from app.geo_monitoring.api import router as geo_monitoring_router

api_router = APIRouter()


@api_router.get("/health", summary="健康检查")
async def health() -> dict:
    return success(
        {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
    )


api_router.include_router(geo_monitoring_router)
```

Create a temporary `backend/app/geo_monitoring/api.py` with a real router and a minimal platform handler that will be replaced in Task 5:

```python
from fastapi import APIRouter

from app.core.response import success

router = APIRouter(prefix="/geo-monitoring", tags=["AI 应用监测"])


@router.get("/platforms")
def list_platforms_placeholder() -> dict:
    return success([])
```

Create `backend/app/geo_monitoring/__init__.py` as an empty package marker.

Update the application defaults in `backend/app/core/config.py`:

```python
APP_NAME: str = "ai-application-monitoring"
APP_ENV: str = "local"
APP_DEBUG: bool = True
API_PREFIX: str = "/api"
```

Remove `ARTICLE_MAX_RETRIES`, `AI_PROVIDER`, and `AI_MOCK_DELAY_SECONDS`. Keep `REDIS_URL` and `DRAMATIQ_BROKER` for future collection workers.

Delete `backend/app/api/endpoints/` after removing its imports.

- [ ] **Step 5: Run the boundary tests and verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/test_app_boundary.py -v
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit the boundary replacement**

```powershell
git add backend/app/api backend/app/core/config.py backend/app/geo_monitoring backend/tests backend/requirements-dev.txt
git commit -m "refactor: replace content routes with monitoring boundary"
```

---

### Task 2: Define the Monitoring Data Model

**Files:**
- Create: `backend/app/geo_monitoring/models.py`
- Create: `backend/app/geo_monitoring/schemas.py`
- Create: `backend/tests/geo_monitoring/test_models.py`
- Modify: `backend/app/models/__init__.py`
- Delete: old model and schema modules

- [ ] **Step 1: Write failing metadata and schema tests**

Create `backend/tests/geo_monitoring/test_models.py`:

```python
from importlib.util import find_spec


def test_monitoring_metadata_contains_only_expected_business_tables():
    assert find_spec("app.geo_monitoring.models") is not None
    from app.core.database import Base
    from app.geo_monitoring import models  # noqa: F401

    expected = {
        "geo_monitor_project",
        "geo_brand",
        "geo_brand_alias",
        "geo_prompt_set",
        "geo_prompt",
        "geo_ai_platform",
        "geo_monitor_run",
        "geo_query_task",
    }
    assert expected.issubset(Base.metadata.tables)
    assert "keyword_library" not in Base.metadata.tables
    assert "writing_task" not in Base.metadata.tables
    assert "article" not in Base.metadata.tables


def test_model_table_names_are_stable():
    assert find_spec("app.geo_monitoring.models") is not None
    from app.geo_monitoring.models import (
        AIPlatform,
        Brand,
        BrandAlias,
        MonitorProject,
        MonitorRun,
        Prompt,
        PromptSet,
        QueryTask,
    )

    assert MonitorProject.__tablename__ == "geo_monitor_project"
    assert Brand.__tablename__ == "geo_brand"
    assert BrandAlias.__tablename__ == "geo_brand_alias"
    assert PromptSet.__tablename__ == "geo_prompt_set"
    assert Prompt.__tablename__ == "geo_prompt"
    assert AIPlatform.__tablename__ == "geo_ai_platform"
    assert MonitorRun.__tablename__ == "geo_monitor_run"
    assert QueryTask.__tablename__ == "geo_query_task"


def test_project_and_run_input_validation():
    assert find_spec("app.geo_monitoring.schemas") is not None
    from app.geo_monitoring.schemas import ProjectCreate, RunCreate

    project = ProjectCreate(project_name="  测试项目  ")
    run = RunCreate(project_id=1, platform_codes=["qwen", "deepseek"])
    assert project.project_name == "测试项目"
    assert run.platform_codes == ["qwen", "deepseek"]
```

- [ ] **Step 2: Run the model tests and verify RED**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_models.py -v
```

Expected: assertion failure because the monitoring model and schema modules do not exist.

- [ ] **Step 3: Implement the eight models**

Create `backend/app/geo_monitoring/models.py` with these classes and relationships:

```python
class MonitorProject(BaseModel):
    __tablename__ = "geo_monitor_project"
    project_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), default="文旅演艺", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    official_domain: Mapped[str | None] = mapped_column(String(255))
    report_title: Mapped[str | None] = mapped_column(String(255))
    report_subtitle: Mapped[str | None] = mapped_column(String(500))


class Brand(BaseModel):
    __tablename__ = "geo_brand"
    __table_args__ = (UniqueConstraint("project_id", "brand_name"),)
    project_id: Mapped[int] = mapped_column(ForeignKey("geo_monitor_project.id", ondelete="CASCADE"), index=True)
    brand_name: Mapped[str] = mapped_column(String(255))
    brand_type: Mapped[str] = mapped_column(String(20), default="competitor", index=True)
    official_domain: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")


class BrandAlias(BaseModel):
    __tablename__ = "geo_brand_alias"
    __table_args__ = (UniqueConstraint("brand_id", "alias_name"),)
    brand_id: Mapped[int] = mapped_column(ForeignKey("geo_brand.id", ondelete="CASCADE"), index=True)
    alias_name: Mapped[str] = mapped_column(String(255))
    match_mode: Mapped[str] = mapped_column(String(20), default="contains")
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    context_keywords: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class PromptSet(BaseModel):
    __tablename__ = "geo_prompt_set"
    __table_args__ = (UniqueConstraint("project_id", "version_no"),)
    project_id: Mapped[int] = mapped_column(ForeignKey("geo_monitor_project.id", ondelete="CASCADE"), index=True)
    set_name: Mapped[str] = mapped_column(String(100))
    version_no: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    prompt_count: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prompt(BaseModel):
    __tablename__ = "geo_prompt"
    __table_args__ = (UniqueConstraint("prompt_set_id", "prompt_code"),)
    prompt_set_id: Mapped[int] = mapped_column(ForeignKey("geo_prompt_set.id", ondelete="CASCADE"), index=True)
    prompt_code: Mapped[str] = mapped_column(String(64))
    prompt_text: Mapped[str] = mapped_column(Text)
    prompt_type: Mapped[str] = mapped_column(String(50), default="generic")
    scene_tag: Mapped[str | None] = mapped_column(String(100))
    contains_brand: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64))


class AIPlatform(BaseModel):
    __tablename__ = "geo_ai_platform"
    platform_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    platform_name: Mapped[str] = mapped_column(String(100))
    adapter_type: Mapped[str] = mapped_column(String(50), default="openai_compatible")
    base_url: Mapped[str | None] = mapped_column(String(500))
    model_name: Mapped[str | None] = mapped_column(String(255))
    search_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    citation_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    extra_config: Mapped[dict] = mapped_column(JSON, default=dict)


class MonitorRun(BaseModel):
    __tablename__ = "geo_monitor_run"
    run_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("geo_monitor_project.id"), index=True)
    prompt_set_id: Mapped[int] = mapped_column(ForeignKey("geo_prompt_set.id"), index=True)
    prompt_set_version: Mapped[str] = mapped_column(String(50))
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    collection_status: Mapped[str] = mapped_column(String(30), default="pending")
    analysis_status: Mapped[str] = mapped_column(String(30), default="skipped")
    report_status: Mapped[str] = mapped_column(String(30), default="skipped")
    platform_codes: Mapped[list] = mapped_column(JSON, default=list)
    expected_query_count: Mapped[int] = mapped_column(Integer, default=0)
    success_query_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_query_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_answer_count: Mapped[int] = mapped_column(Integer, default=0)
    data_completeness_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QueryTask(BaseModel):
    __tablename__ = "geo_query_task"
    __table_args__ = (UniqueConstraint("run_id", "prompt_id", "platform_code"),)
    run_id: Mapped[int] = mapped_column(ForeignKey("geo_monitor_run.id", ondelete="CASCADE"), index=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("geo_prompt.id"), index=True)
    platform_code: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    key_slot: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    request_json: Mapped[dict | None] = mapped_column(JSON)
    response_http_status: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Use SQLAlchemy enums/check constraints exactly as listed in the approved design. Use PostgreSQL `JSONB` with a SQLite `JSON` variant so tests exercise real serialization behavior.

- [ ] **Step 4: Implement schema enums and inputs/outputs**

Create `backend/app/geo_monitoring/schemas.py` with:

```python
class ProjectStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class BrandType(StrEnum):
    TARGET = "target"
    COMPETITOR = "competitor"
    CANDIDATE = "candidate"


class PromptSetStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=100)
    industry: str = Field(default="文旅演艺", max_length=100)
    description: str | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    official_domain: str | None = Field(default=None, max_length=255)
    report_title: str | None = Field(default=None, max_length=255)
    report_subtitle: str | None = Field(default=None, max_length=500)

    @field_validator("project_name", "industry", "timezone")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value


class RunCreate(BaseModel):
    project_id: int = Field(ge=1)
    prompt_set_id: int | None = Field(default=None, ge=1)
    platform_codes: list[str] | None = None

    @field_validator("platform_codes")
    @classmethod
    def normalize_platform_codes(cls, value):
        if value is None:
            return value
        normalized = list(dict.fromkeys(code.strip() for code in value if code.strip()))
        if not normalized:
            raise ValueError("platform_codes 不能为空")
        return normalized
```

Add matching `Create`, `Update`, and `Out` schemas for all eight models. Every `Out` schema uses `ConfigDict(from_attributes=True)`. Update schemas use optional fields and `model_dump(exclude_unset=True)` semantics.

- [ ] **Step 5: Register only monitoring models**

Rewrite `backend/app/models/__init__.py`:

```python
from app.core.database import Base
from app.geo_monitoring.models import (
    AIPlatform,
    Brand,
    BrandAlias,
    MonitorProject,
    MonitorRun,
    Prompt,
    PromptSet,
    QueryTask,
)
from app.models.base import BaseModel

__all__ = [
    "AIPlatform", "Base", "BaseModel", "Brand", "BrandAlias",
    "MonitorProject", "MonitorRun", "Prompt", "PromptSet", "QueryTask",
]
```

Delete old model files and all old schema files. Keep `backend/app/schemas/__init__.py` only if another generic import still needs the package; otherwise delete the package.

- [ ] **Step 6: Run model tests and full boundary tests**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_models.py tests/test_app_boundary.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit the monitoring model foundation**

```powershell
git add backend/app/geo_monitoring backend/app/models backend/app/schemas backend/tests/geo_monitoring
git commit -m "feat: add ai monitoring domain models"
```

---

### Task 3: Implement Project CRUD

**Files:**
- Create: `backend/app/geo_monitoring/services/projects.py`
- Create: `backend/app/geo_monitoring/services/__init__.py`
- Create: `backend/tests/geo_monitoring/test_projects.py`
- Modify: `backend/app/geo_monitoring/api.py`

- [ ] **Step 1: Write failing project API tests**

```python
def test_project_crud_and_soft_delete(client):
    created = client.post(
        "/api/geo-monitoring/projects",
        json={"project_name": "景区监测", "industry": "文旅"},
    ).json()["data"]
    assert created["status"] == "active"

    listed = client.get("/api/geo-monitoring/projects").json()["data"]
    assert listed["total"] == 1

    updated = client.put(
        f"/api/geo-monitoring/projects/{created['id']}",
        json={"report_title": "AI 可见度监测报告"},
    ).json()["data"]
    assert updated["report_title"] == "AI 可见度监测报告"

    deleted = client.delete(
        f"/api/geo-monitoring/projects/{created['id']}"
    ).json()
    assert deleted["code"] == 0
    assert client.get(
        f"/api/geo-monitoring/projects/{created['id']}"
    ).json()["code"] == 40400
```

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/geo_monitoring/test_projects.py -v`.

Expected: project routes return 404.

- [ ] **Step 3: Implement project service**

Implement `_get_active`, `list_projects`, `create_project`, `update_project`, and `delete_project` in `services/projects.py`. Every query filters `is_deleted=False`; delete sets `is_deleted=True` and `deleted_at=datetime.now(timezone.utc)`.

Use this update pattern:

```python
for field, value in payload.model_dump(exclude_unset=True).items():
    setattr(project, field, value.value if isinstance(value, StrEnum) else value)
```

- [ ] **Step 4: Add project routes**

Add the five routes from the design to `api.py`, using `Depends(get_db)`, `paginate`, `success`, and `ProjectOut.model_validate`.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_projects.py tests/test_app_boundary.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/geo_monitoring backend/tests/geo_monitoring/test_projects.py
git commit -m "feat: add monitoring project api"
```

---

### Task 4: Implement Brand and Alias Management

**Files:**
- Create: `backend/app/geo_monitoring/services/brands.py`
- Create: `backend/tests/geo_monitoring/test_brands.py`
- Modify: `backend/app/geo_monitoring/api.py`

- [ ] **Step 1: Write failing invariant tests**

```python
def test_project_allows_only_one_target_brand(client, project_id):
    first = client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "目标品牌", "brand_type": "target"},
    )
    second = client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "另一个目标", "brand_type": "target"},
    )
    assert first.json()["code"] == 0
    assert second.json()["code"] == 40010


def test_brand_alias_must_be_unique_within_brand(client, target_brand_id):
    path = f"/api/geo-monitoring/brands/{target_brand_id}/aliases"
    assert client.post(path, json={"alias_name": "简称"}).json()["code"] == 0
    assert client.post(path, json={"alias_name": "简称"}).json()["code"] == 40011
```

Add fixtures that create a project and target brand through the API.

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/geo_monitoring/test_brands.py -v`.

Expected: brand and alias routes return 404.

- [ ] **Step 3: Implement brand services and routes**

The service must:

- Validate the parent project/brand is active and not deleted.
- Check for an existing target before creating or changing a brand to `target`.
- Convert SQL unique violations into `BusinessException` with stable codes.
- Soft-delete brands and aliases.
- List brands by project and aliases by brand.

Expose every brand and alias route listed in the design.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_brands.py tests/geo_monitoring/test_projects.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/geo_monitoring backend/tests/geo_monitoring/test_brands.py
git commit -m "feat: add brand and alias management"
```

---

### Task 5: Implement Prompt Set Versioning and Prompt Management

**Files:**
- Create: `backend/app/geo_monitoring/services/prompts.py`
- Create: `backend/tests/geo_monitoring/test_prompts.py`
- Modify: `backend/app/geo_monitoring/api.py`

- [ ] **Step 1: Write failing Prompt lifecycle tests**

```python
def test_activating_prompt_set_archives_previous_active_set(client, project_id):
    first = create_prompt_set(client, project_id, "v1")
    second = create_prompt_set(client, project_id, "v2")
    add_prompt(client, first["id"], "P001", "第一个问题")
    add_prompt(client, second["id"], "P001", "第二个问题")

    client.post(f"/api/geo-monitoring/prompt-sets/{first['id']}/activate")
    client.post(f"/api/geo-monitoring/prompt-sets/{second['id']}/activate")

    assert get_prompt_set(client, first["id"])["status"] == "archived"
    assert get_prompt_set(client, second["id"])["status"] == "active"


def test_active_prompt_set_prompts_are_immutable(client, active_prompt_id):
    response = client.put(
        f"/api/geo-monitoring/prompts/{active_prompt_id}",
        json={"prompt_text": "修改后的问题"},
    )
    assert response.json()["code"] == 40020
```

Also test `prompt_count`, code uniqueness, checksum presence, and deletion only in draft sets.

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/geo_monitoring/test_prompts.py -v`.

Expected: PromptSet and Prompt routes return 404.

- [ ] **Step 3: Implement PromptSet and Prompt services**

Required helpers:

```python
def _content_hash(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.strip().encode("utf-8")).hexdigest()


def _prompt_set_checksum(prompts: list[Prompt]) -> str:
    source = "\n".join(
        f"{p.prompt_code}:{p.content_hash}:{int(p.enabled)}:{p.sort_order}"
        for p in sorted(prompts, key=lambda item: (item.sort_order, item.id))
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
```

Activation must lock the project PromptSet rows, reject empty sets, archive the previous active set, mark the chosen set active, set `activated_at`, and calculate checksum in one transaction.

Prompt create/delete must maintain `prompt_count`. Prompt mutations must reject non-draft sets.

- [ ] **Step 4: Add Prompt routes**

Expose all PromptSet and Prompt routes from the design. List Prompt rows ordered by `sort_order, id`.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_prompts.py tests/geo_monitoring/test_projects.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/geo_monitoring backend/tests/geo_monitoring/test_prompts.py
git commit -m "feat: add versioned prompt configuration"
```

---

### Task 6: Implement AI Platform Configuration

**Files:**
- Create: `backend/app/geo_monitoring/services/platforms.py`
- Create: `backend/tests/geo_monitoring/test_platforms.py`
- Modify: `backend/app/geo_monitoring/api.py`

- [ ] **Step 1: Write failing platform tests**

```python
PLATFORM_CODES = {"doubao", "qwen", "yuanbao", "deepseek", "kimi"}


def test_platform_list_contains_seeded_platforms(client, seed_platforms):
    data = client.get("/api/geo-monitoring/platforms").json()["data"]
    assert {item["platform_code"] for item in data["items"]} == PLATFORM_CODES


def test_platform_code_is_immutable_and_limits_are_validated(client, seed_platforms):
    response = client.put(
        "/api/geo-monitoring/platforms/qwen",
        json={"max_concurrency": 0},
    )
    assert response.json()["code"] == 422
```

The `seed_platforms` fixture inserts the five platform rows into the test database using a shared constant from `services/platforms.py`.

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/geo_monitoring/test_platforms.py -v`.

Expected: placeholder response has no seeded platforms.

- [ ] **Step 3: Implement platform service**

Define:

```python
DEFAULT_PLATFORMS = (
    {"platform_code": "doubao", "platform_name": "豆包", "adapter_type": "openai_compatible"},
    {"platform_code": "qwen", "platform_name": "通义千问", "adapter_type": "openai_compatible"},
    {"platform_code": "yuanbao", "platform_name": "腾讯元宝", "adapter_type": "tencent"},
    {"platform_code": "deepseek", "platform_name": "DeepSeek", "adapter_type": "openai_compatible"},
    {"platform_code": "kimi", "platform_name": "Kimi", "adapter_type": "openai_compatible"},
)
```

Implement list, get, and update operations. Update must never accept `platform_code` and must validate positive concurrency and timeout through Pydantic.

- [ ] **Step 4: Replace the placeholder platform route**

Return paginated data from the real service and add GET detail and PUT update routes.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_platforms.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/geo_monitoring backend/tests/geo_monitoring/test_platforms.py
git commit -m "feat: add ai platform configuration"
```

---

### Task 7: Implement Run Creation and Query Task Fan-Out

**Files:**
- Create: `backend/app/geo_monitoring/services/runs.py`
- Create: `backend/tests/geo_monitoring/test_runs.py`
- Modify: `backend/app/geo_monitoring/api.py`

- [ ] **Step 1: Write failing Cartesian fan-out tests**

```python
def test_create_run_builds_prompt_platform_cartesian_product(
    client, active_project_setup, seed_platforms
):
    setup = active_project_setup(prompt_count=2)
    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": setup.project_id,
            "platform_codes": ["qwen", "deepseek", "kimi"],
        },
    )
    run = response.json()["data"]
    tasks = client.get(
        f"/api/geo-monitoring/runs/{run['id']}/query-tasks"
    ).json()["data"]

    assert run["prompt_set_id"] == setup.prompt_set_id
    assert run["prompt_set_version"] == "v1"
    assert run["expected_query_count"] == 6
    assert tasks["total"] == 6
    assert {
        (task["prompt_id"], task["platform_code"])
        for task in tasks["items"]
    } == {
        (prompt_id, code)
        for prompt_id in setup.prompt_ids
        for code in ("qwen", "deepseek", "kimi")
    }
```

Add tests for:

- defaulting to the active PromptSet;
- defaulting to all enabled platforms;
- rejecting a PromptSet from another project;
- rejecting inactive projects, empty Prompt sets, unknown platforms, or disabled platforms;
- de-duplicating requested platform codes;
- `analysis_status=skipped` and `report_status=skipped`;
- transaction rollback.

Rollback test:

```python
def test_run_creation_rolls_back_when_task_insert_fails(db, complete_run_setup, monkeypatch):
    before_runs = db.scalar(select(func.count()).select_from(MonitorRun))

    def fail_after_run_flush(*args, **kwargs):
        raise RuntimeError("forced fan-out failure")

    monkeypatch.setattr(run_service, "_build_query_tasks", fail_after_run_flush)
    with pytest.raises(RuntimeError, match="forced fan-out failure"):
        run_service.create_run(db, RunCreate(project_id=complete_run_setup.project_id))

    db.rollback()
    after_runs = db.scalar(select(func.count()).select_from(MonitorRun))
    assert after_runs == before_runs
```

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/geo_monitoring/test_runs.py -v`.

Expected: run routes return 404.

- [ ] **Step 3: Implement transactional run creation**

Use this service shape:

```python
def create_run(db: Session, payload: RunCreate) -> MonitorRun:
    project = _require_active_project(db, payload.project_id)
    prompt_set = _resolve_active_prompt_set(db, project.id, payload.prompt_set_id)
    prompts = _enabled_prompts(db, prompt_set.id)
    platforms = _resolve_enabled_platforms(db, payload.platform_codes)

    run = MonitorRun(
        run_no=_new_run_no(),
        project_id=project.id,
        prompt_set_id=prompt_set.id,
        prompt_set_version=prompt_set.version_no,
        trigger_type="manual",
        status="pending",
        collection_status="pending",
        analysis_status="skipped",
        report_status="skipped",
        platform_codes=[platform.platform_code for platform in platforms],
        expected_query_count=len(prompts) * len(platforms),
    )
    db.add(run)
    db.flush()
    _build_query_tasks(db, run, prompts, platforms)
    db.commit()
    db.refresh(run)
    return run
```

`_new_run_no()` must combine UTC time and UUID entropy, for example `RUN-20260615T123456-1A2B3C4D`.

`_build_query_tasks` adds rows only; it does not commit or send Dramatiq messages.

- [ ] **Step 4: Add run routes**

Expose POST/GET `/runs`, GET `/runs/{run_id}`, and GET `/runs/{run_id}/query-tasks`. Run listing supports project, status, and date-independent pagination filters. QueryTask listing supports status and platform code.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/geo_monitoring/test_runs.py -v
```

Expected: all run tests pass, including rollback.

- [ ] **Step 6: Run the complete backend suite**

Run:

```powershell
cd backend
python -m pytest -v
```

Expected: zero failures.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/geo_monitoring backend/tests/geo_monitoring/test_runs.py
git commit -m "feat: add monitoring run task fan-out"
```

---

### Task 8: Remove Remaining Legacy Backend Code and Keep Generic Worker Infrastructure

**Files:**
- Delete: `backend/app/services/` legacy files
- Delete: `backend/app/tasks/`
- Modify: `backend/app/workers/broker.py`
- Modify: `backend/app/workers/worker.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_no_legacy_imports.py`

- [ ] **Step 1: Write a failing repository-boundary test**

```python
from pathlib import Path


FORBIDDEN_NAMES = {
    "keyword.py",
    "title_inspiration.py",
    "image_asset.py",
    "image_category.py",
    "writing_rule.py",
    "writing_task.py",
    "article.py",
    "content_category.py",
}


def test_legacy_backend_modules_are_absent():
    app_dir = Path(__file__).parents[1] / "app"
    remaining = {path.name for path in app_dir.rglob("*.py")}
    assert not FORBIDDEN_NAMES.intersection(remaining)
    assert not (app_dir / "tasks").exists()
    assert not (app_dir / "services" / "ai_generation").exists()
```

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_no_legacy_imports.py -v`.

Expected: legacy files are reported.

- [ ] **Step 3: Delete old services/tasks and simplify worker bootstrap**

Rewrite `backend/app/workers/broker.py` as a generic Redis/Stub broker setup. Remove `CurrentMessage` because no actor needs it yet.

Rewrite `backend/app/workers/worker.py`:

```python
from app.workers.broker import broker

__all__ = ["broker"]
```

Keep `dramatiq[redis]` in runtime requirements. Remove only dependencies or comments specific to the article Mock writer.

- [ ] **Step 4: Verify GREEN and importability**

Run:

```powershell
cd backend
python -m pytest tests/test_no_legacy_imports.py tests/test_app_boundary.py -v
python -c "import app.main; import app.workers.worker; print('imports ok')"
```

Expected: tests pass and output includes `imports ok`.

- [ ] **Step 5: Commit**

```powershell
git add -A backend/app backend/requirements.txt backend/tests/test_no_legacy_imports.py
git commit -m "refactor: remove legacy content generation backend"
```

---

### Task 9: Rebuild Alembic as a Single Monitoring Baseline

**Files:**
- Delete: all existing files in `backend/alembic/versions/`
- Create: `backend/alembic/versions/20260615_0001-ai_monitoring_baseline.py`
- Create: `backend/tests/test_migration_baseline.py`
- Modify: `backend/alembic/env.py`

- [ ] **Step 1: Write failing migration structure tests**

```python
from pathlib import Path


def test_alembic_has_one_monitoring_baseline():
    versions = [
        path
        for path in (Path(__file__).parents[1] / "alembic" / "versions").glob("*.py")
        if path.name != "__init__.py"
    ]
    assert [path.name for path in versions] == [
        "20260615_0001-ai_monitoring_baseline.py"
    ]


def test_baseline_mentions_only_monitoring_business_tables():
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/20260615_0001-ai_monitoring_baseline.py"
    ).read_text(encoding="utf-8")
    assert "geo_monitor_project" in migration
    assert "geo_query_task" in migration
    assert "keyword_library" not in migration
    assert "writing_task" not in migration
```

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_migration_baseline.py -v`.

Expected: multiple legacy revisions are found and the new baseline is absent.

- [ ] **Step 3: Replace migration history**

Delete every old revision and create a baseline with:

```python
revision = "geo_monitoring_0001"
down_revision = None
```

The `upgrade()` function must create the eight tables in dependency order, including:

- PostgreSQL JSONB fields;
- foreign keys and deletion behavior from the design;
- unique constraints;
- check constraints for all status/type fields;
- partial unique indexes for one target brand and one active PromptSet per project;
- query indexes for project/status, Prompt ordering, run/status, and task run/platform/status;
- insertion of the five default platform rows.

The `downgrade()` function drops the tables in reverse dependency order.

- [ ] **Step 4: Verify migration tests and Alembic graph**

Run:

```powershell
cd backend
python -m pytest tests/test_migration_baseline.py -v
alembic heads
alembic history
alembic upgrade head --sql
```

Expected:

- migration tests pass;
- exactly one head: `geo_monitoring_0001`;
- history contains one revision;
- offline SQL contains all eight monitoring tables and no legacy tables.

- [ ] **Step 5: Verify online migration against an empty PostgreSQL database**

Run:

```powershell
docker compose up -d postgres
cd backend
alembic upgrade head
alembic current
```

Expected: `alembic current` reports `geo_monitoring_0001 (head)`.

Because this is a destructive new baseline, use a clean development database/volume. Do not run it against a database containing the old Alembic history.

- [ ] **Step 6: Commit**

```powershell
git add -A backend/alembic backend/tests/test_migration_baseline.py
git commit -m "refactor: rebuild monitoring database baseline"
```

---

### Task 10: Reduce the Frontend to the Monitoring Administration Shell

**Files:**
- Create: `frontend/src/pages/MonitoringHomePage.tsx`
- Create: `frontend/scripts/test-routes.mjs`
- Modify: `frontend/package.json`
- Modify: `frontend/src/router/index.tsx`
- Modify: `frontend/src/layout/MainLayout.tsx`
- Modify: `frontend/src/pages/NotFoundPage.tsx`
- Modify: `frontend/index.html`
- Delete: old pages, API modules, types, and old-only utilities

- [ ] **Step 1: Add a failing static route boundary test**

Create `frontend/scripts/test-routes.mjs`:

```javascript
import { readFile } from 'node:fs/promises'

const router = await readFile(new URL('../src/router/index.tsx', import.meta.url), 'utf8')
const layout = await readFile(new URL('../src/layout/MainLayout.tsx', import.meta.url), 'utf8')
const source = `${router}\n${layout}`

const forbidden = [
  '/material/',
  '/workspace/',
  '关键词库',
  '标题灵感',
  '画像图库',
  '品牌知识库',
  '写作规范',
  '写作任务',
  '文章清单',
]

if (!source.includes('/monitoring')) {
  throw new Error('monitoring route is missing')
}

for (const value of forbidden) {
  if (source.includes(value)) {
    throw new Error(`legacy route or label remains: ${value}`)
  }
}
```

Add to `frontend/package.json`:

```json
"test": "node scripts/test-routes.mjs"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
cd frontend
npm test
```

Expected: failure because `/monitoring` is absent and legacy routes remain.

- [ ] **Step 3: Implement the monitoring-only shell**

Create `frontend/src/pages/MonitoringHomePage.tsx`:

```tsx
import { Card, Result, Typography } from 'antd'

const { Paragraph } = Typography

export default function MonitoringHomePage() {
  return (
    <Card>
      <Result
        status="info"
        title="AI 应用监测基础架构已就绪"
        subTitle="监测项目、品牌、Prompt、平台和运行管理页面将在后续阶段接入。"
        extra={
          <Paragraph type="secondary" style={{ maxWidth: 640, margin: '0 auto' }}>
            当前版本保留管理端框架，并已将后端业务切换为 AI 应用监测领域。
          </Paragraph>
        }
      />
    </Card>
  )
}
```

Rewrite router children to:

```tsx
{ index: true, element: <Navigate to="/monitoring" replace /> },
{ path: 'monitoring', element: <MonitoringHomePage /> },
```

Replace the layout menu with one `/monitoring` item labeled `监测概览`, change product copy to `AI 应用监测`, and remove unused open-key logic and icons.

Change NotFound navigation target to `/monitoring`. Change the HTML title to `AI 应用监测`.

- [ ] **Step 4: Delete old frontend business files**

Delete the directories and files listed in the File Map. Keep `src/api/client.ts`, `src/main.tsx`, `src/layout/MainLayout.tsx`, `src/router/index.tsx`, `src/pages/MonitoringHomePage.tsx`, and `src/pages/NotFoundPage.tsx`.

- [ ] **Step 5: Verify route boundary and production build**

Run:

```powershell
cd frontend
npm test
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit**

```powershell
git add -A frontend
git commit -m "refactor: reduce frontend to monitoring shell"
```

---

### Task 11: Clean Documentation and Rewrite Project Instructions

**Files:**
- Delete: all legacy content under `docs/`
- Keep: `docs/superpowers/specs/2026-06-15-ai-monitoring-domain-replacement-design.md`
- Keep: `docs/superpowers/plans/2026-06-15-ai-monitoring-domain-replacement-plan.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `.env.example`
- Create: `backend/tests/test_documentation_boundary.py`

- [ ] **Step 1: Write failing documentation boundary tests**

```python
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_docs_contains_only_current_superpowers_documents():
    files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "docs").rglob("*")
        if path.is_file()
    }
    assert files == {
        "docs/superpowers/specs/2026-06-15-ai-monitoring-domain-replacement-design.md",
        "docs/superpowers/plans/2026-06-15-ai-monitoring-domain-replacement-plan.md",
    }


def test_claude_instructions_describe_monitoring_only():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AI 应用监测" in text
    assert "/api/geo-monitoring" in text
    assert "关键词库 → 标题灵感" not in text
    assert "写作任务" not in text
```

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_documentation_boundary.py -v` from `backend/`.

Expected: legacy docs and old CLAUDE instructions are reported.

- [ ] **Step 3: Delete legacy docs**

Delete every existing file under `docs/` except the approved spec and this plan. Remove now-empty legacy directories.

- [ ] **Step 4: Rewrite `CLAUDE.md`**

Use these sections:

```markdown
# CLAUDE.md

## 项目定位
本项目是 AI 应用监测平台，用于配置监测项目和 Prompt，采集多个 AI 平台回答，计算确定性指标，并通过 Agent 生成语义分析和改进建议。

## 权威文档
1. `AI应用监测_技术开发文档.md`
2. 当前阶段 `docs/superpowers/specs/` 下已批准的设计
3. 当前阶段 `docs/superpowers/plans/` 下的实施计划

## 当前阶段边界
- 已实现配置域和只落库的运行骨架。
- 未实现真实采集、Agent 分析、指标快照、调度和报告。
- 禁止恢复关键词库、标题灵感、画像图库、内容写作和文章生成模块。

## 技术栈
- 后端：Python、FastAPI、Pydantic、SQLAlchemy、Alembic、PostgreSQL、Redis、Dramatiq。
- 前端：React、TypeScript、Vite、Ant Design、React Router、Axios。

## 后端边界
- 通用基础设施位于 `backend/app/core/`、`backend/app/models/base.py` 和 `backend/app/workers/`。
- 监测业务位于 `backend/app/geo_monitoring/`。
- 对外接口统一使用 `/api/geo-monitoring`。

## 当前领域模型
- `MonitorProject`：监测项目。
- `Brand`、`BrandAlias`：目标品牌、竞品和别名。
- `PromptSet`、`Prompt`：版本化问题集。
- `AIPlatform`：AI 平台配置。
- `MonitorRun`、`QueryTask`：监测运行和查询子任务。

## 核心工程规则
- 采集、分析、报告分阶段解耦。
- 外部 API 和 LLM 调用不得运行在数据库长事务内。
- 数值指标必须由 SQL/Python 确定性计算；LLM 不得修改数值结果。
- 平台失败相互隔离，未来运行允许 `partial_success`。
- 趋势比较必须限定同一 Prompt 集版本。
- 所有新增表结构必须有 Alembic 迁移。
- 所有行为变更必须先写失败测试，再实现并验证。
- 使用 UTF-8 读取和修改中文文档。

## 验证要求
- 后端：`python -m pytest -v`
- 迁移：`alembic heads`、`alembic upgrade head --sql`
- 前端：`npm test`、`npm run build`

## 统一响应
普通接口返回 `{ "code": 0, "message": "success", "data": {} }`。分页接口的 `data` 包含 `items`、`total`、`page`、`page_size`。

## 数据与状态规则
- 所有业务表继承公共主键、时间、软删除、租户和操作人字段。
- 项目状态：`active | disabled | archived`。
- 品牌类型：`target | competitor | candidate`，每个项目最多一个有效目标品牌。
- Prompt 集状态：`draft | active | archived`，每个项目最多一个 active 版本。
- 运行状态预留：`pending | collecting | analyzing | reporting | completed | partial_success | failed | cancelled`。
- 查询任务状态预留：`pending | queued | running | success | failed | cancelled`。

## 开发流程
1. 阅读本文件、业务技术文档、当前批准的 spec 和 plan。
2. 检查现有代码与迁移，明确单次任务边界。
3. 先写失败测试并确认失败原因正确。
4. 实现最小行为，运行相关测试。
5. 运行完整后端测试、迁移验证和前端构建。
6. 说明修改文件、验证命令和剩余限制。

## 禁止事项
- 禁止恢复关键词库、标题灵感、画像图库、写作规范、写作任务和文章生成模块。
- 禁止在数据库事务中调用外部 AI 平台或 LLM。
- 禁止让 LLM 生成或修改确定性统计指标。
- 禁止提交没有测试、没有迁移或无法验证的业务变更。
- 禁止在日志、数据库普通配置字段或仓库中保存明文平台密钥。
```

Write `CLAUDE.md` exactly from the content block above; do not reference deleted docs or reintroduce old task numbering.

- [ ] **Step 5: Update README and environment template**

README must describe only:

- AI application monitoring purpose;
- current implemented scope;
- backend/frontend startup;
- PostgreSQL/Redis startup;
- migrations and tests;
- explicit note that real collection and analysis are not implemented yet.

Remove Mock article worker instructions. Keep Redis/Dramatiq variables for future collection workers. Replace old AI writer variables with future platform adapter guidance; do not add provider secrets until adapters are implemented.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/test_documentation_boundary.py -v
```

Expected: both tests pass.

- [ ] **Step 7: Commit**

```powershell
git add -A docs CLAUDE.md README.md .env.example backend/tests/test_documentation_boundary.py
git commit -m "docs: align repository with ai monitoring product"
```

---

### Task 12: Final End-to-End Verification

**Files:**
- No production changes expected.

- [ ] **Step 1: Run the complete backend test suite**

```powershell
cd backend
python -m pytest -v
```

Expected: zero failed tests.

- [ ] **Step 2: Verify imports and OpenAPI boundary**

```powershell
cd backend
python -c "from app.main import app; paths=app.openapi()['paths']; assert '/api/geo-monitoring/projects' in paths; assert '/api/keywords' not in paths; print(len(paths), 'paths verified')"
```

Expected: command exits 0 and prints the path count.

- [ ] **Step 3: Verify Alembic**

```powershell
cd backend
alembic heads
alembic history
alembic upgrade head --sql
```

Expected: one head and offline SQL generation without errors.

- [ ] **Step 4: Verify frontend**

```powershell
cd frontend
npm test
npm run build
```

Expected: route test and production build both exit 0.

- [ ] **Step 5: Search for forbidden legacy product references**

Run from repository root:

```powershell
rg -n "关键词库|标题灵感|画像图库|写作规范|写作任务|文章清单|MockAIWriter|/api/keywords|/workspace/|/material/" backend frontend CLAUDE.md README.md
```

Expected: no matches. Matches inside the approved historical design/spec are allowed only where they explain what was removed.

- [ ] **Step 6: Inspect repository status and diff**

```powershell
git status --short
git diff --stat 83b0d5e..HEAD
git diff --check
```

Expected: no uncommitted implementation files, no whitespace errors, and changes limited to the approved replacement scope.

- [ ] **Step 7: Record final result**

Report:

- removed legacy backend/frontend modules;
- new monitoring models and API paths;
- migration head ID;
- backend test count and result;
- frontend test/build result;
- any skipped online PostgreSQL verification with the exact reason.
