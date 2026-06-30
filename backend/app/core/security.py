"""API 鉴权上下文与 Bearer token 校验。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from app.core.config import get_settings

_AUTH_STATE_KEY = "auth_context"
_request_ctx: ContextVar[Request | None] = ContextVar("geo_api_request", default=None)


@dataclass(frozen=True)
class AuthContext:
    enabled: bool = False
    tenant_id: int | None = None
    actor_id: int | None = None

    @classmethod
    def anonymous(cls) -> AuthContext:
        return cls(enabled=False, tenant_id=None, actor_id=None)


def bind_request(request: Request) -> None:
    _request_ctx.set(request)


def reset_request_binding() -> None:
    _request_ctx.set(None)


def get_current_auth() -> AuthContext:
    request = _request_ctx.get()
    if request is not None:
        auth = getattr(request.state, _AUTH_STATE_KEY, None)
        if isinstance(auth, AuthContext):
            return auth
    return AuthContext.anonymous()


def _store_auth_context(request: Request, ctx: AuthContext) -> AuthContext:
    setattr(request.state, _AUTH_STATE_KEY, ctx)
    return ctx


def require_api_auth(
    request: Request,
    authorization: str | None = Header(None),
) -> AuthContext:
    """FastAPI 依赖：校验 Bearer token 并绑定租户上下文。"""
    settings = get_settings()
    if not settings.API_AUTH_ENABLED:
        return _store_auth_context(request, AuthContext.anonymous())

    if not authorization or not authorization.strip():
        raise HTTPException(status_code=401, detail="缺少 Authorization 请求头")

    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 必须为 Bearer token")

    token = raw_token.strip()
    if not token:
        raise HTTPException(status_code=401, detail="缺少 Bearer token")

    entry = settings.lookup_api_auth_token(token)
    if entry is None:
        raise HTTPException(status_code=401, detail="无效的 API token")

    actor_id = entry.actor_id if entry.actor_id is not None else entry.tenant_id
    return _store_auth_context(
        request,
        AuthContext(
            enabled=True,
            tenant_id=entry.tenant_id,
            actor_id=actor_id,
        ),
    )
