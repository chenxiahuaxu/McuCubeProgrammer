"""持久连接面板 — 左侧边栏，始终可见，可拖拽调整宽度。

包含: 探针选择 / 接口类型 / 芯片选择
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import flet as ft

from src.backend.interface import BackendABC
from src.i18n import t
from src.logic.probe_manager import ProbeManager
from src.logic.target_manager import TargetManager
from src.ui.theme import Colors, Font, Spacing
from src.utils.config import load as cfg_load, save as cfg_save

PANEL_WIDTH: int = 260
PANEL_MIN: int = 200
PANEL_MAX: int = 420


def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY)


def _build_dropdown(ref, width: int | None = None, expand: bool = False) -> ft.Dropdown:
    kwargs = {"ref": ref, "dense": True}
    if expand:
        kwargs["expand"] = True
    elif width:
        kwargs["width"] = width
    return ft.Dropdown(
        **kwargs,
        text_size=11,
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
        backend: BackendABC,
        on_resize: Callable[[int], None] | None = None,
    ) -> None:
        self.page = page
        self.probe_mgr = probe_manager
        self.target_mgr = target_manager
        self._backend = backend
        self._on_resize = on_resize
        self._panel_width: int = PANEL_WIDTH
        self._dd_width: int = PANEL_WIDTH - 30

        self._probe_dd_ref = ft.Ref[ft.Dropdown]()
        self._vendor_ref = ft.Ref[ft.Dropdown]()
        self._chip_ref = ft.Ref[ft.Dropdown]()
        self._interface_ref = ft.Ref[ft.RadioGroup]()
        self._body_ref = ft.Ref[ft.Container]()
        self._scanning: bool = False

        # 连接状态（懒检查：build 时从 backend 同步）
        self._connected: bool = False
        self._conn_section: ft.Column | None = None
        self._state_dot: ft.Container | None = None
        self._state_label: ft.Text | None = None
        self._connect_text: ft.Text | None = None
        self._disconnect_text: ft.Text | None = None
        self._connect_btn: ft.ElevatedButton | None = None
        self._disconnect_btn: ft.OutlinedButton | None = None

        cfg = cfg_load()
        self._interface: str = cfg.get("interface", "swd")

    # ── 构建 ──────────────────────────────────────────────

    def build(self) -> ft.Control:
        # ── 探针选择 ──
        probe_dd = _build_dropdown(self._probe_dd_ref, self._dd_width)
        probe_dd.hint_text = t("probeSelectHint")
        probe_dd.options = []
        probe_dd.on_select = self._on_probe_selected

        refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip=t("probeRefresh"),
            icon_size=14,
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

        vendor_dd = _build_dropdown(self._vendor_ref, self._dd_width)
        vendor_dd.options = [
            ft.dropdown.Option(key=k, text=f"{label} ({k})") for k, label, _ in _VENDORS
        ]
        vendor_dd.on_select = lambda e: self._populate_chips(
            e.control.value, _VENDORS, _match_vendor
        )

        chip_dd = _build_dropdown(self._chip_ref, self._dd_width)
        chip_dd.editable = True
        chip_dd.enable_filter = True
        chip_dd.menu_height = 280
        chip_dd.on_select = self._on_chip_selected

        return ft.Stack(
            controls=[
                ft.Container(
                    ref=self._body_ref,
                    content=ft.Column(
                        scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Row(
                            controls=[
                                _section_label(t("tabProbe")),
                                refresh_btn,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        probe_dd,
                        _section_label(t("connInterfaceLabel")),
                        interface_group,
                        ft.Divider(height=1, color=Colors.DIVIDER),
                        _section_label(t("targetVendor")),
                        vendor_dd,
                        _section_label(t("targetChip")),
                        chip_dd,
                        ft.Divider(height=1, color=Colors.DIVIDER),
                        _section_label(t("connConnect")),
                        self._build_conn_section(),
                    ],
                        spacing=Spacing.SM,
                    ),
                    width=self._panel_width,
                    bgcolor=Colors.BG_SURFACE,
                    border=ft.Border(
                        right=ft.BorderSide(1, Colors.BORDER),
                    ),
                    padding=ft.Padding(left=Spacing.MD, top=Spacing.MD, right=Spacing.MD, bottom=Spacing.MD),
                ),
                # 拖拽手柄（右侧 6px）
                ft.GestureDetector(
                    content=ft.Container(
                        width=6,
                        bgcolor=Colors.ACCENT_COPPER_MUTED,
                        border_radius=3,
                    ),
                    on_horizontal_drag_update=self._on_drag,
                    left=self._panel_width - 3,
                    top=40,
                    bottom=40,
                ),
            ],
            width=self._panel_width,
            expand=False,
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

    # ── 连接 / 断开 ──────────────────────────────────────

    def _build_conn_section(self) -> ft.Column:
        """构建连接状态指示器 + 按钮区域。"""
        self._state_dot = ft.Container(
            width=8, height=8, border_radius=4, bgcolor=Colors.TEXT_DIM,
        )
        self._state_label = ft.Text(
            t("connDisconnected"), size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY,
        )
        self._connect_text = ft.Text(t("connConnect"), size=Font.Size.CAPTION)
        self._connect_btn = ft.ElevatedButton(
            content=self._connect_text,
            icon=ft.Icons.LINK,
            style=ft.ButtonStyle(
                bgcolor=Colors.ACCENT_PRIMARY,
                color=Colors.TEXT_PRIMARY,
                padding=ft.Padding(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS),
            ),
            on_click=self._on_connect,
            expand=True,
        )
        self._disconnect_text = ft.Text(t("connDisconnect"), size=Font.Size.CAPTION)
        self._disconnect_btn = ft.OutlinedButton(
            content=self._disconnect_text,
            icon=ft.Icons.LINK_OFF,
            style=ft.ButtonStyle(
                color=Colors.ERROR,
                side=ft.BorderSide(1, Colors.ERROR),
                padding=ft.Padding(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS),
            ),
            on_click=self._on_disconnect,
            expand=True,
        )

        self._conn_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[self._state_dot, self._state_label],
                    spacing=Spacing.SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self._connect_btn,
                self._disconnect_btn,
            ],
            spacing=Spacing.SM,
        )

        # 从 backend 同步实际连接状态（仅设值，不 update——控件尚未挂载）
        self._connected = self._backend.is_connected
        if self._connected:
            self._state_dot.bgcolor = Colors.SUCCESS
            self._state_label.value = t("connConnected")
            self._state_label.color = Colors.SUCCESS
            self._connect_btn.visible = False
            self._disconnect_btn.visible = True
        return self._conn_section

    def _on_connect(self, _e: ft.ControlEvent) -> None:
        """连接目标芯片。"""
        target_name = self.target_mgr.get_selected_target()
        if not target_name:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("connSelectTarget")), bgcolor=Colors.WARNING)
            self.page.snack_bar.open = True
            self.page.update()
            return
        probe = self.probe_mgr.get_selected_probe()
        if not probe:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("connSelectProbe")), bgcolor=Colors.WARNING)
            self.page.snack_bar.open = True
            self.page.update()
            return

        self._connect_btn.disabled = True
        self._connect_text.value = t("connConnecting")
        self._connect_text.update()

        cfg = cfg_load()
        frequency = cfg.get("swd_frequency", 200_000)

        try:
            self._backend.connect(
                target=target_name,
                probe_uid=probe.unique_id,
                frequency=frequency,
            )
            self._connected = True
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"{t('connFailed')}: {ex}"),
                bgcolor=Colors.ERROR,
            )
            self.page.snack_bar.open = True
            self.page.update()
        finally:
            self._update_conn_state()

    def _on_disconnect(self, _e: ft.ControlEvent) -> None:
        """断开目标芯片连接。"""
        try:
            self._backend.disconnect()
        except Exception:
            pass
        self._connected = False
        self._update_conn_state()

    def _update_conn_state(self) -> None:
        """根据 _connected 刷新指示器和按钮可见性。"""
        if self._connected:
            self._state_dot.bgcolor = Colors.SUCCESS
            self._state_label.value = t("connConnected")
            self._state_label.color = Colors.SUCCESS
            self._connect_btn.visible = False
            self._disconnect_btn.visible = True
            self._connect_btn.disabled = False
            self._connect_text.value = t("connConnect")
            self._connect_text.update()
        else:
            self._state_dot.bgcolor = Colors.TEXT_DIM
            self._state_label.value = t("connDisconnected")
            self._state_label.color = Colors.TEXT_SECONDARY
            self._connect_btn.visible = True
            self._disconnect_btn.visible = False

        self._state_dot.update()
        self._state_label.update()
        self._connect_btn.update()
        self._disconnect_btn.update()

    # ── 拖拽调整宽度 ─────────────────────────────────────

    def _on_drag(self, e: ft.DragUpdateEvent) -> None:
        """拖拽面板右边缘调整宽度。"""
        # Flet 各版本属性名不同，兼容 delta_x / global_delta.x
        if hasattr(e, "delta_x"):
            delta = int(e.delta_x)
        elif hasattr(e, "global_delta") and hasattr(e.global_delta, "x"):
            delta = int(e.global_delta.x)
        else:
            return
        if not delta:
            return
        new_w = max(PANEL_MIN, min(PANEL_MAX, self._panel_width + delta))
        if new_w == self._panel_width:
            return
        self._panel_width = new_w
        self._dd_width = new_w - 30

        # 更新 body Container 宽度
        body = self._body_ref.current
        if body:
            body.width = new_w
            body.update()

        # 更新拖拽手柄位置
        handle = e.control
        handle.left = new_w - 3
        handle.update()

        # 更新下拉框宽度
        for dd_ref in (self._probe_dd_ref, self._vendor_ref, self._chip_ref):
            dd = dd_ref.current
            if dd:
                dd.width = self._dd_width
                dd.update()

        # 通知 app.py 更新 page.padding
        if self._on_resize:
            self._on_resize(new_w)

    @property
    def panel_width(self) -> int:
        return self._panel_width

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
