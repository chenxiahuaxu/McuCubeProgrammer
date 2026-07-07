"""关于标签页 — 应用信息展示。"""

from __future__ import annotations

import flet as ft

from src.i18n import t
from src.ui.theme import (
    APP_TITLE,
    APP_VERSION,
    Colors,
    Font,
    Spacing,
    card_container,
)


class AboutTab:  # pylint: disable=too-few-public-methods
    """关于标签页。"""

    def build(self) -> ft.Control:
        return ft.ListView(
            controls=[
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                APP_TITLE,
                                size=Font.Size.TITLE,
                                weight=600,
                                color=Colors.ACCENT_PRIMARY,
                            ),
                            ft.Text(
                                f"v{APP_VERSION}",
                                size=Font.Size.CAPTION,
                                color=Colors.TEXT_DIM,
                            ),
                            ft.Divider(height=1, color=Colors.DIVIDER),
                            self._info_row(t("settingsBackend"), "pyOCD 0.44+"),
                            self._info_row(t("settingsUiFramework"), "Flet (Flutter)"),
                            self._info_row(t("settingsLicense"), "Apache 2.0"),
                        ],
                        spacing=Spacing.SM,
                    ),
                ),
            ],
            expand=True,
            spacing=Spacing.LG,
            padding=Spacing.XXL,
        )

    @staticmethod
    def _info_row(label: str, value: str) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Text(label, width=120, size=Font.Size.BODY,
                        color=Colors.TEXT_SECONDARY),
                ft.Text(value, size=Font.Size.BODY, color=Colors.TEXT_PRIMARY),
            ],
            spacing=Spacing.SM,
        )
