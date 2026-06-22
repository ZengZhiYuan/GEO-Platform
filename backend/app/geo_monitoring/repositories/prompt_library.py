"""Prompt 词库仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import PromptLibrary


def list_entries(
    db: Session,
    *,
    page: int,
    page_size: int,
    industry: str | None = None,
    enabled: bool | None = True,
) -> tuple[list[PromptLibrary], int]:
    conditions = [PromptLibrary.is_deleted.is_(False)]
    if enabled is not None:
        conditions.append(PromptLibrary.enabled.is_(enabled))
    if industry:
        conditions.append(PromptLibrary.industry == industry.strip())
    total = db.execute(
        select(func.count()).select_from(PromptLibrary).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(PromptLibrary)
            .where(*conditions)
            .order_by(PromptLibrary.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def get_by_code(db: Session, prompt_code: str) -> PromptLibrary | None:
    return db.execute(
        select(PromptLibrary).where(
            PromptLibrary.prompt_code == prompt_code,
            PromptLibrary.is_deleted.is_(False),
            PromptLibrary.enabled.is_(True),
        )
    ).scalar_one_or_none()


def seed_defaults(db: Session) -> None:
    existing = db.execute(select(func.count()).select_from(PromptLibrary)).scalar_one()
    if existing:
        return
    defaults = [
        PromptLibrary(
            prompt_code="LIB_RECOMMEND_001",
            prompt_text="推荐国内有哪些值得看的文旅演艺项目？",
            prompt_type="recommendation",
            industry="文旅演艺",
            scene_tag="推荐",
            default_core_keyword="文旅演艺",
        ),
        PromptLibrary(
            prompt_code="LIB_COMPARE_001",
            prompt_text="宋城演艺和只有河南·戏剧幻城哪个更值得看？",
            prompt_type="comparison",
            industry="文旅演艺",
            scene_tag="对比",
            default_core_keyword="文旅演艺",
        ),
        PromptLibrary(
            prompt_code="LIB_VISIBILITY_001",
            prompt_text="介绍一下只有河南·戏剧幻城这个品牌。",
            prompt_type="brand_visibility",
            industry="文旅演艺",
            scene_tag="品牌认知",
            default_core_keyword="只有河南",
        ),
    ]
    for item in defaults:
        db.add(item)
    db.commit()
