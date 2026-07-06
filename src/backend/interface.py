"""
MCU Cube Programmer — 后端抽象接口

定义所有后端实现必须遵守的契约。新增后端（如 OpenOCD、J-Link 直连）
只需继承 BackendABC 并实现所有抽象方法。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from .error_codes import ErrorCode


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════


@dataclass
class ProbeInfo:
    """调试探针信息。

    表示一个已连接到主机的调试探针（物理设备）。
    """

    name: str
    """探针名称，例如 "ST-Link/V2-1"。"""

    unique_id: str
    """探针唯一标识符，例如 "E6616407E3646B29"。"""

    probe_type: str
    """探针类型：``"stlink"`` | ``"cmsisdap"`` | ``"jlink"`` | ``"unknown"``。"""

    vendor_name: str
    """制造商名称，例如 "STMicroelectronics"。"""

    product_name: str
    """产品名称，例如 "STM32 STLink"。"""

    description: str
    """完整描述字符串（来自 USB 描述符）。"""


@dataclass
class FlashRegion:
    """Flash 存储区域信息。

    一片连续的 Flash 地址空间。一个芯片可能包含多个 Flash 区域
    （如内部 Flash + 外部 QSPI Flash）。
    """

    name: str
    """区域名称，例如 "Internal Flash"。"""

    start: int
    """起始地址（字节）。"""

    length: int
    """区域大小（字节）。"""

    sector_size: int
    """扇区大小（字节），即最小擦除单元。"""

    access: str
    """访问权限字符串，例如 ``"rwx"``。"""


@dataclass
class TargetInfo:
    """目标芯片信息。

    连接成功后由后端返回，包含芯片的完整存储布局。
    上层模块据此判断固件是否适配、Flash 容量是否足够等。
    """

    name: str
    """目标名称，例如 "stm32l475xg"。"""

    part_number: str
    """完整料号，例如 "STM32L475VGTx"。"""

    vendor: str
    """制造商，例如 "STMicroelectronics" 或 "GigaDevice"。"""

    flash_regions: list[FlashRegion] = field(default_factory=list)
    """所有 Flash 区域列表。"""

    ram_regions: list[FlashRegion] = field(default_factory=list)
    """所有 RAM 区域列表（可能有多个不连续的 RAM 块）。"""

    ram_start: int = 0
    """主 RAM 起始地址（首个 RAM 区域）。"""

    ram_size: int = 0
    """所有 RAM 区域总容量（字节）。"""

    @property
    def total_flash_size(self) -> int:
        """所有 Flash 区域的总容量（字节）。"""
        return sum(r.length for r in self.flash_regions)

    @property
    def flash_start(self) -> int:
        """第一个 Flash 区域的起始地址（通常即固件烧录基址）。"""
        if not self.flash_regions:
            return 0
        return self.flash_regions[0].start

    @property
    def total_ram_size(self) -> int:
        """所有 RAM 区域的总容量。"""
        return sum(r.length for r in self.ram_regions)


@dataclass
class FlashResult:
    """烧录/验证操作的汇总结果。

    注意：操作过程中抛出的异常通过 ``BackendError`` 传递，
    本结构仅用于记录成功完成后的统计信息。
    """

    success: bool
    """操作是否成功。"""

    error_code: ErrorCode
    """结果码（成功时为 ``ErrorCode.OK``）。"""

    message: str
    """面向用户的结果描述。"""

    duration_seconds: float
    """操作耗时（秒）。"""


# ═══════════════════════════════════════════════════════════
# 抽象基类
# ═══════════════════════════════════════════════════════════


class BackendABC(ABC):
    """MCU 烧录后端抽象基类。

    所有后端实现（pyOCD、OpenOCD、J-Link 等）必须继承此类并实现
    全部抽象方法。上层业务逻辑只依赖此接口，不感知具体后端。

    Usage::

        backend = PyOCDBackend()
        probes = backend.list_probes()
        info = backend.connect("stm32f407vg", probe_uid=probes[0].unique_id)
        backend.erase_chip()
        backend.program("firmware.bin", progress_callback=on_progress)
        backend.verify("firmware.bin")
        backend.reset()
        backend.disconnect()
    """

    @abstractmethod
    def list_probes(self, blocking: bool = False) -> list[ProbeInfo]:
        """扫描当前主机上已连接的所有调试探针。

        扫描过程不修改任何内部状态，无需先调用 ``connect``。

        Args:
            blocking: 若为 True，阻塞等待直到至少发现一个探针。
                      用于批量扫描脚本。GUI 场景通常传 False。

        Returns:
            探针信息列表。若未发现任何探针，返回空列表 **不抛异常**。

        Raises:
            BackendError: 仅当底层驱动初始化失败时抛出。
        """
        ...

    @abstractmethod
    def connect(
        self,
        target: str,
        probe_uid: str | None = None,
        frequency: int = 1_000_000,
        pack_path: str | None = None,
    ) -> TargetInfo:
        """连接到指定目标芯片。

        连接成功后，``self.is_connected`` 变为 True。

        Args:
            target:     目标芯片标识符（pyOCD target name），例如 ``"stm32f407vg"``。
            probe_uid:  探针唯一 ID（来自 ``list_probes``）。
                        若为 None，自动选择第一个可用探针。
            frequency:  SWD 时钟频率（Hz），默认 200 kHz。
            pack_path:  自定义 CMSIS-Pack 文件路径。
                        若芯片不在 pyOCD 内置列表中，需提供此参数。

        Returns:
            目标芯片信息，包含 Flash/RAM 布局。

        Raises:
            BackendError(PROBE_NOT_FOUND):       无可用探针。
            BackendError(PROBE_CONNECT_FAILED):  探针通信失败。
            BackendError(TARGET_NOT_FOUND):      未检测到目标芯片。
            BackendError(TARGET_CONNECT_FAILED): 目标连接失败。
            BackendError(TARGET_NOT_SUPPORTED):  芯片型号不受支持。
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开当前连接，释放探针资源。

        调用后 ``self.is_connected`` 变为 False。
        重复调用是安全的（幂等）。
        """
        ...

    @abstractmethod
    def erase_chip(self) -> None:
        """执行全片擦除（Mass Erase）。

        擦除目标芯片的全部 Flash。

        Raises:
            BackendError(NOT_CONNECTED):  未连接目标。
            BackendError(ERASE_FAILED):   擦除操作失败。
        """
        ...

    @abstractmethod
    def program(
        self,
        file_path: str,
        base_address: int = 0x0800_0000,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """将固件文件烧录到目标芯片。

        自动识别文件格式（.bin / .hex / .elf / .axf）。
        对 .bin 文件使用 ``base_address`` 作为烧录起始地址；
        对 .hex/.elf/.axf 文件，烧录地址由文件内部分段信息决定，
        ``base_address`` 参数被忽略。

        Args:
            file_path:          固件文件路径。
            base_address:       .bin 文件的烧录基址（默认 0x08000000）。
            progress_callback:  进度回调，参数为 0.0 ~ 1.0 的进度值。
                                在 GUI 线程安全的前提下更新进度条。
                                若为 None，不报告进度。

        Raises:
            BackendError(NOT_CONNECTED):          未连接目标。
            BackendError(FILE_NOT_FOUND):         文件不存在。
            BackendError(FILE_FORMAT_UNSUPPORTED):文件格式不支持。
            BackendError(FLASH_SIZE_EXCEEDED):    固件超出 Flash 容量。
            BackendError(PROGRAM_FAILED):         烧录失败。
        """
        ...

    @abstractmethod
    def verify(
        self,
        file_path: str,
        base_address: int = 0x0800_0000,
    ) -> bool:
        """验证目标 Flash 内容与固件文件一致。

        将文件中的二进制数据与芯片 Flash 对应地址的内容逐字节比对。

        Args:
            file_path:    固件文件路径（与烧录时相同的文件）。
            base_address: 比较起始地址（仅 .bin 文件有效）。

        Returns:
            True 表示内容完全一致，False 表示存在差异。

        Raises:
            BackendError(NOT_CONNECTED):  未连接目标。
            BackendError(VERIFY_FAILED):  验证过程出错（非内容不一致）。
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """复位目标芯片并使其开始运行。

        硬件 Reset 后目标从复位向量开始执行（即运行刚烧录的固件）。

        Raises:
            BackendError(NOT_CONNECTED):  未连接目标。
        """
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """返回当前是否已连接到目标芯片。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # 上下文管理器
    # ═══════════════════════════════════════════════════════════

    def __enter__(self) -> "BackendABC":
        """进入上下文管理器，返回自身。

        使用 with 语句确保即使发生异常也会自动断开连接::

            with PyOCDBackend() as backend:
                backend.connect("stm32f407vg")
                backend.program("firmware.bin")
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器，自动调用 disconnect() 释放资源。"""
        self.disconnect()
        return False
