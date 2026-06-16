import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import requests

API_URL = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
SEARCH_MODEL = "hunyuan-turbos-latest"
THINKING_MODEL = "hunyuan-t1-latest"
QUESTION = "杭州看文艺演出有哪些好去处？"
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"

TestMode = Literal["search", "thinking"]


@dataclass
class SearchResult:
    index: int | None
    title: str
    url: str
    snippet: str


@dataclass
class HunyuanTestResult:
    mode: TestMode
    mode_label: str
    question: str
    model: str
    started_at: str
    finished_at: str
    duration_seconds: float
    success: bool
    error: str = ""
    search_enabled: bool = False
    thinking_enabled: bool = False
    citation_enabled: bool = False
    search_results: list[SearchResult] = field(default_factory=list)
    thinking: str = ""
    reply: str = ""
    support_deep_search: bool = False

    @property
    def search_count(self) -> int:
        return len(self.search_results)

    @property
    def has_thinking(self) -> bool:
        return bool(self.thinking.strip())

    @property
    def has_reply(self) -> bool:
        return bool(self.reply.strip())


@dataclass
class HunyuanCombinedResult:
    question: str
    search_result: HunyuanTestResult
    thinking_result: HunyuanTestResult


def load_dotenv(env_path: Path | None = None) -> None:
    path = env_path or PROJECT_ROOT / ".env"
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content)


