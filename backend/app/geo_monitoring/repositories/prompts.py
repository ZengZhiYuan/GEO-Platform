"""提示词仓储。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import MonitorRun, Prompt, PromptSet, QueryTask


def get_prompt_set_by_id(db: Session, prompt_set_id: int) -> PromptSet | None:
    return db.execute(
        select(PromptSet).where(
            PromptSet.id == prompt_set_id,
            PromptSet.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def list_prompt_sets(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[PromptSet], int]:
    conditions = [
        PromptSet.project_id == project_id,
        PromptSet.is_deleted.is_(False),
    ]
    if status:
        conditions.append(PromptSet.status == status)
    total = db.execute(
        select(func.count()).select_from(PromptSet).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(PromptSet)
            .where(*conditions)
            .order_by(PromptSet.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def find_duplicate_version(
    db: Session, project_id: int, version_no: str
) -> int | None:
    return db.execute(
        select(PromptSet.id).where(
            PromptSet.project_id == project_id,
            PromptSet.version_no == version_no,
            PromptSet.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def find_active_prompt_set(
    db: Session, project_id: int, *, exclude_id: int | None = None
) -> PromptSet | None:
    conditions = [
        PromptSet.project_id == project_id,
        PromptSet.status == "active",
        PromptSet.is_deleted.is_(False),
    ]
    if exclude_id is not None:
        conditions.append(PromptSet.id != exclude_id)
    return db.execute(select(PromptSet).where(*conditions)).scalar_one_or_none()


def resolve_active_prompt_set(
    db: Session, project_id: int, prompt_set_id: int | None
) -> PromptSet | None:
    conditions = [
        PromptSet.project_id == project_id,
        PromptSet.status == "active",
        PromptSet.is_deleted.is_(False),
    ]
    if prompt_set_id is not None:
        conditions.append(PromptSet.id == prompt_set_id)
    return db.execute(select(PromptSet).where(*conditions)).scalar_one_or_none()


def list_enabled_prompts(db: Session, prompt_set_id: int) -> list[Prompt]:
    return list(
        db.execute(
            select(Prompt)
            .where(
                Prompt.prompt_set_id == prompt_set_id,
                Prompt.enabled.is_(True),
                Prompt.is_deleted.is_(False),
            )
            .order_by(Prompt.sort_order, Prompt.id)
        )
        .scalars()
        .all()
    )


def list_prompts_for_activation(db: Session, prompt_set_id: int) -> list[Prompt]:
    return list(
        db.execute(
            select(Prompt)
            .where(
                Prompt.prompt_set_id == prompt_set_id,
                Prompt.is_deleted.is_(False),
                Prompt.enabled.is_(True),
            )
            .order_by(Prompt.prompt_code, Prompt.id)
        )
        .scalars()
        .all()
    )


def get_prompt_by_id(db: Session, prompt_id: int) -> Prompt | None:
    return db.execute(
        select(Prompt).where(Prompt.id == prompt_id, Prompt.is_deleted.is_(False))
    ).scalar_one_or_none()


def list_prompts(
    db: Session, *, prompt_set_id: int, page: int, page_size: int
) -> tuple[list[Prompt], int]:
    conditions = [
        Prompt.prompt_set_id == prompt_set_id,
        Prompt.is_deleted.is_(False),
    ]
    total = db.execute(
        select(func.count()).select_from(Prompt).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(Prompt)
            .where(*conditions)
            .order_by(Prompt.sort_order, Prompt.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def find_duplicate_prompt_code(
    db: Session, prompt_set_id: int, prompt_code: str
) -> int | None:
    return db.execute(
        select(Prompt.id).where(
            Prompt.prompt_set_id == prompt_set_id,
            Prompt.prompt_code == prompt_code,
            Prompt.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


def add_prompt_set(db: Session, prompt_set: PromptSet) -> None:
    db.add(prompt_set)


def add_prompt(db: Session, prompt: Prompt) -> None:
    db.add(prompt)


def has_runs(db: Session, prompt_set_id: int) -> bool:
    return (
        db.execute(
            select(MonitorRun.id).where(
                MonitorRun.prompt_set_id == prompt_set_id,
                MonitorRun.is_deleted.is_(False),
            )
        ).first()
        is not None
    )


def has_query_tasks(db: Session, prompt_id: int) -> bool:
    return (
        db.execute(
            select(QueryTask.id).where(
                QueryTask.prompt_id == prompt_id,
                QueryTask.is_deleted.is_(False),
            )
        ).first()
        is not None
    )
