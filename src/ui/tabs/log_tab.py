"""日志标签页 — 全屏日志视图 + 清除/导出工具栏。

与 FlashTab 共享同一个 LogView 实例。
"""

from __future__ import annotations

import flet as ft

from src.ui.components.log_view import LogView
from src.ui.theme import Colors, Font, Spacing, standard_divider


class LogTab:
    """日志标签页。

    全屏展示日志视图，提供清除和导出功能。
    日志数据与 FlashTab 共享（通过同一个 LogView 实例）。
    """

    def __init__(self, log_view: LogView, page: ft.Page) -> None:
        self.log_view = log_view
        self.page = page

    def build(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    # 工具栏
                    ft.Row(
                        controls=[
                            ft.Text(
                                "日志",
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.FILE_DOWNLOAD,
                                        tooltip="导出日志",
                                        on_click=self._on_export,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLEAR_ALL,
                                        tooltip="清空日志",
                                        on_click=self._on_clear,
                                    ),
                                ],
                                spacing=Spacing.XS,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    standard_divider(),
                    # 日志视图（复用 LogView 实例）
                    self.log_view.build(),
                ],
                spacing=Spacing.SM,
                expand=True,
            ),
            padding=Spacing.XL,
            expand=True,
        )

    def _on_clear(self, e: ft.ControlEvent) -> None:
        self.log_view.clear()

    def _on_export(self, e: ft.ControlEvent) -> None:
        import tempfile
        text = self.log_view.export()
        # 保存到临时文件
        path = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ).name
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        # 复制到剪贴板
        import pyperclip
        pyperclip.copy(text)
        self.log_view.add_log("DONE", f"日志已导出: {path} ({len(text)} 字符, 已复制到剪贴板)")
