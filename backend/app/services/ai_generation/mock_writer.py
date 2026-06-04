"""MockAIWriter：第一版确定性 Mock 生成器（不接真实大模型）。

特性：
- 完全确定性、无网络、无外部依赖，便于本地与 CI 验证业务闭环。
- 生成内容真实反映上下文（关键词 / 分类 / 指令 / 配图），证明上下文拼接正确。
- 失败路径可控：当 ``distill_keywords`` 含哨兵 ``__fail__`` 时主动抛错，
  用于验证「小任务失败 -> 记录 error_message -> 大任务聚合失败」全链路。
- 可选模拟耗时：``settings.AI_MOCK_DELAY_SECONDS``（默认 0，不阻塞）。
"""

from __future__ import annotations

import html
import time

from app.core.config import settings
from app.services.ai_generation.base import AIWriter, ArticleContext, ArticleResult
from app.services.ai_generation.prompt_assembler import (
    build_article_prompt,
    build_title_prompt,
)

# 哨兵：蒸馏训练词中包含该子串时，Mock 主动失败（用于验证失败/重试路径）
FAILURE_SENTINEL = "__fail__"


class MockAIWriter(AIWriter):
    """确定性 Mock 文章生成器。"""

    def _maybe_delay(self) -> None:
        delay = settings.AI_MOCK_DELAY_SECONDS
        if delay and delay > 0:
            time.sleep(delay)

    def _guard_failure(self, context: ArticleContext) -> None:
        if FAILURE_SENTINEL in (context.distill_keywords or ""):
            raise RuntimeError(
                f"MockAIWriter 触发模拟失败（distill_keywords 含 {FAILURE_SENTINEL}）"
            )

    def generate_title(self, context: ArticleContext) -> str:
        """生成确定性标题（围绕主创作词）。"""
        self._guard_failure(context)
        # 组装 Prompt（Mock 不真正发送，仅证明上下文被纳入 / 便于后续接真实模型）
        build_title_prompt(context)

        keyword = (context.distill_keywords or "内容").strip() or "内容"
        category = (context.category_name or "").strip()
        suffix = f"·{category}" if category else ""
        return f"【{keyword}{suffix}】第{context.generation_index}篇 · 深度内容创作指南"

    def generate_article(
        self, context: ArticleContext, title: str
    ) -> ArticleResult:
        """生成确定性正文（HTML），并按配图数量嵌入候选图片。"""
        self._guard_failure(context)
        self._maybe_delay()
        build_article_prompt(context, title)

        keyword = html.escape((context.distill_keywords or "内容").strip() or "内容")
        category = html.escape((context.category_name or "未分类").strip() or "未分类")
        rule = html.escape(
            (context.content_rule_content or "").strip() or "（沿用默认内容创作指令）"
        )
        safe_title = html.escape(title)

        # 按 article_image_count 选取候选配图（不超过可用数量）
        pick = max(0, int(context.article_image_count or 0))
        chosen = context.image_urls[:pick] if context.image_urls else []
        image_html = "".join(
            f'<p><img src="{html.escape(url)}" alt="配图{i + 1}" /></p>'
            for i, url in enumerate(chosen)
        )

        content_html = (
            f"<h1>{safe_title}</h1>"
            f"<p>本文围绕主创作词「{keyword}」展开，归属分类「{category}」。"
            f"以下内容由 MockAIWriter 生成，用于跑通写作任务异步生成闭环。</p>"
            f"<h2>一、选题背景</h2>"
            f"<p>{keyword} 是当前自媒体内容创作的重要方向，本文结合内容创作指令进行组织。</p>"
            f"<h2>二、核心要点</h2>"
            f"<ul><li>紧扣主创作词：{keyword}</li>"
            f"<li>遵循内容创作指令</li>"
            f"<li>结构清晰，便于审核与二次编辑</li></ul>"
            f"<h2>三、内容创作指令摘要</h2>"
            f"<p>{rule}</p>"
            f"{image_html}"
            f"<h2>四、结语</h2>"
            f"<p>以上为「{keyword}」主题的示例文章，可在文章清单中进一步审核、编辑与发布。</p>"
        )

        content_text = (
            f"{title}\n\n本文围绕主创作词「{context.distill_keywords}」展开，"
            f"归属分类「{context.category_name or '未分类'}」。"
            f"内容由 MockAIWriter 生成，用于跑通写作任务异步生成闭环。"
        )

        cover = chosen[0] if chosen else (
            context.image_urls[0] if context.image_urls else None
        )

        return ArticleResult(
            title=title,
            content_html=content_html,
            content_text=content_text,
            cover_image_url=cover,
        )


def get_ai_writer() -> AIWriter:
    """返回当前生效的 AI 生成器实例。

    第一版恒为 ``MockAIWriter``（见 docs/decisions.md 004）。后续接入真实
    LLM Provider 时，可在此根据 ``settings.AI_PROVIDER`` 选择不同实现。
    """
    return MockAIWriter()
