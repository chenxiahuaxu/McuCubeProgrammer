"""探针标签页 — 卡片列表展示已连接探针详细信息。

铜色图标 + 类型 Chip + 空状态提示。
"""

from __future__ import annotations

import flet as ft

from src.logic.probe_manager import ProbeManager
from src.ui.theme import Colors, Font, Spacing


class ProbeTab:  # pylint: disable=too-few-public-methods
    """探针标签页。

    以卡片形式展示每个已连接探针的名称、UID、类型、厂家等信息。
    """

    def __init__(self, probe_manager: ProbeManager) -> None:
        self.probe_manager = probe_manager
        self._list_ref = ft.Ref[ft.ListView]()
        self._empty_ref = ft.Ref[ft.Text]()

    def build(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Text("刷新探针列表"),
                                icon=ft.Icons.REFRESH,
                                on_click=self._on_refresh,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                    ft.Text(
                        ref=self._empty_ref,
                        value="未检测到探针",
                        size=Font.Size.BODY,
                        color=Colors.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.ListView(
                        ref=self._list_ref,
                        expand=True,
                        spacing=Spacing.SM,
                        controls=[],
                    ),
                ],
                spacing=Spacing.MD,
                expand=True,
            ),
            padding=Spacing.XL,
            expand=True,
        )

    def _on_refresh(self, e: ft.ControlEvent) -> None:
        probes = self.probe_manager.refresh()
        self._list_ref.current.controls.clear()
        if probes:
            self._empty_ref.current.visible = False
            for p in probes:
                self._list_ref.current.controls.append(self._probe_card(p))
        else:
            self._empty_ref.current.visible = True
        self._empty_ref.current.update()
        self._list_ref.current.update()

    def _probe_card(self, probe) -> ft.Card:
        return ft.Card(
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.USB,
                        color=Colors.ACCENT_COPPER,
                    ),
                    title=ft.Text(
                        probe.description or probe.name,
                        size=Font.Size.BODY,
                        weight=500,
                        color=Colors.TEXT_PRIMARY,
                    ),
                    subtitle=ft.Text(
                        f"UID: {probe.unique_id[:20]}...",
                        size=Font.Size.CAPTION,
                        color=Colors.TEXT_SECONDARY,
                    ),
                    trailing=ft.Container(
                        content=ft.Text(
                            probe.probe_type.upper(),
                            size=Font.Size.MICRO,
                            color=Colors.TEXT_PRIMARY,
                        ),
                        bgcolor=Colors.ACCENT_COPPER_MUTED,
                        border_radius=4,
                        padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                    ),
                ),
                bgcolor=Colors.BG_SURFACE,
                border=ft.Border(
                    top=ft.BorderSide(1, Colors.BORDER),
                    left=ft.BorderSide(1, Colors.BORDER),
                    right=ft.BorderSide(1, Colors.BORDER),
                    bottom=ft.BorderSide(1, Colors.BORDER),
                ),
                border_radius=6,
                padding=Spacing.MD,
            ),
        )
