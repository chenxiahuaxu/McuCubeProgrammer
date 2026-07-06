"""
MCU Cube Programmer — pyOCD 后端实现

基于 pyOCD 库封装，实现 BackendABC 的全部抽象方法。
支持的探针：ST-Link / CMSIS-DAP / J-Link
支持的芯片：pyOCD 内置芯片 + 通过 CMSIS-Pack 扩展的芯片（如 GD32）
"""

from __future__ import annotations

import io
import logging
import os
from collections.abc import Callable

from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session
from pyocd.core.target import Target
from pyocd.flash.file_programmer import FileProgrammer
from pyocd.flash.eraser import FlashEraser
from pyocd.target.pack.cmsis_pack import CmsisPack
from pyocd.core.memory_map import MemoryMap
from pyocd.core import exceptions as pyocd_exc
from pyocd.probe import debug_probe
from pyocd.trace.swv import SWVReader

from .error_codes import ErrorCode, BackendError
from .interface import (
    BackendABC,
    ProbeInfo,
    TargetInfo,
    FlashRegion,
)

# ═══════════════════════════════════════════════════════════
# 约定常量
# ═══════════════════════════════════════════════════════════

_SUPPORTED_EXTENSIONS: tuple[str, ...] = (".bin", ".hex", ".elf", ".axf")
_ADDRESSED_EXTENSIONS: tuple[str, ...] = (".hex", ".elf", ".axf")
_DEFAULT_FREQUENCY: int = 200_000  # CMSIS-DAP 稳定值，避免 Unexpected ACK

_log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════


def _infer_probe_type(probe: debug_probe.DebugProbe) -> str:
    """根据探针对象的类名推断探针类型。"""
    class_name: str = type(probe).__name__.lower()
    if "stlink" in class_name:
        return "stlink"
    if "cmsisdap" in class_name or "dap" in class_name:
        return "cmsisdap"
    if "jlink" in class_name:
        return "jlink"
    return "unknown"


def _probe_to_probe_info(probe: debug_probe.DebugProbe) -> ProbeInfo:
    """将 pyOCD 探针对象转换为项目的 ProbeInfo 数据结构。"""
    return ProbeInfo(
        name=probe.product_name,
        unique_id=probe.unique_id,
        probe_type=_infer_probe_type(probe),
        vendor_name=probe.vendor_name,
        product_name=probe.product_name,
        description=probe.description,
    )


def _extract_target_info(target: Target) -> TargetInfo:
    """从 pyOCD Target 对象中提取芯片的存储布局信息。"""
    memory_map: MemoryMap = target.memory_map

    flash_regions: list[FlashRegion] = []
    for region in memory_map.iter_matching_regions(type="flash"):
        flash_regions.append(
            FlashRegion(
                name=region.name,
                start=region.start,
                length=region.length,
                sector_size=region.sector_size,
                access=region.access,
            )
        )

    ram_region = memory_map.get_default_region_of_type("ram")
    ram_start: int = ram_region.start if ram_region else 0
    ram_size: int = ram_region.length if ram_region else 0

    part_number: str = getattr(target, "part_number", "") or ""
    vendor: str = getattr(target, "vendor", "") or ""

    return TargetInfo(
        name=getattr(target, "name", None) or target.__class__.__name__.lower() or "unknown",
        part_number=part_number,
        vendor=vendor,
        flash_regions=flash_regions,
        ram_start=ram_start,
        ram_size=ram_size,
    )


# ═══════════════════════════════════════════════════════════
# 主实现
# ═══════════════════════════════════════════════════════════


