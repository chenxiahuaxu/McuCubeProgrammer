"""探针选择器组件 — 下拉框 + 刷新按钮。

通过回调与逻辑层的 ProbeManager 交互，组件本身不导入逻辑层。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from src.ui.theme import Colors, Font, Spacing


class ProbeSelector:
    """探针选择器。

    展示已连接调试探针的下拉框，附带刷新按钮。
    所有业务逻辑通过回调函数注入。

    Usage::

        selector = ProbeSelector(
            on_refresh=lambda: probe_manager.scan_probes(),
            on_probe_selected=lambda uid: probe_manager.select_probe(uid),
        )
        page.add(selector.build())
    """

    def __init__(
        self,
        on_refresh: Callable[[], list],
        on_probe_selected: Callable[[str], None],
    ) -> None:
        self.on_refresh = on_refresh
        self.on_probe_selected = on_probe_selected
        self._dropdown_ref = ft.Ref[ft.Dropdown]()
        self._refresh_btn_ref = ft.Ref[ft.IconButton]()
        self._is_loading: bool = False

    def build(self) -> ft.Control:
        """返回探针选择器控件树。"""
        self._dropdown = ft.Dropdown(
            ref=self._dropdown_ref,
            width=340,
            menu_height=200,
            menu_width=340,
            dense=False,
            hint_text="选择调试探针",
            disabled=True,
            bgcolor=Colors.BG_ELEVATED,
            border=ft.Border(
                top=ft.BorderSide(1, Colors.BORDER),
                left=ft.BorderSide(1, Colors.BORDER),
                right=ft.BorderSide(1, Colors.BORDER),
                bottom=ft.BorderSide(1, Colors.BORDER),
            ),
            border_radius=6,
            options=[],
            on_select=self._on_change,
        )

        self._refresh_btn = ft.IconButton(
            ref=self._refresh_btn_ref,
            icon=ft.Icons.REFRESH,
            tooltip="刷新探针列表",
            on_click=self._on_refresh_click,
        )

        return ft.Row(
            controls=[self._dropdown, self._refresh_btn],
            spacing=Spacing.SM,
        )

    # ── 事件处理 ─────────────────────────────────────────

    async def _on_refresh_click(self, e: ft.ControlEvent) -> None:
        if self._is_loading:
            return
        self.set_loading(True)
        try:
            probes = self.on_refresh()
            self._dropdown.options.clear()
            if probes:
                for p in probes:
                    self._dropdown.options.append(
                        ft.dropdown.Option(
                            key=p.unique_id,
                            text=f"[{p.probe_type.upper()}] {p.description}",
                        )
                    )
                self._dropdown.disabled = False
                self._dropdown.hint_text = "选择调试探针"
            else:
                self._dropdown.disabled = True
                self._dropdown.hint_text = "未检测到探针"
            self._dropdown.update()
        finally:
            self.set_loading(False)

    def _on_change(self, e: ft.ControlEvent) -> None:
        if e.control.value:
            self.on_probe_selected(e.control.value)

    # ── 公共方法 ─────────────────────────────────────────

    def select_probe(self, unique_id: str) -> None:
        """程序化选中指定探针。"""
        if self._dropdown_ref.current:
            self._dropdown_ref.current.value = unique_id
            self._dropdown_ref.current.update()

    def set_loading(self, loading: bool) -> None:
        """切换加载状态（禁用控件防止重复操作）。"""
        self._is_loading = loading
        if self._dropdown_ref.current:
            self._dropdown_ref.current.disabled = loading
            if loading:
                self._dropdown_ref.current.hint_text = "正在扫描..."
            self._dropdown_ref.current.update()
        if self._refresh_btn_ref.current:
            self._refresh_btn_ref.current.disabled = loading
            self._refresh_btn_ref.current.update()
