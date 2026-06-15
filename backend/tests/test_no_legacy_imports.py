from pathlib import Path


FORBIDDEN_NAMES = {
    "keyword.py",
    "title_inspiration.py",
    "image_asset.py",
    "image_category.py",
    "writing_rule.py",
    "writing_task.py",
    "article.py",
    "content_category.py",
}


def test_legacy_backend_modules_are_absent():
    app_dir = Path(__file__).parents[1] / "app"
    remaining = {path.name for path in app_dir.rglob("*.py")}

    assert not FORBIDDEN_NAMES.intersection(remaining)
    assert not (app_dir / "tasks").exists()
    assert not (app_dir / "services").exists()


def test_worker_bootstrap_has_no_legacy_actor_imports():
    app_dir = Path(__file__).parents[1] / "app"
    worker_source = (app_dir / "workers" / "worker.py").read_text(encoding="utf-8")
    broker_source = (app_dir / "workers" / "broker.py").read_text(encoding="utf-8")

    assert "app.tasks" not in worker_source
    assert "generate_article" not in worker_source
    assert "CurrentMessage" not in broker_source
