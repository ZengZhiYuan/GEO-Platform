import os
import sys

from dashscope import MultiModalConversation

QUESTION = "杭州看文艺演出有哪些好去处？"


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content)


api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    print("请设置环境变量 DASHSCOPE_API_KEY", file=sys.stderr)
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

stream = MultiModalConversation.call(
    api_key=api_key,
    model="qwen3.7-plus",
    messages=[
        {"role": "user", "content": [{"text": QUESTION}]}
    ],
    stream=True,
    incremental_output=True,
    enable_thinking=True,
    enable_search=True,
    search_options={
        "forced_search": True,
        "search_strategy": "turbo",
        "enable_source": True,
        "enable_citation": True,
        "citation_format": "[ref_<number>]",
        "freshness": 365,
        "intention_options": {
            "prompt_intervene": "仅检索与问题相关的中文网页、平台内容、媒体文章、官方页面和测评内容。"
        },
    },
)

search_info = {}
thinking_parts = []
reply_parts = []

for chunk in stream:
    if chunk.status_code != 200:
        print(
            f"API 调用失败: status={chunk.status_code}, "
            f"code={getattr(chunk, 'code', None)}, "
            f"message={getattr(chunk, 'message', None)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if chunk.output is None:
        continue

    if chunk.output.search_info:
        search_info = chunk.output.search_info

    if not chunk.output.choices:
        continue

    message = chunk.output.choices[0].message
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        thinking_parts.append(reasoning)

    text = extract_text(message.content)
    if text:
        reply_parts.append(text)

print("========== 搜索来源 ==========")
for web in search_info.get("search_results", []):
    print(f"[{web['index']}] {web['title']} - {web['url']}")

if thinking_parts:
    print("\n========== 思考过程 ==========")
    print("".join(thinking_parts))

print("\n========== 回复内容 ==========")
print("".join(reply_parts))
