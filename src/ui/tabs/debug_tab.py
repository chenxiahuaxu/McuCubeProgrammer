"""调试标签页 — 目标控制 + 变量监控 + RTOS 线程。"""

from __future__ import annotations

import asyncio
import struct

import flet as ft
import flet.canvas as cv

from src.backend.interface import BackendABC
from src.i18n import t
from src.ui.theme import Colors, Font, Spacing, card_container, standard_divider
from src.utils.elf_parser import parse_elf_symbols
from src.utils.logger import add_log

_HISTORY_MAX = 300


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
        self._trend_dlg: ft.AlertDialog | None = None
        self._trend_name: str = ""
        self._trend_canvas: cv.Canvas | None = None
        self._trend_info: ft.Text | None = None
        self._add_addr: ft.TextField | None = None
        self._add_size: ft.Dropdown | None = None
        self._add_name: ft.TextField | None = None
        self._elf_path: ft.Text | None = None
        self._elf_full_path: str = ""
        self._elf_view_btn: ft.ElevatedButton | None = None
        self._elf_symbols_data: list[dict] = []
        # chart canvas removed — trend shown via dialog per watch
        self._rtos_column: ft.Column | None = None
        self._rtos_auto: bool = False

    def build(self) -> ft.Control:
        self._state_text = ft.Text(t("debugUnknown"), size=Font.Size.BODY, color=Colors.TEXT_SECONDARY)
        self._toggle_btn = ft.ElevatedButton(content=ft.Text(""), on_click=lambda _: self._do_toggle())
        self._reset_btn = ft.ElevatedButton(content=ft.Text(t("debugReset")), icon=ft.Icons.RESTART_ALT, on_click=lambda _: self._do_reset())
        self._apply_state()

        self._add_addr = ft.TextField(hint_text="0x20000000", width=130, text_size=12)
        self._add_size = ft.Dropdown(width=100, dense=True, text_size=12, value="4",
            options=[ft.dropdown.Option("1", "u8"), ft.dropdown.Option("2", "u16"), ft.dropdown.Option("4", "u32"), ft.dropdown.Option("4f", "f32")])
        self._add_name = ft.TextField(hint_text=t("debugWatchName"), width=100, text_size=12)
        add_btn = ft.ElevatedButton(content=ft.Text(t("debugWatchAdd"), size=Font.Size.CAPTION), icon=ft.Icons.ADD, on_click=lambda _: self._add_watch())
        self._watch_column = ft.Column(spacing=Spacing.XS)
        # trend chart is built per-watch in dialog
        self._elf_path = ft.Text("", size=Font.Size.CAPTION, color=Colors.TEXT_DIM, no_wrap=True, tooltip="")
        self._elf_view_btn = ft.ElevatedButton(content=ft.Text(t("debugElfView")), icon=ft.Icons.LIST, disabled=True, on_click=lambda _: self._show_symbols())
        self._elf_symbols_data: list[dict] = []
        self._rtos_column = ft.Column(spacing=Spacing.XS)

        return ft.ListView(
            controls=[
                # 1. ELF 符号表（最前面——调试基础）
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugElfTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[
                        ft.ElevatedButton(content=ft.Text(t("debugElfLoad"), size=Font.Size.CAPTION), icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: self._pick_elf()),
                        ft.Row(controls=[self._elf_path], scroll=ft.ScrollMode.AUTO, width=300,
                               height=30, vertical_alignment=ft.CrossAxisAlignment.START),
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
                # 4. RTOS
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
            name = w["name"]
            self._watch_column.controls.append(ft.Row(controls=[
                ft.Text(name, width=100, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                ft.Text(f"0x{w['addr']:08X}", width=110, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                ft.Text(w.get("value", "—"), size=Font.Size.CAPTION, color=Colors.ACCENT_PRIMARY, font_family=Font.MONO),
                ft.IconButton(icon=ft.Icons.BAR_CHART, icon_size=14, icon_color=Colors.ACCENT_COPPER,
                              on_click=lambda e, n=name: self._show_trend(n)),
            ], spacing=Spacing.SM))
        self._watch_column.update()

    def _clear_watches(self) -> None:
        self._watches.clear()
        self._rebuild_watch_list()

    async def _watch_loop(self) -> None:
        while self._watch_running and self._watches:
            # 暂停时跳过采样
            if self._backend and self._backend.is_halted:
                self._rebuild_watch_list()
                await asyncio.sleep(0.5)
                continue
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
            # 记录历史（用于趋势弹窗）
            for w in self._watches:
                if not w.get("history"):
                    w["history"] = []
                v = w.get("val_num")
                if v is not None:
                    w["history"].append(v)
                if len(w["history"]) > _HISTORY_MAX:
                    w["history"] = w["history"][-_HISTORY_MAX:]
            self._rebuild_watch_list()
            # 自动刷新趋势弹窗（暂停时不绘制）
            if self._trend_name and self._trend_canvas and not self._backend.is_halted:
                self._refresh_waveform_data()
            await asyncio.sleep(0.5)

    def _show_trend(self, name: str) -> None:
        """弹出波形图对话框，Canvas 和 Info 只创建一次，之后原位刷新。"""
        self._trend_name = name
        W = 800; H = 260

        self._trend_info = ft.Text(
            f"{name}:  —", size=Font.Size.CAPTION,
            color=Colors.TEXT_DIM, font_family=Font.MONO)
        self._trend_canvas = cv.Canvas(shapes=[], width=W, height=H)

        scroll_row = ft.Row(
            [self._trend_canvas],
            scroll=ft.ScrollMode.ADAPTIVE,
            height=H + 12,
        )
        content = ft.Column([
            self._trend_info,
            ft.Divider(height=6),
            scroll_row,
        ], spacing=Spacing.XS, scroll=ft.ScrollMode.AUTO, width=560, height=400)

        self._trend_dlg = ft.AlertDialog(
            modal=True,
            open=True,
            title=ft.Text(f"Waveform — {name}"),
            content=content,
            actions=[ft.ElevatedButton(content=ft.Text("Close"), on_click=lambda _: self._close_trend())],
        )
        self._page.show_dialog(self._trend_dlg)
        # 首次填充数据（必须在 dialog 添加到 page 之后）
        self._refresh_waveform_data()

    def _refresh_waveform_data(self) -> None:
        """原位更新 Canvas 形状 + Info 文本（不替换 dialog content）。"""
        if not self._trend_name or not self._trend_canvas:
            return
        watch = next((w for w in self._watches if w["name"] == self._trend_name), None)
        if not watch:
            return
        hist = watch.get("history", [])
        vals = [v for v in hist if isinstance(v, (int, float))]

        W = 800; H = 260; PAD = 28; MAX_DOTS = 120
        COPPER = "#D99A5A"; GREEN = "#26A641"
        shapes: list[cv.Shape] = []

        def y_of(v, vmin, span):
            return PAD + (H - 2 * PAD) * (1 - (v - vmin) / span)

        if vals:
            vmax = max(vals); vmin = min(vals)
            span = vmax - vmin if vmax != vmin else 1
            if self._trend_info:
                self._trend_info.value = f"{self._trend_name}:  min={vmin}  max={vmax}  cur={vals[-1]}"
            recent = vals[-MAX_DOTS:]
            bottom_y = y_of(vmin, vmin, span)
            n = len(recent)
            x_step = (W - 2 * PAD) / max(n - 1, 1)

            # 1. 边框
            shapes.append(cv.Rect(PAD, PAD, W - 2 * PAD, H - 2 * PAD,
                paint=ft.Paint(color="#30D99A5A", stroke_width=1)))
            # 2. 网格线
            grid_paint = ft.Paint(color="#20D99A5A", stroke_width=0.5)
            for pct in [0.25, 0.5, 0.75]:
                y = PAD + (H - 2 * PAD) * (1 - pct)
                shapes.append(cv.Line(PAD, y, W - PAD, y, paint=grid_paint))
            # 3. 像素坐标
            pts = [(PAD + i * x_step, y_of(v, vmin, span)) for i, v in enumerate(recent)]

            if n >= 2:
                # 4. 填充
                fill_path = [cv.Path.MoveTo(pts[0][0], pts[0][1])]
                for px, py in pts[1:]:
                    fill_path.append(cv.Path.LineTo(px, py))
                fill_path.append(cv.Path.LineTo(pts[-1][0], bottom_y))
                fill_path.append(cv.Path.LineTo(pts[0][0], bottom_y))
                fill_path.append(cv.Path.Close())
                shapes.append(cv.Path(elements=fill_path,
                    paint=ft.Paint(color="#26D99A5A", style=ft.PaintingStyle.FILL)))
                # 5. 连线
                shapes.append(cv.Points(points=pts, point_mode=cv.PointMode.POLYGON,
                    paint=ft.Paint(color=GREEN, stroke_width=2, anti_alias=True)))
                # 6. 圆点（每 3 个）
                for i in range(0, n, 3):
                    px, py = pts[i]
                    shapes.append(cv.Circle(px, py, 3,
                        paint=ft.Paint(color=GREEN, style=ft.PaintingStyle.FILL)))
            elif n == 1:
                px, py = pts[0]
                shapes.append(cv.Circle(px, py, 4,
                    paint=ft.Paint(color=GREEN, style=ft.PaintingStyle.FILL)))

        self._trend_canvas.shapes = shapes
        self._trend_canvas.update()
        if self._trend_info:
            if not vals:
                self._trend_info.value = f"{self._trend_name}:  0 samples"
            self._trend_info.update()

    def _close_trend(self) -> None:
        """关闭趋势弹窗并清空自动刷新状态。"""
        self._trend_name = ""
        if self._trend_dlg:
            self._trend_dlg.open = False
            self._trend_dlg.update()
            self._trend_dlg = None
        self._trend_canvas = None
        self._trend_info = None
        if self._page:
            self._page.update()

    # ── ELF 符号加载 ─────────────────────────────────────
    def _pick_elf(self) -> None:
        self._loop.create_task(self._do_pick_elf())

    async def _do_pick_elf(self) -> None:
        picker = ft.FilePicker()
        files = await picker.pick_files(dialog_title="Select ELF file", allowed_extensions=["elf", "axf"])
        if files and files[0].path:
            self._elf_full_path = files[0].path
            self._elf_path.value = files[0].path; self._elf_path.tooltip = files[0].path; self._elf_path.update()
            self._load_elf(files[0].path)

    def _load_elf(self, path: str) -> None:
        if not path: return
        try:
            symbols = parse_elf_symbols(path)
            add_log("INFO", f"从 ELF 加载 {len(symbols)} 个全局变量符号")
            self._elf_symbols_data = symbols
            self._elf_view_btn.disabled = False
            self._elf_view_btn.update()
            # ELF 加载成功后自动触发 RTOS 刷新
            self._refresh_rtos()
        except Exception as e:
            add_log("ERROR", f"ELF 解析失败: {e}")

    def _show_symbols(self) -> None:
        add_log("INFO", f"查看符号被点击，符号数: {len(self._elf_symbols_data)}, page: {self._page is not None}")
        if not self._elf_symbols_data:
            add_log("WARN", "符号表为空")
            return
        if not self._page:
            add_log("WARN", "page 未设置")
            return
        self._loop.create_task(self._do_show_symbols())

    async def _do_show_symbols(self) -> None:
        try:
            rows: list[ft.Control] = []
            for s in self._elf_symbols_data[:200]:
                rows.append(ft.Row(controls=[
                    ft.Text(s["name"], width=200, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                    ft.Text(f"0x{s['addr']:08X}", width=120, size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY, font_family=Font.MONO),
                    ft.Text(str(s["size"]), width=60, size=Font.Size.CAPTION, color=Colors.TEXT_DIM),
                    ft.IconButton(icon=ft.Icons.ADD, icon_size=14, icon_color=Colors.ACCENT_PRIMARY,
                                  on_click=lambda e, a=s["addr"], n=s["name"], sz=s["size"]: self._watch_symbol(a, n, sz)),
                ], spacing=Spacing.SM))
            content_col = ft.Column(controls=rows, spacing=Spacing.XS, scroll=ft.ScrollMode.AUTO, width=560, height=460)
            dlg = ft.AlertDialog(
                modal=True,
                open=True,
                title=ft.Text(f"ELF Symbols ({len(self._elf_symbols_data)})"),
                content=content_col,
                actions=[ft.ElevatedButton(content=ft.Text("Close"), on_click=lambda _: self._close_dialog(dlg))],
            )
            self._page.show_dialog(dlg)
            add_log("INFO", "符号弹窗已设置")
        except Exception as e:
            add_log("ERROR", f"弹窗失败: {e}")

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

        # 首次加载后启动自动刷新
        if not self._rtos_auto:
            self._rtos_auto = True
            self._loop.create_task(self._rtos_loop())

    async def _rtos_loop(self) -> None:
        while self._rtos_auto:
            self._refresh_rtos()
            await asyncio.sleep(2)
