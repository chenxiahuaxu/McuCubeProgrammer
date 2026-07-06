"""设置标签页 — 主题切换 + 语言选择 + 关于信息。

使用卡片容器展示各设置区块。
"""

from __future__ import annotations

import flet as ft

from src.i18n import get_l10n, t
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

    提供深色模式开关、语言选择和关于信息展示。
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        cfg = cfg_load()
        self._current_frequency: int = cfg.get("swd_frequency", 200_000)
        self._connect_mode: str = cfg.get("connect_mode", "normal")
        self._reset_mode: str = cfg.get("reset_mode", "hw")
        self._freq_label: ft.Text | None = None
        self._l10n = get_l10n()
        self._lang_ref = ft.Ref[ft.Dropdown]()
        self._connect_ref = ft.Ref[ft.Dropdown]()
        self._reset_ref = ft.Ref[ft.Dropdown]()

    def build(self) -> ft.Control:
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK
        current_lang = self._l10n.current_locale

        return ft.ListView(
            controls=[
                # ── 主题设置 ──
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                t("settingsTheme"),
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
                                        label=t("settingsDarkMode"),
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
                # ── 语言设置 ──
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                t("settingsLanguage"),
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.LANGUAGE,
                                        color=Colors.TEXT_SECONDARY,
                                    ),
                                    ft.Dropdown(
                                        ref=self._lang_ref,
                                        width=220,
                                        dense=True,
                                        value=current_lang,
                                        bgcolor=Colors.BG_ELEVATED,
                                        border=ft.Border(
                                            top=ft.BorderSide(1, Colors.BORDER),
                                            left=ft.BorderSide(1, Colors.BORDER),
                                            right=ft.BorderSide(1, Colors.BORDER),
                                            bottom=ft.BorderSide(1, Colors.BORDER),
                                        ),
                                        border_radius=4,
                                        options=[
                                            ft.dropdown.Option(
                                                key="zh",
                                                text=t("settingsLangZh"),
                                            ),
                                            ft.dropdown.Option(
                                                key="en",
                                                text=t("settingsLangEn"),
                                            ),
                                        ],
                                        on_select=self._on_language_change,
                                    ),
                                ],
                                spacing=Spacing.SM,
                            ),
                        ],
                        spacing=Spacing.SM,
                    ),
                ),
                standard_divider(),
                # ── 连接与复位 ──
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                t("connModeLabel"),
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Dropdown(
                                ref=self._connect_ref,
                                value=self._connect_mode,
                                width=220,
                                dense=True,
                                bgcolor=Colors.BG_ELEVATED,
                                border=ft.Border(
                                    top=ft.BorderSide(1, Colors.BORDER),
                                    left=ft.BorderSide(1, Colors.BORDER),
                                    right=ft.BorderSide(1, Colors.BORDER),
                                    bottom=ft.BorderSide(1, Colors.BORDER),
                                ),
                                border_radius=4,
                                options=[
                                    ft.dropdown.Option("normal", t("connModeNormal")),
                                    ft.dropdown.Option("under_reset", t("connModeUnderReset")),
                                    ft.dropdown.Option("hotplug", t("connModeHotPlug")),
                                ],
                                on_select=self._on_connect_mode_change,
                            ),
                            ft.Dropdown(
                                ref=self._reset_ref,
                                value=self._reset_mode,
                                width=220,
                                dense=True,
                                bgcolor=Colors.BG_ELEVATED,
                                border=ft.Border(
                                    top=ft.BorderSide(1, Colors.BORDER),
                                    left=ft.BorderSide(1, Colors.BORDER),
                                    right=ft.BorderSide(1, Colors.BORDER),
                                    bottom=ft.BorderSide(1, Colors.BORDER),
                                ),
                                border_radius=4,
                                options=[
                                    ft.dropdown.Option("hw", t("connResetHw")),
                                    ft.dropdown.Option("sw_sys", t("connResetSwSys")),
                                    ft.dropdown.Option("sw_vect", t("connResetSwVect")),
                                    ft.dropdown.Option("sw_core", t("connResetSwCore")),
                                ],
                                on_select=self._on_reset_mode_change,
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
                                t("settingsSwdClock"),
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Text(
                                t("settingsSwdDesc"),
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
                                    ft.Text(t("settingsLowSpeed"), size=Font.Size.CAPTION,
                                            color=Colors.TEXT_SECONDARY,
                                            text_align=ft.TextAlign.CENTER),
                                    ft.Container(expand=True),
                                    ft.Text(t("settingsHighSpeed"), size=Font.Size.CAPTION,
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
                                t("settingsAbout"),
                                size=Font.Size.HEADING,
                                weight=500,
                                color=Colors.TEXT_PRIMARY,
                            ),
                            ft.Column(
                                controls=[
                                    self._info_row(t("settingsAppName"), APP_TITLE),
                                    self._info_row(t("settingsVersion"), f"v{APP_VERSION}"),
                                    self._info_row(t("settingsBackend"), "pyOCD 0.44+"),
                                    self._info_row(t("settingsUiFramework"), "Flet (Flutter)"),
                                    self._info_row(t("settingsLicense"), "Apache 2.0"),
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

    # ── 主题 ──────────────────────────────────────────────

    def _toggle_theme(self, e: ft.ControlEvent) -> None:
        self.page.theme_mode = (
            ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        )
        self.page.update()

    # ── 语言 ──────────────────────────────────────────────

    def _on_language_change(self, e: ft.ControlEvent) -> None:
        new_lang = e.control.value
        if new_lang:
            self._l10n.set_locale(new_lang)

    # ── 连接 / 复位 ──────────────────────────────────────

    def _on_connect_mode_change(self, e: ft.ControlEvent) -> None:
        cfg = cfg_load()
        cfg["connect_mode"] = e.control.value
        cfg_save(cfg)

    def _on_reset_mode_change(self, e: ft.ControlEvent) -> None:
        cfg = cfg_load()
        cfg["reset_mode"] = e.control.value
        cfg_save(cfg)

    # ── 关于 ──────────────────────────────────────────────

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

    def _format_frequency(self, hz: int) -> str:
        if hz >= 1_000_000:
            return t("settingsFreqMHz", freq=f"{hz / 1_000_000:.2f}")
        return t("settingsFreqKHz", freq=f"{hz // 1_000}")
