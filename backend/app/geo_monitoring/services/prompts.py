"""提示词集与提示词服务。"""

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import Prompt, PromptSet
from app.geo_monitoring.repositories import prompts as prompt_repo
from app.geo_monitoring.schemas import (
    PromptCreate,
    PromptSetCreate,
    PromptSetUpdate,
    PromptUpdate,
)
from app.geo_monitoring.services.projects import require_active_project


def _content_hash(prompt_text: str) -> str:
    return sha256(prompt_text.encode("utf-8")).hexdigest()


def _commit_unique(db: Session, *, code: int, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessException(message=message, code=code) from exc


def get_prompt_set(db: Session, prompt_set_id: int) -> PromptSet:
    prompt_set = prompt_repo.get_prompt_set_by_id(db, prompt_set_id)
    if prompt_set is None:
        raise BusinessException(message="提示词集不存在", code=40400)
    return prompt_set


def _require_draft(prompt_set: PromptSet) -> None:
    if prompt_set.status != "draft":
        raise BusinessException(message="只有草稿提示词集允许修改", code=40020)


def list_prompt_sets(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[PromptSet], int]:
    require_active_project(db, project_id)
    return prompt_repo.list_prompt_sets(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        status=status,
    )


def create_prompt_set(
    db: Session, project_id: int, payload: PromptSetCreate
) -> PromptSet:
    require_active_project(db, project_id)
    if (
        prompt_repo.find_duplicate_version(db, project_id, payload.version_no)
        is not None
    ):
        raise BusinessException(message="项目内提示词版本不能重复", code=40023)
    prompt_set = PromptSet(project_id=project_id, **payload.model_dump())
    prompt_repo.add_prompt_set(db, prompt_set)
    _commit_unique(db, code=40023, message="项目内提示词版本不能重复")
    db.refresh(prompt_set)
    return prompt_set


def update_prompt_set(
    db: Session, prompt_set_id: int, payload: PromptSetUpdate
) -> PromptSet:
    prompt_set = get_prompt_set(db, prompt_set_id)
    _require_draft(prompt_set)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prompt_set, field, value)
    db.commit()
    db.refresh(prompt_set)
    return prompt_set


def delete_prompt_set(db: Session, prompt_set_id: int) -> None:
    prompt_set = get_prompt_set(db, prompt_set_id)
    if prompt_repo.has_runs(db, prompt_set_id):
        raise BusinessException(
            message="提示词集已被监测运行引用，无法删除",
            code=40906,
            status_code=409,
        )
    _require_draft(prompt_set)
    prompt_set.is_deleted = True
    prompt_set.deleted_at = datetime.now(timezone.utc)
    db.commit()


def get_prompt(db: Session, prompt_id: int) -> Prompt:
    prompt = prompt_repo.get_prompt_by_id(db, prompt_id)
    if prompt is None:
        raise BusinessException(message="提示词不存在", code=40400)
    return prompt


def list_prompts(
    db: Session,
    *,
    prompt_set_id: int,
    page: int,
    page_size: int,
) -> tuple[list[Prompt], int]:
    get_prompt_set(db, prompt_set_id)
    return prompt_repo.list_prompts(
        db, prompt_set_id=prompt_set_id, page=page, page_size=page_size
    )


def create_prompt(
    db: Session, prompt_set_id: int, payload: PromptCreate
) -> Prompt:
    prompt_set = get_prompt_set(db, prompt_set_id)
    _require_draft(prompt_set)
    if (
        prompt_repo.find_duplicate_prompt_code(
            db, prompt_set_id, payload.prompt_code
        )
        is not None
    ):
        raise BusinessException(message="提示词编码不能重复", code=40021)
    data = payload.model_dump()
    prompt = Prompt(
        prompt_set_id=prompt_set_id,
        **data,
        content_hash=_content_hash(data["prompt_text"]),
    )
    prompt_repo.add_prompt(db, prompt)
    prompt_set.prompt_count += 1
    _commit_unique(db, code=40021, message="提示词编码不能重复")
    db.refresh(prompt)
    return prompt


def update_prompt(db: Session, prompt_id: int, payload: PromptUpdate) -> Prompt:
    prompt = get_prompt(db, prompt_id)
    prompt_set = get_prompt_set(db, prompt.prompt_set_id)
    _require_draft(prompt_set)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prompt, field, value)
    if payload.prompt_text is not None:
        prompt.content_hash = _content_hash(payload.prompt_text)
    _commit_unique(db, code=40021, message="提示词编码不能重复")
    db.refresh(prompt)
    return prompt


def delete_prompt(db: Session, prompt_id: int) -> None:
    prompt = get_prompt(db, prompt_id)
    prompt_set = get_prompt_set(db, prompt.prompt_set_id)
    _require_draft(prompt_set)
    if prompt_repo.has_query_tasks(db, prompt_id):
        raise BusinessException(
            message="提示词已被监测任务引用，无法删除",
            code=40907,
            status_code=409,
        )
    prompt.is_deleted = True
    prompt.deleted_at = datetime.now(timezone.utc)
    prompt_set.prompt_count = max(0, prompt_set.prompt_count - 1)
    db.commit()


def activate_prompt_set(db: Session, prompt_set_id: int) -> PromptSet:
    prompt_set = get_prompt_set(db, prompt_set_id)
    _require_draft(prompt_set)
    prompts = prompt_repo.list_prompts_for_activation(db, prompt_set_id)
    if not prompts:
        raise BusinessException(message="空提示词集不能激活", code=40022)

    previous = prompt_repo.find_active_prompt_set(
        db, prompt_set.project_id, exclude_id=prompt_set.id
    )
    if previous is not None:
        previous.status = "archived"

    checksum_source = "\n".join(
        f"{item.prompt_code}:{item.content_hash}:{item.enabled}:{item.sort_order}"
        for item in prompts
    )
    prompt_set.checksum = sha256(checksum_source.encode("utf-8")).hexdigest()
    prompt_set.status = "active"
    prompt_set.activated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(prompt_set)
    return prompt_set
