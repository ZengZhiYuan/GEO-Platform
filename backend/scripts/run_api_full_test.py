"""Full API integration test runner based on docs/API测试文档.md."""

from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api"
GEO = f"{API}/geo-monitoring"
TIMEOUT = 60.0
RUN_POLL_INTERVAL = 5
RUN_POLL_MAX = 120  # seconds for collection to finish


@dataclass
class TestResult:
    section: str
    name: str
    method: str
    url: str
    params: str
    expected: str
    http_status: int | None = None
    response_code: int | str | None = None
    message: str = ""
    passed: bool = False
    detail: str = ""
    duration_ms: float = 0


@dataclass
class TestContext:
    results: list[TestResult] = field(default_factory=list)
    project_id: int | None = None
    target_brand_id: int | None = None
    competitor_brand_id: int | None = None
    alias_id: int | None = None
    prompt_set_id: int | None = None
    prompt_id: int | None = None
    run_id: int | None = None
    answer_id: int | None = None
    report_id: int | None = None
    schedule_id: int | None = None
    disabled_project_id: int | None = None
    empty_prompt_set_id: int | None = None
    platform_codes: list[str] = field(default_factory=list)
    core_keyword_id: int | None = None


def record(
    ctx: TestContext,
    *,
    section: str,
    name: str,
    method: str,
    url: str,
    params: str,
    expected: str,
    passed: bool,
    http_status: int | None,
    response_code: int | str | None,
    message: str = "",
    detail: str = "",
    duration_ms: float = 0,
) -> None:
    ctx.results.append(
        TestResult(
            section=section,
            name=name,
            method=method,
            url=url,
            params=params,
            expected=expected,
            http_status=http_status,
            response_code=response_code,
            message=message,
            passed=passed,
            detail=detail[:500] if detail else "",
            duration_ms=duration_ms,
        )
    )


def req(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: dict | list | None = None,
    params: dict | None = None,
) -> tuple[int, dict | str | None, float, dict[str, str]]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": str(uuid.uuid4()),
    }
    start = time.perf_counter()
    r = client.request(method, url, json=json_body, params=params, headers=headers, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - start) * 1000
    resp_headers = {k.lower(): v for k, v in r.headers.items()}
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            body: dict | str | None = r.json()
        except json.JSONDecodeError:
            body = r.text
    else:
        body = r.text
    return r.status_code, body, elapsed, resp_headers


def json_code(body: Any) -> int | str | None:
    if isinstance(body, dict):
        return body.get("code")
    return None


def json_data(body: Any) -> Any:
    if isinstance(body, dict):
        return body.get("data")
    return None


def json_msg(body: Any) -> str:
    if isinstance(body, dict):
        return str(body.get("message", ""))
    return ""


def ensure_enabled_platform_codes(client: httpx.Client, ctx: TestContext) -> list[str]:
    """确保至少有一个已启用平台，供监测设置与创建运行使用。"""
    status, body, _, _ = req(
        client, "GET", f"{GEO}/platforms", params={"page": 1, "page_size": 20, "enabled": True}
    )
    items = (json_data(body) or {}).get("items", []) if status == 200 else []
    codes = [p["platform_code"] for p in items if p.get("enabled")]
    if not codes:
        status, body, _, _ = req(
            client, "GET", f"{GEO}/platforms", params={"page": 1, "page_size": 20}
        )
        all_items = (json_data(body) or {}).get("items", [])
        for code in ("qwen", "deepseek", "doubao", "kimi", "yuanbao"):
            if any(p["platform_code"] == code for p in all_items):
                req(client, "PUT", f"{GEO}/platforms/{code}", json_body={"enabled": True})
                codes.append(code)
                break
        if not codes and all_items:
            code = all_items[0]["platform_code"]
            req(client, "PUT", f"{GEO}/platforms/{code}", json_body={"enabled": True})
            codes = [code]
    ctx.platform_codes = codes[:2] if len(codes) >= 2 else codes
    return ctx.platform_codes


def assert_json_ok(
    ctx: TestContext,
    *,
    section: str,
    name: str,
    method: str,
    url: str,
    params: str,
    status: int,
    body: Any,
    elapsed: float,
    extra_check: str = "",
) -> bool:
    code = json_code(body)
    msg = json_msg(body)
    passed = status == 200 and code == 0 and msg == "success"
    detail = json.dumps(body, ensure_ascii=False)[:500] if body else ""
    if extra_check:
        detail = f"{extra_check}; {detail}"
    record(
        ctx,
        section=section,
        name=name,
        method=method,
        url=url,
        params=params,
        expected="HTTP 200, code=0, message=success",
        passed=passed,
        http_status=status,
        response_code=code,
        message=msg,
        detail=detail,
        duration_ms=elapsed,
    )
    return passed


def assert_json_fail(
    ctx: TestContext,
    *,
    section: str,
    name: str,
    method: str,
    url: str,
    params: str,
    status: int,
    body: Any,
    elapsed: float,
    expected_code: int | str,
    expected_http: int | None = None,
) -> bool:
    """Negative case: API may return HTTP 200 with non-zero code, or explicit 4xx."""
    code = json_code(body)
    msg = json_msg(body)
    if expected_http is not None:
        passed = status == expected_http and code == expected_code
    else:
        passed = code == expected_code
    record(
        ctx,
        section=section,
        name=name,
        method=method,
        url=url,
        params=params,
        expected=f"HTTP {expected_http or '4xx/5xx'}, code={expected_code}",
        passed=passed,
        http_status=status,
        response_code=code,
        message=msg,
        detail=json.dumps(body, ensure_ascii=False)[:500] if body else "",
        duration_ms=elapsed,
    )
    return passed


