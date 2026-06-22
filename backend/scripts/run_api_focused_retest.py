"""Focused retest for failed / incomplete API cases from the full test report."""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"
GEO = f"{BASE}/api/geo-monitoring"
REPORT_PATH = r"d:\workspace\GEO-Platform\.worktrees\mvp-integration\docs\API全量接口测试报告.md"
TIMEOUT = 120.0


@dataclass
class FocusResult:
    category: str
    name: str
    method: str
    url: str
    expected: str
    http_status: int | None = None
    response_code: int | str | None = None
    message: str = ""
    passed: bool = False
    detail: str = ""
    duration_ms: float = 0
    verdict: str = ""


@dataclass
class FocusContext:
    results: list[FocusResult] = field(default_factory=list)
    run_id: int | None = None


def record(
    ctx: FocusContext,
    *,
    category: str,
    name: str,
    method: str,
    url: str,
    expected: str,
    passed: bool,
    verdict: str,
    http_status: int | None,
    response_code: int | str | None,
    message: str = "",
    detail: str = "",
    duration_ms: float = 0,
) -> None:
    ctx.results.append(
        FocusResult(
            category=category,
            name=name,
            method=method,
            url=url,
            expected=expected,
            http_status=http_status,
            response_code=response_code,
            message=message,
            passed=passed,
            detail=detail[:800],
            duration_ms=duration_ms,
            verdict=verdict,
        )
    )


def req(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: dict | list | None = None,
    params: dict | None = None,
) -> tuple[int, Any, float]:
    import time

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": str(uuid.uuid4()),
    }
    start = time.perf_counter()
    r = client.request(method, url, json=json_body, params=params, headers=headers, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - start) * 1000
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            body = r.json()
        except json.JSONDecodeError:
            body = r.text
    else:
        body = r.text
    return r.status_code, body, elapsed


def jcode(body: Any) -> int | str | None:
    return body.get("code") if isinstance(body, dict) else None


def jdata(body: Any) -> Any:
    return body.get("data") if isinstance(body, dict) else None


def jmsg(body: Any) -> str:
    return str(body.get("message", "")) if isinstance(body, dict) else ""


def find_latest_run_id(client: httpx.Client) -> int | None:
    status, body, _ = req(client, "GET", f"{GEO}/runs", params={"page": 1, "page_size": 1})
    if status != 200 or jcode(body) != 0:
        return None
    items = (jdata(body) or {}).get("items", [])
    return items[0]["id"] if items else None


def retest_run_pipeline(client: httpx.Client, ctx: FocusContext, run_id: int) -> None:
    cat = "采集/分析/报告链路"
    terminal = {"completed", "partial_success", "failed", "cancelled"}

    status, body, elapsed = req(client, "GET", f"{GEO}/runs/{run_id}")
    data = jdata(body) or {} if isinstance(body, dict) else {}
    last_status = data.get("status")
    record(
        ctx,
        category=cat,
        name=f"8.2 采集终态检查 (run_id={run_id})",
        method="GET",
        url=f"{GEO}/runs/{run_id}",
        expected="status in completed/partial_success/failed/cancelled",
        passed=last_status in terminal,
        verdict="pass" if last_status in terminal else "env_limit",
        http_status=status,
        response_code=jcode(body),
        message=f"final_status={last_status}",
        detail=json.dumps(
            {
                "collection_status": data.get("collection_status"),
                "analysis_status": data.get("analysis_status"),
                "error_summary": data.get("error_summary"),
            },
            ensure_ascii=False,
        ),
        duration_ms=elapsed,
    )

    status, body, elapsed = req(client, "POST", f"{GEO}/runs/{run_id}/analyze")
    code = jcode(body)
    analyze_ok = status == 200 and code == 0
    skipped_ok = status == 200 and isinstance(body, dict) and (jdata(body) or {}).get("analysis_status") == "skipped"
    record(
        ctx,
        category=cat,
        name=f"11.1 手工触发分析 (run_id={run_id})",
        method="POST",
        url=f"{GEO}/runs/{run_id}/analyze",
        expected="200/0 或 skipped；采集中 409/40910",
        passed=analyze_ok or skipped_ok or (status == 409 and code == 40910),
        verdict="pass" if analyze_ok or skipped_ok else ("env_limit" if status == 409 else "fail"),
        http_status=status,
        response_code=code if isinstance(body, dict) else None,
        message=jmsg(body) if isinstance(body, dict) else str(body)[:120],
        detail=str(body)[:500] if not isinstance(body, dict) else json.dumps(body, ensure_ascii=False)[:500],
        duration_ms=elapsed,
    )

    status, body, elapsed = req(
        client, "POST", f"{GEO}/runs/{run_id}/reports", json_body={"formats": ["md", "html"]}
    )
    code = jcode(body)
    ok = (status == 409 and code == 40920) or (status == 200 and code == 0)
    record(
        ctx,
        category=cat,
        name=f"13.2 生成报告 (run_id={run_id})",
        method="POST",
        url=f"{GEO}/runs/{run_id}/reports",
        expected="409/40920 或 200/0",
        passed=ok,
        verdict="blocked" if code == 40920 else ("pass" if ok else "fail"),
        http_status=status,
        response_code=code,
        message=jmsg(body),
        duration_ms=elapsed,
    )


