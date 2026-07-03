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


class SettingsTab:
    """设置标签页。

    提供深色模式开关和应用关于信息展示。
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page

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
