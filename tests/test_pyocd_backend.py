"""
PyOCDBackend 单元测试。

测试目标：验证 PyOCDBackend 的各项方法正确封装 pyOCD API，
并正确抛出 BackendError 异常。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.backend.error_codes import ErrorCode, BackendError
from src.backend.interface import ProbeInfo, TargetInfo, FlashResult
from src.backend.pyocd_backend import PyOCDBackend


@pytest.fixture
def backend():
    return PyOCDBackend()


def _make_mock_probe():
    probe = MagicMock()
    probe.product_name = "STM32 STLink"
    probe.unique_id = "E6616407E3646B29"
    probe.vendor_name = "STMicroelectronics"
    probe.description = "ST-Link/V2-1"
    type(probe).__name__ = "StlinkProbe"
    return probe


def _make_mock_session():
    mock_session = MagicMock()
    mock_session.target.memory_map.iter_matching_regions.return_value = []
    mock_session.target.memory_map.get_default_region_of_type.return_value = None
    mock_session.target.part_number = "STM32F407VGTx"
    mock_session.target.vendor = "STMicroelectronics"
    type(mock_session.target).__name__ = "STM32F407VG"
    return mock_session


@pytest.fixture
def fake_pyocd_probes():
    return [_make_mock_probe()]


@pytest.fixture
def connected_backend(backend, fake_pyocd_probes):
    """返回一个已 mock 连接的 backend。"""
    mock_session = _make_mock_session()
    with patch(
        "src.backend.pyocd_backend.ConnectHelper.session_with_chosen_probe",
        return_value=mock_session,
    ):
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.get_all_connected_probes",
            return_value=fake_pyocd_probes,
        ):
            backend.connect("stm32f407vg", probe_uid="E6616407E3646B29")
    return backend


class TestListProbes:
    def test_list_probes_returns_list(self, backend, fake_pyocd_probes):
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.get_all_connected_probes",
            return_value=fake_pyocd_probes,
        ):
            result = backend.list_probes()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].unique_id == "E6616407E3646B29"

    def test_list_probes_empty_when_no_probes(self, backend):
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.get_all_connected_probes",
            return_value=[],
        ):
            result = backend.list_probes()
        assert result == []

    def test_list_probes_blocking_waits_for_probe(self, backend, fake_pyocd_probes):
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.get_all_connected_probes",
            return_value=fake_pyocd_probes,
        ) as mock_all:
            backend.list_probes(blocking=True)
            mock_all.assert_called_once_with(blocking=True)


class TestConnect:
    def test_connect_returns_target_info(self, connected_backend):
        assert connected_backend.is_connected

    def test_connect_no_probe_raises_error(self, backend):
        from pyocd.core.exceptions import ProbeError as PyocdProbeError
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.session_with_chosen_probe",
            side_effect=PyocdProbeError("no probe"),
        ):
            with pytest.raises(BackendError) as exc:
                backend.connect("stm32f407vg")
            assert exc.value.error_code == ErrorCode.PROBE_NOT_FOUND

    def test_connect_session_is_none_raises_error(self, backend):
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.session_with_chosen_probe",
            return_value=None,
        ):
            with pytest.raises(BackendError) as exc:
                backend.connect("stm32f407vg")
            assert exc.value.error_code == ErrorCode.PROBE_NOT_FOUND

    def test_connect_auto_disconnects_previous(self, backend, fake_pyocd_probes):
        mock_session = _make_mock_session()
        mock_session2 = _make_mock_session()
        with patch(
            "src.backend.pyocd_backend.ConnectHelper.session_with_chosen_probe",
            side_effect=[mock_session, mock_session2],
        ):
            with patch(
                "src.backend.pyocd_backend.ConnectHelper.get_all_connected_probes",
                return_value=fake_pyocd_probes,
            ):
                backend.connect("stm32f407vg")
                first_session = backend._session
                backend.connect("stm32f103rc")
                assert backend._session is not first_session
                first_session.close.assert_called_once()

    def test_connect_with_invalid_pack_raises_error(self, backend):
        with pytest.raises(BackendError) as exc:
            backend.connect("stm32f407vg", pack_path="/nonexistent.pack")
        assert exc.value.error_code == ErrorCode.FILE_NOT_FOUND


class TestDisconnect:
    def test_disconnect_clears_session(self, connected_backend):
        connected_backend.disconnect()
        assert connected_backend.is_connected is False

    def test_disconnect_idempotent(self, backend):
        backend.disconnect()
        backend.disconnect()
        assert backend.is_connected is False

    def test_disconnect_handles_close_failure(self, connected_backend):
        connected_backend._session.close.side_effect = OSError("USB gone")
        connected_backend.disconnect()
        assert connected_backend._session is None


class TestErase:
    def test_erase_chip_not_connected_raises_error(self, backend):
        with pytest.raises(BackendError) as exc:
            backend.erase_chip()
        assert exc.value.error_code == ErrorCode.TARGET_CONNECT_FAILED

    def test_erase_chip_success(self, connected_backend):
        with patch("src.backend.pyocd_backend.FlashEraser") as mock_eraser_cls:
            mock_eraser = MagicMock()
            mock_eraser_cls.return_value = mock_eraser
            connected_backend.erase_chip()
            mock_eraser.erase.assert_called_once()


class TestProgram:
    def test_program_file_not_found_raises_error(self, connected_backend):
        with pytest.raises(BackendError) as exc:
            connected_backend.program("/nonexistent.bin")
        assert exc.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_program_unsupported_format_raises_error(self, connected_backend, tmp_path):
        f = tmp_path / "fw.txt"
        f.write_bytes(b"data")
        with pytest.raises(BackendError) as exc:
            connected_backend.program(str(f))
        assert exc.value.error_code == ErrorCode.FILE_FORMAT_UNSUPPORTED

    def test_program_not_connected_raises_error(self, backend, tmp_path):
        f = tmp_path / "fw.bin"
        f.write_bytes(b"\x00")
        with pytest.raises(BackendError) as exc:
            backend.program(str(f))
        assert exc.value.error_code == ErrorCode.TARGET_CONNECT_FAILED

    def test_program_bin_success(self, connected_backend, tmp_path):
        f = tmp_path / "fw.bin"
        f.write_bytes(b"\x00" * 64)
        with patch("src.backend.pyocd_backend.FileProgrammer") as mock_fp_cls:
            mock_fp = MagicMock()
            mock_fp_cls.return_value = mock_fp
            connected_backend.program(str(f))
            mock_fp.commit.assert_called_once()

    def test_program_hex_success(self, connected_backend, tmp_path):
        f = tmp_path / "fw.hex"
        f.write_text(":020000040000FA\n:00000001FF\n")
        with patch("src.backend.pyocd_backend.FileProgrammer") as mock_fp_cls:
            mock_fp = MagicMock()
            mock_fp_cls.return_value = mock_fp
            connected_backend.program(str(f))
            mock_fp.program.assert_called_once()

    def test_program_with_progress_callback(self, connected_backend, tmp_path):
        f = tmp_path / "fw.bin"
        f.write_bytes(b"\x00" * 64)
        with patch("src.backend.pyocd_backend.FileProgrammer") as mock_fp_cls:
            mock_fp = MagicMock()
            mock_fp_cls.return_value = mock_fp
            connected_backend.program(str(f))
            args, kwargs = mock_fp_cls.call_args
            assert "progress" in kwargs


class TestVerify:
    def test_verify_bin_matches_returns_true(self, connected_backend, tmp_path):
        f = tmp_path / "fw.bin"
        data = b"\x01\x02\x03\x04"
        f.write_bytes(data)
        connected_backend._session.target.read_memory_block8.return_value = bytearray(data)
        result = connected_backend.verify(str(f))
        assert result is True

    def test_verify_bin_mismatch_returns_false(self, connected_backend, tmp_path):
        f = tmp_path / "fw.bin"
        f.write_bytes(b"\x01\x02\x03\x04")
        connected_backend._session.target.read_memory_block8.return_value = bytearray(b"\xFF\xFF\xFF\xFF")
        result = connected_backend.verify(str(f))
        assert result is False

    def test_verify_hex_returns_true(self, connected_backend, tmp_path):
        f = tmp_path / "fw.hex"
        f.write_text(":020000040000FA\n:00000001FF\n")
        result = connected_backend.verify(str(f))
        assert result is True

    def test_verify_not_connected_raises_error(self, backend, tmp_path):
        f = tmp_path / "fw.bin"
        f.write_bytes(b"\x00")
        with pytest.raises(BackendError) as exc:
            backend.verify(str(f))
        assert exc.value.error_code == ErrorCode.TARGET_CONNECT_FAILED

    def test_verify_empty_file(self, connected_backend, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        result = connected_backend.verify(str(f))
        assert result is True


class TestReset:
    def test_reset_success(self, connected_backend):
        connected_backend.reset()
        connected_backend._session.target.reset.assert_called_once()

    def test_reset_not_connected_raises_error(self, backend):
        with pytest.raises(BackendError) as exc:
            backend.reset()
        assert exc.value.error_code == ErrorCode.TARGET_CONNECT_FAILED


class TestIsConnected:
    def test_is_connected_false_initially(self, backend):
        assert backend.is_connected is False

    def test_is_connected_true_after_connect(self, connected_backend):
        assert connected_backend.is_connected is True

    def test_is_connected_false_after_disconnect(self, connected_backend):
        connected_backend.disconnect()
        assert connected_backend.is_connected is False


class TestGetTargetInfo:
    def test_get_target_info_returns_info(self, connected_backend):
        info = connected_backend.get_target_info()
        assert isinstance(info, TargetInfo)
        assert info.part_number == "STM32F407VGTx"