def get_field(item: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return str(value)
    return default


def parse_search_results(search_info: dict) -> list[SearchResult]:
    results: list[SearchResult] = []
    for web in search_info.get("search_results", []):
        results.append(
            SearchResult(
                index=web.get("index", web.get("Index")),
                title=get_field(web, "title", "Title"),
                url=get_field(web, "url", "Url"),
                snippet=get_field(web, "snippet", "text", "Text"),
            )
        )
    return results


def build_payload(question: str, model: str, mode: TestMode) -> dict:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "stream": True,
    }

    if mode == "search":
        payload.update(
            {
                "enable_enhancement": True,
                "force_search_enhancement": True,
                "search_info": True,
                "citation": True,
                "thinking": {"type": "disabled"},
            }
        )
    else:
        payload.update(
            {
                "enable_enhancement": False,
                "search_info": False,
                "citation": False,
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
        )

    return payload


def run_hunyuan_test(
    question: str = QUESTION,
    model: str = SEARCH_MODEL,
    mode: TestMode = "search",
    api_key: str | None = None,
    timeout: int = 120,
) -> HunyuanTestResult:
    mode_label = "联网搜索" if mode == "search" else "深度思考"
    started = datetime.now()
    key = api_key or os.getenv("HUNYUAN_API_KEY")
    if not key:
        finished = datetime.now()
        return HunyuanTestResult(
            mode=mode,
            mode_label=mode_label,
            question=question,
            model=model,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=(finished - started).total_seconds(),
            success=False,
            error="未找到 HUNYUAN_API_KEY，请在 .env 或环境变量中配置",
        )

    payload = build_payload(question, model, mode)
    search_info: dict = {}
    thinking_parts: list[str] = []
    reply_parts: list[str] = []
    error = ""

    try:
        with requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            stream=True,
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                error = f"API 调用失败: status={response.status_code}, body={response.text}"
            else:
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8")
                    if not line.startswith("data:"):
                        continue

                    data_line = line.removeprefix("data:").strip()
                    if data_line == "[DONE]":
                        break

                    try:
                        event = json.loads(data_line)
                    except json.JSONDecodeError:
                        continue

                    if event.get("search_info"):
                        search_info = event["search_info"]

                    choices = event.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        thinking_parts.append(reasoning)

                    content = delta.get("content")
                    if content:
                        reply_parts.append(extract_text(content))
    except requests.RequestException as exc:
        error = f"API 调用失败: {exc}"

    finished = datetime.now()
    return HunyuanTestResult(
        mode=mode,
        mode_label=mode_label,
        question=question,
        model=model,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=finished.isoformat(timespec="seconds"),
        duration_seconds=round((finished - started).total_seconds(), 2),
        success=not error,
        error=error,
        search_enabled=mode == "search",
        thinking_enabled=mode == "thinking",
        citation_enabled=mode == "search",
        search_results=parse_search_results(search_info),
        thinking="".join(thinking_parts),
        reply="".join(reply_parts),
        support_deep_search=bool(search_info.get("support_deep_search")),
    )


def run_combined_test(
    question: str = QUESTION,
    search_model: str = SEARCH_MODEL,
    thinking_model: str = THINKING_MODEL,
    api_key: str | None = None,
    timeout: int = 120,
) -> HunyuanCombinedResult:
    search_result = run_hunyuan_test(
        question=question,
        model=search_model,
        mode="search",
        api_key=api_key,
        timeout=timeout,
    )
    thinking_result = run_hunyuan_test(
        question=question,
        model=thinking_model,
        mode="thinking",
        api_key=api_key,
        timeout=timeout,
    )
    return HunyuanCombinedResult(
        question=question,
        search_result=search_result,
        thinking_result=thinking_result,
    )


def print_search_sources(result: HunyuanTestResult) -> None:
    print("========== 搜索来源 ==========")
    if result.search_results:
        for web in result.search_results:
            label = f"[{web.index}]" if web.index is not None else "-"
            print(f"{label} {web.title} - {web.url}")
            if web.snippet:
                print(f"  摘要: {web.snippet}")
    else:
        print("（未返回搜索结果）")


def print_search_references(result: HunyuanTestResult) -> None:
    print("\n========== 参考依据 ==========")
    if result.search_results:
        for web in result.search_results:
            ref = f"[{web.index}]" if web.index is not None else "-"
            print(f"{ref} {web.title}")
            print(f"  链接: {web.url}")
            if web.snippet:
                print(f"  依据: {web.snippet}")
    else:
        print("（无参考依据）")


def print_thinking_basis(result: HunyuanTestResult) -> None:
    print("\n========== 推理依据 ==========")
    if result.has_thinking:
        print(result.thinking)
    else:
        print("（未返回推理依据）")


def print_mode_result(result: HunyuanTestResult) -> None:
    print(f"\n{'=' * 18}【{result.mode_label}】{'=' * 18}")
    print(f"模型: {result.model}")
    print(f"耗时: {result.duration_seconds} 秒")

    if not result.success:
        print(result.error, file=sys.stderr)
        return

    if result.mode == "search":
        print_search_sources(result)
        print_search_references(result)
        print("\n========== 回复内容 ==========")
        print(result.reply or "（未返回回复内容）")
        return

    if result.has_thinking:
        print("\n========== 思考过程 ==========")
        print(result.thinking)

    print_thinking_basis(result)
    print("\n========== 回复内容 ==========")
    print(result.reply or "（未返回回复内容）")


def print_combined_results(combined: HunyuanCombinedResult) -> None:
    print(f"测试问题: {combined.question}")
    print_mode_result(combined.search_result)
    print_mode_result(combined.thinking_result)


def _append_search_sections(lines: list[str], result: HunyuanTestResult, section_prefix: str) -> None:
    lines.extend([f"### {section_prefix} 搜索来源", ""])
    if result.search_results:
        lines.extend(["| 序号 | 标题 | 链接 | 摘要 |", "| --- | --- | --- | --- |"])
        for web in result.search_results:
            index = web.index if web.index is not None else "-"
            title = web.title.replace("|", "\\|")
            snippet = web.snippet.replace("|", "\\|")
            lines.append(f"| {index} | {title} | {web.url} | {snippet} |")
    else:
        lines.append("未返回搜索结果。")

    lines.extend(["", f"### {section_prefix} 参考依据", ""])
    if result.search_results:
        for web in result.search_results:
            ref = f"[{web.index}]" if web.index is not None else "-"
            lines.append(f"#### {ref} {web.title}")
            lines.append(f"- 链接: {web.url}")
            if web.snippet:
                lines.append(f"- 依据: {web.snippet}")
            lines.append("")
    else:
        lines.append("无参考依据。")
        lines.append("")

    lines.extend([f"### {section_prefix} 回复内容", "", result.reply or "未返回回复内容。", ""])


def _append_thinking_sections(lines: list[str], result: HunyuanTestResult, section_prefix: str) -> None:
    lines.extend([f"### {section_prefix} 思考过程", ""])
    if result.has_thinking:
        lines.append(f"```text\n{result.thinking}\n```")
    else:
        lines.append("未返回思考过程。")

    lines.extend(["", f"### {section_prefix} 推理依据", ""])
    if result.has_thinking:
        lines.append(f"```text\n{result.thinking}\n```")
    else:
        lines.append("未返回推理依据。")

    lines.extend(["", f"### {section_prefix} 回复内容", "", result.reply or "未返回回复内容。", ""])


def _append_mode_summary(lines: list[str], result: HunyuanTestResult) -> None:
    lines.extend(
        [
            f"| 模式 | {result.mode_label} |",
            f"| 模型 | `{result.model}` |",
            f"| 调用结果 | {'成功' if result.success else '失败'} |",
            f"| 耗时 | {result.duration_seconds} 秒 |",
        ]
    )
    if result.mode == "search":
        lines.append(f"| 搜索结果数 | {result.search_count} 条 |")
        lines.append(f"| 深度搜索模式 | {'是' if result.support_deep_search else '否'} |")
    else:
        lines.append(f"| 返回思考过程 | {'是' if result.has_thinking else '否'} |")
    lines.append(f"| 返回回复内容 | {'是' if result.has_reply else '否'} |")
    if result.error:
        lines.append(f"| 错误信息 | {result.error} |")


def build_markdown_report(combined: HunyuanCombinedResult) -> str:
    search = combined.search_result
    thinking = combined.thinking_result
    lines = [
        "# 混元 API 测试报告",
        "",
        "## 1. 测试概览",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        f"| 测试时间 | {search.started_at} |",
        f"| 测试问题 | {combined.question} |",
        "",
        "## 2. 模式结果摘要",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
    ]
    _append_mode_summary(lines, search)
    lines.append("")
    lines.extend(["| 项目 | 内容 |", "| --- | --- |"])
    _append_mode_summary(lines, thinking)
    lines.extend(["", "## 3. 联网搜索", ""])
    if not search.success:
        lines.extend([f"调用失败: {search.error}", ""])
    else:
        _append_search_sections(lines, search, "3.")

    lines.extend(["## 4. 深度思考", ""])
    if not thinking.success:
        lines.extend([f"调用失败: {thinking.error}", ""])
    else:
        _append_thinking_sections(lines, thinking, "4.")

    return "\n".join(lines)


def save_report(
    combined: HunyuanCombinedResult,
    output_dir: Path = REPORTS_DIR,
    prefix: str = "hunyuan_report",
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = output_dir / f"{prefix}_{timestamp}.md"
    json_path = output_dir / f"{prefix}_{timestamp}.json"

    md_path.write_text(build_markdown_report(combined), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "question": combined.question,
                "search_result": asdict(combined.search_result),
                "thinking_result": asdict(combined.thinking_result),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return md_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="混元 API 测试：分别验证联网搜索与深度思考")
    parser.add_argument("--question", default=QUESTION, help="测试问题")
    parser.add_argument("--search-model", default=SEARCH_MODEL, help="联网搜索使用的模型")
    parser.add_argument("--thinking-model", default=THINKING_MODEL, help="深度思考使用的模型")
    parser.add_argument("--report", action="store_true", help="生成 Markdown/JSON 测试报告")
    parser.add_argument("--report-dir", default=str(REPORTS_DIR), help="报告输出目录")
    parser.add_argument("--quiet", action="store_true", help="仅生成报告，不在终端打印结果")
    args = parser.parse_args()

    load_dotenv()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    combined = run_combined_test(
        question=args.question,
        search_model=args.search_model,
        thinking_model=args.thinking_model,
    )

    if not args.quiet:
        print_combined_results(combined)

    if args.report:
        md_path, json_path = save_report(combined, output_dir=Path(args.report_dir))
        print(f"\n测试报告已生成:")
        print(f"- Markdown: {md_path}")
        print(f"- JSON: {json_path}")

    success = combined.search_result.success and combined.thinking_result.success
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
