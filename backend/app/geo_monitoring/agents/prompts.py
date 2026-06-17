"""Agent Prompt 模板与版本管理。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    key: str
    version: str
    system: str
    user: str


PROMPT_TEMPLATES: dict[str, PromptTemplate] = {
    "classify_sentiment": PromptTemplate(
        key="classify_sentiment",
        version="1.0.0",
        system=(
            "你是 AI 应用监测分析助手。根据给定回答文本判断对目标品牌的情感倾向。"
            "只输出符合 JSON Schema 的 JSON，不要输出其它内容。"
        ),
        user=(
            "回答文本：\n{answer_text}\n\n"
            "输出字段：label(positive|neutral|negative|mixed)、confidence(0-1)、rationale。"
        ),
    ),
    "classify_recommendation": PromptTemplate(
        key="classify_recommendation",
        version="1.0.0",
        system=(
            "你是 AI 应用监测分析助手。判断回答是否推荐目标品牌。"
            "只输出符合 JSON Schema 的 JSON，不要输出其它内容。"
        ),
        user=(
            "回答文本：\n{answer_text}\n\n"
            "输出字段：intent(strong_recommend|recommend|neutral|not_recommend|unclear)、"
            "confidence(0-1)、evidence。"
        ),
    ),
    "assess_risk": PromptTemplate(
        key="assess_risk",
        version="1.0.0",
        system=(
            "你是 AI 应用监测分析助手。根据指标摘要评估品牌在该平台的风险。"
            "只输出符合 JSON Schema 的 JSON，不要输出其它内容。"
        ),
        user=(
            "指标摘要：\n{metrics_summary}\n\n"
            "输出字段：level(low|medium|high)、topics(字符串数组)、summary。"
        ),
    ),
    "generate_insights": PromptTemplate(
        key="generate_insights",
        version="1.0.0",
        system=(
            "你是 AI 应用监测分析助手。根据平台指标生成改进洞察。"
            "只输出符合 JSON Schema 的 JSON，不要输出其它内容。"
        ),
        user=(
            "平台：{platform_code}\n"
            "指标摘要：\n{metrics_summary}\n\n"
            "输出字段：platform_summary、key_gaps(字符串数组)、"
            "suggestions(数组，每项含 priority(P0|P1|P2)、title、detail)。"
        ),
    ),
}

REPAIR_PROMPT_VERSION = "1.0.0"
REPAIR_SYSTEM_PROMPT = (
    "你是 JSON 修复助手。根据校验错误修正输出，使其满足给定 JSON Schema。"
    "只输出合法 JSON，不要输出其它内容。"
)
REPAIR_USER_TEMPLATE = (
    "原始输出：\n{raw_text}\n\n"
    "校验错误：\n{validation_errors}\n\n"
    "目标 Schema：\n{schema_hint}\n\n"
    "请输出修正后的 JSON。"
)


def get_prompt_template(template_key: str) -> PromptTemplate:
    try:
        return PROMPT_TEMPLATES[template_key]
    except KeyError as exc:
        raise KeyError(f"unknown prompt template: {template_key}") from exc


def render_prompt(template_key: str, variables: dict[str, str]) -> tuple[str, str, str]:
    """渲染 Prompt，返回 (system_prompt, user_prompt, prompt_version)。"""
    template = get_prompt_template(template_key)
    try:
        user_prompt = template.user.format(**variables)
    except KeyError as exc:
        raise KeyError(
            f"missing prompt variable {exc.args[0]} for template {template_key}"
        ) from exc
    return template.system, user_prompt, template.version
