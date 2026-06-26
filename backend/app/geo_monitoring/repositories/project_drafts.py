"""创建向导草稿仓储。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import ProjectDraft


def get_by_id(db: Session, draft_id: int) -> ProjectDraft | None:
    return db.execute(
        select(ProjectDraft).where(
            ProjectDraft.id == draft_id,
            ProjectDraft.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def get_latest_by_draft_key(db: Session, draft_key: str) -> ProjectDraft | None:
    return db.execute(
        select(ProjectDraft)
        .where(
            ProjectDraft.draft_key == draft_key,
            ProjectDraft.is_deleted.is_(False),
        )
        .order_by(ProjectDraft.updated_at.desc(), ProjectDraft.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def add(db: Session, draft: ProjectDraft) -> None:
    db.add(draft)