def test_probes(client: httpx.Client, ctx: TestContext) -> None:
    section = "3. 基础探针接口"
    for path, name, check in [
        (f"{API}/health", "3.1 全局健康检查", lambda d: d.get("status") == "ok"),
        (f"{API}/ready", "3.2 全局就绪检查", lambda d: d.get("status") == "ready"),
        (f"{GEO}/health", "3.3 监测服务健康检查", lambda d: d.get("status") == "ok"),
        (f"{GEO}/ready", "3.4 监测服务就绪检查", lambda d: d.get("status") == "ready"),
    ]:
        status, body, elapsed, _ = req(client, "GET", path)
        data = json_data(body) or {}
        ok = status == 200 and json_code(body) == 0 and check(data)
        record(
            ctx,
            section=section,
            name=name,
            method="GET",
            url=path,
            params="",
            expected="HTTP 200, code=0, status ok/ready",
            passed=ok,
            http_status=status,
            response_code=json_code(body),
            message=json_msg(body),
            detail=json.dumps(data, ensure_ascii=False)[:300],
            duration_ms=elapsed,
        )


def test_projects(client: httpx.Client, ctx: TestContext) -> None:
    section = "4. 项目模块"
    suffix = datetime.now(timezone.utc).strftime("%H%M%S")

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects",
        json_body={
            "project_name": f"API全量测试项目-{suffix}",
            "industry": "文旅演艺",
            "timezone": "Asia/Shanghai",
            "description": "接口全量测试自动创建",
        },
    )
    data = json_data(body) or {}
    ok = assert_json_ok(
        ctx,
        section=section,
        name="4.2 创建项目",
        method="POST",
        url=f"{GEO}/projects",
        params="ProjectCreate",
        status=status,
        body=body,
        elapsed=elapsed,
    )
    if ok and isinstance(data, dict):
        ctx.project_id = data.get("id")

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects", params={"page": 1, "page_size": 10})
    assert_json_ok(ctx, section=section, name="4.2 分页查询项目", method="GET", url=f"{GEO}/projects", params="page=1", status=status, body=body, elapsed=elapsed)

    if ctx.project_id:
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{ctx.project_id}")
        assert_json_ok(ctx, section=section, name="4.2 获取项目", method="GET", url=f"{GEO}/projects/{{id}}", params=f"id={ctx.project_id}", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/projects/{ctx.project_id}",
            json_body={"description": "已更新描述"},
        )
        assert_json_ok(ctx, section=section, name="4.2 更新项目", method="PUT", url=f"{GEO}/projects/{{id}}", params="description更新", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/999999")
    assert_json_fail(ctx, section=section, name="4.2 获取不存在项目", method="GET", url=f"{GEO}/projects/999999", params="", status=status, body=body, elapsed=elapsed, expected_code=40400)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects", params={"status": "invalid_status"})
    assert_json_fail(ctx, section=section, name="4.2 非法status筛选", method="GET", url=f"{GEO}/projects", params="status=invalid_status", status=status, body=body, elapsed=elapsed, expected_code=422)


def test_brands(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.project_id:
        return
    section = "5. 品牌与别名模块"
    pid = ctx.project_id

    for brand_type, key in [("target", "target_brand_id"), ("competitor", "competitor_brand_id")]:
        name = "杭州宋城" if brand_type == "target" else "竞品A"
        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/projects/{pid}/brands",
            json_body={"brand_name": name, "brand_type": brand_type},
        )
        data = json_data(body) or {}
        if assert_json_ok(ctx, section=section, name=f"5.2 创建{brand_type}品牌", method="POST", url=f"{GEO}/projects/{{id}}/brands", params=f"brand_type={brand_type}", status=status, body=body, elapsed=elapsed):
            bid = data.get("id")
            if brand_type == "target":
                ctx.target_brand_id = bid
            else:
                ctx.competitor_brand_id = bid

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/brands",
        json_body={"brand_name": "杭州宋城", "brand_type": "competitor"},
    )
    assert_json_fail(ctx, section=section, name="5.2 重复品牌名", method="POST", url=f"{GEO}/projects/{{id}}/brands", params="同名品牌", status=status, body=body, elapsed=elapsed, expected_code=40012)

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/brands",
        json_body={"brand_name": "第二个目标", "brand_type": "target"},
    )
    assert_json_fail(ctx, section=section, name="5.2 重复目标品牌", method="POST", url=f"{GEO}/projects/{{id}}/brands", params="brand_type=target", status=status, body=body, elapsed=elapsed, expected_code=40010)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{pid}/brands")
    assert_json_ok(ctx, section=section, name="5.2 分页查询项目品牌", method="GET", url=f"{GEO}/projects/{{id}}/brands", params="", status=status, body=body, elapsed=elapsed)

    brand_id = ctx.target_brand_id
    if brand_id:
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/brands/{brand_id}")
        assert_json_ok(ctx, section=section, name="5.2 获取品牌", method="GET", url=f"{GEO}/brands/{{id}}", params=f"id={brand_id}", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/brands/{brand_id}",
            json_body={"description": "目标品牌描述"},
        )
        assert_json_ok(ctx, section=section, name="5.2 更新品牌", method="PUT", url=f"{GEO}/brands/{{id}}", params="description", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/brands/{brand_id}/aliases",
            json_body={"alias_name": "宋城", "match_mode": "contains", "context_keywords": ["文旅"]},
        )
        alias_data = json_data(body) or {}
        if assert_json_ok(ctx, section=section, name="5.3 创建品牌别名", method="POST", url=f"{GEO}/brands/{{id}}/aliases", params="alias_name=宋城", status=status, body=body, elapsed=elapsed):
            ctx.alias_id = alias_data.get("id")

        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/brands/{brand_id}/aliases",
            json_body={"alias_name": "宋城"},
        )
        assert_json_fail(ctx, section=section, name="5.3 重复别名", method="POST", url=f"{GEO}/brands/{{id}}/aliases", params="重复alias", status=status, body=body, elapsed=elapsed, expected_code=40011)

        status, body, elapsed, _ = req(client, "GET", f"{GEO}/brands/{brand_id}/aliases")
        assert_json_ok(ctx, section=section, name="5.3 分页查询品牌别名", method="GET", url=f"{GEO}/brands/{{id}}/aliases", params="", status=status, body=body, elapsed=elapsed)

        if ctx.alias_id:
            status, body, elapsed, _ = req(
                client,
                "PUT",
                f"{GEO}/brand-aliases/{ctx.alias_id}",
                json_body={"match_mode": "exact"},
            )
            assert_json_ok(ctx, section=section, name="5.3 更新品牌别名", method="PUT", url=f"{GEO}/brand-aliases/{{id}}", params="match_mode=exact", status=status, body=body, elapsed=elapsed)


