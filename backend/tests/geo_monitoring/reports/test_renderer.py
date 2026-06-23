"""报告渲染测试。"""

from __future__ import annotations

from app.geo_monitoring.reports.renderer import build_report_context, render_html, render_markdown


def test_build_report_context_derives_diagnostic_sections(session_factory, analyzed_run):
    with session_factory() as db:
        context = build_report_context(db, analyzed_run["run_id"])

    assert context["diagnosis"]["overall_score"] >= 0
    assert "目标品牌" in context["diagnosis"]["summary"]
    assert context["diagnosis"]["strengths"]
    assert context["diagnosis"]["risks"]
    assert context["platform_scoreboard"][0]["platform_code"] == "qwen"
    assert context["platform_scoreboard"][0]["brand_mention_percent"] == "100%"
    assert context["prompt_scene_cards"][0]["prompt_text"] == "哪个品牌更好？"
    assert context["source_type_distribution"][0]["label"] == "网页来源"
    assert context["top_source_cards"][0]["domain"] == "example.com"
    assert context["action_recommendations"]


def test_render_markdown_includes_core_sections(session_factory, analyzed_run):
    with session_factory() as db:
        context = build_report_context(db, analyzed_run["run_id"])
        content = render_markdown(context)

    assert analyzed_run["project_id"] and analyzed_run["run_id"]
    assert "分析测试" in content
    assert "平台指标" in content or "platform" in content.lower()
    assert "qwen" in content
    assert "Top1(首位)提及率" in content
    assert "Top3(首屏)提及率" in content
    assert "竞品" in content or "竞品B" in content
    assert "来源" in content or "example.com" in content
    assert "整体表现诊断" in content
    assert "核心优势点" in content
    assert "优化建议" in content
    assert "高权重来源内容追踪" in content


def test_render_html_escapes_raw_answer_xss(session_factory, xss_analyzed_run):
    with session_factory() as db:
        context = build_report_context(db, xss_analyzed_run["run_id"])
        html = render_html(context)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Top1(首位)提及率" in html
    assert "Top3(首屏)提及率" in html
    assert "整体表现诊断" in html
    assert "核心问题点" in html
    assert "平台品牌得分" in html
    assert "高权重来源内容追踪" in html
    assert "alert" in html
