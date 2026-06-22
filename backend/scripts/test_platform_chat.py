"""Quick chat connectivity test for Qwen and Doubao via project adapters."""

from __future__ import annotations

import asyncio
import sys
import uuid

from app.core.config import settings
from app.geo_monitoring.adapters.base import (
    PlatformCredential,
    PlatformQuery,
    compute_credential_fingerprint,
)
from app.geo_monitoring.adapters.doubao import DoubaoAdapter
from app.geo_monitoring.adapters.qwen import QwenAdapter

QUESTION = "用一句话介绍杭州西湖。"


def _mask_key_count(raw: str) -> int:
    return len(settings.parsed_api_keys(raw))


async def _test_platform(
    *,
    name: str,
    enabled: bool,
    model: str,
    key_count: int,
    adapter,
    api_key: str,
) -> dict:
    if key_count == 0:
        return {"platform": name, "status": "SKIP", "reason": "未配置 API Key ( *_API_KEYS 为空 )"}
    if not model.strip():
        return {"platform": name, "status": "SKIP", "reason": "未配置模型 ( *_MODEL 为空 )"}

    request = PlatformQuery(
        prompt=QUESTION,
        system_prompt=None,
        model=model,
        temperature=None,
        request_id=str(uuid.uuid4()),
    )
    credential = PlatformCredential(
        platform_code=adapter.code,
        fingerprint=compute_credential_fingerprint(adapter.code, api_key),
        api_key=api_key,
    )
    try:
        answer = await adapter.query(request, credential=credential)
        text = answer.text.strip().replace("\n", " ")
        preview = text[:120] + ("..." if len(text) > 120 else "")
        return {
            "platform": name,
            "status": "OK",
            "enabled_in_env": enabled,
            "model": answer.model,
            "latency_ms": answer.latency_ms,
            "provider_request_id": answer.provider_request_id,
            "usage": answer.usage,
            "reply_preview": preview,
        }
    except Exception as exc:
        msg = str(exc)
        for secret in (api_key,):
            if secret and secret in msg:
                msg = msg.replace(secret, "***")
        return {"platform": name, "status": "FAIL", "error": msg}


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    platforms = [
        (
            "doubao",
            settings.DOUBAO_ENABLED,
            settings.DOUBAO_MODEL,
            settings.DOUBAO_API_KEYS,
            DoubaoAdapter(),
        ),
        (
            "qwen",
            settings.QWEN_ENABLED,
            settings.QWEN_MODEL,
            settings.QWEN_API_KEYS,
            QwenAdapter(),
        ),
    ]

    print("=== 平台 Chat 连通性测试 ===")
    print(f"问题: {QUESTION}\n")

    results = []
    for name, enabled, model, keys_raw, adapter in platforms:
        key_count = _mask_key_count(keys_raw)
        keys = settings.parsed_api_keys(keys_raw)
        api_key = keys[0] if keys else ""
        print(f"[{name}] enabled={enabled}, model={model or '(未设置)'}, api_key_count={key_count}")
        result = await _test_platform(
            name=name,
            enabled=enabled,
            model=model,
            key_count=key_count,
            adapter=adapter,
            api_key=api_key,
        )
        results.append(result)

    print("\n=== 结果 ===")
    exit_code = 0
    for r in results:
        status = r["status"]
        print(f"\n--- {r['platform']} ---")
        if status == "OK":
            print(f"状态: 成功")
            if not r.get("enabled_in_env"):
                print("提示: .env 中 *_ENABLED=false，采集任务不会调用此平台，请将对应 ENABLED 设为 true")
            print(f"模型: {r['model']}")
            print(f"延迟: {r['latency_ms']} ms")
            print(f"请求 ID: {r.get('provider_request_id')}")
            print(f"Token 用量: {r.get('usage')}")
            print(f"回复预览: {r['reply_preview']}")
        elif status == "SKIP":
            print(f"状态: 跳过")
            print(f"原因: {r['reason']}")
            exit_code = 1
        else:
            print(f"状态: 失败")
            print(f"错误: {r['error']}")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