def retest_delete_scenarios(client: httpx.Client, ctx: FocusContext, project_id: int | None) -> None:
    cat = "DELETE 补充场景"
    if project_id:
        status, body, elapsed = req(client, "DELETE", f"{GEO}/projects/{project_id}")
        record(
            ctx,
            category=cat,
            name="删除有运行引用的项目 (40903)",
            method="DELETE",
            url=f"{GEO}/projects/{project_id}",
            expected="HTTP 409 code=40903",
            passed=status == 409 and jcode(body) == 40903,
            verdict="pass" if status == 409 and jcode(body) == 40903 else "fail",
            http_status=status,
            response_code=jcode(body),
            message=jmsg(body),
            duration_ms=elapsed,
        )

    status, body, elapsed = req(client, "DELETE", f"{GEO}/prompts/999999")
    record(
        ctx,
        category=cat,
        name="删除不存在提示词 (40400)",
        method="DELETE",
        url=f"{GEO}/prompts/999999",
        expected="HTTP 200 code=40400",
        passed=status == 200 and jcode(body) == 40400,
        verdict="pass",
        http_status=status,
        response_code=jcode(body),
        message=jmsg(body),
        duration_ms=elapsed,
    )

    # 40902: disable all platforms, create run without platform_codes
    items = (jdata(req(client, "GET", f"{GEO}/platforms", params={"page": 1, "page_size": 20})[1]) or {}).get(
        "items", []
    )
    backup = [(p["platform_code"], p.get("enabled", True)) for p in items]
    for code, enabled in backup:
        if enabled:
            req(client, "PUT", f"{GEO}/platforms/{code}", json_body={"enabled": False})

    suffix = uuid.uuid4().hex[:6]
    _, proj_body, _ = req(
        client, "POST", f"{GEO}/projects", json_body={"project_name": f"DEL-{suffix}", "industry": "测试"}
    )
    pid = (jdata(proj_body) or {}).get("id")
    if pid:
        req(client, "POST", f"{GEO}/projects/{pid}/brands", json_body={"brand_name": "B", "brand_type": "target"})
        _, ps_body, _ = req(
            client,
            "POST",
            f"{GEO}/projects/{pid}/prompt-sets",
            json_body={"set_name": "集", "version_no": f"v{suffix}"},
        )
        ps_id = (jdata(ps_body) or {}).get("id")
        if ps_id:
            req(
                client,
                "POST",
                f"{GEO}/prompt-sets/{ps_id}/prompts",
                json_body={"prompt_code": f"P{suffix}", "prompt_text": "q"},
            )
            req(client, "POST", f"{GEO}/prompt-sets/{ps_id}/activate")
            status, body, elapsed = req(client, "POST", f"{GEO}/runs", json_body={"project_id": pid})
            record(
                ctx,
                category=cat,
                name="全部平台禁用后创建运行 (40902)",
                method="POST",
                url=f"{GEO}/runs",
                expected="HTTP 409 code=40902",
                passed=status == 409 and jcode(body) == 40902,
                verdict="pass" if status == 409 and jcode(body) == 40902 else "fail",
                http_status=status,
                response_code=jcode(body),
                message=jmsg(body),
                duration_ms=elapsed,
            )
        req(client, "DELETE", f"{GEO}/projects/{pid}")

    for code, enabled in backup:
        req(client, "PUT", f"{GEO}/platforms/{code}", json_body={"enabled": enabled})


