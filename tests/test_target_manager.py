"""TargetManager 单元测试。"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.logic.target_manager import TargetManager


@pytest.fixture
def target_mgr(mock_backend):
    return TargetManager(mock_backend)


_SUBPROCESS_TARGET = "subprocess.run"


class TestSelection:
    def test_select_target_stores_value(self, target_mgr):
        target_mgr.select_target("stm32f407vg")
        assert target_mgr.get_selected_target() == "stm32f407vg"

    def test_get_selected_target_none_initially(self, target_mgr):
        assert target_mgr.get_selected_target() is None


class TestBuiltinTargets:
    VALID_OUTPUT = (
        "  stm32f103rc             STM32F103RC\n"
        + "  stm32f407vg             STM32F407VG\n"
        + "  nrf52840                nRF52840\n"
    )

    def test_list_builtin_targets_success(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = self.VALID_OUTPUT
        mock.stderr = ""
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.list_builtin_targets()
        assert len(result) >= 2
        names = [r[0] for r in result]
        assert "stm32f407vg" in names
        assert "nrf52840" in names

    def test_list_builtin_targets_fallback(self, target_mgr):
        with patch(_SUBPROCESS_TARGET, side_effect=FileNotFoundError):
            result = target_mgr.list_builtin_targets()
        assert len(result) >= 5
        names = [r[0] for r in result]
        assert "stm32f407vg" in names
        assert "rp2040" in names

    def test_list_builtin_targets_nonzero_retcode(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = "error"
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.list_builtin_targets()
        assert len(result) > 0


class TestPackTargets:
    PACK_OUTPUT = (
        "  GigaDevice.GD32F4xx_DFP.1.0.0\n"
        + "    Part: GD32F405VG\n"
        + "    Part: GD32F407VE\n"
    )

    def test_list_installed_pack_targets_success(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = self.PACK_OUTPUT
        mock.stderr = ""
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.list_installed_pack_targets()
        assert len(result) == 2
        assert result[0][0] == "GD32F405VG"
        assert "[Pack]" in result[0][1]

    def test_list_installed_pack_targets_empty(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = ""
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.list_installed_pack_targets()
        assert result == []

    def test_list_installed_pack_targets_exception(self, target_mgr):
        with patch(_SUBPROCESS_TARGET, side_effect=OSError):
            result = target_mgr.list_installed_pack_targets()
        assert result == []


class TestAllTargets:
    def test_search_targets_filters(self, target_mgr):
        TARGETS_OUTPUT = "  stm32f103rc STM32F103RC\n  stm32f407vg STM32F407VG\n  nrf52840 nRF52840\n"
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = TARGETS_OUTPUT
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.search_targets("stm32f4")
        names = [r[0] for r in result]
        assert "stm32f407vg" in names
        assert "stm32f103rc" not in names


class TestInstallPack:
    def test_install_pack_success(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.install_pack("/path/to/GD32F4xx.pack")
        assert result is True

    def test_install_pack_failure(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = "install failed"
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.install_pack("/bad.pack")
        assert result is False

    def test_install_pack_exception(self, target_mgr):
        with patch(_SUBPROCESS_TARGET, side_effect=TimeoutError):
            result = target_mgr.install_pack("/tmp/test.pack")
        assert result is False

    def test_install_pack_by_name_success(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.install_pack_by_name("GigaDevice.GD32F4xx_DFP")
        assert result is True

    def test_install_pack_by_name_failure(self, target_mgr):
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = "not found"
        with patch(_SUBPROCESS_TARGET, return_value=mock):
            result = target_mgr.install_pack_by_name("Nonexistent.Pack")
        assert result is False
