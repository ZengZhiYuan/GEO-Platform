"""从 raw_response_json 提取回答展示元数据（思考过程、搜索关键词）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_REASONING_KEYS = ("thinking", "reasoning", "reasoning_content", "reason", "deep_think")
_SEARCH_WORD_KEYS = ("search_word", "search_words", "search_keywords", "keywords")
_MAX_TEXT_LENGTH = 20_000
_MAX_KEYWORDS = 50
_MAX_LIST_ITEMS = 50

# raw_response_safe 仅暴露白名单字段，避免黑名单漏脱敏。
_SAFE_TOP_LEVEL_SCALAR_KEYS = frozenset(
    {
        "id",
        "model",
        "object",
        "created",
        "provider",
        "system_fingerprint",
    }
)
_SAFE_USAGE_KEYS = frozenset(
    {"prompt_tokens", "completion_tokens", "total_tokens"}
)
_SAFE_CHOICE_KEYS = frozenset({"finish_reason", "index"})
_SAFE_SEARCH_RESULT_KEYS = frozenset({"title", "url", "index"})
_SAFE_AIDSO_DATA_KEYS = frozenset({"status", "prompt"})
_SAFE_AIDSO_RESULT_ITEM_KEYS = frozenset(_REASONING_KEYS + _SEARCH_WORD_KEYS)
_SAFE_MOLIZHISHU_CITATION_KEYS = frozenset({"title", "url", "site", "siteName"})
_SAFE_MOLIZHISHU_REFERENCE_KEYS = frozenset({"title", "url", "site", "summary"})
_SAFE_MOLIZHISHU_SCALAR_KEYS = frozenset(
    {"status", "answerContent", "pageScreenshot", "amount", "errorMessage"}
)


@dataclass(frozen=True)
class AnswerMetadata:
    reasoning_text: str | None
    search_keywords: list[str]


def extract_answer_metadata(raw_response_json: dict[str, Any] | None) -> AnswerMetadata:
    """从原始响应 JSON 提取思考过程与搜索关键词。"""
    if not raw_response_json:
        return AnswerMetadata(reasoning_text=None, search_keywords=[])

    reasoning = _extract_reasoning_text(raw_response_json)
    keywords = _extract_search_keywords(raw_response_json)
    return AnswerMetadata(reasoning_text=reasoning, search_keywords=keywords)


def build_answer_metadata_fields(
    raw_response_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """构建 AnswerDetailRead 所需的元数据字段。"""
    metadata = extract_answer_metadata(raw_response_json)
    return {
        "reasoning_text": metadata.reasoning_text,
        "search_keywords": metadata.search_keywords,
        "raw_response_safe": build_raw_response_safe(raw_response_json),
    }


def build_raw_response_safe(raw_response_json: dict[str, Any] | None) -> dict[str, Any] | None:
    """按白名单构建可安全返回的 raw 响应子集。"""
    if not raw_response_json:
        return None

    safe: dict[str, Any] = {}
    for key in _SAFE_TOP_LEVEL_SCALAR_KEYS:
        value = raw_response_json.get(key)
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value

    usage = raw_response_json.get("usage")
    if isinstance(usage, dict):
        usage_safe = {
            key: usage[key]
            for key in _SAFE_USAGE_KEYS
            if key in usage and isinstance(usage[key], (int, float))
        }
        if usage_safe:
            safe["usage"] = usage_safe

    choices = raw_response_json.get("choices")
    if isinstance(choices, list):
        choices_safe = _whitelist_choices(choices)
        if choices_safe:
            safe["choices"] = choices_safe

    output = raw_response_json.get("output")
    if isinstance(output, dict):
        search_info = output.get("search_info")
        if isinstance(search_info, dict):
            search_info_safe = _whitelist_search_info(search_info)
            if search_info_safe:
                safe["output"] = {"search_info": search_info_safe}

    aidso_safe = _whitelist_aidso_result(raw_response_json)
    if aidso_safe:
        safe["result"] = aidso_safe

    molizhishu_safe = _whitelist_molizhishu_result(raw_response_json)
    if molizhishu_safe:
        safe.update(molizhishu_safe)

    return safe if safe else None


def _whitelist_choices(choices: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for choice in choices[:_MAX_LIST_ITEMS]:
        if not isinstance(choice, dict):
            continue
        row = {
            key: choice[key]
            for key in _SAFE_CHOICE_KEYS
            if key in choice and isinstance(choice[key], (str, int))
        }
        if row:
            items.append(row)
    return items


def _whitelist_search_info(search_info: dict[str, Any]) -> dict[str, Any]:
    results = search_info.get("search_results")
    if not isinstance(results, list):
        return {}
    safe_results: list[dict[str, Any]] = []
    for row in results[:_MAX_LIST_ITEMS]:
        if not isinstance(row, dict):
            continue
        safe_row = {
            key: row[key]
            for key in _SAFE_SEARCH_RESULT_KEYS
            if key in row and isinstance(row[key], (str, int))
        }
        if safe_row:
            safe_results.append(safe_row)
    return {"search_results": safe_results} if safe_results else {}


def _molizhishu_result_payload(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not _looks_like_molizhishu_raw(raw):
        return None
    result = raw.get("result")
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, dict):
            return data
    data = raw.get("data")
    return data if isinstance(data, dict) else None


def _looks_like_molizhishu_raw(raw: dict[str, Any]) -> bool:
    if "submit" in raw:
        return True
    result = raw.get("result")
    if not isinstance(result, dict):
        return False
    data = result.get("data")
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("result"), list):
        return False
    molizhishu_keys = (
        "answerContent",
        "citationList",
        "referenceList",
        "reasoningProcess",
        "recommendedQuestions",
        "pageScreenshot",
        "amount",
        "errorMessage",
    )
    return any(key in data for key in molizhishu_keys)


def _whitelist_molizhishu_result(raw: dict[str, Any]) -> dict[str, Any] | None:
    payload = _molizhishu_result_payload(raw)
    if not payload:
        return None

    safe: dict[str, Any] = {}
    for key in _SAFE_MOLIZHISHU_SCALAR_KEYS:
        value = payload.get(key)
        if key == "answerContent" and isinstance(value, str) and value.strip():
            safe[key] = _truncate_text(value.strip())
        elif key == "errorMessage" and isinstance(value, str) and value.strip():
            safe[key] = value.strip()
        elif isinstance(value, (str, int, float, bool)):
            safe[key] = value

    citations = payload.get("citationList")
    if isinstance(citations, list):
        safe_citations = _whitelist_molizhishu_citations(citations)
        if safe_citations:
            safe["citationList"] = safe_citations

    references = payload.get("referenceList")
    if isinstance(references, list):
        safe_references = _whitelist_molizhishu_references(references)
        if safe_references:
            safe["referenceList"] = safe_references

    reasoning = payload.get("reasoningProcess")
    if isinstance(reasoning, dict):
        content = reasoning.get("content")
        if isinstance(content, str) and content.strip():
            safe["reasoningProcess"] = {"content": _truncate_text(content.strip())}

    recommended = payload.get("recommendedQuestions")
    if isinstance(recommended, list):
        safe_questions = _normalize_recommended_questions(recommended)
        if safe_questions:
            safe["recommendedQuestions"] = safe_questions

    return safe if safe else None


def _normalize_recommended_questions(recommended: list[Any]) -> list[str]:
    safe_questions: list[str] = []
    for item in recommended[:_MAX_LIST_ITEMS]:
        text = _recommended_question_text(item)
        if text:
            safe_questions.append(_truncate_text(text))
    return safe_questions


def _recommended_question_text(item: Any) -> str | None:
    if isinstance(item, str):
        trimmed = item.strip()
        return trimmed if trimmed else None
    if isinstance(item, dict):
        for key in ("question", "title"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _whitelist_molizhishu_citations(items: list[Any]) -> list[dict[str, Any]]:
    safe_items: list[dict[str, Any]] = []
    for item in items[:_MAX_LIST_ITEMS]:
        if not isinstance(item, dict):
            continue
        row: dict[str, Any] = {}
        for key in _SAFE_MOLIZHISHU_CITATION_KEYS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                if key == "siteName":
                    row["site"] = value.strip()
                else:
                    row[key] = value.strip()
        if row:
            safe_items.append(row)
    return safe_items


def _whitelist_molizhishu_references(items: list[Any]) -> list[dict[str, Any]]:
    safe_items: list[dict[str, Any]] = []
    for item in items[:_MAX_LIST_ITEMS]:
        if not isinstance(item, dict):
            continue
        row = {
            key: _truncate_text(str(item[key]).strip())
            for key in _SAFE_MOLIZHISHU_REFERENCE_KEYS
            if key in item
            and isinstance(item[key], str)
            and str(item[key]).strip()
        }
        if row:
            safe_items.append(row)
    return safe_items


def _whitelist_aidso_result(raw: dict[str, Any]) -> dict[str, Any] | None:
    data_node: Any = raw.get("result")
    if isinstance(data_node, dict):
        data_node = data_node.get("data")
    elif "data" in raw and isinstance(raw.get("data"), dict):
        data_node = raw["data"]
    else:
        return None

    if not isinstance(data_node, dict):
        return None

    payload: dict[str, Any] = {}
    for key in _SAFE_AIDSO_DATA_KEYS:
        value = data_node.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value

    result_items = data_node.get("result")
    if isinstance(result_items, list):
        safe_items: list[dict[str, Any]] = []
        for item in result_items[:_MAX_LIST_ITEMS]:
            if not isinstance(item, dict):
                continue
            safe_item = {
                key: _truncate_text(str(item[key]).strip())
                for key in _SAFE_AIDSO_RESULT_ITEM_KEYS
                if key in item
                and isinstance(item[key], str)
                and str(item[key]).strip()
            }
            if safe_item:
                safe_items.append(safe_item)
        if safe_items:
            payload["result"] = safe_items

    if not payload:
        return None
    return {"data": payload}


def _extract_reasoning_text(raw: dict[str, Any]) -> str | None:
    molizhishu_payload = _molizhishu_result_payload(raw)
    if isinstance(molizhishu_payload, dict):
        reasoning = molizhishu_payload.get("reasoningProcess")
        if isinstance(reasoning, dict):
            content = reasoning.get("content")
            if isinstance(content, str) and content.strip():
                return _truncate_text(content.strip())
        if isinstance(reasoning, str) and reasoning.strip():
            return _truncate_text(reasoning.strip())

    for item in _iter_result_items(raw):
        for key in _REASONING_KEYS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return _truncate_text(value.strip())

    message = _first_message(raw)
    if message:
        for key in _REASONING_KEYS:
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return _truncate_text(value.strip())
    return None


def _extract_search_keywords(raw: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()

    molizhishu_payload = _molizhishu_result_payload(raw)
    if isinstance(molizhishu_payload, dict):
        recommended = molizhishu_payload.get("recommendedQuestions")
        if isinstance(recommended, list):
            for item in recommended:
                text = _recommended_question_text(item)
                if text:
                    _append_keyword(keywords, seen, text)

    for item in _iter_result_items(raw):
        for key in _SEARCH_WORD_KEYS:
            _extend_keywords(keywords, seen, _normalize_keyword_values(item.get(key)))

    search_info = _dig(raw, "output", "search_info")
    if isinstance(search_info, dict):
        results = search_info.get("search_results")
        if isinstance(results, list):
            for row in results:
                if not isinstance(row, dict):
                    continue
                title = row.get("title")
                if isinstance(title, str) and title.strip():
                    _append_keyword(keywords, seen, title.strip())

    return keywords[:_MAX_KEYWORDS]


def _iter_result_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in (
        ("result", "data", "result"),
        ("data", "result"),
        ("result",),
    ):
        node: Any = raw
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, list):
            items.extend(item for item in node if isinstance(item, dict))
    return items


def _first_message(raw: dict[str, Any]) -> dict[str, Any] | None:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    return message if isinstance(message, dict) else None


def _normalize_keyword_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") or text.startswith("{"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        parts = [part.strip() for part in re.split(r"[,，;；\n]+", text)]
        return [part for part in parts if part]
    return []


def _extend_keywords(
    keywords: list[str],
    seen: set[str],
    values: list[str],
) -> None:
    for value in values:
        _append_keyword(keywords, seen, value)


def _append_keyword(keywords: list[str], seen: set[str], value: str) -> None:
    if not value or value in seen:
        return
    seen.add(value)
    keywords.append(value)


def _dig(raw: dict[str, Any], *keys: str) -> Any:
    node: Any = raw
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _truncate_text(value: str) -> str:
    if len(value) <= _MAX_TEXT_LENGTH:
        return value
    return value[:_MAX_TEXT_LENGTH]
