"""芯片选择器组件 — 两级联动：先选厂家，再选芯片型号。

减少单一下拉框选项数量，提升浏览体验。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from src.ui.theme import Colors, Spacing

# 厂家列表 + 芯片名前缀匹配规则
_VENDORS: list[tuple[str, str, str]] = [
    ("ST", "STMicroelectronics", "stm32"),
    ("GD", "GigaDevice", "gd32"),
    ("NORDIC", "Nordic Semiconductor", "nrf"),
    ("NXP", "NXP Semiconductors", "kx,kl,kv,kw,ke,lpc,mimxrt,s32k"),
    ("RPI", "Raspberry Pi", "rp2"),
    ("MAXIM", "Maxim Integrated", "max"),
    ("NUVOTON", "Nuvoton", "m2,m4,nuc"),
    ("CYPRESS", "Cypress/Infineon", "cy8"),
    ("HC", "HDSC (华大)", "hc32"),
    ("OTHER", "其他厂商", ""),
]


def _match_vendor(chip_name: str, vendor_prefixes: str) -> bool:
    """检查芯片名是否匹配某个厂家的前缀。"""
    pref = vendor_prefixes.split(",")
    return any(chip_name.lower().startswith(p.strip().lower()) for p in pref)


class TargetSelector:
    """芯片选择器 — 厂家 + 芯片两级联动下拉。

    先选择厂家，第二个下拉框自动过滤为该厂家的芯片列表。
    """

    def __init__(
        self,
        targets: list[tuple[str, str]],
        on_target_selected: Callable[[str], None],
        on_pick_pack: Callable[[], Any],
    ) -> None:
        self._all_targets = targets
        self.on_target_selected = on_target_selected
        self.on_pick_pack = on_pick_pack
        self._vendor_ref = ft.Ref[ft.Dropdown]()
        self._chip_ref = ft.Ref[ft.Dropdown]()

    def build(self) -> ft.Control:
        self._vendor_dd = ft.Dropdown(
            ref=self._vendor_ref,
            width=300,
            hint_text="厂家",
            dense=False,
            bgcolor=Colors.BG_ELEVATED,
            border=ft.Border(
                top=ft.BorderSide(1, Colors.BORDER),
                left=ft.BorderSide(1, Colors.BORDER),
                right=ft.BorderSide(1, Colors.BORDER),
                bottom=ft.BorderSide(1, Colors.BORDER),
            ),
            border_radius=4,
            options=[
                ft.dropdown.Option(key=k, text=f"{label} ({k})")
                for k, label, _ in _VENDORS
            ],
            on_select=self._on_vendor_select,
        )

        self._chip_dd = ft.Dropdown(
            ref=self._chip_ref,
            width=260,
            hint_text="选择芯片",
            editable=True,
            enable_filter=True,
            dense=False,
            menu_height=280,
            bgcolor=Colors.BG_ELEVATED,
            border=ft.Border(
                top=ft.BorderSide(1, Colors.BORDER),
                left=ft.BorderSide(1, Colors.BORDER),
                right=ft.BorderSide(1, Colors.BORDER),
                bottom=ft.BorderSide(1, Colors.BORDER),
            ),
            border_radius=4,
            options=[],
            on_select=self._on_select,
        )

        self._pack_btn = ft.ElevatedButton(
            content=ft.Text("安装 Pack"),
            icon=ft.Icons.ADD,
            on_click=self._on_pack_click,
        )

        return ft.Row(
            controls=[self._vendor_dd, self._chip_dd, self._pack_btn],
            spacing=Spacing.SM,
        )

    # ── 事件 ─────────────────────────────────────────────

    def _on_vendor_select(self, e: ft.ControlEvent) -> None:
        self._populate_chips(e.control.value)

    def _populate_chips(self, vendor_key: str) -> None:
        """根据厂家 key 填充芯片下拉框。"""
        if not self._chip_ref.current:
            return
        # 找到该厂家的前缀规则
        prefix = ""
        for k, label, p in _VENDORS:
            if k == vendor_key:
                prefix = p
                break
        # 过滤芯片
        if prefix and prefix != "":
            if vendor_key == "OTHER":
                all_prefixes = [p for _, _, p in _VENDORS if p]
                chips = [
                    (name, label)
                    for name, label in self._all_targets
                    if not any(_match_vendor(name, pp) for pp in all_prefixes)
                ]
            else:
                chips = [
                    (name, label)
                    for name, label in self._all_targets
                    if _match_vendor(name, prefix)
                ]
        else:
            chips = self._all_targets
        self._chip_ref.current.options = [
            ft.dropdown.Option(key=name, text=name) for name, _ in chips
        ]
        self._chip_ref.current.hint_text = f"共 {len(chips)} 款芯片"
        self._chip_ref.current.update()

    def _on_select(self, e: ft.ControlEvent) -> None:
        if e.control.value:
            self.on_target_selected(e.control.value)

    async def _on_pack_click(self, e: ft.ControlEvent) -> None:
        await self.on_pick_pack()

    # ── 公共方法 ─────────────────────────────────────────

    def update_targets(self, targets: list[tuple[str, str]]) -> None:
        self._all_targets = targets

    def set_selected(self, name: str) -> None:
        """程序化选中芯片（自动推断厂家并填充芯片下拉）。"""
        if not self._vendor_ref.current or not self._chip_ref.current:
            return
        # 推断厂家
        vendor_key = "OTHER"
        for k, _, p in _VENDORS:
            if p and _match_vendor(name, p):
                vendor_key = k
                break
        # 设置厂家并触发过滤
        self._vendor_ref.current.value = vendor_key
        self._vendor_ref.current.update()
        # 手动触发厂家选择逻辑
        self._populate_chips(vendor_key)
        # 选芯片
        self._chip_ref.current.value = name
        self._chip_ref.current.update()

    def get_selected(self) -> str | None:
        if self._chip_ref.current:
            return self._chip_ref.current.value
        return None

    def set_loading(self, loading: bool) -> None:
        if self._chip_ref.current:
            self._chip_ref.current.disabled = loading
            if loading:
                self._chip_ref.current.hint_text = "正在加载..."
            self._chip_ref.current.update()
