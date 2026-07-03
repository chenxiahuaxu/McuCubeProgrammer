"""FlashController 单元测试。"""

from __future__ import annotations

import pytest

from src.logic.flash_controller import FlashController, FlashTask, FlashProgress
from src.backend.error_codes import ErrorCode, BackendError


@pytest.fixture
def controller(mock_backend):
    return FlashController(mock_backend)


@pytest.fixture
def sample_task(tmp_path):
    """创建临时 .bin 文件并返回 FlashTask。"""
    fw = tmp_path / "firmware.bin"
    fw.write_bytes(b"\x00" * 1024)
    return FlashTask(
        firmware_path=str(fw),
        target_name="stm32f407vg",
        probe_uid="E6616407E3646B29",
        base_address=0x08000000,
    )


class TestFlashTask:
    def test_flash_task_creation(self):
        task = FlashTask(
            firmware_path="/tmp/fw.bin",
            target_name="stm32f103rc",
            probe_uid="ABC123",
            base_address=0x08000000,
            erase_chip=True,
        )
        assert task.firmware_path == "/tmp/fw.bin"
        assert task.target_name == "stm32f103rc"
        assert task.probe_uid == "ABC123"
        assert task.erase_chip is True
        assert task.pack_path is None

    def test_flash_task_defaults(self):
        task = FlashTask(firmware_path="fw.bin", target_name="stm32f407vg")
        assert task.base_address == 0x08000000
        assert task.probe_uid is None
        assert task.erase_chip is False


@pytest.mark.asyncio
class TestExecute:
    async def test_execute_success(self, controller, sample_task, mock_backend):
        result = await controller.execute(sample_task)
        assert result.success is True
        assert result.error_code == ErrorCode.OK
        mock_backend.connect.assert_called_once()
        mock_backend.program.assert_called_once()
        mock_backend.verify.assert_called_once()
        mock_backend.reset.assert_called()

    async def test_execute_with_erase(self, controller, sample_task, mock_backend):
        sample_task.erase_chip = True
        result = await controller.execute(sample_task)
        assert result.success is True
        mock_backend.erase_chip.assert_called_once()

    async def test_execute_verify_failure(self, controller, sample_task, mock_backend):
        mock_backend.verify.return_value = False
        result = await controller.execute(sample_task)
        assert result.success is False
        assert result.error_code == ErrorCode.VERIFY_FAILED

    async def test_execute_connect_failure(self, controller, sample_task, mock_backend):
        mock_backend.connect.side_effect = BackendError(
            ErrorCode.PROBE_NOT_FOUND, "无探针"
        )
        result = await controller.execute(sample_task)
        assert result.success is False
        assert result.error_code == ErrorCode.PROBE_NOT_FOUND

    async def test_execute_backend_error(self, controller, sample_task, mock_backend):
        mock_backend.program.side_effect = BackendError(
            ErrorCode.PROGRAM_FAILED, "烧录失败"
        )
        result = await controller.execute(sample_task)
        assert result.success is False
        assert result.error_code == ErrorCode.PROGRAM_FAILED

    async def test_execute_progress_callback(self, controller, sample_task, mock_backend):
        events = []

        def on_progress(ev: FlashProgress):
            events.append(ev)

        result = await controller.execute(sample_task, on_progress=on_progress)
        assert result.success is True
        assert len(events) > 0
        stages = [e.stage for e in events]
        assert "connect" in stages
        assert "program" in stages
        assert "verify" in stages
        assert "reset" in stages
        assert stages[-1] == "done" or stages[-1] == "reset"

    async def test_progress_stages_in_order(self, controller, sample_task, mock_backend):
        events = []

        def on_progress(ev):
            events.append(ev)

        await controller.execute(sample_task, on_progress=on_progress)
        stage_order = [e.stage for e in events if e.stage != "reset"]
        connect_idx = stage_order.index("connect")
        program_idx = stage_order.index("program")
        verify_idx = stage_order.index("verify")
        assert connect_idx < program_idx < verify_idx

    async def test_progress_percent_increasing(self, controller, sample_task, mock_backend):
        events = []

        def on_progress(ev):
            events.append(ev)

        await controller.execute(sample_task, on_progress=on_progress)
        percents = [e.percent for e in events]
        for i in range(1, len(percents)):
            assert percents[i] >= percents[i - 1] - 0.01


class TestRunningState:
    @pytest.mark.asyncio
    async def test_is_running_false_after_execute(self, controller, sample_task):
        await controller.execute(sample_task)
        assert controller.is_running() is False

    def test_is_running_false_initially(self, controller):
        assert controller.is_running() is False


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_stops_execution(self, controller, sample_task, mock_backend):
        """取消操作应立即使 execute 返回失败结果。"""
        import asyncio

        def blocking_program(*args, **kwargs):
            raise BackendError(ErrorCode.PROGRAM_FAILED, "已取消")

        mock_backend.program.side_effect = blocking_program

        task = asyncio.ensure_future(controller.execute(sample_task))
        controller.cancel()

        result = await task
        assert result.success is False
