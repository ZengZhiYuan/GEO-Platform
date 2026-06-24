# Aidso Collection Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-selectable Aidso collection source that can collect Web/App AI answers through Aidso while preserving the existing official-provider collection and analysis pipeline.

**Architecture:** `MonitorRun.collection_source` chooses the collection data source; `platform_codes` remain the platform/display/analysis dimension. Aidso platform codes are stored in `geo_ai_platform`, Aidso `reqId/taskId` is persisted in `QueryTask.request_json`, and successful Aidso responses are normalized into the existing `PlatformAnswer` shape.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic, httpx, pytest, respx, Dramatiq.

---

## File Structure

- Modify `backend/app/geo_monitoring/schemas.py`: add `CollectionSource`, `RunCreate.collection_source`, `RunCreate.aidso_thinking_enabled`, and response fields.
- Modify `backend/app/geo_monitoring/models.py`: add `MonitorRun.collection_source` and `MonitorRun.aidso_thinking_enabled`.
- Create `backend/alembic/versions/20260624_0007-geo_monitoring_0007_aidso_collection_source.py`: add run columns and seed Aidso platform rows.
- Modify `backend/app/geo_monitoring/services/runs.py`: validate platforms by collection source, persist run source/options, and set Aidso task retry attempts.
- Modify `backend/app/geo_monitoring/services/platforms.py`: add Aidso platform catalog constants and mapping metadata.
- Modify `backend/app/core/config.py`: add Aidso token/base URL config and runtime summaries.
- Modify `backend/app/geo_monitoring/adapters/base.py`: add `PlatformQuery.metadata` for persisted source-specific state.
- Create `backend/app/geo_monitoring/adapters/aidso.py`: submit/poll Aidso API and convert results to `PlatformAnswer`.
- Modify `backend/app/geo_monitoring/adapters/registry.py`: register Aidso adapters when configured.
- Modify `backend/app/geo_monitoring/services/collection.py`: pass task `request_json` into `PlatformQuery`, persist Aidso pending metadata, and use existing answer persistence after success.
- Modify `.env.example`, `README.md`, and `docs/API接口文档.md`: document Aidso config and run payload.
- Add/modify tests under `backend/tests/geo_monitoring/`, `backend/tests/geo_monitoring/adapters/`, `backend/tests/worker/`, and `backend/tests/test_config.py`.

---

### Task 1: Run Schema And Migration

**Files:**
- Modify: `backend/app/geo_monitoring/schemas.py`
- Modify: `backend/app/geo_monitoring/models.py`
- Modify: `backend/app/geo_monitoring/services/runs.py`
- Create: `backend/alembic/versions/20260624_0007-geo_monitoring_0007_aidso_collection_source.py`
- Test: `backend/tests/geo_monitoring/test_models.py`
- Test: `backend/tests/geo_monitoring/test_runs.py`

- [ ] **Step 1: Write failing schema/model tests**

Add tests that document the public API and ORM defaults:

```python
def test_run_create_defaults_to_official_collection_source():
    run = RunCreate(project_id=1, platform_codes=[" qwen ", "qwen"])
    assert run.collection_source == "official"
    assert run.aidso_thinking_enabled is True
    assert run.platform_codes == ["qwen"]


def test_run_create_accepts_aidso_collection_source():
    run = RunCreate(
        project_id=1,
        collection_source="aidso",
        aidso_thinking_enabled=False,
        platform_codes=["aidso_doubao_web"],
    )
    assert run.collection_source == "aidso"
    assert run.aidso_thinking_enabled is False
```

Add an API-level test in `test_runs.py`:

```python
def test_create_aidso_run_persists_collection_source(
    client, session_factory, project_id
):
    setup = _active_prompt_setup(client, project_id, prompt_count=1)
    with session_factory() as db:
        db.add(
            AIPlatform(
                platform_code="aidso_doubao_web",
                platform_name="豆包 Web 端",
                adapter_type="aidso",
                model_name="aidso:DB",
                enabled=True,
                extra_config={"aidso_name": "DB"},
            )
        )
        db.commit()

    response = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "aidso",
            "aidso_thinking_enabled": False,
            "platform_codes": ["aidso_doubao_web"],
        },
    ).json()

    run = response["data"]
    assert response["code"] == 0
    assert run["prompt_set_id"] == setup["prompt_set"]["id"]
    assert run["collection_source"] == "aidso"
    assert run["aidso_thinking_enabled"] is False
    assert run["platform_codes"] == ["aidso_doubao_web"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\geo_monitoring\test_models.py backend\tests\geo_monitoring\test_runs.py -q
```

