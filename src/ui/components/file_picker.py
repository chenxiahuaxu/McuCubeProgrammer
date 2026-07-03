"""固件文件选择器组件 — 封装 ft.FilePicker。

Flet 0.85: FilePicker 必须通过 page.overlay.append() 注册，
pick_files() 现在返回可 await 的协程。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from src.ui.theme import Colors, Font, Spacing
from src.utils.config import load as load_config


class FirmwareFilePicker:
    """固件文件选择器。

    Flet 0.85 中 FilePicker.pick_files() 同步返回选中文件列表。
    """

    ALLOWED_EXTENSIONS: list[str] = ["bin", "hex", "elf", "axf"]

    def __init__(
        self,
        page: ft.Page,
        on_file_selected: Callable[[str], None],
    ) -> None:
        self.page = page
        self.on_file_selected = on_file_selected
        self._path_ref = ft.Ref[ft.Text]()
        self.selected_path: str | None = None

        self._picker = ft.FilePicker()

    def build(self) -> ft.Control:
        return ft.Column(
            controls=[
                ft.ElevatedButton(
                    content=ft.Text("选择固件"),
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=self._pick_file,
                ),
                ft.Text(
                    ref=self._path_ref,
                    value="未选择文件",
                    size=Font.Size.CAPTION,
                    color=Colors.TEXT_DIM,
                ),
            ],
            spacing=Spacing.XS,
        )

    def restore_last(self) -> None:
        """从配置文件恢复上次固件路径。"""
        import os
        path = load_config().get("firmware_path", "")
        if path and os.path.isfile(path):
            self.selected_path = path
            self._path_ref.current.value = path
            self._path_ref.current.color = Colors.SUCCESS
            self._path_ref.current.update()
            self.on_file_selected(path)

    async def _pick_file(self, e: ft.ControlEvent) -> None:
        files = await self._picker.pick_files(
            dialog_title="选择固件文件",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=self.ALLOWED_EXTENSIONS,
            allow_multiple=False,
        )
        if files and len(files) > 0:
            self.selected_path = files[0].path or ""
            if self._path_ref.current:
                self._path_ref.current.value = self.selected_path
                self._path_ref.current.color = Colors.SUCCESS
                self._path_ref.current.update()
            self.on_file_selected(self.selected_path)

    def get_path(self) -> str | None:
        return self.selected_path

    def clear(self) -> None:
        self.selected_path = None
        if self._path_ref.current:
            self._path_ref.current.value = "未选择文件"
            self._path_ref.current.color = Colors.TEXT_DIM
            self._path_ref.current.update()
