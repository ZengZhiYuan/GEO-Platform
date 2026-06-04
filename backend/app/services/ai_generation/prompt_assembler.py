"""Prompt 组装。

根据 ``ArticleContext`` 拼接标题 / 正文 Prompt（模板见 dev 文档 11.3 / 11.4）。
Mock 实现并不真正发送这些 Prompt，但仍按模板组装并随结果记录，便于：
- 验证「上下文拼接」逻辑正确（关键词、分类、指令、配图等都被纳入）；
- 后续替换为真实 LLM Provider 时直接复用该 Prompt 组装层。
"""

from __future__ import annotations

from app.services.ai_generation.base import ArticleContext


def _fallback(value: str | None, default: str = "（无）") -> str:
    """空值占位，保证 Prompt 模板字段不为空字符串。"""
    if value is None:
        return default
    value = value.strip()
    return value or default


def _image_url_block(image_urls: list[str]) -> str:
    """把候选配图 URL 列表渲染为 Prompt 文本块。"""
    if not image_urls:
        return "（无可用配图）"
    return "\n".join(f"- {url}" for url in image_urls)


def build_title_prompt(context: ArticleContext) -> str:
    """组装标题创作 Prompt（dev 文档 11.3）。"""
    return (
        "你是一个擅长小红书、知乎、微信公众号内容选题的标题策划专家。\n\n"
        f"【创作平台/类型】\n{_fallback(context.copywriting_type)}\n\n"
        f"【主创作词】\n{_fallback(context.distill_keywords)}\n\n"
        "【品牌信息】\n"
        f"公司名称：{_fallback(context.company_name)}\n"
        f"公司简称：{_fallback(context.company_short_name)}\n"
        f"创作方向：{_fallback(context.creation_direction)}\n"
        f"产品服务：{_fallback(context.product_service)}\n"
        f"产品特点：{_fallback(context.product_features)}\n\n"
        f"【标题创作指令】\n{_fallback(context.title_rule_content)}\n\n"
        "【要求】\n"
        "1. 生成一个适合自媒体传播的标题。\n"
        "2. 标题要围绕主创作词展开。\n"
        "3. 不要夸大承诺，不要出现违规表达。\n"
        "4. 只返回标题本身，不要返回解释。\n"
    )


def build_article_prompt(context: ArticleContext, title: str) -> str:
    """组装正文创作 Prompt（dev 文档 11.4）。"""
    return (
        "你是一个专业的新媒体内容写作专家，请根据以下信息生成一篇可发布的文章。\n\n"
        f"【文章标题】\n{title}\n\n"
        f"【创作关键词】\n{_fallback(context.distill_keywords)}\n\n"
        f"【文章分类】\n{_fallback(context.category_name)}\n\n"
        "【品牌知识】\n"
        f"公司名称：{_fallback(context.company_name)}\n"
        f"公司简称：{_fallback(context.company_short_name)}\n"
        f"创作方向：{_fallback(context.creation_direction)}\n"
        f"文案类型：{_fallback(context.copywriting_type)}\n"
        f"产品服务：{_fallback(context.product_service)}\n"
        f"产品特点：{_fallback(context.product_features)}\n\n"
        f"【内容创作指令】\n{_fallback(context.content_rule_content)}\n\n"
        f"【配图要求】\n文章需要使用 {context.article_image_count} 张图片。\n"
        f"可用图片URL：\n{_image_url_block(context.image_urls)}\n\n"
        "【输出要求】\n"
        "请返回 JSON，包含 title / content_html / content_text / "
        "suggested_cover_image_url 字段。\n"
    )
