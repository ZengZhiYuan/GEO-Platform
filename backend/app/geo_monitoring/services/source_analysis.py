"""信源引用分析页面级聚合服务。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.analysis.dto import AnswerInput, CitationInput
from app.geo_monitoring.analysis.metrics import compute_citation_rate, compute_rate
from app.geo_monitoring.analysis.sources import normalize_domain
from app.geo_monitoring.models import Answer, AnswerCitation, MonitorRun, QueryTask
from app.geo_monitoring.services.analysis import SourceStat
from app.geo_monitoring.services.dashboard import _select_latest_run
from app.geo_monitoring.services.metadata import resolve_display_source_type
from app.geo_monitoring.services.projects import require_active_project
from app.geo_monitoring.services.runs import get_run

_RATE_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class _SourceAggRow:
    platform_code: str
    domain: str
    source_name: str | None
    source_type: str | None
    citation_count: int


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(_RATE_QUANT))


def _normalize_platform_codes(platform_codes: list[str] | None) -> list[str] | None:
    if not platform_codes:
        return None
    return list(dict.fromkeys(code.strip() for code in platform_codes if code.strip()))


def _resolve_run(
    db: Session,
    project_id: int,
    *,
    run_id: int | None,
) -> MonitorRun | None:
    if run_id is not None:
        run = get_run(db, run_id)
        if run.project_id != project_id:
            raise BusinessException(code=40400, message="监测运行不存在")
        return run
    return _select_latest_run(db, project_id)


def _resolve_platform_columns(
    run: MonitorRun,
    platform_codes: list[str] | None,
) -> list[str]:
    if platform_codes:
        return platform_codes
    return list(run.platform_codes or [])


def _load_source_stats(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
) -> list[SourceStat]:
    conditions = [
        SourceStat.run_id == run_id,
        SourceStat.is_deleted.is_(False),
    ]
    if platform_codes:
        conditions.append(SourceStat.platform_code.in_(platform_codes))
    return list(
        db.execute(select(SourceStat).where(*conditions).order_by(SourceStat.rank_no))
        .scalars()
        .all()
    )


def _source_stats_to_agg_rows(rows: list[SourceStat]) -> list[_SourceAggRow]:
    return [
        _SourceAggRow(
            platform_code=row.platform_code or "",
            domain=row.domain,
            source_name=row.source_name,
            source_type=row.source_type,
            citation_count=row.citation_count,
        )
        for row in rows
    ]


def _domain_from_citation_row(
    domain: str | None,
    url: str | None,
) -> str | None:
    normalized = normalize_domain(domain)
    if normalized:
        return normalized
    if not url:
        return None
    host = urlparse(url.strip()).hostname
    return normalize_domain(host)


def _load_agg_rows_from_citations(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[_SourceAggRow]:
    conditions = [
        QueryTask.run_id == run_id,
        QueryTask.is_deleted.is_(False),
        Answer.is_deleted.is_(False),
        AnswerCitation.is_deleted.is_(False),
    ]
    if platform_codes:
        conditions.append(Answer.platform_code.in_(platform_codes))
    if start_at is not None:
        conditions.append(Answer.collected_at >= start_at)
    if end_at is not None:
        conditions.append(Answer.collected_at <= end_at)

    rows = db.execute(
        select(
            Answer.platform_code,
            AnswerCitation.domain,
            AnswerCitation.title,
            AnswerCitation.source_type,
            AnswerCitation.url,
        )
        .join(Answer, Answer.id == AnswerCitation.answer_id)
        .join(QueryTask, QueryTask.id == Answer.task_id)
        .where(*conditions)
    ).all()

    grouped: dict[tuple[str, str, str, str | None], int] = defaultdict(int)
    for platform_code, domain, title, source_type, url in rows:
        resolved_domain = _domain_from_citation_row(domain, url)
        if not resolved_domain and not (url and url.strip()):
            continue
        if not resolved_domain:
            continue
        source_name = (title or "").strip() or None
        key = (platform_code, resolved_domain, source_name or "", source_type)
        grouped[key] += 1

    return [
        _SourceAggRow(
            platform_code=platform_code,
            domain=domain,
            source_name=source_name or None,
            source_type=source_type,
            citation_count=count,
        )
        for (platform_code, domain, source_name, source_type), count in grouped.items()
    ]


def _load_agg_rows(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[_SourceAggRow]:
    if start_at is not None or end_at is not None:
        return _load_agg_rows_from_citations(
            db,
            run_id=run_id,
            platform_codes=platform_codes,
            start_at=start_at,
            end_at=end_at,
        )
    return _source_stats_to_agg_rows(
        _load_source_stats(
            db,
            run_id=run_id,
            platform_codes=platform_codes,
        )
    )


def _text_matches_keyword(*values: str | None, keyword: str | None) -> bool:
    if not keyword:
        return True
    needle = keyword.strip().casefold()
    if not needle:
        return True
    return any(needle in (value or "").casefold() for value in values)


def _matches_source_type(storage_value: str | None, source_type: str | None) -> bool:
    if not source_type:
        return True
    display_code, _ = resolve_display_source_type(storage_value)
    return display_code == source_type.strip()


def _filter_agg_rows(
    rows: list[_SourceAggRow],
    *,
    source_type: str | None,
    keyword: str | None,
) -> list[_SourceAggRow]:
    return [
        row
        for row in rows
        if _matches_source_type(row.source_type, source_type)
        and _text_matches_keyword(row.domain, row.source_name, keyword=keyword)
    ]


def _count_distinct_article_urls(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
    keyword: str | None,
    source_type: str | None,
) -> int:
    conditions = [
        QueryTask.run_id == run_id,
        QueryTask.is_deleted.is_(False),
        Answer.is_deleted.is_(False),
        AnswerCitation.is_deleted.is_(False),
        AnswerCitation.url.is_not(None),
        AnswerCitation.url != "",
    ]
    if platform_codes:
        conditions.append(Answer.platform_code.in_(platform_codes))
    if start_at is not None:
        conditions.append(Answer.collected_at >= start_at)
    if end_at is not None:
        conditions.append(Answer.collected_at <= end_at)

    rows = db.execute(
        select(
            AnswerCitation.url,
            AnswerCitation.domain,
            AnswerCitation.source_type,
        )
        .join(Answer, Answer.id == AnswerCitation.answer_id)
        .join(QueryTask, QueryTask.id == Answer.task_id)
        .where(*conditions)
    ).all()

    urls: set[str] = set()
    for url, domain, storage_type in rows:
        if not _text_matches_keyword(domain, keyword=keyword):
            continue
        if not _matches_source_type(storage_type, source_type):
            continue
        normalized = (url or "").strip()
        if normalized:
            urls.add(normalized)
    return len(urls)


def _compute_kpi_citation_rate(
    db: Session,
    *,
    run_id: int,
    platform_codes: list[str] | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> str | None:
    conditions = [
        QueryTask.run_id == run_id,
        QueryTask.is_deleted.is_(False),
        Answer.is_deleted.is_(False),
    ]
    if platform_codes:
        conditions.append(Answer.platform_code.in_(platform_codes))
    if start_at is not None:
        conditions.append(Answer.collected_at >= start_at)
    if end_at is not None:
        conditions.append(Answer.collected_at <= end_at)

    answers = db.execute(
        select(Answer, QueryTask.status)
        .join(QueryTask, QueryTask.id == Answer.task_id)
        .where(*conditions)
    ).all()
    if not answers:
        return None

    answer_ids = [answer.id for answer, _ in answers]
    citations_by_answer: dict[int, list[CitationInput]] = defaultdict(list)
    if answer_ids:
        citation_rows = db.execute(
            select(AnswerCitation).where(
                AnswerCitation.answer_id.in_(answer_ids),
                AnswerCitation.is_deleted.is_(False),
            )
        ).scalars()
        for citation in citation_rows:
            citations_by_answer[citation.answer_id].append(
                CitationInput(
                    citation_no=citation.citation_no,
                    url=citation.url,
                    domain=citation.domain,
                    title=citation.title,
                    source_type=citation.source_type,
                )
            )

    answer_inputs = [
        AnswerInput(
            answer_id=answer.id,
            prompt_id=answer.prompt_id,
            platform_code=answer.platform_code,
            task_status=status,
            normalized_text=answer.normalized_text or answer.raw_text or "",
            citations=tuple(citations_by_answer.get(answer.id, [])),
        )
        for answer, status in answers
    ]
    metric = compute_citation_rate(answer_inputs)
    return _decimal_str(metric.rate)


def _display_value(
    *,
    metric: str,
    link_count: int,
    citation_rate: str | None,
) -> str:
    if metric == "rate":
        return citation_rate if citation_rate is not None else "0.0000"
    return str(link_count)


def _build_type_distribution(
    rows: list[_SourceAggRow],
    *,
    metric: str,
    total_links: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        display_code, display_label = resolve_display_source_type(row.source_type)
        bucket = grouped.setdefault(
            display_code,
            {
                "source_type": display_code,
                "source_type_label": display_label,
                "link_count": 0,
            },
        )
        bucket["link_count"] += row.citation_count

    distribution: list[dict[str, Any]] = []
    for display_code in sorted(grouped):
        item = grouped[display_code]
        rate = _decimal_str(compute_rate(item["link_count"], total_links))
        item["citation_rate"] = rate
        item["display_value"] = _display_value(
            metric=metric,
            link_count=item["link_count"],
            citation_rate=rate,
        )
        distribution.append(item)
    distribution.sort(key=lambda item: (-item["link_count"], item["source_type"]))
    return distribution


def _build_site_rows(
    rows: list[_SourceAggRow],
    *,
    platform_columns: list[str],
    metric: str,
    total_links: int,
) -> list[dict[str, Any]]:
    by_site: dict[tuple[str, str], dict[str, Any]] = {}
    platform_totals = {
        code: sum(row.citation_count for row in rows if row.platform_code == code)
        for code in platform_columns
    }

    for row in rows:
        display_code, display_label = resolve_display_source_type(row.source_type)
        site_key = (row.domain, row.source_name or "")
        site = by_site.setdefault(
            site_key,
            {
                "domain": row.domain,
                "source_name": row.source_name,
                "source_type": display_code,
                "source_type_label": display_label,
                "link_count": 0,
                "platform_values": {
                    code: {
                        "platform_code": code,
                        "link_count": 0,
                        "has_citation_data": platform_totals.get(code, 0) > 0,
                    }
                    for code in platform_columns
                },
            },
        )
        site["link_count"] += row.citation_count
        if row.platform_code in site["platform_values"]:
            site["platform_values"][row.platform_code]["link_count"] += row.citation_count

    site_rows: list[dict[str, Any]] = []
    for site in by_site.values():
        site_rate = _decimal_str(compute_rate(site["link_count"], total_links))
        site["citation_rate"] = site_rate
        site["display_value"] = _display_value(
            metric=metric,
            link_count=site["link_count"],
            citation_rate=site_rate,
        )
        platform_values = []
        for code in platform_columns:
            bucket = site["platform_values"][code]
            platform_rate = _decimal_str(
                compute_rate(bucket["link_count"], platform_totals.get(code, 0))
            )
            bucket["citation_rate"] = platform_rate
            bucket["display_value"] = _display_value(
                metric=metric,
                link_count=bucket["link_count"],
                citation_rate=platform_rate,
            )
            platform_values.append(bucket)
        site["platform_values"] = platform_values
        site_rows.append(site)

    site_rows.sort(
        key=lambda item: (
            -item["link_count"],
            item["domain"],
            item["source_name"] or "",
        )
    )
    return site_rows


def _empty_payload(
    *,
    run_id: int | None,
    metric: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "metric": metric,
        "has_citation_data": False,
        "kpi": {
            "citation_count": 0,
            "site_count": 0,
            "article_count": 0,
            "citation_rate": None,
        },
        "type_distribution": [],
        "platform_columns": [],
        "sites": {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        },
    }


def get_source_analysis(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
    metric: str = "links",
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """聚合信源引用分析页 KPI、类型分布、站点矩阵。"""
    require_active_project(db, project_id)
    normalized_metric = metric if metric in {"links", "rate"} else "links"
    platform_codes = _normalize_platform_codes(platform_codes)

    run = _resolve_run(db, project_id, run_id=run_id)
    if run is None:
        return _empty_payload(
            run_id=None,
            metric=normalized_metric,
            page=page,
            page_size=page_size,
        )

    platform_columns = _resolve_platform_columns(run, platform_codes)
    agg_rows = _load_agg_rows(
        db,
        run_id=run.id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
    )
    filtered_rows = _filter_agg_rows(
        agg_rows,
        source_type=source_type,
        keyword=keyword,
    )

    if not filtered_rows:
        payload = _empty_payload(
            run_id=run.id,
            metric=normalized_metric,
            page=page,
            page_size=page_size,
        )
        payload["platform_columns"] = [
            {
                "platform_code": code,
                "has_citation_data": any(
                    row.platform_code == code and row.citation_count > 0
                    for row in agg_rows
                ),
            }
            for code in platform_columns
        ]
        if agg_rows:
            payload["kpi"]["article_count"] = _count_distinct_article_urls(
                db,
                run_id=run.id,
                platform_codes=platform_codes,
                start_at=start_at,
                end_at=end_at,
                keyword=keyword,
                source_type=source_type,
            )
            payload["kpi"]["citation_rate"] = _compute_kpi_citation_rate(
                db,
                run_id=run.id,
                platform_codes=platform_codes,
                start_at=start_at,
                end_at=end_at,
            )
        return payload

    total_links = sum(row.citation_count for row in filtered_rows)
    distinct_domains = {row.domain for row in filtered_rows}
    site_rows = _build_site_rows(
        filtered_rows,
        platform_columns=platform_columns,
        metric=normalized_metric,
        total_links=total_links,
    )
    total_sites = len(site_rows)
    start_index = max(page - 1, 0) * page_size
    end_index = start_index + page_size

    return {
        "run_id": run.id,
        "metric": normalized_metric,
        "has_citation_data": True,
        "kpi": {
            "citation_count": total_links,
            "site_count": len(distinct_domains),
            "article_count": _count_distinct_article_urls(
                db,
                run_id=run.id,
                platform_codes=platform_codes,
                start_at=start_at,
                end_at=end_at,
                keyword=keyword,
                source_type=source_type,
            ),
            "citation_rate": _compute_kpi_citation_rate(
                db,
                run_id=run.id,
                platform_codes=platform_codes,
                start_at=start_at,
                end_at=end_at,
            ),
        },
        "type_distribution": _build_type_distribution(
            filtered_rows,
            metric=normalized_metric,
            total_links=total_links,
        ),
        "platform_columns": [
            {
                "platform_code": code,
                "has_citation_data": any(
                    row.platform_code == code and row.citation_count > 0
                    for row in agg_rows
                ),
            }
            for code in platform_columns
        ],
        "sites": {
            "items": site_rows[start_index:end_index],
            "total": total_sites,
            "page": page,
            "page_size": page_size,
        },
    }


_EXPORT_BATCH_SIZE = 1000


def _collect_all_source_analysis_sites(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
    metric: str = "links",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """分批拉取全部站点行，避免导出静默截断。"""
    page = 1
    sites: list[dict[str, Any]] = []
    snapshot: dict[str, Any] | None = None
    total: int | None = None
    while True:
        data = get_source_analysis(
            db,
            project_id,
            run_id=run_id,
            platform_codes=platform_codes,
            start_at=start_at,
            end_at=end_at,
            source_type=source_type,
            keyword=keyword,
            metric=metric,
            page=page,
            page_size=_EXPORT_BATCH_SIZE,
        )
        if snapshot is None:
            snapshot = data
            total = int(data.get("sites", {}).get("total") or 0)
        batch = data.get("sites", {}).get("items") or []
        if not batch:
            break
        sites.extend(batch)
        if total is not None and len(sites) >= total:
            break
        page += 1
    return snapshot or {}, sites


def export_source_analysis_rows(
    db: Session,
    project_id: int,
    *,
    run_id: int | None = None,
    platform_codes: list[str] | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
    metric: str = "links",
) -> tuple[list[str], list[list[Any]]]:
    """导出信源分析站点矩阵 CSV 行（Query 与列表接口一致）。"""
    data, site_items = _collect_all_source_analysis_sites(
        db,
        project_id,
        run_id=run_id,
        platform_codes=platform_codes,
        start_at=start_at,
        end_at=end_at,
        source_type=source_type,
        keyword=keyword,
        metric=metric,
    )
    platform_columns = [
        item["platform_code"] for item in data.get("platform_columns", [])
    ]
    headers = [
        "域名",
        "站点名称",
        "信源类型",
        "信源类型名称",
        "链接数",
        "引用率",
        "展示值",
        *[f"{code}_链接数" for code in platform_columns],
        *[f"{code}_引用率" for code in platform_columns],
        *[f"{code}_展示值" for code in platform_columns],
    ]
    rows: list[list[Any]] = []
    for site in site_items:
        platform_map = {
            item["platform_code"]: item for item in site.get("platform_values", [])
        }
        row = [
            site.get("domain"),
            site.get("source_name"),
            site.get("source_type"),
            site.get("source_type_label"),
            site.get("link_count"),
            site.get("citation_rate"),
            site.get("display_value"),
        ]
        for code in platform_columns:
            bucket = platform_map.get(code, {})
            row.append(bucket.get("link_count", 0))
        for code in platform_columns:
            bucket = platform_map.get(code, {})
            row.append(bucket.get("citation_rate"))
        for code in platform_columns:
            bucket = platform_map.get(code, {})
            row.append(bucket.get("display_value"))
        rows.append(row)
    return headers, rows
