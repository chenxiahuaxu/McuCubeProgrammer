"""设置标签页 — 主题切换 + 关于信息。

使用卡片容器展示各设置区块。
"""

from __future__ import annotations

import flet as ft

from src.ui.theme import (
    APP_TITLE,
    APP_VERSION,
    Colors,
    Font,
    Spacing,
    card_container,
    standard_divider,
)
from src.utils.config import load as cfg_load, save as cfg_save


class SettingsTab:  # pylint: disable=too-few-public-methods
    """设置标签页。

    提供深色模式开关和应用关于信息展示。
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        cfg = cfg_load()
        self._current_frequency: int = cfg.get("swd_frequency", 200_000)
        self._freq_label: ft.Text | None = None

    def build(self) -> ft.Control:
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK

        return ft.ListView(
            controls=[
                # ── 主题设置 ──
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "主题设置",
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.DARK_MODE,
                                        color=Colors.TEXT_SECONDARY,
                                    ),
                                    ft.Switch(
                                        label="深色模式",
                                        value=is_dark,
                                        on_change=self._toggle_theme,
                                    ),
                                ],
                                spacing=Spacing.SM,
                            ),
                        ],
                        spacing=Spacing.SM,
                    ),
                ),
                standard_divider(),
                # ── SWD 频率设置 ──
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "SWD 调试时钟",
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Text(
                                "调整 SWD/JTAG 通信时钟频率。"
                                "CMSIS-DAP 探针或非标芯片建议降低频率（200-500 kHz）以提高连接稳定性。",
                                size=Font.Size.CAPTION,
                                color=Colors.TEXT_SECONDARY,
                            ),
                            self._build_freq_label(),
                            ft.Slider(
                                min=100_000,
                                max=10_000_000,
                                divisions=99,
                                value=self._current_frequency,
                                label="{value}",
                                active_color=Colors.ACCENT_PRIMARY,
                                on_change=self._on_frequency_change,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text("低速\n100 kHz", size=Font.Size.CAPTION,
                                            color=Colors.TEXT_SECONDARY,
                                            text_align=ft.TextAlign.CENTER),
                                    ft.Container(expand=True),
                                    ft.Text("高速\n10 MHz", size=Font.Size.CAPTION,
                                            color=Colors.TEXT_SECONDARY,
                                            text_align=ft.TextAlign.CENTER),
                                ],
                            ),
                        ],
                        spacing=Spacing.SM,
                    ),
                ),
                standard_divider(),
                # ── 关于 ──
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "关于",
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Column(
                                controls=[
                                    self._info_row("应用名称", APP_TITLE),
                                    self._info_row("版本", f"v{APP_VERSION}"),
                                    self._info_row("后端", "pyOCD 0.44+"),
                                    self._info_row("界面框架", "Flet (Flutter)"),
                                    self._info_row("许可", "Apache 2.0"),
                                ],
                                spacing=Spacing.XS,
                            ),
                        ],
                        spacing=Spacing.SM,
                    ),
                ),
            ],
            expand=True,
            spacing=Spacing.LG,
            padding=Spacing.XL,
        )

    def _toggle_theme(self, e: ft.ControlEvent) -> None:
        self.page.theme_mode = (
            ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        )
        self.page.update()

    @staticmethod
    def _info_row(label: str, value: str) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Text(
                    label,
                    width=100,
                    size=Font.Size.BODY,
                    color=Colors.TEXT_SECONDARY,
                ),
                ft.Text(
                    value,
                    size=Font.Size.BODY,
                    color=Colors.TEXT_PRIMARY,
                ),
            ],
            spacing=Spacing.SM,
        )

    # ── SWD 频率 ──────────────────────────────────────────

    def _build_freq_label(self) -> ft.Text:
        self._freq_label = ft.Text(
            self._format_frequency(self._current_frequency),
            size=Font.Size.BODY,
            weight=600,
            color=Colors.ACCENT_PRIMARY,
        )
        return self._freq_label

    def _on_frequency_change(self, e: ft.ControlEvent) -> None:
        freq = int(e.control.value)
        self._current_frequency = freq
        if self._freq_label:
            self._freq_label.value = self._format_frequency(freq)
            self._freq_label.update()
        cfg = cfg_load()
        cfg["swd_frequency"] = freq
        cfg_save(cfg)

    @staticmethod
    def _format_frequency(hz: int) -> str:
        if hz >= 1_000_000:
            return f"当前: {hz / 1_000_000:.2f} MHz"
        return f"当前: {hz // 1_000} kHz"
