"""
MCU Cube Programmer — 统一错误码定义

错误码分段规则：
- 1xxx: 探针相关错误
- 2xxx: 目标连接相关错误
- 3xxx: Flash 操作相关错误
- 4xxx: 文件相关错误
- 5xxx: 用户交互相关错误
- 6xxx: Pack 相关错误
- 9xxx: 系统/未知错误
"""

from enum import Enum


class ErrorCode(Enum):
    """统一错误码枚举。

    每个成员是一个 (code, description) 元组：
    - code:     整数错误码
    - description: 中文错误描述
    """

    # ── 成功 ──────────────────────────────────────────────
    OK = (0, "操作成功")

    # ── 探针相关 (1xxx) ───────────────────────────────────
    PROBE_NOT_FOUND = (1001, "未检测到调试探针，请检查连接")
    PROBE_CONNECT_FAILED = (1002, "探针连接失败")

    # ── 目标连接相关 (2xxx) ────────────────────────────────
    TARGET_NOT_FOUND = (2001, "未识别到目标芯片")
    TARGET_CONNECT_FAILED = (2002, "目标芯片连接失败")
    TARGET_NOT_SUPPORTED = (2003, "不支持的芯片型号，请安装对应 CMSIS-Pack")

    # ── Flash 操作相关 (3xxx) ──────────────────────────────
    ERASE_FAILED = (3001, "Flash 擦除失败")
    PROGRAM_FAILED = (3002, "Flash 烧录失败")
    VERIFY_FAILED = (3003, "Flash 验证失败，数据不一致")

    # ── 文件相关 (4xxx) ────────────────────────────────────
    FILE_NOT_FOUND = (4001, "固件文件不存在")
    FILE_FORMAT_UNSUPPORTED = (4002, "不支持的固件文件格式，请使用 .bin/.hex/.elf")
    FLASH_SIZE_EXCEEDED = (4003, "固件大小超出芯片 Flash 容量")

    # ── 用户交互相关 (5xxx) ────────────────────────────────
    OPERATION_CANCELLED = (5001, "操作已取消")

    # ── Pack 相关 (6xxx) ───────────────────────────────────
    PACK_INSTALL_FAILED = (6001, "CMSIS-Pack 安装失败")

    # ── 未知错误 ───────────────────────────────────────────
    UNKNOWN_ERROR = (9999, "未知错误")

    # ───────────────────────────────────────────────────────
    # 辅助方法
    # ───────────────────────────────────────────────────────

    @property
    def code(self) -> int:
        """返回整数错误码。"""
        return self.value[0]

    @property
    def description(self) -> str:
        """返回中文错误描述。"""
        return self.value[1]

    def __str__(self) -> str:
        """格式化为 "[CODE] 描述" 的字符串。"""
        return f"[{self.code}] {self.description}"


class BackendError(Exception):
    """后端统一异常，携带 ErrorCode。

    Attributes:
        error_code: ErrorCode 枚举成员
        detail:     附加的详细错误信息（可选），用于异常链或 pyOCD 原始消息
    """

    def __init__(self, error_code: ErrorCode, detail: str = "") -> None:
        self.error_code = error_code
        self.detail = detail
        super().__init__(format_error(error_code, detail))


def format_error(error_code: ErrorCode, detail: str = "") -> str:
    """将 ErrorCode 和可选详情拼接为面向用户的错误字符串。

    Args:
        error_code: ErrorCode 枚举成员
        detail:     附加详情（如异常原文或调试信息）

    Returns:
        格式化后的错误字符串，形如 "[1002] 探针连接失败: ST-Link firmware error"
    """
    if detail:
        return f"{error_code}: {detail}"
    return str(error_code)
