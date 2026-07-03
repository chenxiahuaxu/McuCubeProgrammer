"""终端风格日志视图 — Monospace 字体 + 彩色级别标记 + 自动滚动。

共享实例：FlashTab 和 LogTab 引用同一个 LogView。
"""

from __future__ import annotations

from typing import ClassVar

import flet as ft

from src.ui.theme import Colors, Font


class LogView:
    """终端风格日志视图。

    使用 ft.ListView 虚拟化渲染，支持等宽字体、彩色级别标记、
    自动滚动、行数上限、批量导入、纯文本导出。

    FlashTab 和 LogTab 共享同一个 LogView 实例。
    """

    _COLOR_MAP: ClassVar[dict[str, str]] = {
        "INFO": Colors.LOG_INFO,
        "WARN": Colors.LOG_WARN,
        "ERROR": Colors.LOG_ERROR,
        "DONE": Colors.LOG_DONE,
        "DEBUG": Colors.LOG_DEBUG,
    }

    def __init__(self, max_lines: int = 500) -> None:
        self.max_lines = max_lines
        self._list_ref = ft.Ref[ft.ListView]()

    def build(self) -> ft.Control:
        """返回日志视图控件树。"""
        self._list = ft.ListView(
            ref=self._list_ref,
            expand=True,
            spacing=2,
            auto_scroll=True,
            controls=[],
        )
        return self._list

    # ── 公共方法 ─────────────────────────────────────────

    def add_log(self, level: str, message: str) -> None:
        """添加一条日志。

        Args:
            level:   日志级别 (INFO/WARN/ERROR/DONE/DEBUG).
            message: 日志内容。
        """
        color = self._COLOR_MAP.get(level, Colors.TEXT_SECONDARY)
        # 级别右对齐到 5 字符: " INFO", " WARN", "ERROR", " DONE", "DEBUG"
        padded_level: str = f"{level:>5}"
        text = ft.Text(
            value=f"{padded_level}  {message}",
            size=Font.Size.LOG,
            font_family=Font.MONO,
            color=color,
            selectable=True,
        )
        self._list_ref.current.controls.append(text)

        # 行数上限
        if len(self._list_ref.current.controls) > self.max_lines:
            self._list_ref.current.controls = self._list_ref.current.controls[
                -self.max_lines:
            ]

        self._list_ref.current.update()

    def add_batch(self, entries: list[tuple[str, str]]) -> None:
        """批量添加日志条目。"""
        for level, message in entries:
            self.add_log(level, message)

    def clear(self) -> None:
        """清空所有日志。"""
        if self._list_ref.current:
            self._list_ref.current.controls.clear()
            self._list_ref.current.update()

    def export(self) -> str:
        """导出全部日志为纯文本。"""
        if not self._list_ref.current:
            return ""
        lines: list[str] = []
        for ctrl in self._list_ref.current.controls:
            if isinstance(ctrl, ft.Text):
                lines.append(ctrl.value or "")
        return "\n".join(lines)
