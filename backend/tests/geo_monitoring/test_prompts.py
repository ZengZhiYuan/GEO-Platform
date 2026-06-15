def _create_prompt_set(client, project_id: int, version_no: str) -> dict:
    response = client.post(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets",
        json={"set_name": f"监测提示词 {version_no}", "version_no": version_no},
    )
    assert response.json()["code"] == 0
    return response.json()["data"]


def _create_prompt(client, prompt_set_id: int, code: str, text: str) -> dict:
    response = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts",
        json={
            "prompt_code": code,
            "prompt_text": text,
            "prompt_type": "brand_visibility",
            "sort_order": 10,
        },
    )
    assert response.json()["code"] == 0
    return response.json()["data"]


def test_prompt_set_activation_archives_previous_version(client, project_id):
    first = _create_prompt_set(client, project_id, "v1")
    second = _create_prompt_set(client, project_id, "v2")
    _create_prompt(client, first["id"], "visibility", "推荐本地文旅品牌")
    _create_prompt(client, second["id"], "visibility", "推荐热门文旅品牌")

    activated_first = client.post(
        f"/api/geo-monitoring/prompt-sets/{first['id']}/activate"
    ).json()["data"]
    activated_second = client.post(
        f"/api/geo-monitoring/prompt-sets/{second['id']}/activate"
    ).json()["data"]
    listed = client.get(
        f"/api/geo-monitoring/projects/{project_id}/prompt-sets"
    ).json()["data"]
    statuses = {item["id"]: item["status"] for item in listed["items"]}

    assert activated_first["status"] == "active"
    assert activated_first["checksum"]
    assert activated_second["status"] == "active"
    assert statuses[first["id"]] == "archived"
    assert statuses[second["id"]] == "active"


def test_only_draft_prompt_sets_can_be_mutated(client, project_id):
    prompt_set = _create_prompt_set(client, project_id, "v1")
    prompt = _create_prompt(client, prompt_set["id"], "visibility", "原始问题")
    client.post(f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate")

    update_prompt = client.put(
        f"/api/geo-monitoring/prompts/{prompt['id']}",
        json={"prompt_text": "修改后的问题"},
    ).json()
    add_prompt = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
        json={"prompt_code": "new", "prompt_text": "新增问题"},
    ).json()
    update_set = client.put(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}",
        json={"set_name": "不允许修改"},
    ).json()

    assert update_prompt["code"] == 40020
    assert add_prompt["code"] == 40020
    assert update_set["code"] == 40020


def test_prompt_count_hash_and_duplicate_code(client, project_id):
    prompt_set = _create_prompt_set(client, project_id, "v1")
    prompt = _create_prompt(client, prompt_set["id"], "visibility", "  品牌推荐  ")

    duplicate = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/prompts",
        json={"prompt_code": "visibility", "prompt_text": "另一个问题"},
    ).json()
    refreshed = client.get(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}"
    ).json()["data"]

    assert prompt["prompt_text"] == "品牌推荐"
    assert len(prompt["content_hash"]) == 64
    assert duplicate["code"] == 40021
    assert refreshed["prompt_count"] == 1


def test_empty_prompt_set_cannot_be_activated(client, project_id):
    prompt_set = _create_prompt_set(client, project_id, "v1")

    response = client.post(
        f"/api/geo-monitoring/prompt-sets/{prompt_set['id']}/activate"
    ).json()

    assert response["code"] == 40022

