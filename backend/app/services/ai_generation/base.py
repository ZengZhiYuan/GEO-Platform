"""AI 生成服务的抽象基类与数据结构。

设计要点（见 docs/claude-code-dev.md 11）：
- Worker 不直接写死某个模型，统一面向 ``AIWriter`` 抽象编程，便于后续替换
  为真实 LLM Provider（OpenAI 兼容 / 通义千问 / DeepSeek 等）。
- ``ArticleContext`` / ``ArticleResult`` 为纯数据类（dataclass），不含任何 DB
  依赖。这样「读取上下文（短事务）」与「调用 AI（无事务）」彻底解耦，
  避免在数据库长事务中调用 AI（见任务要求 16）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ArticleContext:
    """单篇文章生成所需的上下文（由 DB 读取后组装，纯数据）。

    字段来源（见 dev 文档 11.2 Prompt 组装输入）：
    - 写作任务：task_name / distill_keywords / article_image_count / generation_index
    - 内容分类：category_name
    - 写作规范：content_rule_content（内容创作指令）/ title_rule_content（标题创作指令）
    - 画像图库：image_urls（候选配图 URL 列表）
    - 品牌知识库：brand_* 字段（品牌知识库模块尚未实现，暂为 None）
    """

    writing_task_id: int
    article_id: int
    generation_index: int = 1

    task_name: str = ""
    distill_keywords: str = ""
    category_name: str | None = None

    content_rule_content: str = ""
    title_rule_content: str | None = None

    article_image_count: int = 0
    image_urls: list[str] = field(default_factory=list)

    # 品牌知识库（尚未实现，预留字段，便于后续接入）
    company_name: str | None = None
    company_short_name: str | None = None
    creation_direction: str | None = None
    copywriting_type: str | None = None
    product_service: str | None = None
    product_features: str | None = None


@dataclass
class ArticleResult:
    """AI 生成结果（纯数据）。

    ``content_html`` 为最终写入 ``article.content`` 的正文（富文本 HTML）。
    ``content_text`` 为纯文本镜像，便于检索 / 摘要（当前模型未单列存储字段，
    仅在结果对象中携带）。``cover_image_url`` 为建议封面图。
    """

    title: str
    content_html: str
    content_text: str = ""
    cover_image_url: str | None = None


class AIWriter(ABC):
    """文章生成器抽象基类。

    子类需实现 ``generate_title`` 与 ``generate_article``；``generate`` 提供
    「先生成标题、再生成正文」的默认编排，调用方通常只用 ``generate``。
    """

    @abstractmethod
    def generate_title(self, context: ArticleContext) -> str:
        """根据上下文生成文章标题。"""

    @abstractmethod
    def generate_article(self, context: ArticleContext, title: str) -> ArticleResult:
        """根据上下文与标题生成正文，返回完整 ``ArticleResult``。"""

    def generate(self, context: ArticleContext) -> ArticleResult:
        """默认编排：先生成标题，再生成正文。"""
        title = self.generate_title(context)
        return self.generate_article(context, title)
