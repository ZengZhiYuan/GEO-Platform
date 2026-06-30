"""Agent 结构化输出 Schema。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


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


class AiGenerationCompetitorItem(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    competitor_words: list[str] = Field(default_factory=list, max_length=20)
    official_domain: str | None = None


class AiBrandWordsLLMOutput(BaseModel):
    brand_words: list[str] = Field(min_length=1, max_length=50)


class AiCompetitorsLLMOutput(BaseModel):
    competitors: list[AiGenerationCompetitorItem] = Field(default_factory=list, max_length=20)


VALID_AI_QUESTION_PROMPT_TYPES = frozenset(
    {
        "brand_sentiment",
        "brand_info",
        "category_sentiment",
        "competitor_comparison",
        "category_recommendation",
    }
)


class AiGeneratedQuestionLLMItem(BaseModel):
    prompt_text: str = Field(min_length=1, max_length=500)
    prompt_type: str = Field(min_length=1, max_length=64)
    core_keyword: str | None = Field(default=None, max_length=100)

    @field_validator("prompt_type")
    @classmethod
    def validate_prompt_type(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in VALID_AI_QUESTION_PROMPT_TYPES:
            raise ValueError(f"unsupported prompt_type: {normalized}")
        return normalized


class AiQuestionsLLMOutput(BaseModel):
    questions: list[AiGeneratedQuestionLLMItem] = Field(default_factory=list, max_length=50)


class EvaluationTagLLMItem(BaseModel):
    tag: str = Field(min_length=1, max_length=50)
    answer_indexes: list[int] = Field(default_factory=list, max_length=100)


class EvaluationTagsLLMOutput(BaseModel):
    items: list[EvaluationTagLLMItem] = Field(default_factory=list, max_length=50)


OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "classify_sentiment": SentimentOutput,
    "classify_recommendation": RecommendationIntentOutput,
    "assess_risk": RiskAssessmentOutput,
    "generate_insights": InsightSummaryOutput,
    "generate_brand_words": AiBrandWordsLLMOutput,
    "generate_competitors": AiCompetitorsLLMOutput,
    "generate_questions": AiQuestionsLLMOutput,
    "cluster_evaluation_tags": EvaluationTagsLLMOutput,
}
