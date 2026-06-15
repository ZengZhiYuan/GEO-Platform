"""Dramatiq Worker 启动入口。"""

from app.workers.broker import broker

__all__ = ["broker"]
