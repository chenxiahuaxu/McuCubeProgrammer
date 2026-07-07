"""烧录操作面板 — 擦除/烧录/取消按钮 + 进度条 + 状态文字。

通过回调与 FlashTab 交互，组件本身不导入逻辑层。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from src.i18n import t
from src.ui.theme import Colors, Font, Spacing


class FlashPanel:  # pylint: disable=too-many-instance-attributes
    """烧录操作面板。

    包含擦除模式选择器、擦除按钮、烧录按钮、取消按钮、进度条、状态文字。
    通过回调函数注入操作逻辑。
    """

    def __init__(
        self,
        on_erase: Callable[[], None],
        on_flash: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self.on_erase = on_erase
        self.on_flash = on_flash
        self.on_cancel = on_cancel
        self._erase_btn_ref = ft.Ref[ft.OutlinedButton]()
        self._flash_btn_ref = ft.Ref[ft.FilledButton]()
        self._cancel_btn_ref = ft.Ref[ft.OutlinedButton]()
        self._progress_ref = ft.Ref[ft.ProgressBar]()
        self._status_ref = ft.Ref[ft.Text]()
        self._erase_mode_ref = ft.Ref[ft.RadioGroup]()
        self._erase_mode_row_ref = ft.Ref[ft.Row]()

    def build(self) -> ft.Control:
        """返回烧录面板控件树。"""
        self._erase_mode = ft.RadioGroup(
            ref=self._erase_mode_ref,
            value="sector",
            content=ft.Row(
                ref=self._erase_mode_row_ref,
                controls=[
                    ft.Radio(
                        value="sector",
                        label=t("eraseModeSector"),
                        fill_color=Colors.ACCENT_PRIMARY,
                    ),
                    ft.Radio(
                        value="chip",
                        label=t("eraseModeChip"),
                        fill_color=Colors.ACCENT_PRIMARY,
                    ),
                ],
                spacing=Spacing.LG,
            ),
        )
        self._erase_btn = ft.OutlinedButton(
            ref=self._erase_btn_ref,
            content=ft.Text(t("flashErase")),
            icon=ft.Icons.DELETE_FOREVER,
            on_click=lambda e: self.on_erase(),
        )
        self._flash_btn = ft.FilledButton(
            ref=self._flash_btn_ref,
            content=ft.Text(t("flashStart")),
            icon=ft.Icons.FLASH_ON,
            on_click=lambda e: self.on_flash(),
        )
        self._cancel_btn = ft.OutlinedButton(
            ref=self._cancel_btn_ref,
            content=ft.Text(t("flashCancel")),
            icon=ft.Icons.CANCEL,
            visible=False,
            on_click=lambda e: self.on_cancel(),
        )
        self._progress = ft.ProgressBar(
            ref=self._progress_ref,
            width=600,
            value=0.0,
            color=Colors.ACCENT_PRIMARY,
            bgcolor=Colors.BG_ELEVATED,
        )
        self._status = ft.Text(
            ref=self._status_ref,
            value=t("flashReady"),
            size=Font.Size.CAPTION,
            color=Colors.SUCCESS,
        )

        return ft.Column(
            controls=[
                ft.Text(
                    t("eraseModeLabel"),
                    size=Font.Size.CAPTION,
                    color=Colors.TEXT_SECONDARY,
                ),
                self._erase_mode,
                ft.Row(
                    controls=[self._erase_btn, self._flash_btn, self._cancel_btn],
                    spacing=Spacing.SM,
                ),
                self._progress,
                self._status,
            ],
            spacing=Spacing.SM,
        )

    @property
    def erase_chip(self) -> bool:
        """True = 全片擦除, False = 仅擦除所需扇区。"""
        return self._erase_mode_ref.current.value == "chip"

    # ── 公共方法 ─────────────────────────────────────────

    def set_running(self, running: bool) -> None:
        """切换运行/就绪状态。"""
        self._flash_btn_ref.current.disabled = running
        self._erase_btn_ref.current.disabled = running
        self._cancel_btn_ref.current.visible = running
        self._erase_mode_ref.current.disabled = running
        if running:
            self._progress_ref.current.value = 0.0
            self._status_ref.current.value = ""
        self._flash_btn_ref.current.update()
        self._erase_btn_ref.current.update()
        self._cancel_btn_ref.current.update()
        self._erase_mode_ref.current.update()
        self._progress_ref.current.update()
        self._status_ref.current.update()

    def set_progress(self, value: float, message: str) -> None:
        """更新进度条和状态文字。"""
        self._progress_ref.current.value = value
        self._status_ref.current.value = message
        self._status_ref.current.color = Colors.INFO
        self._progress_ref.current.update()
        self._status_ref.current.update()

    def set_status(self, message: str, *, is_error: bool = False) -> None:
        """仅更新状态文字。"""
        self._status_ref.current.value = message
        self._status_ref.current.color = Colors.ERROR if is_error else Colors.TEXT_PRIMARY
        self._status_ref.current.update()

    def set_complete(self, success: bool, message: str) -> None:
        """完成后的最终状态 — 恢复按钮、显示结果。"""
        self.set_running(False)
        self._status_ref.current.value = message
        self._status_ref.current.color = Colors.SUCCESS if success else Colors.ERROR
        self._progress_ref.current.value = 1.0 if success else self._progress_ref.current.value
        self._status_ref.current.update()
        self._progress_ref.current.update()
