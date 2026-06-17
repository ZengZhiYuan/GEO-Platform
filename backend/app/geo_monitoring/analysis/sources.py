"""引用来源统计纯函数。"""

from __future__ import annotations

from urllib.parse import urlparse

from app.geo_monitoring.analysis.dto import AnswerInput, CitationInput, RateMetric, SourceStatRow
from app.geo_monitoring.analysis.metrics import compute_rate, filter_valid_answers


def normalize_domain(domain: str | None) -> str | None:
    if domain is None:
        return None
    normalized = domain.strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized or None


def _domain_from_citation(citation: CitationInput) -> str | None:
    domain = normalize_domain(citation.domain)
    if domain:
        return domain
    if not citation.url:
        return None
    host = urlparse(citation.url.strip()).hostname
    return normalize_domain(host)


def is_valid_citation(citation: CitationInput) -> bool:
    domain = _domain_from_citation(citation)
    if domain:
        return True
    return bool(citation.url and citation.url.strip())


def compute_source_coverage(
    answers: list[AnswerInput],
    *,
    official_domain: str,
) -> RateMetric:
    valid_answers = filter_valid_answers(answers)
    target_domain = normalize_domain(official_domain)
    if not target_domain:
        return RateMetric(0, len(valid_answers), compute_rate(0, len(valid_answers)))

    numerator = 0
    for answer in valid_answers:
        domains = {
            domain
            for citation in answer.citations
            if (domain := _domain_from_citation(citation)) is not None
        }
        if target_domain in domains:
            numerator += 1

    denominator = len(valid_answers)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=compute_rate(numerator, denominator),
    )


def compute_source_stats(
    answers: list[AnswerInput],
    *,
    platform_code: str,
) -> list[SourceStatRow]:
    valid_answers = filter_valid_answers(answers)
    citation_totals: dict[str, int] = {}
    answer_coverage: dict[str, set[int]] = {}

    for answer in valid_answers:
        seen_in_answer: set[str] = set()
        for citation in answer.citations:
            domain = _domain_from_citation(citation)
            if not domain:
                continue
            citation_totals[domain] = citation_totals.get(domain, 0) + 1
            seen_in_answer.add(domain)
        for domain in seen_in_answer:
            answer_coverage.setdefault(domain, set()).add(answer.answer_id)

    total_citations = sum(citation_totals.values())
    if total_citations == 0:
        return []

    rows = [
        SourceStatRow(
            platform_code=platform_code,
            domain=domain,
            citation_count=citation_totals[domain],
            answer_coverage_count=len(answer_coverage.get(domain, set())),
            share_rate=compute_rate(citation_totals[domain], total_citations),
            rank_no=0,
        )
        for domain in citation_totals
    ]
    rows.sort(key=lambda row: (-row.citation_count, row.domain))
    return [
        SourceStatRow(
            platform_code=row.platform_code,
            domain=row.domain,
            citation_count=row.citation_count,
            answer_coverage_count=row.answer_coverage_count,
            share_rate=row.share_rate,
            rank_no=index,
        )
        for index, row in enumerate(rows, start=1)
    ]
