"""芯片信息标签页 — 目标芯片参数展示。"""

from __future__ import annotations

import flet as ft

from src.backend.interface import TargetInfo
from src.i18n import t
from src.ui.theme import (
    Colors,
    Font,
    Spacing,
    card_container,
    section_divider,
    standard_divider,
)


def _fmt_addr(addr: int) -> str:
    """格式化地址为 0x 前缀 8 位 hex。"""
    return f"0x{addr:08X}"


def _fmt_size(size_bytes: int) -> str:
    """人性化容量显示。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


class ChipInfoTab:
    """芯片信息标签页。"""

    def __init__(self, backend):
        self._backend = backend
        self._content: ft.Column | None = None

    def build(self) -> ft.Control:
        self._content = ft.Column(spacing=Spacing.SM)
        self._populate()

        return ft.ListView(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            t("chipTitle"),
                            size=Font.Size.TITLE,
                            weight=600,
                            color=Colors.ACCENT_PRIMARY,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_color=Colors.ACCENT_COPPER,
                            tooltip=t("chipRefresh"),
                            on_click=lambda _: self._refresh(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self._content,
            ],
            expand=True,
            spacing=Spacing.MD,
            padding=Spacing.XXL,
        )

    # ── 数据刷新 ─────────────────────────────────────────
    def _populate(self) -> None:
        """纯数据填充。"""
        self._content.controls.clear()

        if not self._backend or not self._backend.is_connected:
            self._content.controls.append(
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                t("chipNotConnected"),
                                size=Font.Size.BODY,
                                color=Colors.TEXT_SECONDARY,
                            ),
                        ],
                    ),
                ),
            )
            return

        try:
            info: TargetInfo = self._backend.get_target_info()
        except Exception:  # pylint: disable=broad-exception-caught  # OK: UI error handler
            self._content.controls.append(
                card_container(
                    content=ft.Text(
                        t("chipReadError"),
                        size=Font.Size.BODY,
                        color=Colors.ERROR,
                    ),
                ),
            )
            return

        self._build_target_card(info)
        self._build_memory_card(info)
        self._build_flash_regions_card(info)
        self._build_ram_regions_card(info)
        self._build_hex_dump_card()

    def _refresh(self) -> None:
        self._populate()
        self._content.update()

    def refresh(self) -> None:
        self._refresh()

    # ── 目标信息卡片 ─────────────────────────────────────
    def _build_target_card(self, info: TargetInfo) -> None:
        rows = [
            self._info_row(t("chipPartNumber"), info.part_number or "\u2014"),
            self._info_row(t("chipVendor"), info.vendor or "\u2014"),
            self._info_row(t("chipDapIdcode"), info.dap_idcode or "\u2014"),
            self._info_row(t("chipCore"), info.core_name or "\u2014"),
        ]
        self._content.controls.append(
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text(t("chipSectionTarget"), size=Font.Size.HEADING,
                                weight=600, color=Colors.ACCENT_COPPER),
                        section_divider(),
                        *rows,
                    ],
                    spacing=Spacing.SM,
                ),
            ),
        )

    # ── 存储概览卡片 ─────────────────────────────────────
    def _build_memory_card(self, info: TargetInfo) -> None:
        rows = [
            self._info_row(
                t("chipTotalFlash"),
                f"{_fmt_size(info.total_flash_size)}  ({info.total_flash_size:,} B)",
            ),
            self._info_row(
                t("chipTotalRam"),
                f"{_fmt_size(info.total_ram_size)}  ({info.total_ram_size:,} B)",
            ),
        ]
        self._content.controls.append(
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text(t("chipSectionMemory"), size=Font.Size.HEADING,
                                weight=600, color=Colors.ACCENT_COPPER),
                        section_divider(),
                        *rows,
                    ],
                    spacing=Spacing.SM,
                ),
            ),
        )

    # ── Flash 区域表格 ───────────────────────────────────
    def _build_flash_regions_card(self, info: TargetInfo) -> None:
        header = ft.Row(
            controls=[
                ft.Text(t("chipRegionName"), width=140, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
                ft.Text(t("chipRegionAddress"), width=180, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
                ft.Text(t("chipRegionSize"), width=70, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
                ft.Text(t("chipRegionSector"), width=70, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
                ft.Text(t("chipRegionCount"), width=40, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
            ],
            spacing=Spacing.SM,
        )

        rows: list[ft.Control] = [header, standard_divider()]
        child_counts: dict[str, int] = {}
        for r in info.flash_regions:
            if "_0x" in r.name:
                parent = r.name.split("_0x")[0]
                c = r.length // r.sector_size if r.sector_size else 1
                child_counts[parent] = child_counts.get(parent, 0) + c

        for r in info.flash_regions:
            indent = "  " if ("_0x" in r.name) else ""
            if "_0x" in r.name or r.name not in child_counts:
                sector_count = r.length // r.sector_size if r.sector_size else 1
            else:
                sector_count = child_counts[r.name]
            rows.append(
                ft.Row(
                    controls=[
                        ft.Text(indent + r.name, width=140, size=Font.Size.CAPTION,
                                color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                        ft.Text(f"{_fmt_addr(r.start)} \u2014 {_fmt_addr(r.start + r.length - 1)}",
                                width=180, size=Font.Size.CAPTION,
                                color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                        ft.Text(_fmt_size(r.length), width=70, size=Font.Size.CAPTION,
                                color=Colors.TEXT_PRIMARY),
                        ft.Text(_fmt_size(r.sector_size), width=70, size=Font.Size.CAPTION,
                                color=Colors.TEXT_PRIMARY),
                        ft.Text(str(sector_count), width=40, size=Font.Size.CAPTION,
                                color=Colors.ACCENT_COPPER),
                    ],
                    spacing=Spacing.SM,
                ),
            )

        self._content.controls.append(
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text(t("chipSectionFlash"), size=Font.Size.HEADING,
                                weight=600, color=Colors.ACCENT_COPPER),
                        section_divider(),
                        ft.Column(controls=rows, spacing=Spacing.XS),
                    ],
                    spacing=Spacing.SM,
                ),
            ),
        )

    # ── RAM 区域表格 ─────────────────────────────────────
    def _build_ram_regions_card(self, info: TargetInfo) -> None:
        header = ft.Row(
            controls=[
                ft.Text(t("chipRegionName"), width=200, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
                ft.Text(t("chipRegionAddress"), width=250, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
                ft.Text(t("chipRegionSize"), width=80, size=Font.Size.CAPTION,
                        weight=600, color=Colors.TEXT_SECONDARY),
            ],
            spacing=Spacing.SM,
        )

        rows: list[ft.Control] = [header, standard_divider()]
        for r in info.ram_regions:
            rows.append(
                ft.Row(
                    controls=[
                        ft.Text(r.name, width=200, size=Font.Size.CAPTION,
                                color=Colors.ACCENT_COPPER, font_family=Font.MONO),
                        ft.Text(f"{_fmt_addr(r.start)} \u2014 {_fmt_addr(r.start + r.length - 1)}",
                                width=250, size=Font.Size.CAPTION,
                                color=Colors.TEXT_PRIMARY, font_family=Font.MONO),
                        ft.Text(_fmt_size(r.length), width=80, size=Font.Size.CAPTION,
                                color=Colors.TEXT_PRIMARY),
                    ],
                    spacing=Spacing.SM,
                ),
            )

        self._content.controls.append(
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text(t("chipSectionRam"), size=Font.Size.HEADING,
                                weight=600, color=Colors.ACCENT_COPPER),
                        section_divider(),
                        ft.Column(controls=rows, spacing=Spacing.XS),
                    ],
                    spacing=Spacing.SM,
                ),
            ),
        )

    # ── 通用行 ───────────────────────────────────────────
    @staticmethod
    def _info_row(label: str, value: str) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Text(label, width=130, size=Font.Size.BODY,
                        color=Colors.TEXT_SECONDARY),
                ft.Text(value, size=Font.Size.BODY, color=Colors.TEXT_PRIMARY,
                        font_family=Font.MONO),
            ],
            spacing=Spacing.SM,
        )

    # ── Hex Dump ─────────────────────────────────────────
    def _build_hex_dump_card(self) -> None:
        self._hex_addr = ft.TextField(
            value="0x08000000", width=140, text_size=12,
            prefix_icon=ft.Icons.MEMORY,
        )
        self._hex_size = ft.Dropdown(
            width=90, dense=True, text_size=12, value="256",
            options=[
                ft.dropdown.Option("64"), ft.dropdown.Option("128"),
                ft.dropdown.Option("256"), ft.dropdown.Option("512"),
                ft.dropdown.Option("1024"),
            ],
        )
        self._hex_output = ft.Text(
            "", size=Font.Size.CAPTION, font_family=Font.MONO,
            color=Colors.TEXT_PRIMARY,
        )
        read_btn = ft.ElevatedButton(
            content=ft.Text(t("chipHexRead"), size=Font.Size.CAPTION),
            icon=ft.Icons.DOWNLOAD,
            on_click=lambda _: self._do_hex_read(),
        )

        self._content.controls.append(
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text(t("chipHexDump"), size=Font.Size.HEADING,
                                weight=600, color=Colors.ACCENT_COPPER),
                        section_divider(),
                        ft.Row(
                            controls=[self._hex_addr, self._hex_size, read_btn],
                            spacing=Spacing.SM,
                        ),
                        ft.Container(
                            content=self._hex_output,
                            padding=Spacing.SM,
                            border_radius=4,
                            border=ft.Border(
                                top=ft.BorderSide(1, Colors.BORDER),
                                left=ft.BorderSide(1, Colors.BORDER),
                                right=ft.BorderSide(1, Colors.BORDER),
                                bottom=ft.BorderSide(1, Colors.BORDER),
                            ),
                        ),
                    ],
                    spacing=Spacing.SM,
                ),
            ),
        )

    def _do_hex_read(self) -> None:
        if not self._backend or not self._backend.is_connected:
            self._hex_output.value = t("chipNotConnected")
            self._hex_output.update()
            return
        try:
            addr = int(self._hex_addr.value, 0)
            size = int(self._hex_size.value)
            data = self._backend.read_memory(addr, size)
            self._hex_output.value = self._format_hex(data, addr)
        except Exception as e:  # pylint: disable=broad-exception-caught  # OK: UI error handler
            self._hex_output.value = f"Error: {e}"
        self._hex_output.update()

    @staticmethod
    def _format_hex(data: bytes, base_addr: int) -> str:
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            hex_part = f"{hex_part:<48}"
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"0x{base_addr + i:08X}: {hex_part} {ascii_part}")
        return "\n".join(lines)
