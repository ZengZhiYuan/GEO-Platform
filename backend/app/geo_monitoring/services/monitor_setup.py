"""品牌诊断/监控统一设置服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import (
    Brand,
    BrandAlias,
    CoreKeyword,
    MonitorProject,
    Prompt,
    PromptSet,
)
from app.geo_monitoring.repositories import brands as brand_repo
from app.geo_monitoring.repositories import core_keywords as core_keyword_repo
from app.geo_monitoring.repositories import prompts as prompt_repo
from app.geo_monitoring.schemas import MonitorSetupSave
from app.geo_monitoring.services import platforms as platform_service
from app.geo_monitoring.services import prompt_library as prompt_library_service
from app.geo_monitoring.services.brands import _ensure_target_available
from app.geo_monitoring.services.prompt_type_inference import infer_prompt_type
from app.geo_monitoring.services.prompts import activate_prompt_set
from app.geo_monitoring.services.projects import require_active_project


def _content_hash(prompt_text: str) -> str:
    return sha256(prompt_text.encode("utf-8")).hexdigest()


def _normalize_words(words: list[str]) -> list[str]:
    return list(dict.fromkeys(word.strip() for word in words if word.strip()))


def _brand_aliases(db: Session, brand_id: int) -> list[str]:
    aliases, _ = brand_repo.list_aliases(db, brand_id=brand_id, page=1, page_size=500)
    ordered = sorted(
        (alias for alias in aliases if alias.enabled),
        key=lambda item: item.id,
    )
    return [alias.alias_name for alias in ordered]


def _sync_aliases(db: Session, brand_id: int, words: list[str]) -> None:
    existing, _ = brand_repo.list_aliases(db, brand_id=brand_id, page=1, page_size=500)
    existing_by_name = {alias.alias_name: alias for alias in existing}
    desired = _normalize_words(words)
    for alias in existing:
        if alias.alias_name not in desired and not alias.is_deleted:
            alias.is_deleted = True
            alias.deleted_at = datetime.now(timezone.utc)
    for word in desired:
        alias = existing_by_name.get(word)
        if alias is None:
            brand_repo.add_alias(
                db,
                BrandAlias(brand_id=brand_id, alias_name=word, match_mode="contains"),
            )
        else:
            alias.is_deleted = False
            alias.deleted_at = None
            alias.enabled = True


def _get_target_brand(db: Session, project_id: int) -> Brand | None:
    brand_id = brand_repo.find_target_brand_id(db, project_id)
    if brand_id is None:
        return None
    return brand_repo.get_by_id(db, brand_id)


def _list_competitor_brands(db: Session, project_id: int) -> list[Brand]:
    items, _ = brand_repo.list_brands(
        db,
        project_id=project_id,
        page=1,
        page_size=500,
        brand_type="competitor",
    )
    return items


def _get_draft_prompt_set(db: Session, project_id: int) -> PromptSet | None:
    items, _ = prompt_repo.list_prompt_sets(
        db, project_id=project_id, page=1, page_size=100, status="draft"
    )
    return items[0] if items else None


def _get_active_prompt_set(db: Session, project_id: int) -> PromptSet | None:
    return prompt_repo.find_active_prompt_set(db, project_id)


def _serialize_brand(db: Session, brand: Brand) -> dict:
    return {
        "id": brand.id,
        "brand_name": brand.brand_name,
        "official_domain": brand.official_domain,
        "description": brand.description,
        "brand_words": _brand_aliases(db, brand.id),
    }


def _serialize_competitor(db: Session, brand: Brand) -> dict:
    return {
        "id": brand.id,
        "brand_name": brand.brand_name,
        "competitor_words": _brand_aliases(db, brand.id),
    }


def _serialize_ai_questions(db: Session, prompt_set_id: int) -> list[dict]:
    prompts, _ = prompt_repo.list_prompts(
        db, prompt_set_id=prompt_set_id, page=1, page_size=500
    )
    keyword_map: dict[int, str] = {}
    if prompts:
        keyword_ids = {prompt.core_keyword_id for prompt in prompts if prompt.core_keyword_id}
        if keyword_ids:
            rows = list(
                db.execute(
                    select(CoreKeyword).where(
                        CoreKeyword.id.in_(keyword_ids),
                        CoreKeyword.is_deleted.is_(False),
                    )
                )
                .scalars()
                .all()
            )
            keyword_map = {row.id: row.keyword for row in rows}
    result: list[dict] = []
    for prompt in prompts:
        core_keyword = keyword_map.get(prompt.core_keyword_id or -1)
        result.append(
            {
                "prompt_id": prompt.id,
                "prompt_code": prompt.prompt_code,
                "prompt_text": prompt.prompt_text,
                "prompt_type": prompt.prompt_type,
                "core_keyword": core_keyword,
                "core_keyword_id": prompt.core_keyword_id,
                "from_library": prompt.prompt_code.startswith("LIB_"),
            }
        )
    return result


def get_monitor_setup(db: Session, project_id: int) -> dict:
    project = require_active_project(db, project_id)
    target = _get_target_brand(db, project_id)
    competitors = _list_competitor_brands(db, project_id)
    keywords = core_keyword_repo.list_all_for_project(db, project_id)
    active_prompt_set = _get_active_prompt_set(db, project_id)
    draft_prompt_set = _get_draft_prompt_set(db, project_id)
    prompt_set = draft_prompt_set or active_prompt_set
    ai_questions = (
        _serialize_ai_questions(db, prompt_set.id) if prompt_set is not None else []
    )
    available, _ = platform_service.list_platforms(
        db, page=1, page_size=100, enabled=True
    )
    return {
        "brand": _serialize_brand(db, target) if target else None,
        "competitors": [_serialize_competitor(db, item) for item in competitors],
        "core_keywords": [
            {
                "id": item.id,
                "keyword": item.keyword,
                "description": item.description,
                "sort_order": item.sort_order,
                "enabled": item.enabled,
            }
            for item in keywords
        ],
        "ai_questions": ai_questions,
        "available_platforms": [
            {
                "platform_code": item.platform_code,
                "platform_name": item.platform_name,
                "enabled": item.enabled,
            }
            for item in available
        ],
        "selected_platform_codes": list(project.default_platform_codes or []),
        "draft_prompt_set_id": draft_prompt_set.id if draft_prompt_set else None,
        "active_prompt_set_id": active_prompt_set.id if active_prompt_set else None,
    }


def _validate_platform_codes(db: Session, platform_codes: list[str]) -> list[str]:
    if not platform_codes:
        return []
    available, _ = platform_service.list_platforms(
        db, page=1, page_size=100, enabled=True
    )
    allowed = {item.platform_code for item in available}
    invalid = [code for code in platform_codes if code not in allowed]
    if invalid:
        raise BusinessException(
            message=f"平台不可用: {', '.join(invalid)}",
            code=40025,
        )
    return platform_codes


def _upsert_target_brand(db: Session, project_id: int, payload) -> Brand:
    brand_payload = payload.brand
    target = _get_target_brand(db, project_id)
    if target is None:
        _ensure_target_available(db, project_id)
        target = Brand(
            project_id=project_id,
            brand_name=brand_payload.brand_name,
            brand_type="target",
            official_domain=brand_payload.official_domain,
            description=brand_payload.description,
        )
        brand_repo.add(db, target)
        db.flush()
    else:
        target.brand_name = brand_payload.brand_name
        target.official_domain = brand_payload.official_domain
        target.description = brand_payload.description
    _sync_aliases(db, target.id, brand_payload.brand_words)
    return target


def _replace_competitors(db: Session, project_id: int, payload) -> list[Brand]:
    existing = _list_competitor_brands(db, project_id)
    desired_names = {item.brand_name for item in payload.competitors}
    for brand in existing:
        if brand.brand_name not in desired_names:
            brand.is_deleted = True
            brand.deleted_at = datetime.now(timezone.utc)
    existing_by_name = {brand.brand_name: brand for brand in existing}
    saved: list[Brand] = []
    for item in payload.competitors:
        brand = existing_by_name.get(item.brand_name)
        if brand is None:
            if (
                brand_repo.find_duplicate_name(db, project_id, item.brand_name)
                is not None
            ):
                raise BusinessException(message="项目内品牌名称不能重复", code=40012)
            brand = Brand(
                project_id=project_id,
                brand_name=item.brand_name,
                brand_type="competitor",
            )
            brand_repo.add(db, brand)
            db.flush()
        else:
            brand.is_deleted = False
            brand.deleted_at = None
            brand.brand_type = "competitor"
        _sync_aliases(db, brand.id, item.competitor_words)
        saved.append(brand)
    return saved


def _replace_core_keywords(db: Session, project_id: int, payload) -> list[CoreKeyword]:
    existing = core_keyword_repo.list_all_for_project(db, project_id)
    desired = {item.keyword: item for item in payload.core_keywords}
    for keyword in existing:
        if keyword.keyword not in desired:
            keyword.is_deleted = True
            keyword.deleted_at = datetime.now(timezone.utc)
    existing_by_name = {keyword.keyword: keyword for keyword in existing}
    saved: list[CoreKeyword] = []
    for item in payload.core_keywords:
        keyword = existing_by_name.get(item.keyword)
        if keyword is None:
            keyword = CoreKeyword(
                project_id=project_id,
                keyword=item.keyword,
                description=item.description,
                sort_order=item.sort_order,
                enabled=item.enabled,
            )
            core_keyword_repo.add(db, keyword)
            db.flush()
        else:
            keyword.is_deleted = False
            keyword.deleted_at = None
            keyword.description = item.description
            keyword.sort_order = item.sort_order
            keyword.enabled = item.enabled
        saved.append(keyword)
    return saved


def _ensure_draft_prompt_set(db: Session, project_id: int) -> PromptSet:
    prompt_set = _get_draft_prompt_set(db, project_id)
    if prompt_set is not None:
        return prompt_set
    version_no = f"setup-{uuid4().hex[:8]}"
    prompt_set = PromptSet(
        project_id=project_id,
        set_name="监测设置问题集",
        version_no=version_no,
        status="draft",
    )
    prompt_repo.add_prompt_set(db, prompt_set)
    db.flush()
    return prompt_set


def _replace_ai_questions(
    db: Session,
    *,
    project_id: int,
    prompt_set: PromptSet,
    payload,
    target_brand: Brand,
    keyword_by_name: dict[str, CoreKeyword],
) -> None:
    existing, _ = prompt_repo.list_prompts(
        db, prompt_set_id=prompt_set.id, page=1, page_size=500
    )
    for prompt in existing:
        prompt.is_deleted = True
        prompt.deleted_at = datetime.now(timezone.utc)
    prompt_set.prompt_count = 0

    for index, item in enumerate(payload.ai_questions, start=1):
        prompt_text = item.prompt_text
        prompt_type = item.prompt_type
        core_keyword_name = item.core_keyword
        library_code = item.library_prompt_code
        if library_code:
            library_entry = prompt_library_service.get_library_entry_by_code(
                db, library_code
            )
            if library_entry is None:
                raise BusinessException(message="Prompt 词库条目不存在", code=40400)
            prompt_text = library_entry.prompt_text
            prompt_type = library_entry.prompt_type
            core_keyword_name = (
                core_keyword_name or library_entry.default_core_keyword
            )
        if not prompt_text:
            raise BusinessException(message="AI 问题文本不能为空", code=40026)
        keyword = keyword_by_name.get(core_keyword_name or "")
        if core_keyword_name and keyword is None:
            raise BusinessException(
                message=f"核心词不存在: {core_keyword_name}",
                code=40027,
            )
        inferred_type = infer_prompt_type(
            prompt_text,
            brand_name=target_brand.brand_name,
            core_keyword=core_keyword_name,
        )
        final_type = prompt_type or inferred_type
        prompt_code = item.prompt_code or library_code or f"Q{index:03d}"
        prompt = Prompt(
            prompt_set_id=prompt_set.id,
            prompt_code=prompt_code,
            prompt_text=prompt_text.strip(),
            prompt_type=final_type,
            core_keyword_id=keyword.id if keyword else None,
            contains_brand=target_brand.brand_name in prompt_text,
            sort_order=index * 10,
            content_hash=_content_hash(prompt_text.strip()),
        )
        prompt_repo.add_prompt(db, prompt)
        prompt_set.prompt_count += 1


def persist_monitor_setup(
    db: Session, project: MonitorProject, payload: MonitorSetupSave
) -> PromptSet:
    if payload.brand is None:
        raise BusinessException(message="品牌设置不能为空", code=40028)
    selected_platform_codes = _validate_platform_codes(
        db, payload.selected_platform_codes
    )
    target = _upsert_target_brand(db, project.id, payload)
    _replace_competitors(db, project.id, payload)
    keywords = _replace_core_keywords(db, project.id, payload)
    keyword_by_name = {item.keyword: item for item in keywords}
    prompt_set = _ensure_draft_prompt_set(db, project.id)
    if payload.ai_questions:
        _replace_ai_questions(
            db,
            project_id=project.id,
            prompt_set=prompt_set,
            payload=payload,
            target_brand=target,
            keyword_by_name=keyword_by_name,
        )
    project.default_platform_codes = selected_platform_codes
    if payload.brand.official_domain:
        project.official_domain = payload.brand.official_domain
    return prompt_set


def save_monitor_setup(db: Session, project_id: int, payload: MonitorSetupSave) -> dict:
    project = require_active_project(db, project_id)
    try:
        prompt_set = persist_monitor_setup(db, project, payload)
        db.commit()
        if payload.activate_prompt_set and prompt_set.prompt_count > 0:
            activate_prompt_set(db, prompt_set.id)
    except BusinessException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return get_monitor_setup(db, project_id)
