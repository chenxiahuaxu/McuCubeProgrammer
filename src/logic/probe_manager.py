"""探针管理器 — 扫描已连接调试探针，管理探针选择状态。

封装 BackendABC.list_probes()，提供：
  - 探针扫描与缓存
  - 探针选择（按 unique_id）
  - 强制刷新
"""

from __future__ import annotations

from src.backend.interface import BackendABC, ProbeInfo
from src.utils.logger import add_log


class ProbeManager:
    """探针管理器。

    负责：
      - 调用后端扫描已连接探针
      - 缓存探针列表，供 UI 下拉选择
      - 管理当前选中探针的状态

    Usage::

        manager = ProbeManager(backend)
        probes = manager.scan_probes()
        manager.select_probe(probes[0].unique_id)
        selected = manager.get_selected_probe()
    """

    def __init__(self, backend: BackendABC) -> None:
        """初始化探针管理器。

        Args:
            backend: 后端实例（如 PyOCDBackend），提供 list_probes() 能力。
        """
        self._backend: BackendABC = backend
        self._probes: list[ProbeInfo] = []
        self._selected_probe: ProbeInfo | None = None

    def scan_probes(self) -> list[ProbeInfo]:
        """扫描当前主机上已连接的所有调试探针。

        调用后端 list_probes(blocking=False) 进行非阻塞扫描，
        并将结果缓存到 self._probes。

        Returns:
            ProbeInfo 列表。未发现探针时返回空列表（不抛异常）。
        """
        try:
            raw: list[ProbeInfo] = self._backend.list_probes(blocking=False)
            self._probes = raw
            add_log("INFO", f"检测到 {len(raw)} 个调试探针")
            if not raw:
                add_log("WARN", "未检测到调试探针，请检查 USB 连接和驱动")
            return raw
        except Exception as e:  # pylint: disable=broad-exception-caught
            add_log("ERROR", f"探针扫描失败: {e}")
            self._probes = []
            return []

    def select_probe(self, unique_id: str) -> None:
        """选择指定探针为当前操作目标。

        Args:
            unique_id: 探针唯一标识符（来自 ProbeInfo.unique_id）。
        """
        for p in self._probes:
            if p.unique_id == unique_id:
                self._selected_probe = p
                add_log("INFO", f"已选择探针: {p.description}")
                return
        add_log("WARN", f"未找到指定探针: {unique_id}")

    def get_selected_probe(self) -> ProbeInfo | None:
        """返回当前选中的探针信息。"""
        return self._selected_probe

    def get_probes(self) -> list[ProbeInfo]:
        """返回缓存中的探针列表。"""
        return self._probes

    def get_probe_count(self) -> int:
        """返回缓存中探针的数量。"""
        return len(self._probes)

    def refresh(self) -> list[ProbeInfo]:
        """强制重新扫描探针列表。"""
        add_log("INFO", "正在刷新探针列表...")
        return self.scan_probes()
