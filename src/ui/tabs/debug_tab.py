"""调试标签页 — 目标控制 + 变量监控。"""

from __future__ import annotations

import asyncio
import struct

import flet as ft

from src.backend.interface import BackendABC
from src.i18n import t
from src.ui.theme import Colors, Font, Spacing, card_container, standard_divider
from src.utils.elf_parser import parse_elf_symbols
from src.utils.logger import add_log


class DebugTab:
    """调试标签页 — 暂停 / 继续 / 复位 + 变量监控。"""

    def __init__(self, backend: BackendABC, loop: asyncio.AbstractEventLoop, page: ft.Page):
        self._backend = backend
        self._loop = loop
        self._page = page
        self._state_text: ft.Text | None = None
        self._halt_btn: ft.ElevatedButton | None = None
        self._resume_btn: ft.ElevatedButton | None = None
        self._reset_btn: ft.ElevatedButton | None = None
        # 变量监控
        self._watches: list[dict] = []
        self._watch_running: bool = False
        self._watch_column: ft.Column | None = None
        self._add_addr: ft.TextField | None = None
        self._add_size: ft.Dropdown | None = None
        self._add_name: ft.TextField | None = None
        self._elf_path: ft.TextField | None = None
        self._elf_symbols: ft.Column | None = None

    def build(self) -> ft.Control:
        self._state_text = ft.Text(t("debugUnknown"), size=Font.Size.BODY, color=Colors.TEXT_SECONDARY)
        self._halt_btn = ft.ElevatedButton(content=ft.Text(t("debugHalt")), icon=ft.Icons.PAUSE, on_click=lambda _: self._do_halt())
        self._resume_btn = ft.ElevatedButton(content=ft.Text(t("debugResume")), icon=ft.Icons.PLAY_ARROW, on_click=lambda _: self._do_resume())
        self._reset_btn = ft.ElevatedButton(content=ft.Text(t("debugReset")), icon=ft.Icons.RESTART_ALT, on_click=lambda _: self._do_reset())

        self._apply_state()

        # 变量监控区域
        self._add_addr = ft.TextField(hint_text="0x20000000", width=130, text_size=12)
        self._add_size = ft.Dropdown(width=80, dense=True, text_size=12, value="4",
            options=[ft.dropdown.Option("1", "u8"), ft.dropdown.Option("2", "u16"), ft.dropdown.Option("4", "u32"), ft.dropdown.Option("4f", "f32")])
        self._add_name = ft.TextField(hint_text=t("debugWatchName"), width=100, text_size=12)
        add_btn = ft.ElevatedButton(content=ft.Text(t("debugWatchAdd"), size=Font.Size.CAPTION), icon=ft.Icons.ADD, on_click=lambda _: self._add_watch())
        self._watch_column = ft.Column(spacing=Spacing.XS)
        self._elf_path = ft.TextField(hint_text="firmware.elf", expand=True, text_size=12)
        self._elf_symbols = ft.Column(spacing=Spacing.XS)

        return ft.ListView(
            controls=[
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[ft.Container(width=8, height=8, border_radius=4, bgcolor=Colors.TEXT_DIM), self._state_text], spacing=Spacing.SM),
                    ft.Row(controls=[self._halt_btn, self._resume_btn, self._reset_btn], spacing=Spacing.MD),
                ], spacing=Spacing.LG)),
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugWatchTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[self._add_name, self._add_addr, self._add_size, add_btn], spacing=Spacing.SM),
                    self._watch_column,
                ], spacing=Spacing.SM)),
                card_container(content=ft.Column(controls=[
                    ft.Text(t("debugElfTitle"), size=Font.Size.HEADING, weight=600, color=Colors.ACCENT_COPPER),
                    ft.Row(controls=[
                        self._elf_path,
                        ft.ElevatedButton(content=ft.Text("...", size=Font.Size.CAPTION), on_click=lambda _: self._pick_elf()),
                        ft.ElevatedButton(content=ft.Text(t("debugElfLoad"), size=Font.Size.CAPTION), icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: self._load_elf()),
                    ], spacing=Spacing.SM),
                    self._elf_symbols,
                ], spacing=Spacing.SM)),
            ],
            expand=True, spacing=Spacing.LG, padding=Spacing.XXL,
        )

    # ── 目标控制 ─────────────────────────────────────────
    def _apply_state(self) -> None:
        if not self._backend or not self._backend.is_connected:
            self._state_text.value = t("debugNotConnected"); self._state_text.color = Colors.TEXT_SECONDARY
            self._halt_btn.disabled = self._resume_btn.disabled = self._reset_btn.disabled = True
        elif self._backend.is_halted:
            self._state_text.value = t("debugHalted"); self._state_text.color = Colors.WARNING
            self._halt_btn.disabled = True; self._resume_btn.disabled = False; self._reset_btn.disabled = False
        else:
            self._state_text.value = t("debugRunning"); self._state_text.color = Colors.SUCCESS
            self._halt_btn.disabled = False; self._resume_btn.disabled = True; self._reset_btn.disabled = False

    def _refresh_state(self) -> None:
        self._apply_state()
        self._state_text.update(); self._halt_btn.update(); self._resume_btn.update(); self._reset_btn.update()

    def refresh(self) -> None:
        self._refresh_state()

    def _do_halt(self) -> None:
        try: self._backend.halt(); add_log("INFO", "目标已暂停")
        except Exception as e: add_log("ERROR", f"暂停失败: {e}")
        self._refresh_state()

    def _do_resume(self) -> None:
        try: self._backend.resume(); add_log("INFO", "目标已恢复运行")
        except Exception as e: add_log("ERROR", f"恢复失败: {e}")
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
            add_log("WARN", "请输入有效的地址和大小")
            return
        name = self._add_name.value.strip() or f"0x{addr:08X}"
        self._watches.append({"name": name, "addr": addr, "size": size, "is_float": is_float})
        self._rebuild_watch_list()
        if not self._watch_running:
            self._watch_running = True
            self._loop.create_task(self._watch_loop())

    def _rebuild_watch_list(self) -> None:
        self._watch_column.controls.clear()
        header = ft.Row(controls=[
            ft.Text(t("debugWatchName"), width=100, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
            ft.Text(t("chipRegionAddress"), width=110, size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
            ft.Text(t("debugWatchValue"), size=Font.Size.CAPTION, weight=600, color=Colors.TEXT_SECONDARY),
            ft.Container(expand=True),
            ft.IconButton(icon=ft.Icons.CLOSE, icon_size=14, on_click=lambda _: self._clear_watches()),
        ], spacing=Spacing.SM)
        self._watch_column.controls.append(header)
        self._watch_column.controls.append(standard_divider())
        for i, w in enumerate(self._watches):
            self._watch_column.controls.append(
                ft.Row(controls=[
                    ft.Text(w["name"], width=100, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                    ft.Text(f"0x{w['addr']:08X}", width=110, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                    ft.Text(w.get("value", "—"), size=Font.Size.CAPTION, color=Colors.ACCENT_PRIMARY, font_family=Font.MONO),
                ], spacing=Spacing.SM)
            )
        self._watch_column.update()

    def _clear_watches(self) -> None:
        self._watches.clear()
        self._rebuild_watch_list()

    async def _watch_loop(self) -> None:
        while self._watch_running and self._watches:
            for w in self._watches:
                if not self._backend or not self._backend.is_connected:
                    continue
                try:
                    data = await asyncio.to_thread(self._backend.read_memory, w["addr"], w["size"])
                    if w["is_float"] and w["size"] == 4:
                        val = struct.unpack("<f", data)[0]
                        w["value"] = f"{val:.6f}"
                    elif w["size"] == 1:
                        w["value"] = f"0x{data[0]:02X} ({data[0]})"
                    elif w["size"] == 2:
                        val = struct.unpack("<H", data)[0]
                        w["value"] = f"0x{val:04X} ({val})"
                    elif w["size"] == 4:
                        val = struct.unpack("<I", data)[0]
                        w["value"] = f"0x{val:08X} ({val})"
                except Exception:
                    w["value"] = "err"
            self._rebuild_watch_list()
            await asyncio.sleep(1)

    # ── ELF 符号加载 ─────────────────────────────────────
    def _pick_elf(self) -> None:
        picker = ft.FilePicker(on_result=lambda e: self._on_elf_picked(e))
        self._page.overlay.append(picker)
        self._page.update()
        picker.pick_files(
            dialog_title="Select ELF file",
            allowed_extensions=["elf", "axf"],
        )

    def _on_elf_picked(self, e: ft.FilePickerResultEvent) -> None:
        if e.files and e.files[0].path:
            self._elf_path.value = e.files[0].path
            self._elf_path.update()

    def _load_elf(self) -> None:
        path = self._elf_path.value.strip()
        if not path:
            return
        try:
            symbols = parse_elf_symbols(path)
            add_log("INFO", f"从 ELF 加载 {len(symbols)} 个全局变量符号")
            self._elf_symbols.controls.clear()
            for s in symbols:
                size = s["size"]
                self._elf_symbols.controls.append(
                    ft.Row(controls=[
                        ft.Text(s["name"], width=180, size=Font.Size.CAPTION, color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                        ft.Text(f"0x{s['addr']:08X}", width=110, size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY, font_family=Font.MONO),
                        ft.Text(str(size), width=60, size=Font.Size.CAPTION, color=Colors.TEXT_DIM),
                        ft.IconButton(icon=ft.Icons.ADD, icon_size=14, icon_color=Colors.ACCENT_PRIMARY, on_click=lambda e, a=s["addr"], n=s["name"], sz=size: self._watch_symbol(a, n, sz)),
                    ], spacing=Spacing.SM)
                )
            self._elf_symbols.update()
        except Exception as e:
            add_log("ERROR", f"ELF 解析失败: {e}")

    def _watch_symbol(self, addr: int, name: str, size: int) -> None:
        size = max(size, 1) if size < 16 else 4  # 默认 4 字节
        self._watches.append({"name": name, "addr": addr, "size": size, "is_float": False})
        self._rebuild_watch_list()
        if not self._watch_running:
            self._watch_running = True
            self._loop.create_task(self._watch_loop())
