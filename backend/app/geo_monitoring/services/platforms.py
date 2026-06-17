"""AI 平台配置服务。"""

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.repositories import platforms as platform_repo
from app.geo_monitoring.schemas import AIPlatformUpdate

DEFAULT_PLATFORMS = (
    {
        "platform_code": "doubao",
        "platform_name": "豆包",
        "adapter_type": "openai_compatible",
    },
    {
        "platform_code": "qwen",
        "platform_name": "通义千问",
        "adapter_type": "openai_compatible",
    },
    {
        "platform_code": "yuanbao",
        "platform_name": "腾讯元宝",
        "adapter_type": "tencent",
    },
    {
        "platform_code": "deepseek",
        "platform_name": "DeepSeek",
        "adapter_type": "openai_compatible",
    },
    {
        "platform_code": "kimi",
        "platform_name": "Kimi",
        "adapter_type": "openai_compatible",
    },
)


def get_platform(db: Session, platform_code: str) -> AIPlatform:
    platform = platform_repo.get_by_code(db, platform_code)
    if platform is None:
        raise BusinessException(message="AI 平台不存在", code=40400)
    return platform


def list_platforms(
    db: Session,
    *,
    page: int,
    page_size: int,
    enabled: bool | None = None,
) -> tuple[list[AIPlatform], int]:
    return platform_repo.list_platforms(
        db, page=page, page_size=page_size, enabled=enabled
    )


def update_platform(
    db: Session, platform_code: str, payload: AIPlatformUpdate
) -> AIPlatform:
    platform = get_platform(db, platform_code)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(platform, field, value)
    db.commit()
    db.refresh(platform)
    return platform
