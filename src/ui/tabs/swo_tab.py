"""SWO 标签页 — 回调式 SWV 数据采集。

SWVReader 内部已解析 ITM 数据，通过控制台回调直接获取文本。
"""

from __future__ import annotations

import asyncio

import flet as ft

from src.ui.components.log_view import LogView
from src.ui.theme import Colors, Font, Spacing, standard_divider


class SwoTab:
    """SWO 标签页 — 通过 SWVReader 内置 ITM 解析器获取文本。"""

    def __init__(self, backend, loop, probe_manager, target_manager) -> None:
        self._backend = backend
        self._loop = loop
        self._probe_mgr = probe_manager
        self._target_mgr = target_manager
        self._active = False
        self.log_view = LogView(max_lines=1000)
        self._switch_ref = ft.Ref[ft.Switch]()
        self._baud_ref = ft.Ref[ft.Dropdown]()
        self._sysclk_ref = ft.Ref[ft.Dropdown]()

    def build(self) -> ft.Control:
        self._switch = ft.Switch(
            ref=self._switch_ref, label="SWO 捕获", value=False, on_change=self._on_toggle
        )
        self._sysclk = ft.Dropdown(
            ref=self._sysclk_ref, width=130, dense=True, value="168000000",
            options=[ft.dropdown.Option(v, f"{int(v)//1_000_000} MHz") for v in
                     ["8000000", "16000000", "48000000", "72000000", "84000000",
                      "168000000", "180000000", "480000000"]],
            bgcolor=Colors.BG_ELEVATED,
            border=ft.Border(*[ft.BorderSide(1, Colors.BORDER)] * 4),
            border_radius=4,
        )
        self._baud = ft.Dropdown(
            ref=self._baud_ref, width=130, dense=True, value="400000",
            options=[ft.dropdown.Option(v, f"{int(v)//1000} K") for v in
                     ["200000", "400000", "1000000", "2000000"]],
            bgcolor=Colors.BG_ELEVATED,
            border=ft.Border(*[ft.BorderSide(1, Colors.BORDER)] * 4),
            border_radius=4,
        )

        return ft.Container(content=ft.Column(controls=[
            ft.Text("SWO 串行调试输出", size=Font.Size.HEADING, weight=500, color=Colors.TEXT_PRIMARY),
            ft.Row(controls=[ft.Text("系统时钟:", size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY),
                             self._sysclk, ft.Text("SWO:", size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY),
                             self._baud, self._switch], spacing=Spacing.SM),
            standard_divider(), self.log_view.build()
        ], spacing=Spacing.SM, expand=True), padding=Spacing.XL, expand=True)

    async def _on_toggle(self, e):
        if e.control.value:
            await self.start()
        else:
            await self.stop()

    async def start(self) -> None:
        if self._active:
            return
        try:
            sysclk = int(self._sysclk_ref.current.value or "168000000")
            swo_baud = int(self._baud_ref.current.value or "400000")
            swv = {"system_clock": sysclk, "swo_clock": swo_baud}
            t = self._target_mgr.get_selected_target()
            if not t:
                self.log_view.add_log("ERROR", "请先在 Flash 选项卡中选择芯片")
                self._switch_ref.current.value = False
                self._switch_ref.current.update()
                return
            p = self._probe_mgr.get_selected_probe()
            self.log_view.add_log("INFO", f"正在连接: {t}")
            await asyncio.to_thread(self._backend.connect, t, p.unique_id if p else None, 1_000_000, None, swv)
            await asyncio.to_thread(self._backend.swo_start_callback,
                                    sysclk, swo_baud, self._on_swo_line)
            await asyncio.to_thread(self._backend.reset)
            self._active = True
            self.log_view.add_log("DONE", "SWO 已启动")
        except Exception as ex:
            self.log_view.add_log("ERROR", f"SWO 启动失败: {ex}")
            self._switch_ref.current.value = False
            self._switch_ref.current.update()

    def _on_swo_line(self, line: str) -> None:
        """SWVReader 回调 — 线程安全推送日志。"""
        asyncio.run_coroutine_threadsafe(
            self._add_line(line), self._loop
        )

    async def _add_line(self, line: str) -> None:
        self.log_view.add_log("SWO", line)

    async def stop(self) -> None:
        self._active = False
        try:
            await asyncio.to_thread(self._backend.swo_stop)
        except Exception:
            self.log_view.add_log("WARN", "SWO 停止时出现异常（可能已断开）")

    @property
    def is_active(self) -> bool: return self._active
