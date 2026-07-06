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
    """芯片信息标签页。

    连接成功后自动读取 TargetInfo，展示芯片型号、存储布局、
    Flash 区域详情。未连接时提示用户先连接。
    """

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
        """纯数据填充——不清空再重建，仅操作 controls 列表。"""
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
        except Exception:
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
        self._build_regions_card(info)

    def _refresh(self) -> None:
        """按钮回调：重建数据后触发页面更新。"""
        self._populate()
        self._content.update()

    def refresh(self) -> None:
        """公开方法：外部触发刷新（如标签页切换时）。"""
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
                        ft.Text(
                            t("chipSectionTarget"),
                            size=Font.Size.HEADING,
                            weight=600,
                            color=Colors.ACCENT_COPPER,
                        ),
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
        ]
        # 每个 RAM 区域单独一行
        for region in info.ram_regions:
            rows.append(
                self._info_row(
                    region.name or "RAM",
                    f"{_fmt_addr(region.start)} \u2014 "
                    f"{_fmt_addr(region.start + region.length - 1)}"
                    f"  ({_fmt_size(region.length)})",
                ),
            )
        if len(info.ram_regions) > 1:
            rows.append(self._info_row(
                t("chipTotalRam"),
                _fmt_size(info.total_ram_size),
            ))
        self._content.controls.append(
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            t("chipSectionMemory"),
                            size=Font.Size.HEADING,
                            weight=600,
                            color=Colors.ACCENT_COPPER,
                        ),
                        section_divider(),
                        *rows,
                    ],
                    spacing=Spacing.SM,
                ),
            ),
        )

    # ── 存储器区域表格 ───────────────────────────────────
    def _build_regions_card(self, info: TargetInfo) -> None:
        # 表头
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
        for r in info.flash_regions:
            sector_count = r.length // r.sector_size if r.sector_size else 1
            indent = "  " if ("_0x" in r.name) else ""
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
                        ft.Text(
                            t("chipRegionsTitle"),
                            size=Font.Size.HEADING,
                            weight=600,
                            color=Colors.ACCENT_COPPER,
                        ),
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
                ft.Text(
                    label,
                    width=130,
                    size=Font.Size.BODY,
                    color=Colors.TEXT_SECONDARY,
                ),
                ft.Text(
                    value,
                    size=Font.Size.BODY,
                    color=Colors.TEXT_PRIMARY,
                    font_family=Font.MONO,
                ),
            ],
            spacing=Spacing.SM,
        )