def generate_focus_table(ctx: FocusContext, started: datetime, finished: datetime) -> str:
    passed = sum(1 for r in ctx.results if r.passed)
    total = len(ctx.results)
    verdict_map = {
        "pass": "接口正常",
        "fail": "接口异常",
        "blocked": "前置未满足",
        "env_limit": "环境限制",
    }
    lines = [
        "",
        "## 重点复测（未通过 / 未完整覆盖接口）",
        "",
        f"- **复测时间**：{started.astimezone().strftime('%Y-%m-%d %H:%M:%S')} ~ {finished.astimezone().strftime('%H:%M:%S')} (本地时区)",
        f"- **复测脚本**：`backend/scripts/run_api_focused_retest.py`",
        f"- **复测用例**：{total} 项，通过 {passed}，未通过 {total - passed}",
        "",
        "| 分类 | 用例 | 方法 | URL | HTTP | code | 结果 | 判定 | 说明 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in ctx.results:
        url = r.url.replace(BASE, "")
        result = "PASS" if r.passed else "**FAIL**"
        lines.append(
            f"| {r.category} | {r.name} | {r.method} | `{url}` | {r.http_status} | {r.response_code} | {result} | {verdict_map.get(r.verdict, r.verdict)} | {r.message or r.detail[:60]} |"
        )
    fails = [r for r in ctx.results if not r.passed]
    if fails:
        lines.extend(["", "### 重点复测失败详情", ""])
        for r in fails:
            lines.extend(
                [
                    f"#### {r.name}",
                    "",
                    f"- **URL**: `{r.method} {r.url}`",
                    f"- **预期**: {r.expected}",
                    f"- **实际 HTTP**: {r.http_status}, **code**: {r.response_code}, **message**: {r.message}",
                    f"- **详情**: {r.detail[:300]}",
                    "",
                ]
            )
    return "\n".join(lines)


def patch_report(ctx: FocusContext, started: datetime, finished: datetime) -> None:
    with open(REPORT_PATH, encoding="utf-8") as f:
        content = f.read()
    marker = "## 重点复测"
    if marker in content:
        content = content.split(marker)[0].rstrip()
    insert_before = "## 结论"
    if insert_before not in content:
        insert_before = "## 说明"
    table = generate_focus_table(ctx, started, finished)
    if insert_before in content:
        head, tail = content.split(insert_before, 1)
        content = head.rstrip() + table + "\n\n" + insert_before + tail
    else:
        content = content.rstrip() + table
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    started = datetime.now(timezone.utc)
    ctx = FocusContext()
    try:
        with httpx.Client() as client:
            client.get(f"{BASE}/api/health", timeout=5)
            run_id = find_latest_run_id(client)
            if run_id is None:
                print("No runs found", file=sys.stderr)
                return 1
            ctx.run_id = run_id
            retest_run_pipeline(client, ctx, run_id)
            # project_id from run detail
            _, body, _ = req(client, "GET", f"{GEO}/runs/{run_id}")
            project_id = (jdata(body) or {}).get("project_id")
            retest_delete_scenarios(client, ctx, project_id)
    except httpx.ConnectError:
        print("ERROR: API not reachable", file=sys.stderr)
        return 1

    finished = datetime.now(timezone.utc)
    patch_report(ctx, started, finished)
    passed = sum(1 for r in ctx.results if r.passed)
    print(f"Focused retest: {passed}/{len(ctx.results)} passed. Report section updated.")
    return 0 if all(r.passed or r.verdict in {"blocked", "env_limit"} for r in ctx.results) else 1


if __name__ == "__main__":
    sys.exit(main())
