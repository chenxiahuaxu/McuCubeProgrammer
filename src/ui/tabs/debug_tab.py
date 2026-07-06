"""调试标签页 — 目标控制（暂停/继续/复位）。"""

from __future__ import annotations

import flet as ft

from src.backend.interface import BackendABC
from src.i18n import t
from src.ui.theme import Colors, Font, Spacing, card_container
from src.utils.logger import add_log


class DebugTab:
    """调试标签页 — 暂停 / 继续 / 复位。"""

    def __init__(self, backend: BackendABC):
        self._backend = backend
        self._state_text: ft.Text | None = None
        self._halt_btn: ft.ElevatedButton | None = None
        self._resume_btn: ft.ElevatedButton | None = None
        self._reset_btn: ft.ElevatedButton | None = None

    def build(self) -> ft.Control:
        self._state_text = ft.Text(
            t("debugUnknown"), size=Font.Size.BODY, color=Colors.TEXT_SECONDARY,
        )

        self._halt_btn = ft.ElevatedButton(
            content=ft.Text(t("debugHalt")),
            icon=ft.Icons.PAUSE,
            on_click=lambda _: self._do_halt(),
        )
        self._resume_btn = ft.ElevatedButton(
            content=ft.Text(t("debugResume")),
            icon=ft.Icons.PLAY_ARROW,
            on_click=lambda _: self._do_resume(),
        )
        self._reset_btn = ft.ElevatedButton(
            content=ft.Text(t("debugReset")),
            icon=ft.Icons.RESTART_ALT,
            on_click=lambda _: self._do_reset(),
        )

        self._apply_state()

        return ft.ListView(
            controls=[
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(t("debugTitle"), size=Font.Size.HEADING,
                                    weight=600, color=Colors.ACCENT_COPPER),
                            ft.Row(
                                controls=[
                                    ft.Container(width=8, height=8, border_radius=4,
                                                  bgcolor=Colors.TEXT_DIM),
                                    self._state_text,
                                ],
                                spacing=Spacing.SM,
                            ),
                            ft.Row(
                                controls=[
                                    self._halt_btn,
                                    self._resume_btn,
                                    self._reset_btn,
                                ],
                                spacing=Spacing.MD,
                            ),
                        ],
                        spacing=Spacing.LG,
                    ),
                ),
            ],
            expand=True,
            spacing=Spacing.LG,
            padding=Spacing.XXL,
        )

    def _apply_state(self) -> None:
        """设置控件属性，不调 update（用于构建时）。"""
        if not self._backend or not self._backend.is_connected:
            self._state_text.value = t("debugNotConnected")
            self._state_text.color = Colors.TEXT_SECONDARY
            self._halt_btn.disabled = True
            self._resume_btn.disabled = True
            self._reset_btn.disabled = True
        elif self._backend.is_halted:
            self._state_text.value = t("debugHalted")
            self._state_text.color = Colors.WARNING
            self._halt_btn.disabled = True
            self._resume_btn.disabled = False
            self._reset_btn.disabled = False
        else:
            self._state_text.value = t("debugRunning")
            self._state_text.color = Colors.SUCCESS
            self._halt_btn.disabled = False
            self._resume_btn.disabled = True
            self._reset_btn.disabled = False

    def _refresh_state(self) -> None:
        self._apply_state()
        self._state_text.update()
        self._halt_btn.update()
        self._resume_btn.update()
        self._reset_btn.update()

    def refresh(self) -> None:
        """公开方法：外部触发状态刷新（标签页切换时）。"""
        self._refresh_state()

    def _do_halt(self) -> None:
        try:
            self._backend.halt()
            add_log("INFO", "目标已暂停")
        except Exception as e:
            add_log("ERROR", f"暂停失败: {e}")
        self._refresh_state()

    def _do_resume(self) -> None:
        try:
            self._backend.resume()
            add_log("INFO", "目标已恢复运行")
        except Exception as e:
            add_log("ERROR", f"恢复失败: {e}")
        self._refresh_state()

    def _do_reset(self) -> None:
        try:
            self._backend.reset()
            add_log("INFO", "目标已复位")
        except Exception as e:
            add_log("ERROR", f"复位失败: {e}")
        self._refresh_state()
