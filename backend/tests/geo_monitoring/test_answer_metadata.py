"""Task P1-3：回答元数据提取单元测试。"""

from __future__ import annotations

from app.geo_monitoring.services.answer_metadata import (
    build_answer_metadata_fields,
    build_raw_response_safe,
    extract_answer_metadata,
)


def test_extract_aidso_search_word_and_thinking():
    raw = {
        "result": {
            "data": {
                "result": [
                    {"search_word": "杭州文旅,宋城演艺"},
                    {"thinking": "先比较各品牌口碑。"},
                    {"context": "推荐目标品牌。"},
                ]
            }
        }
    }
    metadata = extract_answer_metadata(raw)
    assert metadata.reasoning_text == "先比较各品牌口碑。"
    assert metadata.search_keywords == ["杭州文旅", "宋城演艺"]


def test_extract_openai_compatible_reasoning_content():
    raw = {
        "choices": [
            {
                "message": {
                    "content": "正式回答",
                    "reasoning_content": "逐步分析用户需求。",
                }
            }
        ]
    }
    metadata = extract_answer_metadata(raw)
    assert metadata.reasoning_text == "逐步分析用户需求。"
    assert metadata.search_keywords == []


def test_extract_qwen_search_info_keywords():
    raw = {
        "output": {
            "search_info": {
                "search_results": [
                    {"title": "宋城旅游攻略", "url": "https://example.com/a"},
                    {"title": "杭州演艺推荐", "url": "https://example.com/b"},
                ]
            }
        }
    }
    metadata = extract_answer_metadata(raw)
    assert metadata.search_keywords == ["宋城旅游攻略", "杭州演艺推荐"]


def test_extract_returns_empty_when_raw_missing():
    metadata = extract_answer_metadata(None)
    assert metadata.reasoning_text is None
    assert metadata.search_keywords == []


def test_build_answer_metadata_fields_whitelists_safe_subset():
    raw = {
        "Authorization": "secret-token",
        "cookie": "session-id=abc",
        "model": "qwen-plus",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "content": "正文不应暴露",
                    "reasoning_content": "逐步分析用户需求。",
                },
            }
        ],
        "result": {
            "data": {
                "status": "SUCCESS",
                "result": [
                    {"search_word": "关键词"},
                    {"thinking": "思考过程"},
                    {"context": "正文不应暴露"},
                ],
            }
        },
    }
    fields = build_answer_metadata_fields(raw)
    assert fields["reasoning_text"] == "思考过程"
    assert fields["search_keywords"] == ["关键词"]
    safe = fields["raw_response_safe"]
    assert safe is not None
    assert safe == {
        "model": "qwen-plus",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
        "choices": [{"finish_reason": "stop", "index": 0}],
        "result": {
            "data": {
                "status": "SUCCESS",
                "result": [
                    {"search_word": "关键词"},
                    {"thinking": "思考过程"},
                ],
            }
        },
    }
    assert "Authorization" not in safe
    assert "cookie" not in safe
    assert "secret-token" not in str(safe)
    assert "正文不应暴露" not in str(safe)


def test_build_raw_response_safe_allows_qwen_search_info_only():
    raw = {
        "output": {
            "search_info": {
                "search_results": [
                    {
                        "title": "宋城旅游攻略",
                        "url": "https://example.com/a",
                        "index": 1,
                        "snippet": "不应暴露",
                    }
                ],
                "session_id": "hidden",
            }
        },
        "headers": {"Set-Cookie": "sid=1"},
    }
    safe = build_raw_response_safe(raw)
    assert safe == {
        "output": {
            "search_info": {
                "search_results": [
                    {
                        "title": "宋城旅游攻略",
                        "url": "https://example.com/a",
                        "index": 1,
                    }
                ]
            }
        }
    }
