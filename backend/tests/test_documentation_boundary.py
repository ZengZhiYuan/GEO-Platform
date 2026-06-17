from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_docs_contains_only_approved_documents():
    files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "docs").rglob("*")
        if path.is_file()
    }

    assert files == {
        "docs/AI应用监测_MVP_Cursor实施任务.md",
        "docs/AI应用监测_MVP_Cursor实施任务V2.md",
        "docs/AI应用监测_MVP_V2_Task索引.md",
        "docs/采集任务生命周期说明.md",
        "docs/superpowers/specs/2026-06-15-ai-monitoring-domain-replacement-design.md",
        "docs/superpowers/plans/2026-06-15-ai-monitoring-domain-replacement-plan.md",
    }


def test_monitoring_documents_match_current_delivery_scope():
    technical_document = (ROOT / "AI应用监测_技术开发文档.md").read_text(
        encoding="utf-8"
    )
    implementation_plan = (
        ROOT / "docs" / "AI应用监测_MVP_Cursor实施任务.md"
    ).read_text(encoding="utf-8")

    assert "V2.0" in technical_document
    assert "geo_monitoring_0004" in technical_document
    assert "官方 API" in technical_document
    assert "REPORT_STORAGE_DIR" in technical_document

    assert "Cursor" in implementation_plan
    assert "[S]" in implementation_plan
    assert "[P]" in implementation_plan
    assert "worktree" in implementation_plan
    assert "Task 1：创建采集域库表" in implementation_plan
    assert "Task 3：依赖与环境变量契约" in implementation_plan


def test_claude_instructions_describe_monitoring_only():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "AI 应用监测" in text
    assert "/api/geo-monitoring" in text
    assert "关键词" + "库 → 标题" + "灵感" not in text
    assert "写作" + "任务" not in text
