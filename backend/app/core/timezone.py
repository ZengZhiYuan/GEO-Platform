"""进程级时区初始化。"""

from __future__ import annotations

import logging
import os
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_APP_TIMEZONE = "Asia/Shanghai"


def validate_timezone_name(tz_name: str) -> str:
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"timezone is invalid: {tz_name}") from exc
    return tz_name


def configure_process_timezone(tz_name: str) -> ZoneInfo:
    """声明并应用进程默认时区（Linux 下同步 TZ 环境变量）。"""
    validate_timezone_name(tz_name)
    os.environ["TZ"] = tz_name
    if hasattr(time, "tzset"):
        time.tzset()
    logger.info("application timezone configured: %s", tz_name)
    return ZoneInfo(tz_name)
