"""持久连接面板 — 左侧边栏，始终可见，不跟随标签切换。

包含: 探针选择 / 接口类型 / 芯片选择
"""

from __future__ import annotations

import asyncio

import flet as ft

from src.i18n import t
from src.logic.probe_manager import ProbeManager
from src.logic.target_manager import TargetManager
from src.ui.theme import Colors, Font, Spacing
from src.utils.config import load as cfg_load, save as cfg_save

PANEL_WIDTH: int = 240
DROPDOWN_WIDTH: int = PANEL_WIDTH - 30  # 210px usable


def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=Font.Size.MICRO, color=Colors.TEXT_DIM)


def _build_dropdown(ref, width: int | None = None, expand: bool = False) -> ft.Dropdown:
    kwargs = {"ref": ref, "dense": True}
    if expand:
        kwargs["expand"] = True
    elif width:
        kwargs["width"] = width
    return ft.Dropdown(
        **kwargs,
        text_size=12,
        bgcolor=Colors.BG_ELEVATED,
        border=ft.Border(
            top=ft.BorderSide(1, Colors.BORDER),
            left=ft.BorderSide(1, Colors.BORDER),
            right=ft.BorderSide(1, Colors.BORDER),
            bottom=ft.BorderSide(1, Colors.BORDER),
        ),
        border_radius=4,
    )


