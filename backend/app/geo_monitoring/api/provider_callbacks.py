"""第三方采集 provider 回调接口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.response import fail, success
from app.geo_monitoring.services import collection as collection_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/provider-callbacks", tags=["Provider Callbacks"])


def _resolve_callback_token(
    header_token: str | None,
    query_token: str | None,
) -> str | None:
    if header_token and header_token.strip():
        return header_token.strip()
    if query_token and query_token.strip():
        return query_token.strip()
    return None


def _validate_molizhishu_callback_token(token: str | None) -> None:
    expected = settings.MOLIZHISHU_CALLBACK_TOKEN.strip()
    if not expected:
        logger.warning("molizhishu callback rejected: callback token not configured")
        raise HTTPException(status_code=503, detail="callback token is not configured")
    if token != expected:
        logger.warning("molizhishu callback rejected: invalid token")
        raise HTTPException(status_code=401, detail="invalid callback token")


@router.post("/molizhishu", summary="模力指数采集结果回调")
def molizhishu_callback(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    x_callback_token: str | None = Header(None, alias="X-Callback-Token"),
    token: str | None = Query(None),
) -> dict:
    """接收模力指数子任务完成回调，作为轮询补充并保证幂等入库。"""
    callback_token = _resolve_callback_token(x_callback_token, token)
    _validate_molizhishu_callback_token(callback_token)

    try:
        result = collection_service.handle_molizhishu_callback(db, payload)
    except Exception:
        logger.exception("molizhishu callback handler failed")
        return fail(code=50001, message="callback processing failed")

    if result.outcome == "invalid_payload":
        return fail(code=42201, message=result.message or "invalid callback payload")
    if result.outcome == "task_not_found":
        return fail(code=40401, message="query task not found")

    return success(
        {
            "outcome": result.outcome,
            "task_id": result.task_id,
            "message": result.message,
        }
    )
