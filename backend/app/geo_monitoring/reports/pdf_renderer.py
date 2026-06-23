"""PDF report rendering based on the shared report context."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_FALLBACK_FONT_NAME = "STSong-Light"
_TTF_FONT_NAME = "GEOReportFont"
_ACTIVE_FONT_NAME: str | None = None

_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)


def _register_fonts() -> None:
    global _ACTIVE_FONT_NAME
    if _ACTIVE_FONT_NAME:
        return

    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        if _TTF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(_TTF_FONT_NAME, str(path), subfontIndex=0))
        _ACTIVE_FONT_NAME = _TTF_FONT_NAME
        return

    if _FALLBACK_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(_FALLBACK_FONT_NAME))
    _ACTIVE_FONT_NAME = _FALLBACK_FONT_NAME


def _styles() -> dict[str, ParagraphStyle]:
    _register_fonts()
    font_name = _ACTIVE_FONT_NAME or _FALLBACK_FONT_NAME
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#1e2636"),
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#718096"),
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ReportHeading2",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "ReportHeading3",
            parent=base["Heading3"],
            fontName=font_name,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#2f3a4d"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#263247"),
        ),
        "muted": ParagraphStyle(
            "ReportMuted",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#78869d"),
        ),
        "center": ParagraphStyle(
            "ReportCenter",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#263247"),
        ),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(str(text or "").replace("\n", "<br/>"), style)


def _section(title: str, styles: dict[str, ParagraphStyle]) -> list:
    return [Spacer(1, 3 * mm), _p(title, styles["h2"])]


def _metric_card(label: str, value: Any, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [
            [_p(label, styles["muted"])],
            [_p(value, styles["h3"])],
        ],
        colWidths=[38 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7ebf2")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _simple_table(
    rows: list[list[Any]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
) -> Table:
    normalized = [
        [_p(cell, styles["body"] if row_index else styles["muted"]) for cell in row]
        for row_index, row in enumerate(rows)
    ]
    table = Table(normalized, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fc")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#edf0f6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _bullet_panel(
    title: str,
    items: list[str],
    *,
    tone: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    color = colors.HexColor("#149451" if tone == "good" else "#e5483f")
    fill = colors.HexColor("#f3fbf6" if tone == "good" else "#fff4f2")
    body = "<br/>".join(f"• {item}" for item in items) or "暂无数据。"
    table = Table(
        [[_p(title, styles["h3"])], [_p(body, styles["body"])]],
        colWidths=[78 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), fill),
                ("TEXTCOLOR", (0, 0), (-1, 0), color),
                ("BOX", (0, 0), (-1, -1), 0.5, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _page_header_footer(canvas, doc, context: dict[str, Any]) -> None:
    canvas.saveState()
    canvas.setFont(_ACTIVE_FONT_NAME or _FALLBACK_FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor("#73819a"))
    header = f"{context['project']['name']} GEO 品牌诊断报告"
    canvas.drawString(16 * mm, 287 * mm, header)
    canvas.line(16 * mm, 283 * mm, 194 * mm, 283 * mm)
    canvas.drawRightString(194 * mm, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def render_pdf(context: dict[str, Any]) -> bytes:
    """Render a printable PDF report from the shared report context."""

    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=22 * mm,
        bottomMargin=16 * mm,
        title="GEO Monitoring Report",
    )
    story: list = []

    project = context["project"]
    run = context["run"]
    diagnosis = context["diagnosis"]

    story.append(_p(project["report_title"], styles["title"]))
    if project.get("report_subtitle"):
        story.append(_p(project["report_subtitle"], styles["subtitle"]))
    story.append(
        _p(
            f"运行编号: {run['run_no']} | Prompt 集版本: {run['prompt_set_version']} | 目标品牌: {context['target_brand_name']}",
            styles["muted"],
        )
    )

    metrics = Table(
        [
            [
                _metric_card("综合得分", f"{diagnosis['overall_score']}/100", styles),
                _metric_card("诊断等级", diagnosis["level"], styles),
                _metric_card("有效回答", run["valid_answer_count"], styles),
                _metric_card("优化建议", diagnosis["recommendation_count"], styles),
            ]
        ],
        colWidths=[40 * mm, 40 * mm, 40 * mm, 40 * mm],
    )
    story.extend([Spacer(1, 5 * mm), metrics, Spacer(1, 5 * mm)])
    story.append(_p(diagnosis["summary"], styles["body"]))

    story.extend(_section("整体表现诊断", styles))
    story.append(
        Table(
            [
                [
                    _bullet_panel(
                        "核心优势点",
                        diagnosis["strengths"],
                        tone="good",
                        styles=styles,
                    ),
                    _bullet_panel(
                        "核心问题点",
                        diagnosis["risks"],
                        tone="warn",
                        styles=styles,
                    ),
                ]
            ],
            colWidths=[82 * mm, 82 * mm],
        )
    )

    story.extend(_section("平台品牌得分", styles))
    platform_rows = [
        ["AI 平台", "综合得分", "品牌提及率", "Top1(首位)", "Top3(首屏)", "平均排名", "倾向"]
    ]
    for item in context["platform_scoreboard"]:
        platform_rows.append(
            [
                item["platform_code"],
                f"{item['score']}/100",
                item["brand_mention_percent"],
                item["brand_top1_percent"],
                item["brand_top3_percent"],
                item["avg_rank_label"],
                item["sentiment_label"],
            ]
        )
    story.append(
        _simple_table(
            platform_rows,
            [26 * mm, 23 * mm, 24 * mm, 22 * mm, 22 * mm, 23 * mm, 26 * mm],
            styles,
        )
    )

    story.extend(_section("问题场景表现", styles))
    scene_rows = [["平台", "问题场景", "竞争力", "梯队"]]
    for item in context["prompt_scene_cards"][:12]:
        scene_rows.append(
            [
                item["platform_code"],
                item["prompt_text"] or f"Prompt {item['prompt_id']}",
                f"{item['score']}/100",
                item["rank_label"],
            ]
        )
    story.append(_simple_table(scene_rows, [24 * mm, 92 * mm, 25 * mm, 25 * mm], styles))

    story.extend(_section("引用来源分析", styles))
    source_type_rows = [["信源类型", "占比", "引用次数"]]
    for item in context["source_type_distribution"]:
        source_type_rows.append([item["label"], item["share_percent"], item["citation_count"]])
    story.append(_simple_table(source_type_rows, [80 * mm, 40 * mm, 40 * mm], styles))

    story.extend(_section("高权重来源内容追踪", styles))
    for source in context["top_source_cards"][:6]:
        prompts = "；".join(source["prompts"]) or "—"
        platforms = "、".join(source["platforms"]) or "—"
        story.append(
            KeepTogether(
                [
                    _p(
                        f"{source['source_name']} | {source['domain']} | 引用 {source['citation_count']} 次",
                        styles["h3"],
                    ),
                    _p(
                        f"信源类型: {source['source_type']} | 引用占比: {source['share_percent']} | 关联平台: {platforms}",
                        styles["muted"],
                    ),
                    _p(f"关联问题: {prompts}", styles["body"]),
                    Spacer(1, 3 * mm),
                ]
            )
        )

    story.extend(_section("优化建议", styles))
    recommendation_rows = [["建议", "依据", "动作"]]
    for item in context["action_recommendations"]:
        recommendation_rows.append([item["title"], item["basis"], item["action"]])
    story.append(
        _simple_table(
            recommendation_rows,
            [38 * mm, 48 * mm, 80 * mm],
            styles,
        )
    )

    story.extend(_section("原始回答摘录", styles))
    for answer in context["answers"][:8]:
        story.append(_p(f"{answer['platform_code']} / Prompt {answer['prompt_id']}", styles["h3"]))
        story.append(_p(answer.get("prompt_text") or "", styles["muted"]))
        story.append(_p((answer.get("raw_text") or "")[:800], styles["body"]))
        story.append(Spacer(1, 3 * mm))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc: _page_header_footer(canvas, doc, context),
        onLaterPages=lambda canvas, doc: _page_header_footer(canvas, doc, context),
    )
    return buffer.getvalue()