Expected: failures mention missing `collection_source` or missing `aidso_thinking_enabled`.

- [ ] **Step 3: Add schema/model fields**

Implement:

```python
class CollectionSource(StrEnum):
    OFFICIAL = "official"
    AIDSO = "aidso"


class RunCreate(BaseModel):
    project_id: int = Field(ge=1)
    prompt_set_id: int | None = Field(default=None, ge=1)
    platform_codes: list[str] | None = None
    collection_source: CollectionSource = CollectionSource.OFFICIAL
    aidso_thinking_enabled: bool = True
```

Add `collection_source: str` and `aidso_thinking_enabled: bool` to `MonitorRunOut` and `RunDetailRead` through inheritance.

Add model columns:

```python
collection_source: Mapped[str] = mapped_column(
    String(20), default="official", server_default="official", nullable=False
)
aidso_thinking_enabled: Mapped[bool] = mapped_column(
    Boolean, default=True, server_default=text("true"), nullable=False
)
```

Extend `MonitorRun.__table_args__` with:

```python
CheckConstraint(
    "collection_source IN ('official', 'aidso')",
    name="ck_geo_monitor_run_collection_source",
)
```

- [ ] **Step 4: Add migration**

Create revision `geo_monitoring_0007`, down revision `geo_monitoring_0006`, and add:

```python
op.add_column(
    "geo_monitor_run",
    sa.Column(
        "collection_source",
        sa.String(length=20),
        server_default="official",
        nullable=False,
    ),
)
op.add_column(
    "geo_monitor_run",
    sa.Column(
        "aidso_thinking_enabled",
        sa.Boolean(),
        server_default=sa.text("true"),
        nullable=False,
    ),
)
op.create_check_constraint(
    "ck_geo_monitor_run_collection_source",
    "geo_monitor_run",
    "collection_source IN ('official', 'aidso')",
)
```

Downgrade drops the check constraint and both columns.

- [ ] **Step 5: Persist fields in run creation**

In `create_run`, set:

```python
collection_source=payload.collection_source.value,
aidso_thinking_enabled=payload.aidso_thinking_enabled,
```

- [ ] **Step 6: Run tests to verify green**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\geo_monitoring\test_models.py backend\tests\geo_monitoring\test_runs.py -q
```

Expected: the Task 1 tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend\app\geo_monitoring\schemas.py backend\app\geo_monitoring\models.py backend\app\geo_monitoring\services\runs.py backend\alembic\versions\20260624_0007-geo_monitoring_0007_aidso_collection_source.py backend\tests\geo_monitoring\test_models.py backend\tests\geo_monitoring\test_runs.py
git commit -m "feat(collection): add run collection source fields"
```

---

### Task 2: Aidso Platform Catalog And Source Validation

**Files:**
- Modify: `backend/app/geo_monitoring/services/platforms.py`
- Modify: `backend/app/geo_monitoring/services/runs.py`
- Modify: `backend/alembic/versions/20260624_0007-geo_monitoring_0007_aidso_collection_source.py`
- Test: `backend/tests/geo_monitoring/test_platforms.py`
- Test: `backend/tests/geo_monitoring/test_runs.py`

- [ ] **Step 1: Write failing catalog and validation tests**

Add tests:

```python
def test_platform_catalog_includes_aidso_endpoint_platforms(client, session_factory):
    _seed_platforms(session_factory)
    listed = client.get("/api/geo-monitoring/platforms", params={"page_size": 50}).json()["data"]
    codes = {item["platform_code"] for item in listed["items"]}
    assert "aidso_doubao_web" in codes
    assert "aidso_doubao_app" in codes
    assert "aidso_qwen_app" in codes


def test_official_run_rejects_aidso_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    body = client.post(
        "/api/geo-monitoring/runs",
        json={"project_id": project_id, "platform_codes": ["aidso_doubao_web"]},
    ).json()
    assert body["code"] == 40031


def test_aidso_run_rejects_official_platform(client, session_factory, project_id):
    _active_prompt_setup(client, project_id, prompt_count=1)
    _seed_platforms(session_factory)
    body = client.post(
        "/api/geo-monitoring/runs",
        json={
            "project_id": project_id,
            "collection_source": "aidso",
            "platform_codes": ["qwen"],
        },
    ).json()
    assert body["code"] == 40031
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\geo_monitoring\test_platforms.py backend\tests\geo_monitoring\test_runs.py -q
```

Expected: missing Aidso platform codes and source validation failures.

- [ ] **Step 3: Add Aidso platform catalog**

In `platforms.py`, define:

