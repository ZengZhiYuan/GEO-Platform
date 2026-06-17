"""监测 API 路径契约测试。"""

from app.main import app

EXPECTED_PATH_TEMPLATES = {
    "/api/geo-monitoring/platforms",
    "/api/geo-monitoring/platforms/{platform_code}",
    "/api/geo-monitoring/projects",
    "/api/geo-monitoring/projects/{project_id}",
    "/api/geo-monitoring/projects/{project_id}/brands",
    "/api/geo-monitoring/brands/{brand_id}",
    "/api/geo-monitoring/brands/{brand_id}/aliases",
    "/api/geo-monitoring/brand-aliases/{alias_id}",
    "/api/geo-monitoring/projects/{project_id}/prompt-sets",
    "/api/geo-monitoring/prompt-sets/{prompt_set_id}",
    "/api/geo-monitoring/prompt-sets/{prompt_set_id}/activate",
    "/api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts",
    "/api/geo-monitoring/prompts/{prompt_id}",
    "/api/geo-monitoring/runs",
    "/api/geo-monitoring/runs/{run_id}",
    "/api/geo-monitoring/runs/{run_id}/query-tasks",
    "/api/geo-monitoring/runs/{run_id}/tasks",
    "/api/geo-monitoring/runs/{run_id}/answers",
    "/api/geo-monitoring/answers/{answer_id}",
}


def _openapi_paths() -> set[str]:
    return set(app.openapi()["paths"].keys())


def test_monitoring_path_templates_are_registered():
    paths = _openapi_paths()
    missing = EXPECTED_PATH_TEMPLATES - paths
    assert not missing, f"missing path templates: {sorted(missing)}"


def test_v1_compat_paths_mirror_geo_monitoring_routes():
    paths = _openapi_paths()
    for template in EXPECTED_PATH_TEMPLATES:
        legacy = template.replace("/api/geo-monitoring", "/api/v1/geo-monitoring", 1)
        assert legacy in paths, legacy


def test_paginated_list_response_shape(client, project_id):
    response = client.get(
        "/api/geo-monitoring/projects",
        params={"page": 1, "page_size": 10},
    ).json()
    assert response["code"] == 0
    assert set(response["data"]) == {"items", "total", "page", "page_size"}


def test_v1_compat_route_returns_same_payload(client, project_id):
    current = client.get(f"/api/geo-monitoring/projects/{project_id}").json()
    legacy = client.get(f"/api/v1/geo-monitoring/projects/{project_id}").json()
    assert current == legacy
