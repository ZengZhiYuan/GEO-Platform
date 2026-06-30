import json
import os
import sys

import httpx

QUESTION = "杭州看文艺演出有哪些好去处？"

API_KEY = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODEL = os.getenv("DOUBAO_MODEL") or os.getenv("ARK_MODEL")


def extract_annotations(output_items: list) -> list[dict]:
    annotations: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for item in output_items:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            for ann in content.get("annotations") or []:
                url = ann.get("url", "")
                title = ann.get("title", "")
                key = (url, title)
                if key in seen:
                    continue
                seen.add(key)
                annotations.append(ann)
    return annotations


def extract_web_search_sources(output_items: list) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()

    for item in output_items:
        if item.get("type") != "web_search_call":
            continue
        action = item.get("action") or {}
        for source in action.get("sources") or []:
            url = source.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(source)
    return sources


if not API_KEY:
    print("请设置环境变量 ARK_API_KEY 或 DOUBAO_API_KEY", file=sys.stderr)
    sys.exit(1)

if not MODEL:
    print("请设置环境变量 DOUBAO_MODEL 或 ARK_MODEL（推理接入点 ID / 模型名）", file=sys.stderr)
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

payload = {
    "model": MODEL,
    "stream": True,
    "thinking": {"type": "enabled"},
    "tools": [{"type": "web_search"}],
    "include": ["web_search_call.action.sources"],
    "input": [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": QUESTION}],
        }
    ],
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

thinking_parts: list[str] = []
reply_parts: list[str] = []
search_sources: list[dict] = []
citations: list[dict] = []

with httpx.stream(
    "POST",
    f"{BASE_URL.rstrip('/')}/responses",
    headers=headers,
    json=payload,
    timeout=120.0,
) as response:
    if response.status_code != 200:
        print(
            f"API 调用失败: status={response.status_code}, body={response.read().decode('utf-8', errors='replace')}",
            file=sys.stderr,
        )
        sys.exit(1)

    for line in response.iter_lines():
        if not line.startswith("data:"):
            continue

        data_str = line[len("data:") :].strip()
        if not data_str or data_str == "[DONE]":
            continue

        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        if event_type == "response.reasoning_summary_text.delta":
            delta = event.get("delta")
            if delta:
                thinking_parts.append(delta)
            continue

        if event_type == "response.output_text.delta":
            delta = event.get("delta")
            if delta:
                reply_parts.append(delta)
            continue

        if event_type == "response.failed":
            error = event.get("response", {}).get("error") or event.get("error") or {}
            print(
                f"API 调用失败: code={error.get('code')}, message={error.get('message')}",
                file=sys.stderr,
            )
            sys.exit(1)

        if event_type == "response.completed":
            output_items = event.get("response", {}).get("output") or []
            citations = extract_annotations(output_items)
            search_sources = extract_web_search_sources(output_items)

print("========== 搜索来源 ==========")
if search_sources:
    for index, source in enumerate(search_sources, start=1):
        print(f"[{index}] {source.get('title') or source.get('site_name') or '未知标题'} - {source.get('url', '')}")
elif citations:
    for index, citation in enumerate(citations, start=1):
        print(f"[{index}] {citation.get('title', '未知标题')} - {citation.get('url', '')}")
else:
    print("（未返回搜索来源）")

if thinking_parts:
    print("\n========== 思考过程 ==========")
    print("".join(thinking_parts))

print("\n========== 回复内容 ==========")
print("".join(reply_parts))