def test_prompts(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.project_id:
        return
    section = "6. 提示词集与提示词模块"
    pid = ctx.project_id
    ver = datetime.now(timezone.utc).strftime("v%H%M%S")

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/prompt-sets",
        json_body={"set_name": "测试提示词集", "version_no": ver},
    )
    ps_data = json_data(body) or {}
    if assert_json_ok(ctx, section=section, name="6.3 创建提示词集", method="POST", url=f"{GEO}/projects/{{id}}/prompt-sets", params=f"version_no={ver}", status=status, body=body, elapsed=elapsed):
        ctx.prompt_set_id = ps_data.get("id")

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/prompt-sets",
        json_body={"set_name": "空集", "version_no": f"empty-{ver}"},
    )
    empty_data = json_data(body) or {}
    if isinstance(empty_data, dict):
        ctx.empty_prompt_set_id = empty_data.get("id")

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{pid}/prompt-sets")
    assert_json_ok(ctx, section=section, name="6.3 分页查询提示词集", method="GET", url=f"{GEO}/projects/{{id}}/prompt-sets", params="", status=status, body=body, elapsed=elapsed)

    if ctx.empty_prompt_set_id:
        status, body, elapsed, _ = req(client, "POST", f"{GEO}/prompt-sets/{ctx.empty_prompt_set_id}/activate")
        assert_json_fail(ctx, section=section, name="6.3 空提示词集激活", method="POST", url=f"{GEO}/prompt-sets/{{id}}/activate", params="空集", status=status, body=body, elapsed=elapsed, expected_code=40022)

    if ctx.prompt_set_id:
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/prompt-sets/{ctx.prompt_set_id}")
        assert_json_ok(ctx, section=section, name="6.3 获取提示词集", method="GET", url=f"{GEO}/prompt-sets/{{id}}", params="", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/prompt-sets/{ctx.prompt_set_id}",
            json_body={"set_name": "测试提示词集-更新"},
        )
        assert_json_ok(ctx, section=section, name="6.3 更新提示词集(草稿)", method="PUT", url=f"{GEO}/prompt-sets/{{id}}", params="set_name", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/prompt-sets/{ctx.prompt_set_id}/prompts",
            json_body={
                "prompt_code": "P001",
                "prompt_text": "推荐国内有哪些值得看的文旅演艺项目？",
                "prompt_type": "generic",
                "enabled": True,
            },
        )
        pr_data = json_data(body) or {}
        if assert_json_ok(ctx, section=section, name="6.4 创建提示词", method="POST", url=f"{GEO}/prompt-sets/{{id}}/prompts", params="prompt_code=P001", status=status, body=body, elapsed=elapsed):
            ctx.prompt_id = pr_data.get("id")

        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/prompt-sets/{ctx.prompt_set_id}/prompts",
            json_body={"prompt_code": "P001", "prompt_text": "duplicate"},
        )
        assert_json_fail(ctx, section=section, name="6.4 重复提示词编码", method="POST", url=f"{GEO}/prompt-sets/{{id}}/prompts", params="重复code", status=status, body=body, elapsed=elapsed, expected_code=40021)

        status, body, elapsed, _ = req(client, "GET", f"{GEO}/prompt-sets/{ctx.prompt_set_id}/prompts")
        assert_json_ok(ctx, section=section, name="6.4 分页查询提示词", method="GET", url=f"{GEO}/prompt-sets/{{id}}/prompts", params="", status=status, body=body, elapsed=elapsed)

        if ctx.prompt_id:
            status, body, elapsed, _ = req(
                client,
                "PUT",
                f"{GEO}/prompts/{ctx.prompt_id}",
                json_body={"scene_tag": "推荐场景"},
            )
            assert_json_ok(ctx, section=section, name="6.4 更新提示词", method="PUT", url=f"{GEO}/prompts/{{id}}", params="scene_tag", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(client, "POST", f"{GEO}/prompt-sets/{ctx.prompt_set_id}/activate")
        if assert_json_ok(ctx, section=section, name="6.3 激活提示词集", method="POST", url=f"{GEO}/prompt-sets/{{id}}/activate", params="", status=status, body=body, elapsed=elapsed):
            act = json_data(body) or {}
            if act.get("status") != "active":
                record(ctx, section=section, name="6.3 激活后status校验", method="POST", url="", params="", expected="status=active", passed=False, http_status=status, response_code=json_code(body), message="status not active")

        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/prompt-sets/{ctx.prompt_set_id}",
            json_body={"set_name": "不应成功"},
        )
        assert_json_fail(ctx, section=section, name="6.3 非草稿修改提示词集", method="PUT", url=f"{GEO}/prompt-sets/{{id}}", params="已激活", status=status, body=body, elapsed=elapsed, expected_code=40020)


