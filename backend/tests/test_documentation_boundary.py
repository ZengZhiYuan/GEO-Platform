from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_docs_contains_only_current_superpowers_documents():
    files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "docs").rglob("*")
        if path.is_file()
    }

    assert files == {
        "docs/superpowers/specs/2026-06-15-ai-monitoring-domain-replacement-design.md",
        "docs/superpowers/plans/2026-06-15-ai-monitoring-domain-replacement-plan.md",
    }


def test_claude_instructions_describe_monitoring_only():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "AI 应用监测" in text
    assert "/api/geo-monitoring" in text
    assert "关键词" + "库 → 标题" + "灵感" not in text
    assert "写作" + "任务" not in text