```python
AIDSO_PLATFORM_MAPPINGS = {
    "aidso_doubao_web": {"aidso_name": "DB", "platform_name": "豆包 Web 端"},
    "aidso_doubao_app": {"aidso_name": "DOUBA", "platform_name": "豆包 App 端"},
    "aidso_deepseek_web": {"aidso_name": "DP", "platform_name": "DeepSeek Web 端"},
    "aidso_deepseek_app": {"aidso_name": "DPA", "platform_name": "DeepSeek App 端"},
    "aidso_kimi_web": {"aidso_name": "KIMI", "platform_name": "Kimi Web 端"},
    "aidso_yuanbao_web": {"aidso_name": "TXYB", "platform_name": "元宝 Web 端"},
    "aidso_yuanbao_app": {"aidso_name": "TXYBA", "platform_name": "元宝 App 端"},
    "aidso_qwen_web": {"aidso_name": "TYQW", "platform_name": "千问 Web 端"},
    "aidso_qwen_app": {"aidso_name": "TYQWA", "platform_name": "千问 App 端"},
    "aidso_baidu_web": {"aidso_name": "BDAI", "platform_name": "百度 AI"},
    "aidso_douyin_web": {"aidso_name": "DYAI", "platform_name": "抖音 AI"},
    "aidso_wenxin_web": {"aidso_name": "WXYY", "platform_name": "文心一言"},
}
```

Append rows to `DEFAULT_PLATFORMS` with `adapter_type="aidso"`, `citation_supported=True`, `model_name=f"aidso:{aidso_name}"`, and `extra_config={"aidso_name": aidso_name}`.

- [ ] **Step 4: Seed Aidso platforms in migration**

In migration upgrade, `bulk_insert` rows into `geo_ai_platform` with the Aidso platform codes above. Use `adapter_type="aidso"`, `citation_supported=True`, `search_enabled=True`, `enabled=True`, `max_concurrency=2`, `timeout_seconds=120`, and JSON `extra_config`.

Downgrade deletes rows where `platform_code` starts with `aidso_`.

- [ ] **Step 5: Validate platforms by source**

In `_resolve_platforms`, accept `collection_source` and filter candidates:

```python
expected_adapter_type = "aidso" if collection_source == "aidso" else None
```

For official runs, reject platforms with `adapter_type == "aidso"`. For Aidso runs, reject platforms unless `adapter_type == "aidso"`. Preserve request order and existing `40031` behavior.

- [ ] **Step 6: Run tests to verify green**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\geo_monitoring\test_platforms.py backend\tests\geo_monitoring\test_runs.py -q
```

Expected: catalog and source validation tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend\app\geo_monitoring\services\platforms.py backend\app\geo_monitoring\services\runs.py backend\alembic\versions\20260624_0007-geo_monitoring_0007_aidso_collection_source.py backend\tests\geo_monitoring\test_platforms.py backend\tests\geo_monitoring\test_runs.py
git commit -m "feat(platforms): add aidso endpoint platform catalog"
```

---

### Task 3: Aidso Runtime Configuration And Registry

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/geo_monitoring/adapters/registry.py`
- Modify: `backend/app/geo_monitoring/services/collection.py`
- Test: `backend/tests/test_config.py`
- Test: `backend/tests/geo_monitoring/adapters/test_registry.py`

- [ ] **Step 1: Write failing config and registry tests**

Add tests:

```python
def test_enabled_aidso_requires_token(tmp_path):
    with pytest.raises(ValueError, match="AIDSO_API_TOKEN"):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            REDIS_URL="redis://localhost:6379/0",
            REPORT_STORAGE_DIR=str(tmp_path),
            AIDSO_ENABLED=True,
            AIDSO_API_TOKEN="",
        )


def test_aidso_token_is_redacted_from_runtime_summary(tmp_path):
    settings = Settings(
        _env_file=None,
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/0",
        REPORT_STORAGE_DIR=str(tmp_path),
        AIDSO_ENABLED=True,
        AIDSO_API_TOKEN="aidso-secret-token",
    )
    rendered = repr(settings.runtime_summary())
    assert "aidso-secret-token" not in rendered
    assert settings.runtime_summary()["platforms"]["aidso"]["enabled"] is True
```

Add registry test:

```python
def test_build_adapter_registry_registers_aidso_platforms_when_configured():
    registry = build_adapter_registry(
        _runtime_settings(
            AIDSO_ENABLED=True,
            AIDSO_BASE_URL="https://aidso.test",
            AIDSO_API_TOKEN="aidso-token",
        )
    )
    assert "aidso_doubao_web" in registry.registered_codes()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py backend\tests\geo_monitoring\adapters\test_registry.py -q
