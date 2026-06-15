OLD_PATHS = (
    "/api/keywords",
    "/api/title-inspirations",
    "/api/image-categories",
    "/api/image-assets",
    "/api/brand-knowledges",
    "/api/writing-rules",
    "/api/content-categories",
    "/api/writing-tasks",
    "/api/articles",
)


def test_health_uses_monitoring_product_name(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["app"] == "ai-application-monitoring"


def test_old_business_routes_are_removed(client):
    for path in OLD_PATHS:
        assert client.get(path).status_code == 404


def test_monitoring_router_is_registered(client):
    response = client.get("/api/geo-monitoring/platforms")
    assert response.status_code != 404
