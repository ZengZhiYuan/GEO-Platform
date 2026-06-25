"""Task P0-2：AI 生成辅助接口测试。"""

import pytest


_SONGCHENG_BASE = {
    "brand_name": "杭州宋城",
    "category": "文旅演艺",
    "region": "杭州",
    "official_domain": "https://www.hzsongcheng.com",
}


def test_brand_words_generate_rejects_empty_brand_name(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={"brand_name": "   "},
    ).json()
    assert response["code"] == 422


def test_brand_words_generate_songcheng_example(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={**_SONGCHENG_BASE, "limit": 10},
    ).json()
    assert response["code"] == 0
    words = response["data"]["brand_words"]
    assert words[0] == "杭州宋城"
    assert "杭州宋城" in words
    assert "宋城千古情" in words
    assert "宋城" in words
    assert len(words) == len(set(words))
    assert all(word.strip() for word in words)


def test_brand_words_generate_respects_limit_one(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={**_SONGCHENG_BASE, "limit": 1},
    ).json()
    assert response["code"] == 0
    words = response["data"]["brand_words"]
    assert words == ["杭州宋城"]


def test_competitors_generate_songcheng_example(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        json={**_SONGCHENG_BASE, "limit": 5},
    ).json()
    assert response["code"] == 0
    competitors = response["data"]["competitors"]
    names = {item["brand_name"] for item in competitors}
    assert "印象西湖" in names
    assert "只有河南·戏剧幻城" in names
    assert "杭州宋城" not in names
    assert "宋城演艺" not in names
    assert "宋城" not in names
    for item in competitors:
        assert item["brand_name"] in item["competitor_words"]
        assert len(item["competitor_words"]) == len(set(item["competitor_words"]))


def test_questions_generate_songcheng_example(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            **_SONGCHENG_BASE,
            "core_keywords": ["杭州旅游"],
            "competitors": ["印象西湖", "只有河南·戏剧幻城"],
            "limit": 5,
        },
    ).json()
    assert response["code"] == 0
    questions = response["data"]["questions"]
    assert len(questions) == 5
    prompt_types = {item["prompt_type"] for item in questions}
    assert prompt_types == {
        "brand_sentiment",
        "brand_info",
        "category_sentiment",
        "competitor_comparison",
        "category_recommendation",
    }
    assert any("杭州宋城" in item["prompt_text"] for item in questions)
    assert any(item["core_keyword"] == "杭州旅游" for item in questions)


def test_questions_generate_respects_limit(client, project_id):
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            "brand_name": "杭州宋城",
            "category": "文旅演艺",
            "core_keywords": ["杭州旅游"],
            "limit": 3,
        },
    ).json()
    assert response["code"] == 0
    assert len(response["data"]["questions"]) == 3


def test_ai_generation_does_not_persist_monitor_setup(client, project_id):
    before = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()["data"]
    assert before["brand"] is None

    client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        json={"brand_name": "杭州宋城", "category": "文旅演艺", "limit": 5},
    )
    client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        json={"brand_name": "杭州宋城", "category": "文旅演艺", "region": "杭州", "limit": 5},
    )
    client.post(
        f"/api/geo-monitoring/projects/{project_id}/ai/questions:generate",
        json={
            "brand_name": "杭州宋城",
            "category": "文旅演艺",
            "core_keywords": ["杭州旅游"],
            "limit": 5,
        },
    )

    after = client.get(
        f"/api/geo-monitoring/projects/{project_id}/monitor-setup"
    ).json()["data"]
    assert after["brand"] is None
    assert after["competitors"] == []
    assert after["ai_questions"] == []


def test_ai_generation_returns_404_for_missing_project(client):
    response = client.post(
        "/api/geo-monitoring/projects/99999/ai/brand-words:generate",
        json={"brand_name": "杭州宋城"},
    ).json()
    assert response["code"] == 40400


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/geo-monitoring/projects/{project_id}/ai/brand-words:generate",
        "/api/v1/geo-monitoring/projects/{project_id}/ai/competitors:generate",
        "/api/v1/geo-monitoring/projects/{project_id}/ai/questions:generate",
    ],
)
def test_ai_generation_routes_available_on_v1_prefix(client, project_id, path):
    body = {
        "brand_name": "杭州宋城",
        "category": "文旅演艺",
        "region": "杭州",
        "core_keywords": ["杭州旅游"],
        "competitors": ["印象西湖"],
        "limit": 3,
    }
    response = client.post(path.format(project_id=project_id), json=body).json()
    assert response["code"] == 0
    assert response["data"]
