from pathlib import Path


ROOT = Path(__file__).parents[2]


def read_root_file(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_backend_dockerfile_builds_single_reusable_runtime_image():
    dockerfile = read_root_file("Dockerfile")

    assert "FROM python:3.11-slim" in dockerfile
    assert "backend/requirements.txt" in dockerfile
    assert "COPY backend" in dockerfile
    assert "USER appuser" in dockerfile
    assert "REPORT_STORAGE_DIR=/app/backend/data/reports" in dockerfile
    assert "uvicorn" in dockerfile


def test_compose_starts_api_worker_and_scheduler_from_same_backend_image():
    compose = read_root_file("docker-compose.yml")

    for service_name in ("api:", "worker:", "scheduler:"):
        assert service_name in compose

    assert compose.count("image: geo-platform-backend") == 3
    assert "postgres:" not in compose
    assert "redis:" not in compose
    assert "env_file:" in compose
    assert "- .env" in compose
    assert "alembic -c backend/alembic.ini upgrade head" in compose
    assert "uvicorn app.main:app" in compose
    assert "dramatiq app.worker.actors.collection" in compose
    assert "python -m app.scheduler.main" in compose
    assert "REPORT_STORAGE_DIR=/app/backend/data/reports" in compose
    assert "reports_data:/app/backend/data/reports" in compose


def test_env_example_exposes_deployment_process_and_fallback_switches():
    env_example = read_root_file(".env.example")

    for name in (
        "BACKEND_HOST=0.0.0.0",
        "BACKEND_PORT=8000",
        "DRAMATIQ_BROKER=redis",
        "NACOS_ENABLED=false",
        "REPORT_STORAGE_DIR=./data/reports",
        "DOUBAO_ENABLED=false",
        "QWEN_ENABLED=false",
        "YUANBAO_ENABLED=false",
        "DEEPSEEK_ENABLED=false",
        "KIMI_ENABLED=false",
    ):
        assert name in env_example


def test_readme_documents_release_smoke_and_rollback_runbook():
    readme = read_root_file("README.md")

    for phrase in (
        "后端部署、发布与回滚",
        "docker compose build",
        "alembic -c backend/alembic.ini upgrade head",
        "启动 worker/scheduler，最后切换 API",
        "health、ready、创建测试项目、mock 运行和报告下载",
        "应用回滚优先回滚镜像，不自动 downgrade 数据库",
        "*_ENABLED=false",
        "NACOS_ENABLED=false",
        "备份数据库和报告目录",
    ):
        assert phrase in readme
