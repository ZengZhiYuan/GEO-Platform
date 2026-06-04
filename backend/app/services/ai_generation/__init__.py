"""AI 内容生成服务（可插拔 LLM Provider）。

第一版按 docs/decisions.md 004 使用 Mock 实现，先跑通业务闭环，
避免早期被真实模型接口 / 费用 / 网络 / 提示词问题阻塞。

对外导出：
- ``AIWriter``：生成器抽象基类（generate_title / generate_article / generate）。
- ``ArticleContext`` / ``ArticleResult``：上下文与结果数据类（纯数据，无 DB 依赖）。
- ``MockAIWriter``：确定性 Mock 实现。
- ``get_ai_writer``：按配置返回当前生成器实例（当前恒为 MockAIWriter）。
- ``build_title_prompt`` / ``build_article_prompt``：Prompt 组装（见 dev 文档 11.3/11.4）。
"""

from app.services.ai_generation.base import (
    AIWriter,
    ArticleContext,
    ArticleResult,
)
from app.services.ai_generation.mock_writer import MockAIWriter, get_ai_writer
from app.services.ai_generation.prompt_assembler import (
    build_article_prompt,
    build_title_prompt,
)

__all__ = [
    "AIWriter",
    "ArticleContext",
    "ArticleResult",
    "MockAIWriter",
    "build_article_prompt",
    "build_title_prompt",
    "get_ai_writer",
]
