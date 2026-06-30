from pathlib import Path


ROOT = Path(__file__).parents[2]

APPROVED_DOCS = {
    "docs/AI应用监测_MVP_Cursor实施任务.md",
    "docs/AI应用监测_MVP_Cursor实施任务V2.md",
    "docs/AI应用监测_MVP_V2_Task索引.md",
    "docs/AI应用监测平台操作手册.md",
    "docs/API全量接口测试报告.md",
    "docs/API接口文档.md",
    "docs/API测试文档.md",
    "docs/Cursor接口缺口开发任务书.md",
    "docs/Cursor接口缺口开发任务书_Task索引.md",
    "docs/Cursor模力指数API替换Aidso开发任务书.md",
    "docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md",
    "docs/ER图.md",
    "docs/PostgreSQL建表操作文档.md",
    "docs/PostgreSQL远程建表操作文档_无需部署代码.md",
    "docs/geo-platform_schema.sql",
    "docs/molizhishu-collection-source-design.md",
    "docs/superpowers/plans/2026-06-15-ai-monitoring-domain-replacement-plan.md",
    "docs/superpowers/plans/2026-06-24-aidso-collection-source.md",
    "docs/superpowers/plans/2026-06-30-production-readiness-remediation.md",
    "docs/superpowers/specs/2026-06-15-ai-monitoring-domain-replacement-design.md",
    "docs/superpowers/specs/2026-06-24-aidso-collection-source-design.md",
    "docs/代码审核要求.md",
    "docs/原型功能-API映射_v1.md",
    "docs/原型功能_API映射与缺口清单.md",
    "docs/原型功能_API映射整合精简版.md",
    "docs/端到端流水线测试报告.md",
    "docs/采集任务生命周期说明.md",
}


def test_docs_contains_only_approved_documents():
    files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "docs").rglob("*")
        if path.is_file()
    }

    assert files == APPROVED_DOCS


def test_monitoring_documents_match_current_delivery_scope():
    technical_document = (ROOT / "AI应用监测_技术开发文档.md").read_text(
        encoding="utf-8"
    )
    implementation_plan = (
        ROOT / "docs" / "AI应用监测_MVP_Cursor实施任务.md"
    ).read_text(encoding="utf-8")

    assert "V2.1" in technical_document
    assert "geo_monitoring_0005" in technical_document
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
