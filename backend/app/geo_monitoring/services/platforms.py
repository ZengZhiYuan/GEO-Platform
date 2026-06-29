"""AI 平台配置服务。"""

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.geo_monitoring.models import AIPlatform
from app.geo_monitoring.repositories import platforms as platform_repo
from app.geo_monitoring.schemas import AIPlatformUpdate

OFFICIAL_PLATFORMS = (
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

AIDSO_PLATFORM_MAPPINGS = {
    "aidso_doubao_web": {"aidso_name": "DB", "platform_name": "豆包 Web 端"},
    "aidso_doubao_app": {"aidso_name": "DOUBA", "platform_name": "豆包 App 端"},
    "aidso_deepseek_web": {"aidso_name": "DP", "platform_name": "DeepSeek Web 端"},
    "aidso_deepseek_app": {"aidso_name": "DPA", "platform_name": "DeepSeek App 端"},
    "aidso_kimi_web": {"aidso_name": "KIMI", "platform_name": "Kimi Web 端"},
    "aidso_yuanbao_web": {"aidso_name": "TXYB", "platform_name": "元宝 Web 端"},
    "aidso_yuanbao_app": {"aidso_name": "TXYBA", "platform_name": "元宝 App 端"},
    "aidso_qwen_web": {"aidso_name": "TYQW", "platform_name": "千问 Web 端"},
    "aidso_qwen_app": {"aidso_name": "TYQWA", "platform_name": "千问 App 端"},
    "aidso_baidu_web": {"aidso_name": "BDAI", "platform_name": "百度 AI"},
    "aidso_douyin_web": {"aidso_name": "DYAI", "platform_name": "抖音 AI"},
    "aidso_wenxin_web": {"aidso_name": "WXYY", "platform_name": "文心一言"},
}

AIDSO_PLATFORMS = tuple(
    {
        "platform_code": code,
        "platform_name": item["platform_name"],
        "adapter_type": "aidso",
        "model_name": f"aidso:{item['aidso_name']}",
        "search_enabled": True,
        "citation_supported": True,
        "extra_config": {"aidso_name": item["aidso_name"]},
    }
    for code, item in AIDSO_PLATFORM_MAPPINGS.items()
)

_MOLIZHISHU_SEARCH_MODES = ("standard", "search")
_MOLIZHISHU_REASONING_SEARCH_MODES = ("standard", "reasoning", "search", "reasoning_search")

MOLIZHISHU_PLATFORM_MAPPINGS = {
    "molizhishu_deepseek_web": {
        "molizhishu_platform": "deepseek",
        "platform_name": "DeepSeek 网页端",
        "base_platform": "deepseek",
        "endpoint_type": "web",
        "default_mode": "reasoning_search",
        "supported_modes": _MOLIZHISHU_REASONING_SEARCH_MODES,
    },
    "molizhishu_deepseek_mobile": {
        "molizhishu_platform": "deepseek_mobile",
        "platform_name": "DeepSeek 手机端",
        "base_platform": "deepseek",
        "endpoint_type": "app",
        "default_mode": "reasoning_search",
        "supported_modes": _MOLIZHISHU_REASONING_SEARCH_MODES,
    },
    "molizhishu_doubao_web": {
        "molizhishu_platform": "doubao",
        "platform_name": "豆包网页端",
        "base_platform": "doubao",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_doubao_mobile": {
        "molizhishu_platform": "doubao_mobile",
        "platform_name": "豆包手机端",
        "base_platform": "doubao",
        "endpoint_type": "app",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_yuanbao_web": {
        "molizhishu_platform": "yuanbao",
        "platform_name": "腾讯元宝",
        "base_platform": "yuanbao",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_kimi_web": {
        "molizhishu_platform": "kimi",
        "platform_name": "Kimi",
        "base_platform": "kimi",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_qianwen_web": {
        "molizhishu_platform": "qianwen",
        "platform_name": "通义千问",
        "base_platform": "qianwen",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_quark_web": {
        "molizhishu_platform": "quark",
        "platform_name": "夸克 AI",
        "base_platform": "quark",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_baiduai_web": {
        "molizhishu_platform": "baiduai",
        "platform_name": "百度 AI+",
        "base_platform": "baiduai",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_weibo_zhisou_web": {
        "molizhishu_platform": "weibo_zhisou",
        "platform_name": "微博智搜",
        "base_platform": "weibo_zhisou",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
    "molizhishu_wenxinyiyan_web": {
        "molizhishu_platform": "wenxinyiyan",
        "platform_name": "文心一言",
        "base_platform": "wenxinyiyan",
        "endpoint_type": "web",
        "default_mode": "search",
        "supported_modes": _MOLIZHISHU_SEARCH_MODES,
    },
}

MOLIZHISHU_PLATFORMS = tuple(
    {
        "platform_code": code,
        "platform_name": item["platform_name"],
        "adapter_type": "molizhishu",
        "model_name": f"molizhishu:{item['molizhishu_platform']}",
        "search_enabled": True,
        "citation_supported": True,
        "extra_config": {
            "molizhishu_platform": item["molizhishu_platform"],
            "base_platform": item["base_platform"],
            "endpoint_type": item["endpoint_type"],
            "default_mode": item["default_mode"],
            "supported_modes": list(item["supported_modes"]),
        },
    }
    for code, item in MOLIZHISHU_PLATFORM_MAPPINGS.items()
)

DEFAULT_PLATFORMS = (*OFFICIAL_PLATFORMS, *MOLIZHISHU_PLATFORMS)


# 按平台编码查询 AI 平台，不存在则抛业务异常
def get_platform(db: Session, platform_code: str) -> AIPlatform:
    platform = platform_repo.get_by_code(db, platform_code)
    if platform is None:
        raise BusinessException(message="AI 平台不存在", code=40400)
    return platform


# 分页列出 AI 平台配置
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


# 更新 AI 平台配置字段
def update_platform(
    db: Session, platform_code: str, payload: AIPlatformUpdate
) -> AIPlatform:
    platform = get_platform(db, platform_code)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(platform, field, value)
    db.commit()
    db.refresh(platform)
    return platform
