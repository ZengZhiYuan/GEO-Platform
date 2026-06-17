"""AI 平台仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import AIPlatform


def get_by_code(db: Session, platform_code: str) -> AIPlatform | None:
    return db.execute(
        select(AIPlatform).where(
            AIPlatform.platform_code == platform_code,
            AIPlatform.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def list_platforms(
    db: Session,
    *,
    page: int,
    page_size: int,
    enabled: bool | None = None,
) -> tuple[list[AIPlatform], int]:
    conditions = [AIPlatform.is_deleted.is_(False)]
    if enabled is not None:
        conditions.append(AIPlatform.enabled.is_(enabled))
    total = db.execute(
        select(func.count()).select_from(AIPlatform).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(AIPlatform)
            .where(*conditions)
            .order_by(AIPlatform.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def list_candidates(
    db: Session, platform_codes: list[str] | None
) -> list[AIPlatform]:
    conditions = [AIPlatform.is_deleted.is_(False)]
    if platform_codes is not None:
        conditions.append(AIPlatform.platform_code.in_(platform_codes))
    return list(db.execute(select(AIPlatform).where(*conditions)).scalars().all())
