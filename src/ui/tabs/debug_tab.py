"""调试标签页 — 目标控制 + 变量监控 + 内存图表 + RTOS。"""

from __future__ import annotations

import asyncio
import struct

import flet as ft

from src.backend.interface import BackendABC
from src.i18n import t
from src.ui.theme import Colors, Font, Spacing, card_container, standard_divider
from src.utils.elf_parser import parse_elf_symbols
from src.utils.logger import add_log

_LINE_COLORS = [Colors.ACCENT_PRIMARY, Colors.ACCENT_COPPER, Colors.INFO, Colors.WARNING, Colors.SUCCESS]
_HISTORY_MAX = 60


class DebugTab:

    def __init__(self, backend: BackendABC, loop: asyncio.AbstractEventLoop):
        self._backend = backend
        self._loop = loop
        self._page: ft.Page | None = None
        self._state_text: ft.Text | None = None
        self._toggle_btn: ft.ElevatedButton | None = None
        self._reset_btn: ft.ElevatedButton | None = None
        self._watches: list[dict] = []
        self._watch_running: bool = False
        self._watch_column: ft.Column | None = None
        self._add_addr: ft.TextField | None = None
        self._add_size: ft.Dropdown | None = None
        self._add_name: ft.TextField | None = None
        self._elf_path: ft.Text | None = None
        self._elf_full_path: str = ""
        self._elf_view_btn: ft.TextButton | None = None
        self._elf_symbols_data: list[dict] = []
        self._chart_canvas: ft.Column | None = None
        self._sample_count: int = 0
        self._rtos_column: ft.Column | None = None

    def build(self) -> ft.Control:
        self._state_text = ft.Text(t("debugUnknown"), size=Font.Size.BODY, color=Colors.TEXT_SECONDARY)
        self._toggle_btn = ft.ElevatedButton(content=ft.Text(""), on_click=lambda _: self._do_toggle())
        self._reset_btn = ft.ElevatedButton(content=ft.Text(t("debugReset")), icon=ft.Icons.RESTART_ALT, on_click=lambda _: self._do_reset())
        self._apply_state()

        self._add_addr = ft.TextField(hint_text="0x20000000", width=130, text_size=12)
        self._add_size = ft.Dropdown(width=80, dense=True, text_size=12, value="4",
            options=[ft.dropdown.Option("1", "u8"), ft.dropdown.Option("2", "u16"), ft.dropdown.Option("4", "u32"), ft.dropdown.Option("4f", "f32")])
        self._add_name = ft.TextField(hint_text=t("debugWatchName"), width=100, text_size=12)
        add_btn = ft.ElevatedButton(content=ft.Text(t("debugWatchAdd"), size=Font.Size.CAPTION), icon=ft.Icons.ADD, on_click=lambda _: self._add_watch())
        self._watch_column = ft.Column(spacing=Spacing.XS)
        self._chart_canvas = ft.Column(spacing=Spacing.XS)
        self._elf_path = ft.Text("", size=Font.Size.CAPTION, color=Colors.TEXT_DIM)
        self._elf_view_btn = ft.TextButton(content=ft.Text(t("debugElfView")), icon=ft.Icons.LIST, visible=False, on_click=lambda _: self._show_symbols())
        self._elf_symbols_data: list[dict] = []
        self._rtos_column = ft.Column(spacing=Spacing.XS)

        return ft.ListView(
            controls=[
                # 1. ELF 符号表（最前面——调试基础）
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugElfTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[
                        ft.ElevatedButton(content=ft.Text(t("debugElfLoad"), size=Font.Size.CAPTION), icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: self._pick_elf()),
                        self._elf_path,
                        ft.Container(expand=True),
                        self._elf_view_btn,
                    ], spacing=Spacing.SM),
                ], spacing=Spacing.SM)),
                # 2. 目标控制
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[ft.Container(width=8, height=8, border_radius=4, bgcolor=Colors.TEXT_DIM), self._state_text], spacing=Spacing.SM),
                    ft.Row(controls=[self._toggle_btn, self._reset_btn], spacing=Spacing.MD),
                ], spacing=Spacing.LG)),
                # 3. 变量监控
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugWatchTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[self._add_name, self._add_addr, self._add_size, add_btn], spacing=Spacing.SM),
                    self._watch_column,
                ], spacing=Spacing.SM)),
                # 4. 内存趋势
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugChartTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    self._chart_canvas,
                ], spacing=Spacing.SM)),
                # 5. RTOS
                card_container(content=ft.Column(controls=[
                    ft.Row(controls=[
                        ft.Text(t("debugRtosTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                        ft.ElevatedButton(content=ft.Text(t("debugRefresh"), size=Font.Size.CAPTION), icon=ft.Icons.REFRESH, on_click=lambda _: self._refresh_rtos()),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self._rtos_column,
                ], spacing=Spacing.SM)),
            ],
            expand=True, spacing=Spacing.LG, padding=Spacing.XXL,
        )

    # ── 目标控制 ─────────────────────────────────────────
    def _apply_state(self) -> None:
        if not self._backend or not self._backend.is_connected:
            self._state_text.value = t("debugNotConnected"); self._state_text.color = Colors.TEXT_SECONDARY
            self._toggle_btn.content.value = t("debugHalt"); self._toggle_btn.icon = ft.Icons.PAUSE
            self._toggle_btn.disabled = True; self._reset_btn.disabled = True
        elif self._backend.is_halted:
            self._state_text.value = t("debugHalted"); self._state_text.color = Colors.WARNING
            self._toggle_btn.content.value = t("debugResume"); self._toggle_btn.icon = ft.Icons.PLAY_ARROW
            self._toggle_btn.disabled = False; self._reset_btn.disabled = False
        else:
            self._state_text.value = t("debugRunning"); self._state_text.color = Colors.SUCCESS
            self._toggle_btn.content.value = t("debugHalt"); self._toggle_btn.icon = ft.Icons.PAUSE
            self._toggle_btn.disabled = False; self._reset_btn.disabled = False

    def _refresh_state(self) -> None:
        self._apply_state()
        self._state_text.update(); self._toggle_btn.update(); self._reset_btn.update()

    def refresh(self) -> None:
        self._refresh_state()

    def _do_toggle(self) -> None:
        try:
            if self._backend.is_halted: self._backend.resume(); add_log("INFO", "目标已恢复运行")
            else: self._backend.halt(); add_log("INFO", "目标已暂停")
        except Exception as e: add_log("ERROR", f"操作失败: {e}")
        self._refresh_state()

    def _do_reset(self) -> None:
        try: self._backend.reset(); add_log("INFO", "目标已复位")
        except Exception as e: add_log("ERROR", f"复位失败: {e}")
        self._refresh_state()

    # ── 变量监控 ─────────────────────────────────────────
    def _add_watch(self) -> None:
        try:
            addr = int(self._add_addr.value, 0)
            size_str = self._add_size.value
            is_float = size_str.endswith("f")
            size = int(size_str.replace("f", ""))
        except (ValueError, AttributeError):
            return
        name = self._add_name.value.strip() or f"0x{addr:08X}"
        self._watches.append({"name": name, "addr": addr, "size": size, "is_float": is_float, "history": []})
        self._rebuild_watch_list()
        if not self._watch_running:
            self._watch_running = True
            self._loop.create_task(self._watch_loop())

    def _rebuild_watch_list(self) -> None:
        self._watch_column.controls.clear()
        hdr = ft.Row(controls=[
            ft.Text(t("debugWatchName"), width=100, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
            ft.Text(t("chipRegionAddress"), width=110, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
            ft.Text(t("debugWatchValue"), size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
            ft.Container(expand=True),
            ft.IconButton(icon=ft.Icons.CLOSE, icon_size=14, on_click=lambda _: self._clear_watches()),
        ], spacing=Spacing.SM)
        self._watch_column.controls.append(hdr)
        self._watch_column.controls.append(standard_divider())
        for w in self._watches:
            self._watch_column.controls.append(ft.Row(controls=[
                ft.Text(w["name"], width=100, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                ft.Text(f"0x{w['addr']:08X}", width=110, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                ft.Text(w.get("value", "—"), size=Font.Size.CAPTION, color=Colors.ACCENT_PRIMARY, font_family=Font.MONO),
            ], spacing=Spacing.SM))
        self._watch_column.update()

    def _clear_watches(self) -> None:
        self._watches.clear(); self._sample_count = 0
        self._rebuild_watch_list()
        self._chart_canvas.controls.clear(); self._chart_canvas.update()

    async def _watch_loop(self) -> None:
        while self._watch_running and self._watches:
            for w in self._watches:
                if not self._backend or not self._backend.is_connected:
                    continue
                try:
                    data = await asyncio.to_thread(self._backend.read_memory, w["addr"], w["size"])
                    if w["is_float"] and w["size"] == 4:
                        val = struct.unpack("<f", data)[0]
                        w["value"] = f"{val:.6f}"; w["val_num"] = val
                    elif w["size"] == 1:
                        w["value"] = f"0x{data[0]:02X} ({data[0]})"; w["val_num"] = data[0]
                    elif w["size"] == 2:
                        val = struct.unpack("<H", data)[0]
                        w["value"] = f"0x{val:04X} ({val})"; w["val_num"] = val
                    elif w["size"] == 4:
                        val = struct.unpack("<I", data)[0]
                        w["value"] = f"0x{val:08X} ({val})"; w["val_num"] = val
                    else:
                        w["val_num"] = 0
                except Exception:
                    w["value"] = "err"; w["val_num"] = None
            self._sample_count += 1
            self._rebuild_watch_list()
            self._update_chart()
            await asyncio.sleep(1)

    def _update_chart(self) -> None:
        for w in self._watches:
            if not w.get("history"):
                w["history"] = []
            v = w.get("val_num")
            if v is not None:
                w["history"].append(v)
            if len(w["history"]) > _HISTORY_MAX:
                w["history"] = w["history"][-_HISTORY_MAX:]

        self._chart_canvas.controls.clear()
        for i, watch in enumerate(self._watches):
            hist = watch.get("history", [])
            vals = [v for v in hist if isinstance(v, (int, float))]
            if not vals: continue
            color = _LINE_COLORS[i % len(_LINE_COLORS)]
            # 趋势摘要
            label = f"{watch['name']}: min={min(vals)}  max={max(vals)}  cur={vals[-1]}"
            self._chart_canvas.controls.append(ft.Text(label, size=Font.Size.CAPTION, color=color, font_family=Font.MONO))
            # 条形趋势图
            bars = ft.Row(spacing=1)
            vmax = max(vals); vmin = min(vals)
            if vmax == vmin: vmax += 1
            for v in vals[-40:]:
                h = max(2, int((v - vmin) / (vmax - vmin) * 20))
                bars.controls.append(ft.Container(width=4, height=h, bgcolor=color, border_radius=1))
            self._chart_canvas.controls.append(bars)
        self._chart_canvas.update()

    # ── ELF 符号加载 ─────────────────────────────────────
    def _pick_elf(self) -> None:
        self._loop.create_task(self._do_pick_elf())

    async def _do_pick_elf(self) -> None:
        picker = ft.FilePicker()
        files = await picker.pick_files(dialog_title="Select ELF file", allowed_extensions=["elf", "axf"])
        if files and files[0].path:
            import os
            self._elf_full_path = files[0].path
            self._elf_path.value = os.path.basename(files[0].path); self._elf_path.update()
            self._load_elf(files[0].path)

    def _load_elf(self, path: str) -> None:
        if not path: return
        try:
            symbols = parse_elf_symbols(path)
            add_log("INFO", f"从 ELF 加载 {len(symbols)} 个全局变量符号")
            self._elf_symbols_data = symbols
            self._elf_view_btn.visible = True
            self._elf_view_btn.update()
        except Exception as e:
            add_log("ERROR", f"ELF 解析失败: {e}")

    def _show_symbols(self) -> None:
        """弹出对话框展示符号表。"""
        if not self._page or not self._elf_symbols_data:
            return
        rows: list[ft.Control] = []
        for s in self._elf_symbols_data[:200]:  # 最多 200 个
            rows.append(ft.Row(controls=[
                ft.Text(s["name"], width=180, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                ft.Text(f"0x{s['addr']:08X}", width=110, size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY, font_family=Font.MONO),
                ft.Text(str(s["size"]), width=60, size=Font.Size.CAPTION, color=Colors.TEXT_DIM),
                ft.IconButton(icon=ft.Icons.ADD, icon_size=14, icon_color=Colors.ACCENT_PRIMARY,
                              on_click=lambda e, a=s["addr"], n=s["name"], sz=s["size"]: self._watch_symbol(a, n, sz)),
            ], spacing=Spacing.SM))
        dlg = ft.AlertDialog(
            title=ft.Text(f"ELF Symbols ({len(self._elf_symbols_data)})"),
            content=ft.Container(content=ft.Column(controls=rows, spacing=Spacing.XS, scroll=ft.ScrollMode.AUTO), width=600, height=500),
            actions=[ft.TextButton(content=ft.Text("Close"), on_click=lambda _: self._close_dialog(dlg))],
        )
        self._page.dialog = dlg
        dlg.open = True
        self._page.update()

    def _close_dialog(self, dlg) -> None:
        dlg.open = False
        if self._page:
            self._page.update()

    def _watch_symbol(self, addr: int, name: str, size: int) -> None:
        size = max(size, 1) if size < 16 else 4
        self._watches.append({"name": name, "addr": addr, "size": size, "is_float": False, "history": []})
        self._rebuild_watch_list()
        if not self._watch_running:
            self._watch_running = True
            self._loop.create_task(self._watch_loop())

    # ── RTOS 线程 ────────────────────────────────────────
    def _refresh_rtos(self) -> None:
        if not self._backend or not self._backend.is_connected:
            return
        try:
            elf = self._elf_full_path
            threads = self._backend.get_rtos_threads(elf)
            self._rtos_column.controls.clear()
            if not threads:
                self._rtos_column.controls.append(ft.Text(t("debugRtosNone"), size=Font.Size.CAPTION, color=Colors.TEXT_DIM))
            else:
                hdr = ft.Row(controls=[
                    ft.Text(t("debugWatchName"), width=140, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
                    ft.Text("Prio", width=50, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
                    ft.Text("State", width=80, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
                    ft.Text("Stack", width=100, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
                    ft.Text("TCB", width=100, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
                ], spacing=Spacing.SM)
                self._rtos_column.controls.append(hdr)
                self._rtos_column.controls.append(standard_divider())
                for thread in threads:
                    marker = "* " if thread["is_current"] else "  "
                    color = Colors.ACCENT_COPPER if thread["is_current"] else Colors.TEXT_PRIMARY
                    self._rtos_column.controls.append(ft.Row(controls=[
                        ft.Text(marker + thread["name"], width=140, size=Font.Size.CAPTION, color=color, font_family=Font.MONO),
                        ft.Text(thread["priority"], width=50, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY),
                        ft.Text(thread["state"], width=80, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY),
                        ft.Text(thread["stack_usage"], width=100, size=Font.Size.CAPTION, color=Colors.TEXT_DIM, font_family=Font.MONO),
                        ft.Text(thread.get("tcb", "—"), width=100, size=Font.Size.CAPTION, color=Colors.TEXT_DIM, font_family=Font.MONO),
                    ], spacing=Spacing.SM))
            self._rtos_column.update()
        except Exception:
            import traceback
            add_log("ERROR", f"RTOS 读取失败:\n{traceback.format_exc()}")
