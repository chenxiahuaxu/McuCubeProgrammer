"""应用状态枚举 — 用于跟踪当前页面的操作阶段。"""

from enum import Enum, auto


class AppState(Enum):
    """应用全局状态。"""

    IDLE: int = auto()
    """空闲 — 等待用户操作。"""

    SCANNING: int = auto()
    """正在扫描探针。"""

    CONNECTING: int = auto()
    """正在连接目标芯片。"""

    ERASING: int = auto()
    """正在擦除 Flash。"""

    PROGRAMMING: int = auto()
    """正在烧录固件。"""

    VERIFYING: int = auto()
    """正在验证 Flash。"""

    CANCELLING: int = auto()
    """正在取消操作。"""

    ERROR: int = auto()
    """错误状态。"""
