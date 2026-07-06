"""统一日志工具 — 单例 Logger 与全局便捷函数 add_log()。

提供模块级的 add_log(level, message) 函数，
所有模块通过此函数输出日志，无需持有 Logger 实例。

日志级别: INFO / WARN / ERROR / DONE / DEBUG
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime


class LogEntry:  # pylint: disable=too-few-public-methods
    """单条日志记录。"""

    def __init__(self, level: str, message: str) -> None:
        self.timestamp: str = datetime.now().strftime("%H:%M:%S")
        self.level: str = level
        self.message: str = message

    def __repr__(self) -> str:
        return f"LogEntry(level={self.level!r}, message={self.message!r})"


class Logger:
    """全局日志单例。

    提供 add(level, message) 方法记录日志，并通过回调通知 UI 层。
    """

    _instance: "Logger | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "Logger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._entries: list[LogEntry] = []
                    obj._callback: Callable[[LogEntry], None] | None = None
                    cls._instance = obj
        return cls._instance

    def add(self, level: str, message: str) -> None:
        """记录一条日志。

        Args:
            level:   日志级别（INFO/WARN/ERROR/DONE/DEBUG）。
            message: 日志消息。
        """
        entry = LogEntry(level, message)
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > 1000:
                self._entries = self._entries[-500:]
        if self._callback:
            self._callback(entry)

    def set_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """设置日志回调（供 UI 的 LogView 注册使用）。

        Args:
            callback: 接收 LogEntry 的回调函数。
        """
        self._callback = callback

    def get_all(self) -> list[LogEntry]:
        """返回所有日志条目的副本。"""
        with self._lock:
            return self._entries.copy()

    def clear(self) -> None:
        """清空所有日志。"""
        with self._lock:
            self._entries.clear()


def add_log(level: str, message: str) -> None:
    """全局日志记录函数。

    所有模块通过此函数输出日志，自动路由到 Logger 单例。

    Args:
        level:   日志级别（INFO/WARN/ERROR/DONE/DEBUG）。
        message: 日志消息。
    """
    Logger().add(level, message)
