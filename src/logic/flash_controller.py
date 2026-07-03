"""烧录控制器 — 烧录主流程编排。

完整的 connect→erase→program→verify→reset 流程。
通过 asyncio.to_thread 将阻塞式后端调用放入线程池，
主线程通过进度回调实时获取状态更新。

进度映射表::

    阶段      权重
    ───────── ──────────
    connect    0.00–0.05
    erase      0.05–0.15
    program    0.15–0.90
    verify     0.90–0.97
    reset      0.97–1.00

pyOCD 内部的 program 进度 (0.0–1.0) 被映射到 0.15–0.90 区间。
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from src.backend.error_codes import BackendError, ErrorCode
from src.backend.interface import BackendABC, FlashResult
from src.utils.logger import add_log


@dataclass
class FlashTask:
    """烧录任务参数。

    包含一次完整烧录操作所需的所有配置项。
    由 UI 层创建，传递给 FlashController.execute()。
    """

    firmware_path: str
    """固件文件路径（.bin / .hex / .elf）。"""

    target_name: str
    """芯片型号名称（如 "stm32f407vg"）。"""

    probe_uid: str | None = None
    """调试探针 UID，None 表示自动选择第一个可用探针。"""

    base_address: int = 0x08000000
    """Flash 起始地址，默认 0x08000000（STM32 Flash 首地址）。"""

    pack_path: str | None = None
    """自定义 CMSIS-Pack 文件路径（可选）。"""

    erase_chip: bool = False
    """是否在烧录前执行全片擦除（默认否，使用扇区擦除）。"""

    frequency: int = 200_000
    """SWD/JTAG 调试时钟频率（Hz），默认 200 kHz。"""

    swv_config: dict | None = None
    """SWV 配置（system_clock, swo_clock）。"""

    frequency: int = 200_000
    """SWD/JTAG 调试时钟频率（Hz），默认 200 kHz。"""


@dataclass
class FlashProgress:
    """烧录进度事件。

    Attributes:
        stage: 当前阶段 —
            "connect" / "erase" / "program" / "verify" / "reset" / "done" / "error"。
        percent: 总体进度 0.0–1.0。
        message: 用户可读的状态描述。
    """

    stage: str
    percent: float
    message: str


class FlashController:
    """烧录流程控制器。

    编排完整的 connect → erase → program → verify → reset 流程。
    所有后端调用通过 asyncio.to_thread 在独立线程中执行，
    避免阻塞 Flet UI 主线程。

    Usage::

        controller = FlashController(backend)
        task = FlashTask(firmware_path="firmware.bin", target_name="stm32f407vg")
        result = await controller.execute(task, on_progress=handle_progress)
    """

    STAGE_WEIGHTS: dict[str, tuple[float, float]] = {
        "connect": (0.00, 0.05),
        "erase":   (0.05, 0.15),
        "program": (0.15, 0.90),
        "verify":  (0.90, 0.97),
        "reset":   (0.97, 1.00),
    }

    def __init__(self, backend: BackendABC) -> None:
        self._backend: BackendABC = backend
        self._task: FlashTask | None = None
        self._is_running: bool = False
        self._cancelled: bool = False
        self._lock: threading.Lock = threading.Lock()

    async def execute(
        self,
        task: FlashTask,
        on_progress: Callable[[FlashProgress], None] | None = None,
    ) -> FlashResult:
        with self._lock:
            self._is_running = True
            self._cancelled = False
        self._task = task
        t_start: float = time.time()

        def emit(stage: str, percent: float, message: str) -> None:
            if on_progress:
                on_progress(FlashProgress(stage, percent, message))

        def check_cancel() -> None:
            with self._lock:
                cancelled = self._cancelled
            if cancelled:
                raise BackendError(ErrorCode.UNKNOWN_ERROR, "操作已取消")

        try:
            emit("connect", 0.00, "正在连接目标芯片...")
            freq_str = f"{task.frequency/1_000_000:.2f} MHz" if task.frequency >= 1_000_000 else f"{task.frequency//1_000} kHz"
            add_log("INFO", f"连接目标: {task.target_name}  |  SWD 时钟: {freq_str}")
            await asyncio.to_thread(
                self._backend.connect,
                task.target_name,
                task.probe_uid,
                task.frequency,
                task.pack_path,
                task.swv_config,
            )
            check_cancel()
            emit("connect", 0.05, "目标芯片连接成功")

            # ── 芯片信息 ──────────────────────────────
            fw_size = os.path.getsize(task.firmware_path)
            ext: str = os.path.splitext(task.firmware_path)[1].lower()
            is_addressed: bool = ext in (".hex", ".elf", ".axf")

            # 实际烧录地址范围
            if is_addressed:
                addr_start, addr_end = self._parse_addr_range(task.firmware_path, ext)
                effective_base = addr_start
                effective_end = addr_end
            else:
                effective_base = task.base_address
                effective_end = task.base_address + fw_size

            # 获取实际扇区大小（connect 后从后端读取）
            sector_size = 0
            try:
                for r in self._backend.get_target_info().flash_regions:
                    if r.start <= effective_base < r.start + r.length:
                        sector_size = r.sector_size
                        add_log("INFO", f"Flash: {r.length//1024} KB ({r.name}), 扇区 {r.sector_size//1024} KB")
                        break
            except Exception:
                sector_size = 16 * 1024  # fallback
            if sector_size == 0:
                sector_size = 16 * 1024
            start_sector = effective_base // sector_size
            end_sector = (effective_end - 1) // sector_size
            sector_count = end_sector - start_sector + 1

            addr_range = f"0x{effective_base:08X}-0x{effective_end:08X}"
            if is_addressed:
                add_log("INFO", f"固件: {fw_size:,} 字节 ({fw_size/1024:.1f} KB), 地址 {addr_range}（从文件解析）")
            else:
                add_log("INFO", f"固件: {fw_size:,} 字节 ({fw_size/1024:.1f} KB), 地址 {addr_range}")
            add_log("INFO", f"擦除扇区 {start_sector}-{end_sector} ({sector_count}个, 各{sector_size//1024}KB)")

            if task.erase_chip:
                emit("erase", 0.05, "正在擦除 Flash...")
                add_log("INFO", "正在全片擦除 Flash...")
                await asyncio.to_thread(self._backend.erase_chip)
                check_cancel()
                emit("erase", 0.15, "Flash 擦除完成")
                add_log("DONE", "Flash 擦除完成")
                await asyncio.to_thread(self._backend.reset)

            emit("program", 0.15, f"正在烧录固件 ({fw_size/1024:.0f} KB)...")
            await asyncio.to_thread(
                self._backend.program,
                task.firmware_path,
                task.base_address,
                self._make_progress_cb(emit),
            )
            check_cancel()
            emit("program", 0.90, "固件烧录完成")
            add_log("DONE", f"烧录完成: 扇区 {start_sector}-{end_sector}，地址 0x{effective_base:08X}-0x{effective_end:08X}")

            emit("verify", 0.90, "正在验证...")
            add_log("INFO", "正在验证 Flash...")
            verified: bool = await asyncio.to_thread(
                self._backend.verify,
                task.firmware_path,
                task.base_address,
            )
            if not verified:
                raise BackendError(ErrorCode.VERIFY_FAILED)
            emit("verify", 0.97, "验证通过")
            add_log("DONE", "验证通过")

            emit("reset", 0.97, "正在复位芯片...")
            await asyncio.to_thread(self._backend.reset)
            emit("reset", 1.00, "芯片已复位运行")
            add_log("DONE", "芯片已复位运行")

            duration: float = time.time() - t_start
            add_log("DONE", f"烧录成功 ({duration:.1f}s)")
            return FlashResult(
                success=True,
                error_code=ErrorCode.OK,
                message=f"烧录成功 ({duration:.1f}s)",
                duration_seconds=duration,
            )

        except BackendError as e:
            duration = time.time() - t_start
            emit("error", 0.0, str(e))
            add_log("ERROR", str(e))
            return FlashResult(
                success=False, error_code=e.error_code,
                message=str(e), duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - t_start
            msg: str = f"未知错误: {e}"
            emit("error", 0.0, msg)
            add_log("ERROR", msg)
            return FlashResult(
                success=False, error_code=ErrorCode.UNKNOWN_ERROR,
                message=msg, duration_seconds=duration,
            )

        finally:
            with self._lock:
                self._is_running = False

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
        add_log("WARN", "正在取消操作...")

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def _make_progress_cb(
        self,
        emit: Callable[[str, float, str], None],
    ) -> Callable[[float], None]:
        def callback(program_percent: float) -> None:
            mapped: float = 0.15 + max(0.0, min(1.0, program_percent)) * 0.75
            emit("program", mapped, f"正在烧录... {program_percent * 100:.0f}%")
        return callback

    @staticmethod
    def _parse_addr_range(file_path: str, ext: str) -> tuple[int, int]:
        """解析 .hex/.elf 文件的实际地址范围，用于日志显示。"""
        import logging as _log
        if ext == ".hex":
            try:
                from intelhex import IntelHex
                ih = IntelHex(file_path)
                addrs = ih.addresses()
                if addrs:
                    return min(addrs), max(addrs) + 1
            except Exception as e:
                _log.getLogger(__name__).warning("IntelHex 解析失败: %s", e)
        elif ext in (".elf", ".axf"):
            try:
                from elftools.elf.elffile import ELFFile
                with open(file_path, "rb") as f:
                    elf = ELFFile(f)
                    lo, hi = None, None
                    for seg in elf.iter_segments():
                        ptype = str(seg.header.get("p_type", ""))
                        if ptype == "PT_LOAD" and seg.header.get("p_filesz", 0) > 0:
                            vaddr = seg.header.get("p_vaddr", 0)
                            fsize = seg.header.get("p_filesz", 0)
                            lo = min(lo, vaddr) if lo is not None else vaddr
                            hi = max(hi, vaddr + fsize) if hi is not None else vaddr + fsize
                    if lo is not None and hi is not None:
                        return lo, hi
            except Exception as e:
                _log.getLogger(__name__).warning("ELF 解析失败: %s", e)
        return 0, 0
