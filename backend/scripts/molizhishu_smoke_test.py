"""Manual smoke test for Molizhishu Business API (adapter layer).

分层说明（Task O4）：
- **默认 dry-run**：仅输出 preflight，不调用真实模力指数接口。
- **adapter-smoke**：加 ``--allow-paid-provider`` 后才会发起真实 HTTP，可能产生费用。
- 不写业务数据库，不触发 Dramatiq worker。

用法（仓库根目录）::

    backend\\.venv\\Scripts\\python.exe backend/scripts/molizhishu_smoke_test.py

真实 adapter 调用（手动、可能付费）::

    backend\\.venv\\Scripts\\python.exe backend/scripts/molizhishu_smoke_test.py --allow-paid-provider

可选参数::

    --prompt "问题文本"
    --platform qianwen
    --mode search
    --screenshot 0
    --max-polls 60
    --poll-interval 8
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for path in (_BACKEND_ROOT, _SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.core.config import settings
from app.geo_monitoring.adapters.base import (
    PlatformCredential,
    PlatformQuery,
    compute_credential_fingerprint,
)
from app.geo_monitoring.adapters.errors import AdapterError
from app.geo_monitoring.adapters.molizhishu import MolizhishuAdapter, MolizhishuPendingError
from app.geo_monitoring.services.platforms import MOLIZHISHU_PLATFORM_MAPPINGS
from smoke_preflight import (
    ensure_allow_paid_provider,
    mask_secret,
    preflight_exit_code,
    print_preflight_report,
    redact_secrets,
)

DEFAULT_PROMPT = "用一句话介绍杭州西湖。"
DEFAULT_PLATFORM = "qianwen"
DEFAULT_MODE = "search"
DEFAULT_SCREENSHOT = 0


def _resolve_platform_code(molizhishu_platform: str) -> str:
    for code, spec in MOLIZHISHU_PLATFORM_MAPPINGS.items():
        if spec["molizhishu_platform"] == molizhishu_platform:
            return code
    supported = sorted(
        {
            spec["molizhishu_platform"]
            for spec in MOLIZHISHU_PLATFORM_MAPPINGS.values()
        }
    )
    raise SystemExit(
        f"不支持的 platform={molizhishu_platform!r}，可选：{', '.join(supported)}"
    )


def _answer_preview(text: str, limit: int = 160) -> str:
    normalized = text.strip().replace("\n", " ")
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def run_dry_run() -> int:
    report = print_preflight_report(settings)
    print("")
    print("Dry-run 完成：未调用模力指数 API。")
    print("真实 adapter 验证请加：--allow-paid-provider")
    if not settings.MOLIZHISHU_API_TOKEN.strip():
        print("提示：当前未配置 MOLIZHISHU_API_TOKEN。")
        return 1
    if not report["molizhishu"]["configured"]:
        return 1
    return 0


async def _run_paid_adapter_smoke(
    *,
    prompt: str,
    platform: str,
    mode: str,
    screenshot: int,
    max_polls: int,
    poll_interval: float,
) -> int:
    token = settings.MOLIZHISHU_API_TOKEN.strip()
    if not token:
        print(
            "未配置 MOLIZHISHU_API_TOKEN，已退出。\n"
            "请在 .env 中设置模力指数 API Token 后重试。"
        )
        return 1

    report = print_preflight_report(settings)
    if not report.get("ready_for_paid_molizhishu"):
        return 1

    platform_code = _resolve_platform_code(platform)
    spec = MOLIZHISHU_PLATFORM_MAPPINGS[platform_code]
    adapter = MolizhishuAdapter(
        code=platform_code,
        molizhishu_platform=spec["molizhishu_platform"],
        default_mode=spec["default_mode"],
        base_url=settings.MOLIZHISHU_BASE_URL,
        timeout_seconds=settings.MOLIZHISHU_REQUEST_TIMEOUT_SECONDS,
        raw_response_enabled=True,
    )
    credential = PlatformCredential(
        platform_code=platform_code,
        fingerprint=compute_credential_fingerprint(platform_code, token),
        api_key=token,
    )

    metadata: dict[str, object] = {
        "provider_mode": mode,
        "provider_screenshot": screenshot,
    }
    request = PlatformQuery(
        prompt=prompt,
        system_prompt=None,
        model=f"molizhishu:{spec['molizhishu_platform']}",
        temperature=None,
        request_id="molizhishu-smoke",
        metadata=metadata,
    )

    print("")
    print("=== 模力指数 Adapter Smoke（真实接口，可能产生费用） ===")
    print(f"Base URL: {settings.MOLIZHISHU_BASE_URL}")
    print(f"Token: {mask_secret(token)}")
    print(f"Prompt 摘要: {_answer_preview(prompt, 80)}")
    print(f"Platform: {platform} ({platform_code})")
    print(f"Mode: {mode}")
    print(f"Screenshot: {screenshot}")
    print(f"Max polls: {max_polls}, interval: {poll_interval}s\n")

    task_id: str | None = None
    subtask_id: str | None = None
    last_status: str | None = None

    for poll in range(1, max_polls + 1):
        query = PlatformQuery(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            model=request.model,
            temperature=request.temperature,
            request_id=request.request_id,
            metadata=dict(metadata),
        )
        try:
            answer = await adapter.query(query, credential=credential)
        except MolizhishuPendingError as exc:
            pending = exc.pending_metadata
            task_id = str(pending.get("molizhishu_task_id") or task_id or "")
            subtask_id = str(pending.get("molizhishu_subtask_id") or subtask_id or "")
            last_status = str(pending.get("molizhishu_status") or "pending")
            metadata.update(
                {
                    "molizhishu_task_id": task_id,
                    "molizhishu_subtask_id": subtask_id,
                    "provider_mode": pending.get("molizhishu_mode", mode),
                }
            )
            print(
                f"[poll {poll}/{max_polls}] status={last_status} "
                f"taskId={task_id} subTaskId={subtask_id}"
            )
            if poll >= max_polls:
                print("达到最大轮询次数，仍未完成。")
                return 1
            time.sleep(poll_interval)
            continue
        except AdapterError as exc:
            message = redact_secrets(str(exc), [token])
            print(f"采集失败: {message}")
            if task_id:
                print(f"taskId={task_id} subTaskId={subtask_id} status={last_status}")
            return 1

        raw = answer.raw_response or {}
        submit = raw.get("submit") or {}
        result = raw.get("result") or {}
        submit_data = submit.get("data") if isinstance(submit, dict) else {}
        result_data = result.get("data") if isinstance(result, dict) else {}
        task_id = str(
            (submit_data or {}).get("taskId")
            or metadata.get("molizhishu_task_id")
            or answer.provider_request_id
            or ""
        )
        subtask_id = str(
            metadata.get("molizhishu_subtask_id") or answer.provider_request_id or ""
        )
        last_status = str((result_data or {}).get("status") or "completed")
        citation_count = len(answer.citations)
        reference_count = 0
        if isinstance(result_data, dict):
            reference_count = len(result_data.get("referenceList") or [])

        print("=== 完成 ===")
        print(f"taskId: {task_id}")
        print(f"subTaskId: {subtask_id}")
        print(f"status: {last_status}")
        if last_status != "completed":
            print(
                "说明: provider 子任务 status 可能尚未 completed，"
                "但 answerContent 已可用，adapter 按生产口径提前返回。"
            )
        print(f"answerContent 摘要: {_answer_preview(answer.text)}")
        print(f"citation 数量: {citation_count}")
        print(f"reference 数量: {reference_count}")
        print(f"latency_ms: {answer.latency_ms}")
        return 0

    print("未达到完成状态。")
    return 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="模力指数 adapter 层 smoke（默认 dry-run；真实调用需 --allow-paid-provider）"
    )
    parser.add_argument(
        "--allow-paid-provider",
        action="store_true",
        help="允许调用真实模力指数 API（可能产生费用）",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="提交的问题文本")
    parser.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        help="模力指数 platform 字段，默认 qianwen",
    )
    parser.add_argument("--mode", default=DEFAULT_MODE, help="采集模式，默认 search")
    parser.add_argument(
        "--screenshot",
        type=int,
        default=DEFAULT_SCREENSHOT,
        choices=[0, 1, 2],
        help="截图策略 0/1/2，默认 0",
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=60,
        help="最大轮询次数，默认 60",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=8.0,
        help="pending 轮询间隔秒数，默认 8",
    )
    args = parser.parse_args()

    if not args.allow_paid_provider:
        return run_dry_run()

    ensure_allow_paid_provider(
        allow_paid_provider=True,
        action="模力指数 adapter smoke",
    )
    return asyncio.run(
        _run_paid_adapter_smoke(
            prompt=args.prompt,
            platform=args.platform,
            mode=args.mode,
            screenshot=args.screenshot,
            max_polls=args.max_polls,
            poll_interval=args.poll_interval,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
