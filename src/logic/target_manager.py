"""目标芯片管理器 — 芯片列表获取与 CMSIS-Pack 管理。

通过 pyOCD CLI 获取：
  - 内置芯片目标列表（pyocd list --targets）
  - 已安装 CMSIS-Pack 目标列表（pyocd pack show）
  - Pack 安装（pyocd pack install）
"""

from __future__ import annotations

import re
import subprocess

from src.backend.interface import BackendABC
from src.utils.logger import add_log


class TargetManager:
    """目标芯片管理器。

    职责：
      - 列出所有可用芯片目标（内置 + Pack）
      - 管理当前选中目标
      - 安装 CMSIS-Pack
      - 搜索与过滤目标
    """

    FALLBACK_TARGETS: list[str] = [
        "stm32f103rc", "stm32f407vg", "stm32f429zi", "stm32h743zi",
        "stm32l475vg", "stm32g071rb", "nrf52840", "nrf52832",
        "rp2040", "k64f", "lpc1768", "max32625", "lpc55s69",
    ]

    def __init__(self, backend: BackendABC) -> None:
        self._backend: BackendABC = backend
        self._selected_target: str | None = None
        self._installed_packs: list[str] = []

    def list_builtin_targets(self) -> list[tuple[str, str]]:
        """获取 pyOCD 内置芯片目标列表。

        Returns:
            (目标名, 显示名) 元组列表，按名称字母排序。
            若 CLI 调用失败，降级为 FALLBACK_TARGETS 列表。
        """
        try:
            result = subprocess.run(
                ["pyocd", "list", "--targets"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "pyOCD returned non-zero")

            targets: list[tuple[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                name = line.strip().split()[0] if line.strip() else ""
                if name and not name.startswith(" "):
                    targets.append((name, name))

            if not targets:
                raise RuntimeError("empty target list")

            add_log("INFO", f"内置目标: {len(targets)} 个")
            return sorted(targets)

        except Exception as e:  # pylint: disable=broad-exception-caught
            add_log("WARN", f"无法获取内置目标列表，使用内置备用列表: {e}")
            return [(t, t) for t in self.FALLBACK_TARGETS]

    def select_target(self, target_name: str) -> None:
        """设置当前选中的芯片目标。"""
        self._selected_target = target_name

    def get_selected_target(self) -> str | None:
        """返回当前选中的芯片目标。"""
        return self._selected_target

    def list_installed_pack_targets(self) -> list[tuple[str, str]]:
        """获取已安装 CMSIS-Pack 中包含的芯片目标。

        Returns:
            (目标名, 目标名 [Pack]) 元组列表，按名称字母排序。
            无已安装 Pack 时返回空列表。
        """
        try:
            result = subprocess.run(
                ["pyocd", "pack", "show"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if result.returncode != 0:
                return []

            targets: list[tuple[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                match = re.search(r"Part:\s+(\S+)", line)
                if match:
                    name = match.group(1)
                    targets.append((name, f"{name} [Pack]"))

            return sorted(targets)

        except Exception as e:  # pylint: disable=broad-exception-caught
            add_log("WARN", f"无法获取 Pack 目标列表: {e}")
            return []

    def list_all_targets(self) -> list[tuple[str, str]]:
        """获取所有可用目标（内置 + Pack），去重后按名称排序。"""
        builtin = dict(self.list_builtin_targets())
        packs = dict(self.list_installed_pack_targets())
        merged = {**builtin, **packs}
        return sorted(merged.items(), key=lambda x: x[0])

    def search_targets(self, query: str) -> list[tuple[str, str]]:
        """按名称模糊搜索芯片目标。"""
        all_targets = self.list_all_targets()
        q = query.lower()
        return [(k, v) for k, v in all_targets if q in k.lower()]

    def install_pack(self, pack_path: str) -> bool:
        """安装本地 .pack 文件。

        Args:
            pack_path: .pack 文件的绝对路径。

        Returns:
            True 表示安装成功，False 表示安装失败。
        """
        try:
            add_log("INFO", f"正在安装 Pack: {pack_path}")
            result = subprocess.run(
                ["pyocd", "pack", "install", pack_path],
                capture_output=True, text=True, timeout=60, check=False,
            )
            if result.returncode == 0:
                pack_name = pack_path.replace("\\", "/").split("/")[-1]
                self._installed_packs.append(pack_name)
                add_log("DONE", f"Pack 安装成功: {pack_name}")
                return True
            add_log("ERROR", f"Pack 安装失败: {result.stderr.strip()}")
            return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            add_log("ERROR", f"Pack 安装异常: {e}")
            return False

    def install_pack_by_name(self, pack_name: str) -> bool:
        """通过名称从 pyOCD 仓库安装 Pack。

        Args:
            pack_name: Pack 标识符，如 "GigaDevice.GD32F4xx_DFP"。

        Returns:
            True 表示安装成功，False 表示安装失败。
        """
        try:
            add_log("INFO", f"正在安装 Pack: {pack_name}")
            result = subprocess.run(
                ["pyocd", "pack", "install", pack_name],
                capture_output=True, text=True, timeout=60, check=False,
            )
            if result.returncode == 0:
                self._installed_packs.append(pack_name)
                add_log("DONE", f"Pack 安装成功: {pack_name}")
                return True
            add_log("ERROR", f"Pack 安装失败: {result.stderr.strip()}")
            return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            add_log("ERROR", f"Pack 安装异常: {e}")
            return False
