"""Agent 结构化输出 Schema。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class SentimentOutput(BaseModel):
    label: SentimentLabel
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class RecommendationIntent(StrEnum):
    STRONG_RECOMMEND = "strong_recommend"
    RECOMMEND = "recommend"
    NEUTRAL = "neutral"
    NOT_RECOMMEND = "not_recommend"
    UNCLEAR = "unclear"


class RecommendationIntentOutput(BaseModel):
    intent: RecommendationIntent
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskAssessmentOutput(BaseModel):
    level: RiskLevel
    topics: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class InsightPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class ImprovementSuggestion(BaseModel):
    priority: InsightPriority
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class InsightSummaryOutput(BaseModel):
    platform_summary: str = Field(min_length=1)
    key_gaps: list[str] = Field(default_factory=list)
    suggestions: list[ImprovementSuggestion] = Field(default_factory=list)


OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "classify_sentiment": SentimentOutput,
    "classify_recommendation": RecommendationIntentOutput,
    "assess_risk": RiskAssessmentOutput,
    "generate_insights": InsightSummaryOutput,
}