```

Expected: missing settings fields and no Aidso registry entries.

- [ ] **Step 3: Add config fields**

In `Settings`:

```python
AIDSO_ENABLED: bool = False
AIDSO_BASE_URL: str = "https://odapi.aidso.com"
AIDSO_API_TOKEN: str = ""
```

In `validate_runtime_contract`, require token when enabled. Add runtime summary:

```python
"aidso": {
    "enabled": self.AIDSO_ENABLED,
    "base_url": self.AIDSO_BASE_URL,
    "has_token": bool(self.AIDSO_API_TOKEN.strip()),
}
```

- [ ] **Step 4: Register Aidso credentials and adapters**

In `build_credential_key_pool`, register `ApiKeyCredential` for each Aidso platform code when `AIDSO_API_TOKEN` is present.

In `build_adapter_registry`, register an `AidsoAdapter` instance per Aidso platform code when `_aidso_configured(runtime_settings)` is true.

- [ ] **Step 5: Run tests to verify green**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py backend\tests\geo_monitoring\adapters\test_registry.py -q
```

Expected: Aidso config validation, redaction, and registry tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend\app\core\config.py backend\app\geo_monitoring\adapters\registry.py backend\app\geo_monitoring\services\collection.py backend\tests\test_config.py backend\tests\geo_monitoring\adapters\test_registry.py
git commit -m "feat(config): add aidso runtime configuration"
```

---

### Task 4: Aidso Adapter

**Files:**
- Modify: `backend/app/geo_monitoring/adapters/base.py`
- Create: `backend/app/geo_monitoring/adapters/aidso.py`
- Test: `backend/tests/geo_monitoring/adapters/test_aidso.py`

- [ ] **Step 1: Write failing adapter tests**

Create tests for submit, poll success, pending, existing reqId reuse, quote parsing, and token redaction:

```python
def _query(metadata=None):
    return PlatformQuery(
        prompt="100w汽车推荐",
        system_prompt=None,
        model="aidso:DB",
        temperature=None,
        request_id="task-1",
        metadata=metadata or {"aidso_thinking_enabled": False},
    )


@respx.mock
def test_aidso_submits_then_polls_success_response():
    commit_route = respx.post("https://aidso.test/open/mt/task_commit").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "reqIds": {"DB": "req-db-1"},
                    "taskId": "task-aidso-1",
                },
                "msg": "ok",
            },
        )
    )
    respx.get("https://aidso.test/open/mt/get_result").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "prompt": "100w汽车推荐",
                    "status": "SUCCESS",
                    "result": [
                        {"context": "推荐目标品牌。FINISHED"},
                        {"quote": "[{\"url\":\"https://example.com/a\",\"title\":\"引用\",\"snippet\":\"摘要\"}]"},
                    ],
                },
                "msg": "success",
            },
        )
    )

    answer = asyncio.run(
        AidsoAdapter(
            code="aidso_doubao_web",
            aidso_name="DB",
            base_url="https://aidso.test",
            timeout_seconds=0.2,
        ).query(
            _query(),
            credential=PlatformCredential(
                platform_code="aidso_doubao_web",
                fingerprint="fp",
                api_key="aidso-token",
            ),
        )
    )

    payload = json.loads(commit_route.calls.last.request.content.decode("utf-8"))
    assert payload["platform"] == [{"name": "DB", "thinkingEnabled": 0}]
    assert answer.text == "推荐目标品牌。FINISHED"
    assert answer.citations[0]["url"] == "https://example.com/a"
    assert answer.provider_request_id == "req-db-1"
```

Add a pending test that expects `AidsoPendingError` with `pending_metadata["aidso_req_id"] == "req-db-1"`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\geo_monitoring\adapters\test_aidso.py -q
```

Expected: import errors for missing adapter and missing `PlatformQuery.metadata`.

- [ ] **Step 3: Extend `PlatformQuery`**

Add:

```python
metadata: dict[str, Any] = field(default_factory=dict)
```

Existing adapter tests should keep passing because this field has a default.

- [ ] **Step 4: Implement Aidso adapter**

Implement `AidsoAdapter` with:

- `_submit_task()` posts `/open/mt/task_commit`.
- `_get_result()` gets `/open/mt/get_result?reqId=...`.
- `_extract_context()` scans `data.result` for a non-empty `context`.
- `_extract_citations()` scans `data.result` for `quote`, parses JSON strings or list values, and maps `snippet` to `quoted_text`.
- `AidsoPendingError(AdapterError)` carries `pending_metadata`.
- all errors include `secrets=(api_key,)`.

