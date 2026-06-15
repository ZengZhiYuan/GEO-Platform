def test_project_allows_only_one_target_brand(client, project_id):
    first = client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "目标品牌", "brand_type": "target"},
    )
    second = client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "另一个目标", "brand_type": "target"},
    )

    assert first.json()["code"] == 0
    assert second.json()["code"] == 40010


def test_brand_alias_must_be_unique_within_brand(client, target_brand_id):
    path = f"/api/geo-monitoring/brands/{target_brand_id}/aliases"

    first = client.post(path, json={"alias_name": "简称"})
    second = client.post(path, json={"alias_name": "简称"})

    assert first.json()["code"] == 0
    assert second.json()["code"] == 40011


def test_brand_and_alias_crud(client, project_id):
    brand = client.post(
        f"/api/geo-monitoring/projects/{project_id}/brands",
        json={"brand_name": "竞品 A", "brand_type": "competitor"},
    ).json()["data"]
    alias = client.post(
        f"/api/geo-monitoring/brands/{brand['id']}/aliases",
        json={
            "alias_name": "竞 A",
            "match_mode": "context",
            "context_keywords": ["景区", " 演艺 ", "景区"],
        },
    ).json()["data"]

    assert alias["context_keywords"] == ["景区", "演艺"]

    updated = client.put(
        f"/api/geo-monitoring/brands/{brand['id']}",
        json={"status": "disabled"},
    ).json()["data"]
    assert updated["status"] == "disabled"

    aliases = client.get(
        f"/api/geo-monitoring/brands/{brand['id']}/aliases"
    ).json()["data"]
    assert aliases["total"] == 1

    assert client.delete(
        f"/api/geo-monitoring/brand-aliases/{alias['id']}"
    ).json()["code"] == 0
    assert client.delete(
        f"/api/geo-monitoring/brands/{brand['id']}"
    ).json()["code"] == 0
