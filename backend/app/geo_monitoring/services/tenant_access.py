"""租户隔离与资源访问控制。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.security import get_current_auth
from app.geo_monitoring.repositories import projects as project_repo


def list_tenant_filter() -> int | None:
    auth = get_current_auth()
    if not auth.enabled:
        return None
    return auth.tenant_id


def ensure_tenant_access(
    resource_tenant_id: int | None,
    *,
    resource_label: str = "资源",
) -> None:
    auth = get_current_auth()
    if not auth.enabled:
        return
    if auth.tenant_id is None:
        raise BusinessException(message="未授权", code=40101, status_code=401)
    if resource_tenant_id is None or resource_tenant_id != auth.tenant_id:
        raise BusinessException(message=f"{resource_label}不存在", code=40400)


def stamp_tenant_fields(entity: object) -> None:
    auth = get_current_auth()
    if not auth.enabled or auth.tenant_id is None:
        return
    if hasattr(entity, "tenant_id"):
        entity.tenant_id = auth.tenant_id
    if auth.actor_id is not None:
        if hasattr(entity, "created_by"):
            entity.created_by = auth.actor_id
        if hasattr(entity, "updated_by"):
            entity.updated_by = auth.actor_id


def ensure_project_tenant_access(db: Session, project_id: int) -> None:
    project = project_repo.get_by_id(db, project_id)
    if project is None:
        raise BusinessException(message="监测项目不存在", code=40400)
    ensure_tenant_access(project.tenant_id, resource_label="监测项目")
