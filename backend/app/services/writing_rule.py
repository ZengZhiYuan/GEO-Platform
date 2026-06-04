"""写作规范 CRUD / Service。

同步 SQLAlchemy 2.0 写法；所有查询过滤软删除记录（is_deleted=False）。
记录不存在时抛出 BusinessException，由全局异常处理器统一返回。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.writing_rule import WritingRule
from app.schemas.writing_rule import WritingRuleCreate, WritingRuleUpdate


def _get_active(db: Session, rule_id: int) -> WritingRule:
    """按 id 获取未删除的写作规范，不存在则抛业务异常。"""
    stmt = select(WritingRule).where(
        WritingRule.id == rule_id,
        WritingRule.is_deleted.is_(False),
    )
    rule = db.execute(stmt).scalar_one_or_none()
    if rule is None:
        raise BusinessException(message="写作规范不存在", code=40400)
    return rule


def list_writing_rules(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    rule_name: str | None = None,
    creation_type: str | None = None,
) -> tuple[list[WritingRule], int]:
    """分页查询写作规范，支持按 rule_name 模糊搜索、creation_type 精确筛选。

    返回 (当前页记录列表, 总数)。
    """
    conditions = [WritingRule.is_deleted.is_(False)]
    if rule_name:
        conditions.append(WritingRule.rule_name.ilike(f"%{rule_name.strip()}%"))
    if creation_type:
        conditions.append(WritingRule.creation_type == creation_type)

    total = db.execute(
        select(func.count()).select_from(WritingRule).where(*conditions)
    ).scalar_one()

    stmt = (
        select(WritingRule)
        .where(*conditions)
        .order_by(WritingRule.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_writing_rule(db: Session, rule_id: int) -> WritingRule:
    """获取写作规范详情。"""
    return _get_active(db, rule_id)


def create_writing_rule(db: Session, payload: WritingRuleCreate) -> WritingRule:
    """新增写作规范。"""
    rule = WritingRule(
        rule_name=payload.rule_name,
        creation_type=payload.creation_type.value,
        instruction_content=payload.instruction_content,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_writing_rule(
    db: Session, rule_id: int, payload: WritingRuleUpdate
) -> WritingRule:
    """编辑写作规范。仅更新请求中显式提供的字段。"""
    rule = _get_active(db, rule_id)

    data = payload.model_dump(exclude_unset=True)
    if data.get("rule_name") is not None:
        rule.rule_name = data["rule_name"]
    if data.get("creation_type") is not None:
        # creation_type 为 StrEnum，统一以字符串值存储
        rule.creation_type = str(data["creation_type"])
    if data.get("instruction_content") is not None:
        rule.instruction_content = data["instruction_content"]

    db.commit()
    db.refresh(rule)
    return rule


def delete_writing_rule(db: Session, rule_id: int) -> None:
    """软删除写作规范。"""
    rule = _get_active(db, rule_id)
    rule.is_deleted = True
    rule.deleted_at = datetime.now()
    db.commit()
