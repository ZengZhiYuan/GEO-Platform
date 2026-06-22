"""Prompt 词库服务。"""

from sqlalchemy.orm import Session

from app.geo_monitoring.models import PromptLibrary
from app.geo_monitoring.repositories import prompt_library as prompt_library_repo


def list_prompt_library(
    db: Session,
    *,
    page: int,
    page_size: int,
    industry: str | None = None,
) -> tuple[list[PromptLibrary], int]:
    prompt_library_repo.seed_defaults(db)
    return prompt_library_repo.list_entries(
        db,
        page=page,
        page_size=page_size,
        industry=industry,
    )


def get_library_entry_by_code(db: Session, prompt_code: str) -> PromptLibrary | None:
    prompt_library_repo.seed_defaults(db)
    return prompt_library_repo.get_by_code(db, prompt_code)
