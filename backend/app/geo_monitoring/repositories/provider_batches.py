"""ProviderBatch 仓储。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import ProviderBatch, QueryTask


def add_batch(db: Session, batch: ProviderBatch) -> None:
    db.add(batch)


def get_by_id(db: Session, batch_id: int) -> ProviderBatch | None:
    return db.execute(
        select(ProviderBatch).where(
            ProviderBatch.id == batch_id,
            ProviderBatch.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def list_by_run_id(db: Session, run_id: int) -> list[ProviderBatch]:
    return list(
        db.execute(
            select(ProviderBatch)
            .where(
                ProviderBatch.run_id == run_id,
                ProviderBatch.is_deleted.is_(False),
            )
            .order_by(ProviderBatch.batch_no)
        )
        .scalars()
        .all()
    )


def list_tasks_for_batch(db: Session, batch_id: int) -> list[QueryTask]:
    return list(
        db.execute(
            select(QueryTask)
            .where(
                QueryTask.provider_batch_id == batch_id,
                QueryTask.is_deleted.is_(False),
            )
            .order_by(QueryTask.id)
        )
        .scalars()
        .all()
    )


def get_by_provider_task_id(
    db: Session,
    provider_task_id: str,
    *,
    provider_name: str = "molizhishu",
) -> ProviderBatch | None:
    normalized = provider_task_id.strip()
    if not normalized:
        return None
    return db.execute(
        select(ProviderBatch).where(
            ProviderBatch.provider_name == provider_name,
            ProviderBatch.provider_task_id == normalized,
            ProviderBatch.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