class ConnectionPanel:
    """持久连接面板。"""

    def __init__(
        self,
        page: ft.Page,
        probe_manager: ProbeManager,
        target_manager: TargetManager,
    ) -> None:
        self.page = page
        self.probe_mgr = probe_manager
        self.target_mgr = target_manager

        self._probe_dd_ref = ft.Ref[ft.Dropdown]()
        self._vendor_ref = ft.Ref[ft.Dropdown]()
        self._chip_ref = ft.Ref[ft.Dropdown]()
        self._interface_ref = ft.Ref[ft.RadioGroup]()
        self._scanning: bool = False

        cfg = cfg_load()
        self._interface: str = cfg.get("interface", "swd")

    # ── 构建 ──────────────────────────────────────────────

    def build(self) -> ft.Control:
        # ── 探针选择 ──
        probe_dd = _build_dropdown(self._probe_dd_ref, DROPDOWN_WIDTH - 30)
        probe_dd.hint_text = t("probeSelectHint")
        probe_dd.options = []
        probe_dd.on_select = self._on_probe_selected

        refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip=t("probeRefresh"),
            icon_size=16,
            on_click=self._on_refresh_click,
        )

        # ── 接口类型 ──
        interface_group = ft.RadioGroup(
            ref=self._interface_ref,
            value=self._interface,
            content=ft.Row(
                controls=[
                    ft.Radio(value="swd", label=t("connSwd"), fill_color=Colors.ACCENT_PRIMARY,
                              label_style=ft.TextStyle(size=Font.Size.CAPTION)),
                    ft.Radio(value="jtag", label=t("connJtag"), fill_color=Colors.ACCENT_PRIMARY,
                              label_style=ft.TextStyle(size=Font.Size.CAPTION)),
                ],
                spacing=Spacing.MD,
            ),
            on_change=self._on_interface_change,
        )

        # ── 芯片选择 ──
        from src.ui.components.target_selector import _VENDORS, _match_vendor

        vendor_dd = _build_dropdown(self._vendor_ref, DROPDOWN_WIDTH)
        vendor_dd.hint_text = t("targetVendor")
        vendor_dd.options = [
            ft.dropdown.Option(key=k, text=f"{label} ({k})") for k, label, _ in _VENDORS
        ]
        vendor_dd.on_select = lambda e: self._populate_chips(
            e.control.value, _VENDORS, _match_vendor
        )

        chip_dd = _build_dropdown(self._chip_ref, DROPDOWN_WIDTH)
        chip_dd.hint_text = t("targetChip")
        chip_dd.editable = True
        chip_dd.enable_filter = True
        chip_dd.menu_height = 280
        chip_dd.on_select = self._on_chip_selected

        return ft.Container(
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(t("tabProbe"), size=Font.Size.BODY, weight=500,
                            color=Colors.TEXT_PRIMARY),
                    ft.Row(
                        controls=[probe_dd, refresh_btn],
                        spacing=Spacing.XS,
                    ),
                    _section_label(t("connInterfaceLabel")),
                    interface_group,
                    ft.Divider(height=1, color=Colors.DIVIDER),
                    _section_label(t("targetVendor")),
                    vendor_dd,
                    _section_label(t("targetChip")),
                    chip_dd,
                ],
                spacing=Spacing.SM,
            ),
            width=PANEL_WIDTH,
            bgcolor=Colors.BG_SURFACE,
            border=ft.Border(
                right=ft.BorderSide(1, Colors.BORDER),
            ),
            padding=ft.Padding(left=Spacing.MD, top=Spacing.MD, right=Spacing.SM, bottom=Spacing.MD),
        )

    # ── 探针 ──────────────────────────────────────────────

    async def _on_refresh_click(self, _e: ft.ControlEvent) -> None:
        if self._scanning:
            return
        self._scanning = True
        self._probe_dd_ref.current.disabled = True
        self._probe_dd_ref.current.hint_text = t("probeScanning")
        self._probe_dd_ref.current.update()

        try:
            await asyncio.to_thread(self.probe_mgr.scan_probes)
            probes = self.probe_mgr.get_probes()
            dd = self._probe_dd_ref.current
            dd.options.clear()
            if probes:
                for p in probes:
                    dd.options.append(
                        ft.dropdown.Option(
                            key=p.unique_id,
                            text=f"[{p.probe_type.upper()}] {p.description}",
                        )
                    )
                dd.hint_text = t("probeSelectHint")
            else:
                dd.hint_text = t("probeNotFound")
            dd.update()
        finally:
            self._scanning = False
            self._probe_dd_ref.current.disabled = False
            self._probe_dd_ref.current.update()

    def _on_probe_selected(self, e: ft.ControlEvent) -> None:
        uid = e.control.value
        if uid:
            self.probe_mgr.select_probe(uid)
            targets = self.target_mgr.list_all_targets()
            self._all_targets = targets
            self._save_config()

    # ── 芯片 ──────────────────────────────────────────────

    def _populate_chips(self, vendor_key: str, vendors, matcher) -> None:
        if not vendor_key or not self._chip_ref.current:
            return
        prefix = ""
        for k, _, p in vendors:
            if k == vendor_key:
                prefix = p
                break
        if prefix and prefix != "":
            if vendor_key == "OTHER":
                all_prefixes = [p for _, _, p in vendors if p]
                chips = [
                    n for n, _ in self._all_targets
                    if not any(matcher(n, pp) for pp in all_prefixes)
                ]
            else:
                chips = [
                    n for n, _ in self._all_targets
                    if matcher(n, prefix)
                ]
        else:
            chips = [n for n, _ in self._all_targets]
        self._chip_ref.current.options = [
            ft.dropdown.Option(key=name, text=name) for name in chips
        ]
        self._chip_ref.current.hint_text = t("targetCount", count=len(chips))
        self._chip_ref.current.update()

    def _on_chip_selected(self, e: ft.ControlEvent) -> None:
        name = e.control.value
        if name:
            self.target_mgr.select_target(name)
            self._save_config()

    # ── 接口 ───────────────────────────────────────────────

    def _on_interface_change(self, e: ft.ControlEvent) -> None:
        self._interface = e.control.value
        self._save_config()

    # ── 配置持久化 ───────────────────────────────────────

    def _save_config(self) -> None:
        cfg = cfg_load()
        if self.probe_mgr.get_selected_probe():
            cfg["probe_uid"] = self.probe_mgr.get_selected_probe().unique_id
        if self.target_mgr.get_selected_target():
            cfg["target_name"] = self.target_mgr.get_selected_target()
        cfg["interface"] = self._interface
        cfg_save(cfg)

    # ── 公共方法 ─────────────────────────────────────────

    def select_probe(self, unique_id: str) -> None:
        """程序化选中探针（启动时自动恢复）。"""
        dd = self._probe_dd_ref.current
        if not dd:
            return
        probes = self.probe_mgr.get_probes()
        dd.options.clear()
        for p in probes:
            dd.options.append(
                ft.dropdown.Option(
                    key=p.unique_id,
                    text=f"[{p.probe_type.upper()}] {p.description}",
                )
            )
        dd.value = unique_id
        dd.hint_text = t("probeSelectHint")
        dd.update()

        self.probe_mgr.select_probe(unique_id)
        self._all_targets = self.target_mgr.list_all_targets()
        # 恢复芯片选择
        saved_target = cfg_load().get("target_name")
        if saved_target:
            target_names = [n for n, _ in self._all_targets]
            if saved_target in target_names:
                # 推断厂家
                from src.ui.components.target_selector import _VENDORS, _match_vendor
                vendor_key = "OTHER"
                for k, _, p in _VENDORS:
                    if p and _match_vendor(saved_target, p):
                        vendor_key = k
                        break
                self._vendor_ref.current.value = vendor_key
                self._vendor_ref.current.update()
                self._populate_chips(vendor_key, _VENDORS, _match_vendor)
                self._chip_ref.current.value = saved_target
                self._chip_ref.current.update()
                self.target_mgr.select_target(saved_target)
