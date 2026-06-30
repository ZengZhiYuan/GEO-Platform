"""Production smoke test runner with layered dry-run / paid gates (Task O4).

分层：
1. **preflight（默认）**：配置与依赖就绪检查，不调用付费接口。
2. **adapter-smoke**：单条模力指数 adapter 真实调用（``--adapter-smoke --allow-paid-provider``）。
3. **business-loop**：经 API 创建 molizhishu Run → worker 采集 → 分析 → 报告（``--business-loop --allow-paid-provider``）。

mock 回归请使用 pytest；本脚本仅供手动线上/联调 smoke。

用法::

    backend\\.venv\\Scripts\\python.exe backend/scripts/run_production_smoke_test.py

    backend\\.venv\\Scripts\\python.exe backend/scripts/run_production_smoke_test.py \\
        --base-url http://127.0.0.1:8000 --business-loop --allow-paid-provider
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for path in (_BACKEND_ROOT, _SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import httpx

from app.core.config import settings
from smoke_preflight import (
    ensure_allow_paid_provider,
    mask_secret,
    preflight_exit_code,
    print_preflight_report,
    redact_secrets,
    resolve_smoke_auth_headers,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PLATFORM = "molizhishu_qianwen_web"
COLLECT_POLL_INTERVAL = 8
COLLECT_POLL_MAX = 900
ANALYSIS_TIMEOUT = 300.0


@dataclass
class StepResult:
    phase: str
    name: str
    passed: bool
    detail: str = ""


@dataclass
class SmokeContext:
    base_url: str
    auth_headers: dict[str, str] = field(default_factory=dict)
    project_id: int | None = None
    run_id: int | None = None
    report_ids: list[int] = field(default_factory=list)
    steps: list[StepResult] = field(default_factory=list)


def _geo(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/geo-monitoring"


def _record(ctx: SmokeContext, phase: str, name: str, passed: bool, detail: str = "") -> None:
    ctx.steps.append(StepResult(phase=phase, name=name, passed=passed, detail=detail))


def _req(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: dict | list | None = None,
    params: dict | None = None,
    timeout: float = 60.0,
    auth_headers: dict[str, str] | None = None,
) -> tuple[int, Any, float]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": str(uuid.uuid4()),
    }
    if auth_headers:
        headers.update(auth_headers)
    start = time.perf_counter()
    response = client.request(
        method,
        url,
        json=json_body,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    elapsed = (time.perf_counter() - start) * 1000
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body: Any = response.json()
        except Exception:
            body = response.text
    else:
        body = response.content if "/download" in url else response.text
    return response.status_code, body, elapsed


def _jcode(body: Any) -> int | str | None:
    return body.get("code") if isinstance(body, dict) else None


def _jdata(body: Any) -> Any:
    return body.get("data") if isinstance(body, dict) else None


def _jmsg(body: Any) -> str:
    return str(body.get("message", "")) if isinstance(body, dict) else ""


def _sanitize_detail(detail: str) -> str:
    secrets = [
        settings.MOLIZHISHU_API_TOKEN.strip(),
        settings.AGENT_LLM_API_KEY.strip(),
    ]
    return redact_secrets(detail, [item for item in secrets if item])


def run_local_preflight() -> int:
    report = print_preflight_report(settings)
    print("")
    print("Layer: preflight (local config only)")
    print("Paid layers require --allow-paid-provider:")
    print("  --adapter-smoke     模力指数 adapter 单条真实调用")
    print("  --business-loop     API 创建 molizhishu Run 并等待 worker 闭环")
    if not settings.MOLIZHISHU_API_TOKEN.strip():
        return 1
    return preflight_exit_code(report)


def probe_api_preflight(ctx: SmokeContext) -> bool:
    phase = "API preflight"
    try:
        with httpx.Client(base_url=ctx.base_url, timeout=15.0) as client:
            status, body, _ = _req(
                client, "GET", f"{_geo(ctx.base_url)}/health", auth_headers=ctx.auth_headers
            )
            ok = status == 200 and isinstance(body, dict) and body.get("code") == 0
            _record(ctx, phase, "health", ok, _sanitize_detail(_jmsg(body) if isinstance(body, dict) else str(status)))
            if not ok:
                return False

            status, body, _ = _req(
                client, "GET", f"{_geo(ctx.base_url)}/ready", auth_headers=ctx.auth_headers
            )
            ready_ok = status in {200, 503} and isinstance(body, dict) and body.get("code") == 0
            data = _jdata(body) or {}
            platform_runtime = data.get("platform_runtime") or {}
            collection_ready = platform_runtime.get("collection_ready")
            _record(
                ctx,
                phase,
                "ready",
                ready_ok,
                _sanitize_detail(
                    f"status={data.get('status')}, collection_ready={collection_ready}"
                ),
            )
            return ready_ok
    except httpx.HTTPError as exc:
        _record(ctx, phase, "API 连通", False, _sanitize_detail(str(exc)))
        return False


def run_adapter_smoke_subprocess() -> int:
    script = _SCRIPTS_DIR / "molizhishu_smoke_test.py"
    command = [
        sys.executable,
        str(script),
        "--allow-paid-provider",
        "--max-polls",
        "30",
        "--poll-interval",
        "8",
    ]
    proc = subprocess.run(command, cwd=_SCRIPTS_DIR.parents[1], check=False)
    return proc.returncode


def _ensure_minimal_project(client: httpx.Client, ctx: SmokeContext) -> bool:
    phase = "Business setup"
    suffix = uuid.uuid4().hex[:6]
    status, body, _ = _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/projects",
        json_body={"project_name": f"Smoke-{suffix}", "industry": "测试"},
        auth_headers=ctx.auth_headers,
    )
    project_id = (_jdata(body) or {}).get("id") if status == 200 and _jcode(body) == 0 else None
    _record(ctx, phase, "创建项目", project_id is not None, f"project_id={project_id}")
    if not project_id:
        return False
    ctx.project_id = project_id

    _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/projects/{project_id}/brands",
        json_body={"brand_name": "SmokeTarget", "brand_type": "target", "brand_words": ["Smoke"]},
        auth_headers=ctx.auth_headers,
    )
    _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/projects/{project_id}/brands",
        json_body={"brand_name": "SmokeCompetitor", "brand_type": "competitor"},
        auth_headers=ctx.auth_headers,
    )
    _, ps_body, _ = _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/projects/{project_id}/prompt-sets",
        json_body={"set_name": "SmokeSet", "version_no": f"v{suffix}"},
        auth_headers=ctx.auth_headers,
    )
    ps_id = (_jdata(ps_body) or {}).get("id")
    if ps_id:
        _req(
            client,
            "POST",
            f"{_geo(ctx.base_url)}/prompt-sets/{ps_id}/prompts",
            json_body={
                "prompt_code": f"P-{suffix}",
                "prompt_text": "国内有哪些值得关注的 AI 监测平台？",
            },
            auth_headers=ctx.auth_headers,
        )
        _req(
            client,
            "POST",
            f"{_geo(ctx.base_url)}/prompt-sets/{ps_id}/activate",
            auth_headers=ctx.auth_headers,
        )
    _record(ctx, phase, "配置品牌与 Prompt", ps_id is not None, f"prompt_set_id={ps_id}")
    return ps_id is not None


def _create_and_wait_molizhishu_run(client: httpx.Client, ctx: SmokeContext, platform_code: str) -> bool:
    phase = "Business collection"
    status, body, _ = _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/runs",
        json_body={
            "project_id": ctx.project_id,
            "collection_source": "molizhishu",
            "platform_codes": [platform_code],
            "provider_mode_by_platform": {platform_code: "search"},
            "provider_screenshot": 0,
        },
        auth_headers=ctx.auth_headers,
    )
    run = _jdata(body) or {}
    run_id = run.get("id")
    ok = status == 200 and _jcode(body) == 0 and run_id
    _record(
        ctx,
        phase,
        "创建 molizhishu Run",
        ok,
        _sanitize_detail(
            f"run_id={run_id}, status={run.get('status')}, tasks={run.get('total_tasks')}, code={_jcode(body)}"
        ),
    )
    if not ok:
        if _jcode(body) == 40908:
            print("提示：Run 被拒绝 (40908)，请确认 MOLIZHISHU_ENABLED=true 且 worker 运行时配置一致。")
        return False
    ctx.run_id = run_id

    terminal = {"completed", "partial_success", "failed", "cancelled"}
    deadline = time.time() + COLLECT_POLL_MAX
    last_status = None
    while time.time() < deadline:
        status, body, _ = _req(
            client,
            "GET",
            f"{_geo(ctx.base_url)}/runs/{run_id}",
            auth_headers=ctx.auth_headers,
        )
        if status == 200 and _jcode(body) == 0:
            data = _jdata(body) or {}
            last_status = data.get("status")
            if last_status in terminal:
                ok = last_status in {"completed", "partial_success"} and (
                    data.get("succeeded_tasks") or 0
                ) > 0
                _record(
                    ctx,
                    phase,
                    "等待采集终态",
                    ok,
                    _sanitize_detail(
                        f"status={last_status}, succeeded={data.get('succeeded_tasks')}, "
                        f"failed={data.get('failed_tasks')}"
                    ),
                )
                return ok
        time.sleep(COLLECT_POLL_INTERVAL)

    _record(
        ctx,
        phase,
        "等待采集终态",
        False,
        _sanitize_detail(f"timeout after {COLLECT_POLL_MAX}s, last_status={last_status}"),
    )
    return False


def _run_analysis_and_report(client: httpx.Client, ctx: SmokeContext) -> bool:
    phase = "Business analysis/report"
    status, body, elapsed = _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/runs/{ctx.run_id}/analyze",
        timeout=ANALYSIS_TIMEOUT,
        auth_headers=ctx.auth_headers,
    )
    ok = status == 200 and _jcode(body) == 0
    data = _jdata(body) or {}
    _record(
        ctx,
        phase,
        "触发分析",
        ok,
        _sanitize_detail(
            f"analysis_status={data.get('analysis_status')}, elapsed_ms={elapsed:.0f}"
        ),
    )
    if not ok:
        return False

    status, body, _ = _req(
        client,
        "POST",
        f"{_geo(ctx.base_url)}/runs/{ctx.run_id}/reports",
        json_body={"formats": ["pdf"]},
        timeout=120.0,
        auth_headers=ctx.auth_headers,
    )
    reports = (_jdata(body) or {}).get("reports", []) if status == 200 and _jcode(body) == 0 else []
    ctx.report_ids = [item["id"] for item in reports if item.get("id")]
    _record(ctx, phase, "生成 PDF 报告", len(ctx.report_ids) > 0, f"reports={len(ctx.report_ids)}")
    if not ctx.report_ids:
        return False

    report_id = ctx.report_ids[0]
    status, content, _ = _req(
        client,
        "GET",
        f"{_geo(ctx.base_url)}/reports/{report_id}/download",
        timeout=60.0,
        auth_headers=ctx.auth_headers,
    )
    size = len(content) if isinstance(content, bytes) else len(str(content))
    _record(ctx, phase, "下载 PDF", status == 200 and size > 0, f"size={size}")
    return status == 200 and size > 0


def run_business_loop(ctx: SmokeContext, platform_code: str) -> int:
    print("")
    print("=== Business-loop smoke（真实 molizhishu Run + worker + Agent + 报告） ===")
    print(f"Base URL: {ctx.base_url}")
    print(f"Platform: {platform_code}")
    print(f"Molizhishu token: {mask_secret(settings.MOLIZHISHU_API_TOKEN)}")
    print("输出已脱敏，不包含完整 prompt 回答正文。")
    print("")

    if not probe_api_preflight(ctx):
        return 1
    try:
        with httpx.Client(base_url=ctx.base_url, timeout=60.0) as client:
            if not _ensure_minimal_project(client, ctx):
                return 1
            if not _create_and_wait_molizhishu_run(client, ctx, platform_code):
                return 1
            if not _run_analysis_and_report(client, ctx):
                return 1
    except httpx.HTTPError as exc:
        _record(ctx, "Business-loop", "HTTP 错误", False, _sanitize_detail(str(exc)))
        return 1

    passed = sum(1 for step in ctx.steps if step.passed)
    total = len(ctx.steps)
    print("")
    print(f"Business-loop: {passed}/{total} steps passed")
    print(f"project_id={ctx.project_id}, run_id={ctx.run_id}, reports={ctx.report_ids}")
    for step in ctx.steps:
        mark = "PASS" if step.passed else "FAIL"
        print(f"  [{mark}] {step.phase} / {step.name}: {step.detail}")
    return 0 if passed == total else 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="生产 smoke 分层脚本（默认 preflight dry-run）"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API 基地址，默认 {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--allow-paid-provider",
        action="store_true",
        help="允许 adapter-smoke / business-loop 调用真实模力指数与 Agent（可能产生费用）",
    )
    parser.add_argument(
        "--adapter-smoke",
        action="store_true",
        help="执行模力指数 adapter 层真实 smoke（需 --allow-paid-provider）",
    )
    parser.add_argument(
        "--business-loop",
        action="store_true",
        help="执行业务闭环 smoke：创建 molizhishu Run 并等待 worker（需 --allow-paid-provider）",
    )
    parser.add_argument(
        "--platform-code",
        default=DEFAULT_PLATFORM,
        help=f"business-loop 使用的 molizhishu 平台码，默认 {DEFAULT_PLATFORM}",
    )
    parser.add_argument(
        "--api-preflight",
        action="store_true",
        help="在 preflight 之外额外探测 /health 与 /ready",
    )
    args = parser.parse_args()

    if args.adapter_smoke or args.business_loop:
        ensure_allow_paid_provider(
            allow_paid_provider=args.allow_paid_provider,
            action="adapter-smoke / business-loop",
        )

    exit_code = run_local_preflight()
    if exit_code != 0 and (args.adapter_smoke or args.business_loop):
        return exit_code

    if args.api_preflight or args.business_loop:
        ctx = SmokeContext(
            base_url=args.base_url,
            auth_headers=resolve_smoke_auth_headers(settings),
        )
        if not probe_api_preflight(ctx):
            return 1
        passed = sum(1 for step in ctx.steps if step.passed)
        print(f"API preflight: {passed}/{len(ctx.steps)} checks passed")

    if args.adapter_smoke:
        return run_adapter_smoke_subprocess()

    if args.business_loop:
        return run_business_loop(
            SmokeContext(
                base_url=args.base_url,
                auth_headers=resolve_smoke_auth_headers(settings),
            ),
            args.platform_code,
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