class PyOCDBackend(BackendABC):
    """pyOCD 后端实现。

    封装 pyOCD 的 Session、FlashEraser、FileProgrammer 等 API，
    提供探针扫描、目标连接、烧录、验证的完整流程。
    """

    def __init__(self) -> None:
        self._session: Session | None = None
        self._swv_reader: SWVReader | None = None

    def swo_start_callback(self, sys_clock: int, swo_clock: int, callback) -> None:
        """启动 SWV + 回调式文本输出。"""
        session = self._require_session()

        class _Cw(io.StringIO):
            def __init__(self):
                super().__init__()
                self._buf = ""

            def write(self, text):
                self._buf += text
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    line = "".join(c for c in line.strip() if c.isprintable() or c in "\t")
                    if line:
                        callback(line)
                return len(text)
        console = _Cw()
        self._swv_reader = SWVReader(session, core_number=0)
        ok = self._swv_reader.init(sys_clock, swo_clock, console)
        if not ok:
            raise BackendError(ErrorCode.UNKNOWN_ERROR, "SWV init failed")

    # ── 探针扫描 ─────────────────────────────────────────

    def list_probes(self, blocking: bool = False) -> list[ProbeInfo]:
        probes = ConnectHelper.get_all_connected_probes(blocking=blocking)
        return [_probe_to_probe_info(p) for p in probes]

    # ── 连接与断开 ───────────────────────────────────────

    def connect(  # pylint: disable=too-many-positional-arguments
        self,
        target: str,
        probe_uid: str | None = None,
        frequency: int = _DEFAULT_FREQUENCY,
        pack_path: str | None = None,
        swv_config: dict | None = None,
    ) -> TargetInfo:
        self.disconnect()

        options: dict = {
            "target_override": target,
            "frequency": frequency,
            "auto_unlock": False,
            "reset_type": "default",
            "connect_mode": "under-reset",
        }

        # SWV/SWO 配置（必须在 session.open() 前设置）
        if swv_config:
            options["enable_swv"] = True
            options["swv_system_clock"] = swv_config.get("system_clock", 168_000_000)
            options["swv_clock"] = swv_config.get("swo_clock", 400_000)
            options["swv_raw_enable"] = True
            options["swv_raw_port"] = swv_config.get("raw_port", 50035)

        self._swv_raw_port = options.get("swv_raw_port", 0) if swv_config else 0

        if pack_path:
            if not os.path.isfile(pack_path):
                raise BackendError(
                    ErrorCode.FILE_NOT_FOUND,
                    f"指定的 CMSIS-Pack 不存在: {pack_path}",
                )
            try:
                options["pack"] = CmsisPack(pack_path)
            except Exception as e:
                raise BackendError(
                    ErrorCode.TARGET_NOT_SUPPORTED,
                    f"加载 CMSIS-Pack 失败: {e}",
                ) from e

        try:
            session: Session | None = ConnectHelper.session_with_chosen_probe(
                unique_id=probe_uid,
                return_first=(probe_uid is None),
                options=options,
            )
        except pyocd_exc.ProbeError as e:
            raise BackendError(ErrorCode.PROBE_NOT_FOUND, str(e)) from e
        except pyocd_exc.Error as e:
            raise BackendError(ErrorCode.PROBE_CONNECT_FAILED, str(e)) from e

        if session is None:
            raise BackendError(
                ErrorCode.PROBE_NOT_FOUND,
                "无法创建 pyOCD 会话，未发现可用探针",
            )

        self._session = session

        try:
            self._session.open()
        except pyocd_exc.TargetError as e:
            self.disconnect()
            raise BackendError(ErrorCode.TARGET_CONNECT_FAILED, str(e)) from e
        except pyocd_exc.Error as e:
            self.disconnect()
            raise BackendError(ErrorCode.TARGET_NOT_FOUND, str(e)) from e

        # under-reset 模式下 target 可能未完全初始化内存映射，
        # halt 一次确保 target.init() 完整执行
        try:
            self._session.target.halt()
        except Exception:
            pass

        try:
            return _extract_target_info(self._session.target)
        except Exception as e:
            raise BackendError(
                ErrorCode.TARGET_NOT_FOUND,
                f"提取目标信息失败: {e}",
            ) from e

    def disconnect(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # pylint: disable=broad-exception-caught  # OK: backend error boundary
                _log.warning("Session close failed (device may have been unplugged)", exc_info=True)
            finally:
                self._session = None

    # ── Flash 操作 ───────────────────────────────────────

    def _require_session(self) -> Session:
        if self._session is None:
            raise BackendError(
                ErrorCode.TARGET_CONNECT_FAILED,
                "未连接目标芯片，请先调用 connect()",
            )
        return self._session

    def erase_chip(self) -> None:
        session = self._require_session()
        try:
            FlashEraser(session, FlashEraser.Mode.CHIP).erase()
        except pyocd_exc.FlashFailure as e:
            raise BackendError(ErrorCode.ERASE_FAILED, str(e)) from e
        except pyocd_exc.Error as e:
            raise BackendError(ErrorCode.ERASE_FAILED, str(e)) from e

    def program(
        self,
        file_path: str,
        base_address: int = 0x0800_0000,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        session = self._require_session()

        if not os.path.isfile(file_path):
            raise BackendError(
                ErrorCode.FILE_NOT_FOUND,
                f"固件文件不存在: {file_path}",
            )

        ext: str = os.path.splitext(file_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise BackendError(
                ErrorCode.FILE_FORMAT_UNSUPPORTED,
                f"不支持的文件格式: {ext}，支持: {', '.join(_SUPPORTED_EXTENSIONS)}",
            )

        programmer = FileProgrammer(
            session,
            progress=progress_callback,
            chip_erase="sector",
            smart_flash=True,
            trust_crc=False,
        )

        try:
            if ext == ".bin":
                programmer.add_file(file_path, base_address=base_address)
                programmer.commit()
            else:
                programmer.program(file_path)
        except pyocd_exc.FlashFailure as e:
            raise BackendError(ErrorCode.PROGRAM_FAILED, str(e)) from e
        except pyocd_exc.Error as e:
            raise BackendError(ErrorCode.PROGRAM_FAILED, str(e)) from e

    def verify(
        self,
        file_path: str,
        base_address: int = 0x0800_0000,
    ) -> bool:
        session = self._require_session()

        ext: str = os.path.splitext(file_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise BackendError(
                ErrorCode.FILE_FORMAT_UNSUPPORTED,
                f"不支持的文件格式: {ext}，支持: {', '.join(_SUPPORTED_EXTENSIONS)}",
            )

        try:
            if ext == ".bin":
                with open(file_path, "rb") as f:
                    file_data: bytes = f.read()

                size: int = len(file_data)
                if size == 0:
                    return True

                target_data: bytearray = session.target.read_memory_block8(
                    base_address, size
                )

                if len(target_data) != len(file_data):
                    return False

                return file_data == bytes(target_data)
            # .hex/.elf 多段验证在后续版本实现
            _log.warning("非 .bin 文件的 verify 尚未实现完整逐段比对，当前直接返回 True")
            return True

        except pyocd_exc.Error as e:
            raise BackendError(ErrorCode.VERIFY_FAILED, str(e)) from e

    # ── 目标控制 ─────────────────────────────────────────

    def get_target_info(self) -> TargetInfo:
        """获取当前连接目标的芯片信息。"""
        session = self._require_session()
        return _extract_target_info(session.target)

    def reset(self) -> None:
        session = self._require_session()
        try:
            session.target.reset()
        except pyocd_exc.Error as e:
            raise BackendError(
                ErrorCode.TARGET_CONNECT_FAILED,
                f"复位失败: {e}",
            ) from e

    # ── SWO ─────────────────────────────────────────────

    def swo_start(self, baudrate: float = 1_000_000) -> None:
        """启动 SWV Raw TCP Server。"""
        session = self._require_session()
        options = dict(session.options) if hasattr(session.options, '__iter__') else {}
        sys_clock = options.get("swv_system_clock") or 168_000_000
        swo_clock = options.get("swv_clock") or int(baudrate) or 400_000
        try:
            self._swv_reader = SWVReader(session, core_number=0)
            ok = self._swv_reader.init(sys_clock, swo_clock, io.StringIO())
            if not ok:
                raise RuntimeError("SWV init failed (probe may not support SWO)")
        except Exception as e:
            raise BackendError(ErrorCode.UNKNOWN_ERROR, f"SWV 启动失败: {e}") from e

    def swo_read(self) -> bytes:
        return b""  # TCP server 模式不需要

    def swo_stop(self) -> None:
        if self._swv_reader:
            try:
                self._swv_reader._shutdown_event.set()
            except Exception:  # pylint: disable=broad-exception-caught  # OK: backend error boundary
                _log.warning("SWV reader shutdown failed", exc_info=True)
            self._swv_reader = None
        self._swv_raw_port = 0

    @property
    def swv_raw_port(self) -> int:
        return self._swv_raw_port

    # ── 状态查询 ─────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._session is not None
