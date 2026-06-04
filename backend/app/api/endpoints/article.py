"""文章清单 API Router。

路径前缀由 app/api/router.py include 时指定（最终为 /api/articles）。
所有接口返回统一响应格式：{"code": 0, "message": "success", "data": ...}

接口（见 docs/api-contract.md 文章清单）：
    GET  /api/articles             分页查询文章
    GET  /api/articles/{id}        获取文章详情
    PUT  /api/articles/{id}        编辑文章标题/封面图/正文
    POST /api/articles/{id}/status 切换文章状态
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginate, success
from app.schemas.article import (
    ArticleOut,
    ArticleStatus,
    ArticleStatusUpdate,
    ArticleUpdate,
)
from app.services import article as article_service

router = APIRouter(prefix="/articles", tags=["文章清单"])


@router.get("", summary="分页查询文章")
def list_articles(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    writing_task_id: int | None = Query(
        None, ge=1, description="按所属写作任务 ID 筛选"
    ),
    status: ArticleStatus | None = Query(None, description="按文章状态筛选"),
    article_title: str | None = Query(None, description="按文章标题模糊搜索"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = article_service.list_articles(
        db,
        page=page,
        page_size=page_size,
        writing_task_id=writing_task_id,
        status=status.value if status else None,
        article_title=article_title,
    )
    data = [
        ArticleOut.model_validate(item).model_dump(mode="json") for item in items
    ]
    return paginate(data, total=total, page=page, page_size=page_size)


@router.get("/{article_id}", summary="获取文章详情")
def get_article(
    article_id: int = Path(..., ge=1, description="文章 ID"),
    db: Session = Depends(get_db),
) -> dict:
    article = article_service.get_article(db, article_id)
    return success(ArticleOut.model_validate(article).model_dump(mode="json"))


@router.put("/{article_id}", summary="编辑文章标题/封面图/正文")
def update_article(
    payload: ArticleUpdate,
    article_id: int = Path(..., ge=1, description="文章 ID"),
    db: Session = Depends(get_db),
) -> dict:
    article = article_service.update_article(db, article_id, payload)
    return success(ArticleOut.model_validate(article).model_dump(mode="json"))


@router.post("/{article_id}/status", summary="切换文章状态")
def update_article_status(
    payload: ArticleStatusUpdate,
    article_id: int = Path(..., ge=1, description="文章 ID"),
    db: Session = Depends(get_db),
) -> dict:
    article = article_service.update_article_status(db, article_id, payload)
    return success(ArticleOut.model_validate(article).model_dump(mode="json"))
