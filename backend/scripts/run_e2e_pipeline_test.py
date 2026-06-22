"""End-to-end pipeline test: collection -> analysis -> data output -> report export."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"
GEO = f"{BASE}/api/geo-monitoring"
COLLECT_POLL_INTERVAL = 5
COLLECT_POLL_MAX = 600
ANALYSIS_POLL_MAX = 180
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "e2e_test_output"


@dataclass
class StepResult:
    phase: str
    name: str
    passed: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    project_id: int | None = None
    run_id: int | None = None
    answer_ids: list[int] = field(default_factory=list)
    report_ids: list[int] = field(default_factory=list)
    steps: list[StepResult] = field(default_factory=list)


def req(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: dict | list | None = None,
    params: dict | None = None,
    timeout: float = 120.0,
) -> tuple[int, Any, float]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": str(uuid.uuid4()),
    }
    start = time.perf_counter()
    r = client.request(method, url, json=json_body, params=params, headers=headers, timeout=timeout)
    elapsed = (time.perf_counter() - start) * 1000
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            body = r.json()
        except json.JSONDecodeError:
            body = r.text
    else:
        body = r.content if method == "GET" and "/download" in url else r.text
    return r.status_code, body, elapsed


def jcode(body: Any) -> int | str | None:
    return body.get("code") if isinstance(body, dict) else None


def jdata(body: Any) -> Any:
    return body.get("data") if isinstance(body, dict) else None


def jmsg(body: Any) -> str:
    return str(body.get("message", "")) if isinstance(body, dict) else ""


def record_step(ctx: PipelineContext, phase: str, name: str, passed: bool, detail: str = "", **data: Any) -> None:
    ctx.steps.append(StepResult(phase=phase, name=name, passed=passed, detail=detail, data=dict(data)))


def ensure_project(client: httpx.Client, ctx: PipelineContext) -> bool:
    phase = "0. 前置检查"
    status, body, _ = req(client, "GET", f"{BASE}/api/ready", timeout=10)
    ok = status == 200 and isinstance(body, dict) and body.get("code") == 0
    record_step(ctx, phase, "服务就绪检查", ok, jmsg(body) if isinstance(body, dict) else str(body))
    if not ok:
        return False

    status, body, _ = req(client, "GET", f"{GEO}/platforms", params={"page": 1, "page_size": 20, "enabled": True})
    items = (jdata(body) or {}).get("items", []) if status == 200 else []
    if not items:
        status, body, _ = req(client, "GET", f"{GEO}/platforms", params={"page": 1, "page_size": 20})
        all_items = (jdata(body) or {}).get("items", [])
        for code in ("qwen", "deepseek", "doubao"):
            if any(p["platform_code"] == code for p in all_items):
                req(client, "PUT", f"{GEO}/platforms/{code}", json_body={"enabled": True})
                items = [{"platform_code": code}]
                break
    platform_code = items[0]["platform_code"] if items else None
    record_step(
        ctx,
        phase,
        "启用 AI 平台",
        platform_code is not None,
        f"platform={platform_code}",
        platform_code=platform_code,
    )
    if not platform_code:
        return False

    suffix = uuid.uuid4().hex[:6]
    status, body, _ = req(
        client,
        "POST",
        f"{GEO}/projects",
        json_body={"project_name": f"E2E流水线-{suffix}", "industry": "测试"},
    )
    pid = (jdata(body) or {}).get("id") if status == 200 and jcode(body) == 0 else None
    record_step(ctx, phase, "创建测试项目", pid is not None, f"project_id={pid}")
    if not pid:
        return False
    ctx.project_id = pid

    req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/brands",
        json_body={"brand_name": "杭州宋城", "brand_type": "target", "brand_words": ["宋城"]},
    )
    req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/brands",
        json_body={"brand_name": "竞品A", "brand_type": "competitor"},
    )
    _, ps_body, _ = req(
        client,
        "POST",
        f"{GEO}/projects/{pid}/prompt-sets",
        json_body={"set_name": "E2E集", "version_no": f"v{suffix}"},
    )
    ps_id = (jdata(ps_body) or {}).get("id")
    if ps_id:
        req(
            client,
            "POST",
            f"{GEO}/prompt-sets/{ps_id}/prompts",
            json_body={"prompt_code": f"P1-{suffix}", "prompt_text": "国内有哪些靠谱的第三方检测机构？"},
        )
        req(client, "POST", f"{GEO}/prompt-sets/{ps_id}/activate")
    record_step(ctx, phase, "配置品牌与 Prompt 集", ps_id is not None, f"prompt_set_id={ps_id}")
    ctx._platform_code = platform_code  # type: ignore[attr-defined]
    return True


def create_and_wait_collection(client: httpx.Client, ctx: PipelineContext) -> bool:
    phase = "1. 采集"
    platform_code = getattr(ctx, "_platform_code", "qwen")
    status, body, _ = req(
        client,
        "POST",
        f"{GEO}/runs",
        json_body={"project_id": ctx.project_id, "platform_codes": [platform_code]},
    )
    run = jdata(body) or {}
    run_id = run.get("id")
    ok = status == 200 and jcode(body) == 0 and run_id
    record_step(
        ctx,
        phase,
        "创建监测运行",
        ok,
        f"run_id={run_id}, total_tasks={run.get('total_tasks')}, status={run.get('status')}",
        run_id=run_id,
    )
    if not ok:
        return False
    ctx.run_id = run_id

    terminal = {"completed", "partial_success", "failed", "cancelled"}
    deadline = time.time() + COLLECT_POLL_MAX
    last = None
    while time.time() < deadline:
        status, body, _ = req(client, "GET", f"{GEO}/runs/{run_id}")
        if status == 200 and jcode(body) == 0:
            data = jdata(body) or {}
            last = data.get("status")
            if last in terminal:
                ok = last in {"completed", "partial_success"} and (data.get("succeeded_tasks") or 0) > 0
                record_step(
                    ctx,
                    phase,
                    "等待采集终态",
                    ok,
                    f"status={last}, succeeded={data.get('succeeded_tasks')}, failed={data.get('failed_tasks')}",
                )
                return ok
        time.sleep(COLLECT_POLL_INTERVAL)

    record_step(ctx, phase, "等待采集终态", False, f"timeout after {COLLECT_POLL_MAX}s, last_status={last}")
    return False


def verify_answers(client: httpx.Client, ctx: PipelineContext) -> bool:
    phase = "2. 采集数据输出"
    status, body, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/tasks")
    tasks = (jdata(body) or {}).get("items", []) if status == 200 else []
    success_tasks = [t for t in tasks if t.get("status") == "success"]
    record_step(ctx, phase, "查询采集任务", status == 200 and jcode(body) == 0, f"success_tasks={len(success_tasks)}/{len(tasks)}")

    status, body, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/answers")
    items = (jdata(body) or {}).get("items", []) if status == 200 else []
    ctx.answer_ids = [a["id"] for a in items if a.get("id")]
    record_step(ctx, phase, "查询采集答案列表", len(ctx.answer_ids) > 0, f"answers={len(ctx.answer_ids)}")

    if ctx.answer_ids:
        status, body, _ = req(client, "GET", f"{GEO}/answers/{ctx.answer_ids[0]}")
        detail = jdata(body) or {}
        has_text = bool((detail.get("normalized_text") or "").strip())
        citations = detail.get("citations") or []
        brands = detail.get("brand_results") or []
        record_step(
            ctx,
            phase,
            "查询答案详情",
            status == 200 and has_text,
            f"text_len={len(detail.get('normalized_text') or '')}, citations={len(citations)}, brands={len(brands)}",
        )
    return len(ctx.answer_ids) > 0


def run_analysis(client: httpx.Client, ctx: PipelineContext) -> bool:
    phase = "3. 分析"
    status, body, elapsed = req(
        client,
        "POST",
        f"{GEO}/runs/{ctx.run_id}/analyze",
        timeout=300.0,
    )
    ok = status == 200 and jcode(body) == 0
    data = jdata(body) or {}
    record_step(
        ctx,
        phase,
        "触发 Agent 分析",
        ok,
        f"analysis_status={data.get('analysis_status')}, elapsed_ms={elapsed:.0f}, msg={jmsg(body)}",
    )
    if not ok:
        return False

    status, body, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/analysis")
    analysis = jdata(body) or {}
    platforms = analysis.get("platforms") or []
    ok = status == 200 and jcode(body) == 0 and analysis.get("analysis_status") in {
        "completed",
        "partial_success",
        "skipped",
    }
    metrics = platforms[0] if platforms else {}
    record_step(
        ctx,
        phase,
        "获取平台分析指标",
        ok,
        f"status={analysis.get('analysis_status')}, platforms={len(platforms)}, "
        f"mention_rate={metrics.get('brand_mention_rate')}, valid_answers={metrics.get('valid_answer_count')}",
    )

    status, body, _ = req(client, "GET", f"{GEO}/runs/{ctx.run_id}/agent-executions")
    executions = (jdata(body) or {}).get("total", 0) if status == 200 else 0
    record_step(ctx, phase, "查询 Agent 审计", status == 200 and jcode(body) == 0, f"executions={executions}")
    return ok


def verify_dashboard_trends(client: httpx.Client, ctx: PipelineContext) -> bool:
    phase = "4. 数据输出"
    status, body, _ = req(client, "GET", f"{GEO}/projects/{ctx.project_id}/dashboard")
    dash = jdata(body) or {}
    latest = dash.get("latest_run") or {}
    ok = status == 200 and jcode(body) == 0 and latest.get("run_id") == ctx.run_id
    record_step(
        ctx,
        phase,
        "项目看板汇总",
        ok,
        f"latest_run_id={latest.get('run_id')}, analysis_status={latest.get('analysis_status')}",
    )

    status, body, _ = req(
        client,
        "GET",
        f"{GEO}/projects/{ctx.project_id}/trends",
        params={"metric_code": "brand_mention_rate", "page": 1, "page_size": 10},
    )
    items = (jdata(body) or {}).get("items", []) if status == 200 else []
    record_step(ctx, phase, "品牌提及率趋势", status == 200 and jcode(body) == 0, f"points={len(items)}")
    return ok


def export_reports(client: httpx.Client, ctx: PipelineContext) -> bool:
    phase = "5. 报告导出"
    status, body, _ = req(
        client,
        "POST",
        f"{GEO}/runs/{ctx.run_id}/reports",
        json_body={"formats": ["md", "html"]},
        timeout=120.0,
    )
    ok = status == 200 and jcode(body) == 0
    reports = (jdata(body) or {}).get("reports", []) if ok else []
    ctx.report_ids = [r["id"] for r in reports if r.get("id")]
    record_step(ctx, phase, "生成 MD/HTML 报告", ok and len(ctx.report_ids) >= 1, f"reports={len(ctx.report_ids)}")
    if not ok:
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_downloaded = True
    for rid in ctx.report_ids:
        status, body, _ = req(client, "GET", f"{GEO}/reports/{rid}")
        meta = jdata(body) or {}
        fmt = meta.get("format", "unknown")
        expected_checksum = meta.get("checksum")

        status, content, _ = req(client, "GET", f"{GEO}/reports/{rid}/download", timeout=60.0)
        if isinstance(content, bytes):
            raw = content
        else:
            raw = str(content).encode("utf-8")
        checksum = hashlib.sha256(raw).hexdigest()
        match = checksum == expected_checksum
        out_path = OUTPUT_DIR / f"run_{ctx.run_id}_{fmt}_{rid}.{fmt if fmt != 'md' else 'md'}"
        out_path.write_bytes(raw)
        all_downloaded = all_downloaded and status == 200 and len(raw) > 0 and match
        record_step(
            ctx,
            phase,
            f"下载 {fmt.upper()} 报告",
            status == 200 and len(raw) > 0 and match,
            f"size={len(raw)}, checksum_ok={match}, path={out_path.name}",
        )
    return all_downloaded


def generate_markdown_report(ctx: PipelineContext, started: datetime, finished: datetime) -> str:
    passed = sum(1 for s in ctx.steps if s.passed)
    total = len(ctx.steps)
    lines = [
        "# 端到端流水线测试报告",
        "",
        f"- **测试时间**：{started.astimezone().strftime('%Y-%m-%d %H:%M:%S')} ~ {finished.astimezone().strftime('%H:%M:%S')} (本地)",
        f"- **耗时**：{(finished - started).total_seconds():.1f} 秒",
        f"- **脚本**：`backend/scripts/run_e2e_pipeline_test.py`",
        f"- **project_id**：`{ctx.project_id}`",
        f"- **run_id**：`{ctx.run_id}`",
        f"- **步骤通过**：{passed}/{total}",
        "",
        "## 步骤结果",
        "",
        "| 阶段 | 步骤 | 结果 | 说明 |",
        "| --- | --- | --- | --- |",
    ]
    for s in ctx.steps:
        icon = "PASS" if s.passed else "**FAIL**"
        lines.append(f"| {s.phase} | {s.name} | {icon} | {s.detail} |")

    fails = [s for s in ctx.steps if not s.passed]
    if fails:
        lines.extend(["", "## 失败步骤", ""])
        for s in fails:
            lines.append(f"- **{s.phase} / {s.name}**：{s.detail}")

    lines.extend(
        [
            "",
            "## 环境要求",
            "",
            "- FastAPI @ :8000",
            "- Dramatiq collection worker",
            "- 外部 AI 平台密钥（采集）",
            "- Agent LLM 配置（分析）",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    started = datetime.now(timezone.utc)
    ctx = PipelineContext()
    report_path = Path(__file__).resolve().parents[2] / "docs" / "端到端流水线测试报告.md"

    try:
        with httpx.Client() as client:
            if not ensure_project(client, ctx):
                raise RuntimeError("前置检查失败")
            if not create_and_wait_collection(client, ctx):
                raise RuntimeError("采集未完成")
            if not verify_answers(client, ctx):
                raise RuntimeError("采集数据验证失败")
            if not run_analysis(client, ctx):
                raise RuntimeError("分析失败")
            if not verify_dashboard_trends(client, ctx):
                raise RuntimeError("数据输出验证失败")
            if not export_reports(client, ctx):
                raise RuntimeError("报告导出失败")
    except httpx.ConnectError:
        print("ERROR: 无法连接 API http://127.0.0.1:8000", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"PIPELINE STOPPED: {exc}", file=sys.stderr)

    finished = datetime.now(timezone.utc)
    report = generate_markdown_report(ctx, started, finished)
    report_path.write_text(report, encoding="utf-8")
    passed = sum(1 for s in ctx.steps if s.passed)
    total = len(ctx.steps)
    print(f"E2E pipeline: {passed}/{total} steps passed")
    print(f"Report: {report_path}")
    if ctx.report_ids:
        print(f"Downloaded reports to: {OUTPUT_DIR}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
