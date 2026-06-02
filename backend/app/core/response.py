"""统一响应封装。

所有接口统一返回结构：
    {"code": 0, "message": "success", "data": {...}}

分页接口 data 统一为：
    {"items": [], "total": 0, "page": 1, "page_size": 10}
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应。"""
    return {"code": 0, "message": message, "data": data}


def fail(code: int = 1, message: str = "error", data: Any = None) -> dict:
    """失败响应。code 非 0 表示业务错误。"""
    return {"code": code, "message": message, "data": data}


def paginate(
    items: list,
    total: int,
    page: int = 1,
    page_size: int = 10,
    message: str = "success",
) -> dict:
    """分页响应。"""
    return success(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message=message,
    )


# 下列 Pydantic 模型用于在 OpenAPI/Swagger 中描述响应结构，可作为
# 接口 response_model 使用（非强制）。
class ResponseModel(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


class PageData(BaseModel, Generic[T]):
    items: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
