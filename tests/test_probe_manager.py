"""ProbeManager 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.logic.probe_manager import ProbeManager
from src.backend.interface import ProbeInfo


class TestScanProbes:
    def test_scan_probes_returns_list(self, mock_backend, fake_probe_info):
        pm = ProbeManager(mock_backend)
        result = pm.scan_probes()
        assert result == [fake_probe_info]
        assert len(result) == 1

    def test_scan_probes_empty(self, mock_backend_no_probes):
        pm = ProbeManager(mock_backend_no_probes)
        result = pm.scan_probes()
        assert result == []
        assert pm.get_probe_count() == 0

    def test_scan_probes_handles_exception(self, mock_backend):
        mock_backend.list_probes.side_effect = RuntimeError("USB error")
        pm = ProbeManager(mock_backend)
        result = pm.scan_probes()
        assert result == []
        assert pm._probes == []


class TestSelectProbe:
    def test_select_probe_sets_selection(self, mock_backend, fake_probe_info):
        pm = ProbeManager(mock_backend)
        pm.scan_probes()
        pm.select_probe(fake_probe_info.unique_id)
        assert pm.get_selected_probe() == fake_probe_info

    def test_select_probe_not_found(self, mock_backend):
        pm = ProbeManager(mock_backend)
        pm.scan_probes()
        pm.select_probe("NONEXISTENT")
        assert pm.get_selected_probe() is None


class TestGetProbes:
    def test_get_probes_returns_cached(self, mock_backend, fake_probe_info):
        pm = ProbeManager(mock_backend)
        pm.scan_probes()
        assert pm.get_probes() == [fake_probe_info]

    def test_get_probe_count(self, mock_backend, fake_probe_info):
        pm = ProbeManager(mock_backend)
        pm.scan_probes()
        assert pm.get_probe_count() == 1

    def test_get_probe_count_zero(self, mock_backend_no_probes):
        pm = ProbeManager(mock_backend_no_probes)
        pm.scan_probes()
        assert pm.get_probe_count() == 0


class TestRefresh:
    def test_refresh_rescans(self, mock_backend, fake_probe_info):
        pm = ProbeManager(mock_backend)
        pm.scan_probes()
        new_probe = ProbeInfo(
            name="J-Link", unique_id="J123", probe_type="jlink",
            vendor_name="SEGGER", product_name="J-Link", description="J-Link",
        )
        mock_backend.list_probes.return_value = [new_probe]
        result = pm.refresh()
        assert result == [new_probe]
        assert pm.get_probes() == [new_probe]
