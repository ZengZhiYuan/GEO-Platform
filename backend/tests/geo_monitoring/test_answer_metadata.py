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


def test_build_raw_response_safe_molizhishu_whitelists_safe_fields():
    raw = {
        "Authorization": "Bearer secret-token",
        "proxyIp": "10.0.0.1",
        "submit": {"data": {"taskId": "task-1"}},
        "result": {
            "success": True,
            "code": 200,
            "data": {
                "status": "completed",
                "answerContent": "推荐目标品牌。" * 200,
                "citationList": [
                    {
                        "title": "引用标题",
                        "url": "https://example.com/a",
                        "siteName": "Example",
                        "snippet": "不应暴露",
                    }
                ],
                "referenceList": [
                    {
                        "title": "参考标题",
                        "url": "https://example.com/ref",
                        "site": "RefSite",
                        "summary": "参考摘要",
                    }
                ],
                "reasoningProcess": {"content": "逐步分析用户需求。"},
                "recommendedQuestions": ["问题 A", "问题 B"],
                "pageScreenshot": "https://cdn.example.com/shot.png",
                "amount": 1.25,
                "errorMessage": "",
                "mentionPosition": 1,
                "sentiment": "positive",
            },
        },
    }
    safe = build_raw_response_safe(raw)
    assert safe is not None
    assert safe["status"] == "completed"
    assert safe["answerContent"].endswith("。")
    assert len(safe["answerContent"]) <= 20_000
    assert safe["citationList"] == [
        {
            "title": "引用标题",
            "url": "https://example.com/a",
            "site": "Example",
        }
    ]
    assert safe["referenceList"] == [
        {
            "title": "参考标题",
            "url": "https://example.com/ref",
            "site": "RefSite",
            "summary": "参考摘要",
        }
    ]
    assert safe["reasoningProcess"] == {"content": "逐步分析用户需求。"}
    assert safe["recommendedQuestions"] == ["问题 A", "问题 B"]
    assert safe["pageScreenshot"] == "https://cdn.example.com/shot.png"
    assert safe["amount"] == 1.25
    assert "Authorization" not in safe
    assert "proxyIp" not in safe
    assert "secret-token" not in str(safe)
    assert "mentionPosition" not in safe
    assert "sentiment" not in safe


def test_extract_molizhishu_reasoning_process_and_recommended_questions():
    raw = {
        "result": {
            "data": {
                "reasoningProcess": {"content": "模力指数思考过程。"},
                "recommendedQuestions": ["追问 1", "追问 2"],
            }
        }
    }
    metadata = extract_answer_metadata(raw)
    assert metadata.reasoning_text == "模力指数思考过程。"
    assert metadata.search_keywords == ["追问 1", "追问 2"]


def test_build_raw_response_safe_molizhishu_ignores_object_recommended_questions():
    raw = {
        "submit": {"data": {"taskId": "task-1"}},
        "result": {
            "data": {
                "status": "completed",
                "answerContent": "回答",
                "recommendedQuestions": [
                    "合法追问",
                    {"question": "对象型追问", "token": "secret-token", "debug": "internal"},
                    {"title": "标题型追问"},
                    {"token": "must-not-leak"},
                ],
            }
        },
    }
    safe = build_raw_response_safe(raw)
    assert safe is not None
    assert safe["recommendedQuestions"] == ["合法追问", "对象型追问", "标题型追问"]
    assert "secret-token" not in str(safe)
    assert "must-not-leak" not in str(safe)
    assert "debug" not in str(safe)


def test_extract_molizhishu_recommended_questions_from_object_items():
    raw = {
        "result": {
            "data": {
                "recommendedQuestions": [
                    {"question": "对象追问"},
                    {"title": "标题追问", "proxy": "10.0.0.1"},
                ]
            }
        }
    }
    metadata = extract_answer_metadata(raw)
    assert metadata.search_keywords == ["对象追问", "标题追问"]
    assert "10.0.0.1" not in str(metadata.search_keywords)


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
