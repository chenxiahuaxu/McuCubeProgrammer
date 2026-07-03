"""
MCU Cube Programmer — pytest 全局配置与共享夹具

Fixture 命名约定：
- mock_*      : Mock 对象，用于替代真实依赖
- fake_*      : 假数据对象，用于测试数据流转
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.backend.interface import (
    BackendABC,
    ProbeInfo,
    TargetInfo,
    FlashRegion,
    FlashResult,
)
from src.backend.error_codes import ErrorCode


# ═══════════════════════════════════════════════════════════
# 假数据 Fixture
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def fake_probe_info() -> ProbeInfo:
    """返回一个示例 ProbeInfo。"""
    return ProbeInfo(
        name="ST-Link/V2-1",
        unique_id="E6616407E3646B29",
        probe_type="stlink",
        vendor_name="STMicroelectronics",
        product_name="STM32 STLink",
        description="STMicroelectronics STM32 STLink (E6616407E3646B29)",
    )


@pytest.fixture
def fake_flash_region() -> FlashRegion:
    """返回一个示例 FlashRegion（模拟 STM32F407 内部 Flash）。"""
    return FlashRegion(
        name="Internal Flash",
        start=0x0800_0000,
        length=512 * 1024,
        sector_size=16 * 1024,
        access="rwx",
    )


@pytest.fixture
def fake_target_info(fake_flash_region: FlashRegion) -> TargetInfo:
    """返回一个示例 TargetInfo（模拟 STM32F407VG）。"""
    return TargetInfo(
        name="stm32f407vg",
        part_number="STM32F407VGTx",
        vendor="STMicroelectronics",
        flash_regions=[fake_flash_region],
        ram_start=0x2000_0000,
        ram_size=128 * 1024,
    )


@pytest.fixture
def fake_flash_result() -> FlashResult:
    """返回一个成功的 FlashResult。"""
    return FlashResult(
        success=True,
        error_code=ErrorCode.OK,
        message="烧录成功 (2.3s)",
        duration_seconds=2.3,
    )


# ═══════════════════════════════════════════════════════════
# Mock Fixture
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def mock_backend(fake_probe_info, fake_target_info) -> MagicMock:
    """返回一个配置了默认行为的 mock BackendABC。

    默认行为：
    - list_probes() → [fake_probe_info]
    - connect(target, probe_uid) → fake_target_info
    - erase_chip() → 无异常
    - program(file, address, cb) → 无异常（cb 被调用 3 次）
    - verify(file, address) → True
    - reset() → 无异常
    - is_connected → True (connect 后)
    """
    backend = MagicMock(spec=BackendABC)
    backend.list_probes.return_value = [fake_probe_info]
    backend.connect.return_value = fake_target_info
    backend.erase_chip.return_value = None
    backend.program.return_value = None
    backend.verify.return_value = True
    backend.reset.return_value = None
    backend.is_connected = True
    return backend


@pytest.fixture
def mock_backend_no_probes() -> MagicMock:
    """返回一个没有探针的 mock BackendABC。"""
    backend = MagicMock(spec=BackendABC)
    backend.list_probes.return_value = []
    backend.is_connected = False
    return backend