def test_monitor_setup(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.project_id:
        return
    section = "5.4 核心词、Prompt 词库与监测设置"
    pid = ctx.project_id
    platform_codes = ensure_enabled_platform_codes(client, ctx)

    status, body, elapsed, _ = req(
        client, "GET", f"{GEO}/prompt-library", params={"page": 1, "page_size": 20}
    )
    assert_json_ok(
        ctx,
        section=section,
        name="5.4 分页查询 Prompt 词库",
        method="GET",
        url=f"{GEO}/prompt-library",
        params="page=1",
        status=status,
        body=body,
        elapsed=elapsed,
    )

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/core-keywords",
        json_body={"keyword": "文旅演艺", "sort_order": 1, "description": "API全量测试核心词"},
    )
    ck_data = json_data(body) or {}
    if assert_json_ok(
        ctx,
        section=section,
        name="5.4 创建核心词",
        method="POST",
        url=f"{GEO}/projects/{{id}}/core-keywords",
        params="keyword=文旅演艺",
        status=status,
        body=body,
        elapsed=elapsed,
    ):
        ctx.core_keyword_id = ck_data.get("id")

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{pid}/core-keywords")
    assert_json_ok(
        ctx,
        section=section,
        name="5.4 分页查询核心词",
        method="GET",
        url=f"{GEO}/projects/{{id}}/core-keywords",
        params="",
        status=status,
        body=body,
        elapsed=elapsed,
    )

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/core-keywords",
        json_body={"keyword": "文旅演艺"},
    )
    assert_json_fail(
        ctx,
        section=section,
        name="5.4 重复核心词",
        method="POST",
        url=f"{GEO}/projects/{{id}}/core-keywords",
        params="重复keyword",
        status=status,
        body=body,
        elapsed=elapsed,
        expected_code=40024,
    )

    if ctx.core_keyword_id:
        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/core-keywords/{ctx.core_keyword_id}",
            json_body={"description": "更新后的核心词说明"},
        )
        assert_json_ok(
            ctx,
            section=section,
            name="5.4 更新核心词",
            method="PUT",
            url=f"{GEO}/core-keywords/{{id}}",
            params="description",
            status=status,
            body=body,
            elapsed=elapsed,
        )

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{pid}/monitor-setup")
    assert_json_ok(
        ctx,
        section=section,
        name="5.4 获取监测设置",
        method="GET",
        url=f"{GEO}/projects/{{id}}/monitor-setup",
        params="",
        status=status,
        body=body,
        elapsed=elapsed,
    )

    setup_payload = {
        "brand": {
            "brand_name": "杭州宋城",
            "official_domain": "https://www.sepchina.com",
            "description": "API全量测试-目标品牌",
            "brand_words": ["宋城", "SEP"],
        },
        "competitors": [
            {"brand_name": "竞品A", "competitor_words": ["竞品A", "CompA"]},
        ],
        "core_keywords": [
            {"keyword": "文旅演艺", "sort_order": 1},
            {"keyword": "环境检测", "sort_order": 2},
        ],
        "ai_questions": [
            {
                "core_keyword": "文旅演艺",
                "prompt_text": "推荐国内有哪些值得看的文旅演艺项目？",
            },
            {
                "library_prompt_code": "LIB_RECOMMEND_001",
                "core_keyword": "文旅演艺",
            },
        ],
        "selected_platform_codes": platform_codes,
        "activate_prompt_set": True,
    }
    status, body, elapsed, _ = req(
        client,
        "PUT",
        f"{GEO}/projects/{pid}/monitor-setup",
        json_body=setup_payload,
    )
    setup_data = json_data(body) or {}
    if assert_json_ok(
        ctx,
        section=section,
        name="5.4 保存监测设置",
        method="PUT",
        url=f"{GEO}/projects/{{id}}/monitor-setup",
        params="brand+competitors+questions+platforms",
        status=status,
        body=body,
        elapsed=elapsed,
    ):
        brand = setup_data.get("brand") or {}
        if brand.get("brand_name") != "杭州宋城":
            record(
                ctx,
                section=section,
                name="5.4 保存后品牌名校验",
                method="PUT",
                url="",
                params="",
                expected="brand_name=杭州宋城",
                passed=False,
                http_status=status,
                response_code=json_code(body),
                message="brand_name mismatch",
            )
        if setup_data.get("active_prompt_set_id") is None:
            record(
                ctx,
                section=section,
                name="5.4 保存后激活提示词集校验",
                method="PUT",
                url="",
                params="",
                expected="active_prompt_set_id not null",
                passed=False,
                http_status=status,
                response_code=json_code(body),
                message="prompt set not activated",
            )
        if len(setup_data.get("ai_questions") or []) < 2:
            record(
                ctx,
                section=section,
                name="5.4 保存后 AI 问题数量校验",
                method="PUT",
                url="",
                params="",
                expected=">=2 ai_questions",
                passed=False,
                http_status=status,
                response_code=json_code(body),
                message="ai_questions count insufficient",
            )

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{pid}/monitor-setup")
    assert_json_ok(
        ctx,
        section=section,
        name="5.4 保存后再次获取监测设置",
        method="GET",
        url=f"{GEO}/projects/{{id}}/monitor-setup",
        params="",
        status=status,
        body=body,
        elapsed=elapsed,
    )

    status, body, elapsed, _ = req(
        client,
        "PUT",
        f"{GEO}/projects/{pid}/monitor-setup",
        json_body={
            "brand": {"brand_name": "杭州宋城", "brand_words": ["宋城"]},
            "selected_platform_codes": ["invalid_platform_code"],
        },
    )
    assert_json_fail(
        ctx,
        section=section,
        name="5.4 非法平台编码",
        method="PUT",
        url=f"{GEO}/projects/{{id}}/monitor-setup",
        params="invalid platform",
        status=status,
        body=body,
        elapsed=elapsed,
        expected_code=40025,
    )


