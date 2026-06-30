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


def test_legacy_workers_package_is_absent():
    app_dir = Path(__file__).parents[1] / "app"
    assert not (app_dir / "workers").exists()
