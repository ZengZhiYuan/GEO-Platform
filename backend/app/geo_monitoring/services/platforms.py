"""AI 平台配置服务。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.schemas import AIPlatformUpdate


def get_platform(db: Session, platform_code: str) -> AIPlatform:
    platform = db.execute(
        select(AIPlatform).where(
            AIPlatform.platform_code == platform_code,
            AIPlatform.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if platform is None:
        raise BusinessException(message="AI 平台不存在", code=40400)
    return platform


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


def update_platform(
    db: Session, platform_code: str, payload: AIPlatformUpdate
) -> AIPlatform:
    platform = get_platform(db, platform_code)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(platform, field, value)
    db.commit()
    db.refresh(platform)
    return platform