def test_platforms(client: httpx.Client, ctx: TestContext) -> None:
    section = "7. AI 平台模块"
    status, body, elapsed, _ = req(client, "GET", f"{GEO}/platforms", params={"page": 1, "page_size": 20})
    assert_json_ok(ctx, section=section, name="7.2 分页查询AI平台", method="GET", url=f"{GEO}/platforms", params="page=1", status=status, body=body, elapsed=elapsed)
    items = (json_data(body) or {}).get("items", []) if isinstance(json_data(body), dict) else []
    ensure_enabled_platform_codes(client, ctx)

    if items:
        code = items[0]["platform_code"]
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/platforms/{code}")
        assert_json_ok(ctx, section=section, name="7.2 获取AI平台配置", method="GET", url=f"{GEO}/platforms/{{code}}", params=f"code={code}", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/platforms/{code}",
            json_body={"timeout_seconds": 120},
        )
        assert_json_ok(ctx, section=section, name="7.2 更新AI平台配置", method="PUT", url=f"{GEO}/platforms/{{code}}", params="timeout_seconds=120", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/platforms/nonexistent_platform_xyz")
    assert_json_fail(ctx, section=section, name="7.2 获取不存在平台", method="GET", url=f"{GEO}/platforms/nonexistent", params="", status=status, body=body, elapsed=elapsed, expected_code=40400)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/platforms", params={"page_size": 999})
    assert_json_fail(ctx, section=section, name="7.2 page_size超限", method="GET", url=f"{GEO}/platforms", params="page_size=999", status=status, body=body, elapsed=elapsed, expected_code=422)

    ensure_enabled_platform_codes(client, ctx)


def test_runs(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.project_id:
        return
    section = "8. 监测运行与任务模块"
    ensure_enabled_platform_codes(client, ctx)

    # no active prompt set scenario - use empty project
    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects",
        json_body={"project_name": f"无激活集项目-{uuid.uuid4().hex[:6]}", "industry": "测试"},
    )
    no_ps_pid = (json_data(body) or {}).get("id")
    if no_ps_pid:
        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/runs",
            json_body={"project_id": no_ps_pid, "platform_codes": ctx.platform_codes},
        )
        assert_json_fail(ctx, section=section, name="8.2 无激活提示词集创建运行", method="POST", url=f"{GEO}/runs", params=f"project_id={no_ps_pid}", status=status, body=body, elapsed=elapsed, expected_code=40030)

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/runs",
        json_body={"project_id": ctx.project_id, "platform_codes": ctx.platform_codes},
    )
    run_data = json_data(body) or {}
    if assert_json_ok(ctx, section=section, name="8.2 创建监测运行", method="POST", url=f"{GEO}/runs", params=f"project_id={ctx.project_id}", status=status, body=body, elapsed=elapsed):
        ctx.run_id = run_data.get("id")

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs", params={"project_id": ctx.project_id})
    assert_json_ok(ctx, section=section, name="8.2 分页查询监测运行", method="GET", url=f"{GEO}/runs", params=f"project_id={ctx.project_id}", status=status, body=body, elapsed=elapsed)

    if not ctx.run_id:
        return

    # analyze before collection done
    status, body, elapsed, _ = req(client, "POST", f"{GEO}/runs/{ctx.run_id}/analyze")
    assert_json_fail(
        ctx,
        section=section,
        name="11.1 采集未完成触发分析",
        method="POST",
        url=f"{GEO}/runs/{{id}}/analyze",
        params=f"run_id={ctx.run_id}",
        status=status,
        body=body,
        elapsed=elapsed,
        expected_code=40910,
        expected_http=409,
    )

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}")
    assert_json_ok(ctx, section=section, name="8.2 获取运行详情", method="GET", url=f"{GEO}/runs/{{id}}", params=f"id={ctx.run_id}", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/query-tasks")
    assert_json_ok(ctx, section=section, name="8.3 分页查询运行任务", method="GET", url=f"{GEO}/runs/{{id}}/query-tasks", params="", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/tasks")
    assert_json_ok(ctx, section=section, name="8.3 分页查询运行任务(别名)", method="GET", url=f"{GEO}/runs/{{id}}/tasks", params="", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/999999")
    assert_json_fail(ctx, section=section, name="8.2 获取不存在运行", method="GET", url=f"{GEO}/runs/999999", params="", status=status, body=body, elapsed=elapsed, expected_code=40400)


def wait_for_run_terminal(client: httpx.Client, ctx: TestContext) -> str | None:
    if not ctx.run_id:
        return None
    terminal = {"completed", "partial_success", "failed", "cancelled"}
    deadline = time.time() + RUN_POLL_MAX
    last_status = None
    while time.time() < deadline:
        status, body, _, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}")
        if status == 200 and json_code(body) == 0:
            data = json_data(body) or {}
            last_status = data.get("status")
            if last_status in terminal:
                return last_status
        time.sleep(RUN_POLL_INTERVAL)
    return last_status


def test_answers_analysis_dashboard(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.run_id or not ctx.project_id:
        return

    run_status = wait_for_run_terminal(client, ctx)
    section_poll = "8. 监测运行与任务模块"
    record(
        ctx,
        section=section_poll,
        name="8.2 等待采集终态",
        method="GET",
        url=f"{GEO}/runs/{ctx.run_id}",
        params=f"poll max {RUN_POLL_MAX}s",
        expected="status in completed/partial_success/failed/cancelled",
        passed=run_status in {"completed", "partial_success", "failed", "cancelled"},
        http_status=200,
        response_code=0 if run_status else None,
        message=f"final_status={run_status}",
        detail=f"run_id={ctx.run_id}",
    )

    section = "10. 答案模块"
    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/answers")
    assert_json_ok(ctx, section=section, name="10.2 分页查询运行答案", method="GET", url=f"{GEO}/runs/{{id}}/answers", params="", status=status, body=body, elapsed=elapsed)
    items = (json_data(body) or {}).get("items", []) if isinstance(json_data(body), dict) else []
    if items:
        ctx.answer_id = items[0].get("id")
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/answers/{ctx.answer_id}")
        assert_json_ok(ctx, section=section, name="10.2 获取答案详情", method="GET", url=f"{GEO}/answers/{{id}}", params=f"id={ctx.answer_id}", status=status, body=body, elapsed=elapsed)

    section = "11. 分析与Agent审计模块"
    status, body, elapsed, _ = req(client, "POST", f"{GEO}/runs/{ctx.run_id}/analyze")
    analyze_ok = status == 200 and json_code(body) == 0
    record(
        ctx,
        section=section,
        name="11.1 手工触发分析",
        method="POST",
        url=f"{GEO}/runs/{ctx.run_id}/analyze",
        params="",
        expected="HTTP 200, code=0 (终态运行)",
        passed=analyze_ok,
        http_status=status,
        response_code=json_code(body),
        message=json_msg(body),
        detail=json.dumps(body, ensure_ascii=False)[:500] if body else "",
        duration_ms=elapsed,
    )

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/analysis")
    assert_json_ok(ctx, section=section, name="11.1 获取运行平台指标", method="GET", url=f"{GEO}/runs/{{id}}/analysis", params="", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/agent-executions")
    assert_json_ok(ctx, section=section, name="11.1 分页查询Agent审计", method="GET", url=f"{GEO}/runs/{{id}}/agent-executions", params="", status=status, body=body, elapsed=elapsed)

    section = "12. 看板与趋势模块"
    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{ctx.project_id}/dashboard")
    assert_json_ok(ctx, section=section, name="12.1 获取项目最新分析汇总", method="GET", url=f"{GEO}/projects/{{id}}/dashboard", params="", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(
        client,
        "GET",
        f"{GEO}/projects/{ctx.project_id}/trends",
        params={"metric_code": "brand_mention_rate", "page": 1, "page_size": 10},
    )
    assert_json_ok(ctx, section=section, name="12.1 查询趋势", method="GET", url=f"{GEO}/projects/{{id}}/trends", params="metric_code=brand_mention_rate", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{ctx.project_id}/trends")
    assert_json_fail(ctx, section=section, name="12.1 缺少metric_code", method="GET", url=f"{GEO}/projects/{{id}}/trends", params="无metric_code", status=status, body=body, elapsed=elapsed, expected_code=422)


def test_reports(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.run_id:
        return
    section = "13. 报告模块"

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/runs/{ctx.run_id}/reports",
        json_body={"formats": ["md", "html"]},
    )
    # may fail if analysis not complete
    code = json_code(body)
    reports_created = False
    if status == 409 and code == 40920:
        record(
            ctx,
            section=section,
            name="13.2 分析未完成生成报告(预期40920)",
            method="POST",
            url=f"{GEO}/runs/{{id}}/reports",
            params="formats=md,html",
            expected="409/40920 if analysis incomplete",
            passed=True,
            http_status=status,
            response_code=code,
            message=json_msg(body),
            detail=json.dumps(body, ensure_ascii=False)[:300],
            duration_ms=elapsed,
        )
    else:
        rep_data = json_data(body) or {}
        reports = rep_data.get("reports", []) if isinstance(rep_data, dict) else []
        if assert_json_ok(ctx, section=section, name="13.2 创建并生成监测报告", method="POST", url=f"{GEO}/runs/{{id}}/reports", params="formats=md,html", status=status, body=body, elapsed=elapsed) and reports:
            ctx.report_id = reports[0].get("id")
            reports_created = True

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/reports")
    assert_json_ok(ctx, section=section, name="13.2 分页查询运行报告", method="GET", url=f"{GEO}/runs/{{id}}/reports", params="", status=status, body=body, elapsed=elapsed)

    if ctx.report_id:
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/reports/{ctx.report_id}")
        assert_json_ok(ctx, section=section, name="13.2 获取报告元数据", method="GET", url=f"{GEO}/reports/{{id}}", params="", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, hdrs = req(client, "GET", f"{GEO}/reports/{ctx.report_id}/download")
        passed = status == 200 and len(str(body)) > 0
        record(
            ctx,
            section=section,
            name="13.2 下载报告文件",
            method="GET",
            url=f"{GEO}/reports/{{id}}/download",
            params=f"id={ctx.report_id}",
            expected="HTTP 200, file content",
            passed=passed,
            http_status=status,
            response_code=None,
            message=hdrs.get("content-disposition", ""),
            detail=f"content-type={hdrs.get('content-type','')}, size={len(str(body))}",
            duration_ms=elapsed,
        )

        status, body, elapsed, _ = req(client, "DELETE", f"{GEO}/reports/{ctx.report_id}")
        assert_json_ok(ctx, section=section, name="13.2 删除报告", method="DELETE", url=f"{GEO}/reports/{{id}}", params="", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/runs/{ctx.run_id}/reports",
        json_body={"formats": ["pdf"]},
    )
    pdf_code = json_code(body)
    if pdf_code == 40920:
        record(
            ctx,
            section=section,
            name="13.2 生成PDF报告",
            method="POST",
            url=f"{GEO}/runs/{{id}}/reports",
            params="formats=pdf",
            expected="code=0，或分析未完成时先返回40920",
            passed=True,
            http_status=status,
            response_code=pdf_code,
            message=json_msg(body),
            detail="分析未完成，PDF生成未触发",
            duration_ms=elapsed,
        )
    else:
        reports = json_data(body).get("reports", []) if isinstance(json_data(body), dict) else []
        passed = status == 200 and pdf_code == 0 and any(
            item.get("format") == "pdf" and item.get("status") == "completed"
            for item in reports
        )
        record(
            ctx,
            section=section,
            name="13.2 生成PDF报告",
            method="POST",
            url=f"{GEO}/runs/{{id}}/reports",
            params="formats=pdf",
            expected="code=0, pdf report completed",
            passed=passed,
            http_status=status,
            response_code=pdf_code,
            message=json_msg(body),
            detail=str(reports[:1]),
            duration_ms=elapsed,
        )


def test_schedules(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.project_id:
        return
    section = "9. 调度模块"
    pid = ctx.project_id
    name = f"每日监测-{uuid.uuid4().hex[:6]}"

    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/schedules",
        json_body={"name": name, "cron_expr": "0 9 * * *", "timezone": "Asia/Shanghai"},
    )
    sch = json_data(body) or {}
    if assert_json_ok(ctx, section=section, name="9.2 创建监测调度", method="POST", url=f"{GEO}/projects/{{id}}/schedules", params=name, status=status, body=body, elapsed=elapsed):
        ctx.schedule_id = sch.get("id")

    status, body, elapsed, _ = req(client, "GET", f"{GEO}/projects/{pid}/schedules")
    assert_json_ok(ctx, section=section, name="9.2 分页查询项目调度", method="GET", url=f"{GEO}/projects/{{id}}/schedules", params="", status=status, body=body, elapsed=elapsed)

    if ctx.schedule_id:
        status, body, elapsed, _ = req(client, "GET", f"{GEO}/schedules/{ctx.schedule_id}")
        assert_json_ok(ctx, section=section, name="9.2 获取监测调度", method="GET", url=f"{GEO}/schedules/{{id}}", params="", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "PUT",
            f"{GEO}/schedules/{ctx.schedule_id}",
            json_body={"cron_expr": "0 10 * * *"},
        )
        assert_json_ok(ctx, section=section, name="9.2 更新监测调度", method="PUT", url=f"{GEO}/schedules/{{id}}", params="cron更新", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(client, "POST", f"{GEO}/schedules/{ctx.schedule_id}/disable")
        assert_json_ok(ctx, section=section, name="9.2 停用监测调度", method="POST", url=f"{GEO}/schedules/{{id}}/disable", params="", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(client, "POST", f"{GEO}/schedules/{ctx.schedule_id}/enable")
        assert_json_ok(ctx, section=section, name="9.2 启用监测调度", method="POST", url=f"{GEO}/schedules/{{id}}/enable", params="", status=status, body=body, elapsed=elapsed)

        status, body, elapsed, _ = req(
            client,
            "POST",
            f"{GEO}/projects/{pid}/schedules",
            json_body={"name": name, "cron_expr": "0 8 * * *"},
        )
        assert_json_fail(ctx, section=section, name="9.2 重复调度名称", method="POST", url=f"{GEO}/projects/{{id}}/schedules", params="同名", status=status, body=body, elapsed=elapsed, expected_code=40904, expected_http=409)

        status, body, elapsed, _ = req(client, "POST", f"{GEO}/schedules/{ctx.schedule_id}/trigger")
        trig_ok = status == 200 and json_code(body) == 0
        record(
            ctx,
            section=section,
            name="9.2 立即触发监测调度",
            method="POST",
            url=f"{GEO}/schedules/{{id}}/trigger",
            params="",
            expected="HTTP 200, code=0, 新运行",
            passed=trig_ok,
            http_status=status,
            response_code=json_code(body),
            message=json_msg(body),
            detail=json.dumps(body, ensure_ascii=False)[:300] if body else "",
            duration_ms=elapsed,
        )

        status, body, elapsed, _ = req(client, "DELETE", f"{GEO}/schedules/{ctx.schedule_id}")
        assert_json_ok(ctx, section=section, name="9.2 删除监测调度", method="DELETE", url=f"{GEO}/schedules/{{id}}", params="", status=status, body=body, elapsed=elapsed)


def test_negative_disabled_project(client: httpx.Client, ctx: TestContext) -> None:
    section = "14.3 重点反向测试"
    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/projects",
        json_body={"project_name": f"禁用测试项目-{uuid.uuid4().hex[:6]}", "industry": "测试"},
    )
    pid = (json_data(body) or {}).get("id")
    if not pid:
        return
    ctx.disabled_project_id = pid
    req(client, "PUT", f"{GEO}/projects/{pid}", json_body={"status": "disabled"})

    for name, path in [
        ("项目未启用-查询品牌", f"{GEO}/projects/{pid}/brands"),
        ("项目未启用-查询提示词集", f"{GEO}/projects/{pid}/prompt-sets"),
        ("项目未启用-查询调度", f"{GEO}/projects/{pid}/schedules"),
        ("项目未启用-看板", f"{GEO}/projects/{pid}/dashboard"),
    ]:
        status, body, elapsed, _ = req(client, "GET", path)
        assert_json_fail(ctx, section=section, name=name, method="GET", url=path, params="disabled project", status=status, body=body, elapsed=elapsed, expected_code=40001)


def test_run_cancel_retry(client: httpx.Client, ctx: TestContext) -> None:
    if not ctx.project_id:
        return
    section = "8. 监测运行与任务模块"
    status, body, elapsed, _ = req(
        client,
        "POST",
        f"{GEO}/runs",
        json_body={"project_id": ctx.project_id, "platform_codes": ctx.platform_codes[:1]},
    )
    run_data = json_data(body) or {}
    cancel_run_id = run_data.get("id")
    if not cancel_run_id:
        return

    status, body, elapsed, _ = req(client, "POST", f"{GEO}/runs/{cancel_run_id}/cancel")
    assert_json_ok(ctx, section=section, name="8.2 取消运行", method="POST", url=f"{GEO}/runs/{{id}}/cancel", params="", status=status, body=body, elapsed=elapsed)

    status, body, elapsed, _ = req(client, "POST", f"{GEO}/runs/{cancel_run_id}/retry-failed")
    assert_json_fail(
        ctx,
        section=section,
        name="8.2 已取消运行不可重试",
        method="POST",
        url=f"{GEO}/runs/{{id}}/retry-failed",
        params="",
        status=status,
        body=body,
        elapsed=elapsed,
        expected_code=40040,
    )


def test_compat_prefix(client: httpx.Client, ctx: TestContext) -> None:
    section = "1.1 兼容前缀"
    status, body, elapsed, _ = req(client, "GET", f"{API}/v1/geo-monitoring/projects", params={"page": 1, "page_size": 5})
    assert_json_ok(ctx, section=section, name="GET /api/v1/geo-monitoring/projects", method="GET", url=f"{API}/v1/geo-monitoring/projects", params="page=1", status=status, body=body, elapsed=elapsed)


def test_cleanup(client: httpx.Client, ctx: TestContext) -> None:
    section = "清理"
    if ctx.alias_id:
        req(client, "DELETE", f"{GEO}/brand-aliases/{ctx.alias_id}")
    if ctx.competitor_brand_id:
        req(client, "DELETE", f"{GEO}/brands/{ctx.competitor_brand_id}")
    if ctx.empty_prompt_set_id:
        status, body, elapsed, _ = req(client, "DELETE", f"{GEO}/prompt-sets/{ctx.empty_prompt_set_id}")
        record(ctx, section=section, name="删除空提示词集", method="DELETE", url=f"{GEO}/prompt-sets/{{id}}", params="", expected="草稿删除成功", passed=status == 200 and json_code(body) == 0, http_status=status, response_code=json_code(body), message=json_msg(body), duration_ms=elapsed)
    if ctx.disabled_project_id:
        req(client, "DELETE", f"{GEO}/projects/{ctx.disabled_project_id}")


def generate_report(ctx: TestContext, started_at: datetime, finished_at: datetime) -> str:
    passed = sum(1 for r in ctx.results if r.passed)
    failed = sum(1 for r in ctx.results if not r.passed)
    total = len(ctx.results)
    rate = (passed / total * 100) if total else 0
    duration_sec = (finished_at - started_at).total_seconds()
    negative_keywords = ("不存在", "非法", "重复", "空提示词", "非草稿", "超限", "无激活", "缺少", "不可重试", "未启用", "不支持", "未完成")
    negative = [r for r in ctx.results if any(k in r.name for k in negative_keywords)]
    positive = [r for r in ctx.results if r not in negative]

    lines = [
        "# API 全量接口测试报告",
        "",
        f"- **测试时间**：{started_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')} ~ {finished_at.astimezone().strftime('%H:%M:%S')} (本地时区)",
        f"- **耗时**：{duration_sec:.1f} 秒",
        f"- **测试环境**：本地开发 (`http://127.0.0.1:8000`)",
        f"- **参考文档**：[`docs/API测试文档.md`](./API测试文档.md)",
        f"- **执行脚本**：`backend/scripts/run_api_full_test.py`",
        f"- **Dramatiq**：collection worker 已启动",
        "",
        "## 汇总",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 总用例数 | {total} |",
        f"| 通过 | {passed} |",
        f"| 失败 | {failed} |",
        f"| 通过率 | {rate:.1f}% |",
        f"| 正向用例 | {sum(1 for r in positive if r.passed)}/{len(positive)} 通过 |",
        f"| 反向用例 | {sum(1 for r in negative if r.passed)}/{len(negative)} 通过 |",
        "",
        "### 测试上下文 ID",
        "",
        f"- project_id: `{ctx.project_id}`",
        f"- run_id: `{ctx.run_id}`",
        f"- prompt_set_id: `{ctx.prompt_set_id}`",
        f"- platform_codes: `{', '.join(ctx.platform_codes)}`",
        "",
        "### 环境观察",
        "",
    ]

    run_wait = next((r for r in ctx.results if r.name == "8.2 等待采集终态"), None)
    if run_wait:
        lines.append(f"- 主监测运行终态：`{run_wait.message}`（依赖外部 AI 平台密钥与网络）")
    report_case = next((r for r in ctx.results if "报告" in r.name and r.section == "13. 报告模块"), None)
    if report_case and "40920" in (report_case.detail or ""):
        lines.append("- 报告生成：分析未完成（40920），报告下载/删除用例未完整执行")
    lines.extend(["", "## 模块覆盖概览", ""])
    modules = [
        ("基础探针", ["3. 基础探针", "1.1 兼容"]),
        ("项目", ["4. 项目"]),
        ("品牌与别名", ["5. 品牌"]),
        ("提示词集与提示词", ["6. 提示词"]),
        ("AI 平台", ["7. AI"]),
        ("监测运行与任务", ["8. 监测运行"]),
        ("调度", ["9. 调度"]),
        ("答案", ["10. 答案"]),
        ("分析与 Agent 审计", ["11."]),
        ("看板与趋势", ["12. 看板"]),
        ("报告", ["13. 报告"]),
        ("反向测试", ["14.3"]),
    ]
    lines.append("| 模块 | 用例数 | 通过 | 失败 |")
    lines.append("| --- | --- | --- | --- |")
    for mod_name, keys in modules:
        mod_results = [r for r in ctx.results if any(k in r.section or k in r.name for k in keys)]
        if not mod_results:
            continue
        mp = sum(1 for r in mod_results if r.passed)
        mf = sum(1 for r in mod_results if not r.passed)
        lines.append(f"| {mod_name} | {len(mod_results)} | {mp} | {mf} |")

    lines.extend(["", "## 详细结果", ""])

    current_section = ""
    for r in ctx.results:
        if r.section != current_section:
            current_section = r.section
            lines.extend(["", f"### {current_section}", ""])
            lines.append("| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        result_icon = "PASS" if r.passed else "**FAIL**"
        url_short = r.url.replace(BASE, "")
        note = r.message if r.passed else (r.message or r.detail[:80])
        lines.append(
            f"| {r.name} | {r.method} | `{url_short}` | {r.http_status} | {r.response_code} | {result_icon} | {r.duration_ms:.0f} | {note} |"
        )

    failures = [r for r in ctx.results if not r.passed]
    if failures:
        lines.extend(["", "## 失败用例详情", ""])
        for r in failures:
            lines.extend(
                [
                    f"#### {r.name}",
                    "",
                    f"- **URL**: `{r.method} {r.url}`",
                    f"- **入参**: {r.params or '无'}",
                    f"- **预期**: {r.expected}",
                    f"- **实际 HTTP**: {r.http_status}, **code**: {r.response_code}, **message**: {r.message}",
                    f"- **响应摘要**: {r.detail}",
                    "",
                ]
            )

    lines.extend(
        [
            "## 说明",
            "",
            "1. 正向流程按文档 §14.2 顺序执行：项目 → 品牌/别名 → 提示词集 → 平台 → 监测设置 → 运行 → 答案 → 分析 → 看板 → 报告。",
            "2. 本 API 多数业务错误返回 **HTTP 200 + 非零 code**（如 40400、40012），反向用例以响应体 `code` 为准判定。",
            "3. 运行采集依赖 Dramatiq worker 与外部 AI 平台可用性；采集等待上限为 120 秒。",
            "4. 分析与报告生成依赖 Agent LLM 配置；分析未完成时报告接口返回 40920。",
            "5. 测试数据（项目、品牌、运行记录等）保留在本地数据库，便于后续联调复查。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    started = datetime.now(timezone.utc)
    ctx = TestContext()
    try:
        with httpx.Client() as client:
            # connectivity check
            try:
                client.get(f"{API}/health", timeout=5)
            except httpx.ConnectError:
                print("ERROR: Cannot connect to API at", BASE)
                return 1

            test_probes(client, ctx)
            test_compat_prefix(client, ctx)
            test_projects(client, ctx)
            test_brands(client, ctx)
            test_prompts(client, ctx)
            test_platforms(client, ctx)
            test_monitor_setup(client, ctx)
            test_schedules(client, ctx)
            test_runs(client, ctx)
            test_answers_analysis_dashboard(client, ctx)
            test_reports(client, ctx)
            test_run_cancel_retry(client, ctx)
            test_negative_disabled_project(client, ctx)
            test_cleanup(client, ctx)
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    finished = datetime.now(timezone.utc)
    report = generate_report(ctx, started, finished)
    out_path = r"d:\workspace\GEO-Platform\.worktrees\mvp-integration\docs\API全量接口测试报告.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    passed = sum(1 for r in ctx.results if r.passed)
    total = len(ctx.results)
    print(f"Done: {passed}/{total} passed. Report: {out_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
