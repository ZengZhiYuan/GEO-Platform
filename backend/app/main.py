"""后端入口。

启动：
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, new_request_id, request_id_var
from app.core.readiness import check_nacos_ready, check_platform_runtime_diagnostics, check_readiness
from app.core.response import success
from app.core.security import bind_request, reset_request_binding


# 从环境变量解析 CORS 允许的源列表（逗号分隔）
def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


# 为每个 HTTP 请求注入 request_id 并记录响应耗时
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 复用客户端传入的 X-Request-ID，否则生成新 ID
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        token = request_id_var.set(request_id)
        bind_request(request)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            reset_request_binding()
            request_id_var.reset(token)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response


# 创建并配置 FastAPI 应用实例（中间件、路由、探针）
def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.APP_DEBUG,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    allowed_origins = _parse_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=bool(allowed_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_PREFIX)
    _register_geo_monitoring_probes(app)

    return app


# 注册监测域专用的 health / ready 探针端点
def _register_geo_monitoring_probes(app: FastAPI) -> None:
    prefix = f"{settings.API_PREFIX}/geo-monitoring"

    # 轻量健康检查：仅返回应用名与环境，不探测依赖
    @app.get(f"{prefix}/health", summary="监测服务健康检查", tags=["AI 应用监测"])
    async def geo_monitoring_health() -> dict:
        return success(
            {
                "status": "ok",
                "app": settings.APP_NAME,
                "env": settings.APP_ENV,
            }
        )

    # 就绪检查：探测数据库、Redis，可选探测 Nacos
    @app.get(f"{prefix}/ready", summary="监测服务就绪检查", tags=["AI 应用监测"])
    async def geo_monitoring_ready() -> dict:
        from app.core.database import SessionLocal

        payload = check_readiness()
        with SessionLocal() as db:
            payload["platform_runtime"] = check_platform_runtime_diagnostics(db)
        # Nacos 启用时追加配置中心连通性探测
        if settings.NACOS_ENABLED:
            try:
                payload["nacos"] = check_nacos_ready(
                    enabled=True,
                    server_addresses=settings.NACOS_SERVER_ADDRESSES,
                    client_factory=lambda: _NacosReadyProbe(),
                )
            except Exception as exc:  # noqa: BLE001
                payload["nacos"] = {
                    "ok": False,
                    "enabled": True,
                    "target": settings.NACOS_SERVER_ADDRESSES,
                    "error": str(exc),
                }
                payload["status"] = "not_ready"
        status_code = 200 if payload.get("status") == "ready" else 503
        return JSONResponse(status_code=status_code, content=success(payload))


# Nacos 就绪探针占位实现（实际部署可替换为真实客户端）
class _NacosReadyProbe:
    def is_ready(self) -> bool:
        return True


app = create_app()