- [ ] **Step 5: Run adapter tests to verify green**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\geo_monitoring\adapters\test_aidso.py backend\tests\geo_monitoring\adapters\test_qwen.py -q
```

Expected: Aidso tests pass and existing adapter contract remains compatible.

- [ ] **Step 6: Commit**

```powershell
git add backend\app\geo_monitoring\adapters\base.py backend\app\geo_monitoring\adapters\aidso.py backend\tests\geo_monitoring\adapters\test_aidso.py
git commit -m "feat(adapter): add aidso collection adapter"
```

---

### Task 5: Collection Service Aidso State Reuse

**Files:**
- Modify: `backend/app/geo_monitoring/services/collection.py`
- Test: `backend/tests/worker/test_collection_actor.py`

- [ ] **Step 1: Write failing collection tests**

Add a mock Aidso adapter that raises `AidsoPendingError` on first call and succeeds on second when metadata contains `aidso_req_id`.

Test expectations:

```python
def test_aidso_pending_persists_req_id_and_reuses_on_retry(...):
    dispatch_task(seeded["task_id"])
    with session_factory() as db:
        task = db.get(QueryTask, seeded["task_id"])
        assert task.status == "success"
        assert task.request_json["aidso_req_id"] == "req-db-1"
        assert task.provider_request_id == "req-db-1"
```

Also assert the second adapter call receives:

```python
adapter.calls[1][0].metadata["aidso_req_id"] == "req-db-1"
adapter.calls[1][0].metadata["aidso_thinking_enabled"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\worker\test_collection_actor.py -q
```

Expected: pending metadata is not persisted or not passed back to the adapter.

- [ ] **Step 3: Add snapshot fields**

Extend `TaskSnapshot`:

```python
collection_source: str
aidso_thinking_enabled: bool
request_json: dict[str, Any] | None
```

Populate from `MonitorRun` and `QueryTask`.

- [ ] **Step 4: Pass metadata to adapter**

Build metadata:

```python
metadata = dict(snapshot.request_json or {})
metadata["collection_source"] = snapshot.collection_source
metadata["aidso_thinking_enabled"] = snapshot.aidso_thinking_enabled
```

Pass it into `PlatformQuery`.

- [ ] **Step 5: Persist pending Aidso metadata**

In `_handle_adapter_failure`, if the error has `pending_metadata`, merge it into `task.request_json`, set `task.provider_request_id` if present, then continue with existing retry logic.

- [ ] **Step 6: Run collection tests to verify green**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\worker\test_collection_actor.py -q
```

Expected: all collection actor tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend\app\geo_monitoring\services\collection.py backend\tests\worker\test_collection_actor.py
git commit -m "feat(collection): reuse aidso request ids across retries"
```

---

### Task 6: Documentation And Examples

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/API接口文档.md`

- [ ] **Step 1: Update docs**

Add `.env.example` entries:

```dotenv
AIDSO_ENABLED=false
AIDSO_BASE_URL=https://odapi.aidso.com
AIDSO_API_TOKEN=
```

Add run example:

```json
{
  "project_id": 1,
  "collection_source": "aidso",
  "aidso_thinking_enabled": false,
  "platform_codes": ["aidso_doubao_web", "aidso_doubao_app"]
}
```

Update API docs `RunCreate` and `MonitorRunOut` field tables with `collection_source` and `aidso_thinking_enabled`.

- [ ] **Step 2: Run documentation boundary tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_documentation_boundary.py backend\tests\test_api_contract.py -q
```

Expected: docs and API contract tests pass.

- [ ] **Step 3: Commit**

```powershell
git add .env.example README.md docs\API接口文档.md
git commit -m "docs: document aidso collection source"
```

---

### Task 7: Full Verification And CodeGraph

**Files:**
- No new source files.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py backend\tests\geo_monitoring\test_models.py backend\tests\geo_monitoring\test_platforms.py backend\tests\geo_monitoring\test_runs.py backend\tests\geo_monitoring\adapters\test_registry.py backend\tests\geo_monitoring\adapters\test_aidso.py backend\tests\worker\test_collection_actor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run migration tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_migrations.py backend\tests\test_migration_roundtrip.py -q
```

Expected: migrations apply and downgrade/upgrade roundtrip passes.

- [ ] **Step 3: Run full backend test suite**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: all backend tests pass.

- [ ] **Step 4: Sync CodeGraph**

Run from repository root:

```powershell
codegraph status
codegraph sync
codegraph status
```

Expected: CodeGraph sync completes, or any failure is reported with the exact command output summary.

- [ ] **Step 5: Final status**

Review:

```powershell
git status --short
git log --oneline -5
```

Expected: only intended files changed, with implementation commits present.
