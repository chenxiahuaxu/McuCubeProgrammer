"""App 主类 — 全局状态管理、窗口配置、Tab 路由。

整个应用的核心初始化文件。持有:
  - ft.Page 引用
  - asyncio 事件循环引用
  - 逻辑层实例 (ProbeManager / TargetManager / FlashController)
  - 共享 LogView 实例
"""

import asyncio

import flet as ft

from src.ui.theme import APP_TITLE, APP_VERSION, create_dark_theme
from src.utils.logger import add_log, Logger as _Logger


class App:
    """MCU Cube Programmer 应用主类。"""

    is_web: bool = False
    is_desktop: bool = False
    is_mobile: bool = False
    platform_name: str = "unknown"
    pyocd_available: bool = False

    def __init__(self, page: ft.Page) -> None:
        self.page: ft.Page = page
        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        self._detect_platform()
        add_log("INFO", f"平台: {App.platform_name}"
                f" | Web={App.is_web} | Desktop={App.is_desktop}"
                f" | pyOCD={'OK' if App.pyocd_available else 'N/A'}")

        self._configure_window()
        self._configure_page()
        self._configure_theme()

        # ── 窗口关闭拦截（仅桌面模式） ──
        if App.is_desktop:
            self.page.window.prevent_close = True
            self.page.window.on_event = self._on_window_event

        self._init_backend()
        self._init_log_view()
        self._build_tabs()

        # 启动日志写入 UI LogView
        add_log("INFO", "=" * 40)
        add_log("INFO", f"MCU Cube Programmer v{APP_VERSION} 已启动")
        add_log("INFO", f"平台: {App.platform_name} | pyOCD: {'可用' if App.pyocd_available else '不可用'}")

        # ── 启动时自动扫描探针（延迟确保UI就绪） ──
        asyncio.ensure_future(self._delayed_scan())

    async def _delayed_scan(self) -> None:
        await asyncio.sleep(0.5)  # 等待 UI 渲染完成
        await self._auto_scan_probes()

        self.page.update()

    # ── 平台检测 ──────────────────────────────────────────

    def _detect_platform(self) -> None:
        p = self.page.platform
        if p is None:
            type(self).platform_name = "web" if self.page.web else "unknown"
            type(self).is_web = self.page.web
            type(self).is_desktop = False
            type(self).is_mobile = False
        else:
            plat = str(p.value) if hasattr(p, "value") else str(p)
            type(self).platform_name = plat
            type(self).is_web = self.page.web
            type(self).is_desktop = plat in ("windows", "macos", "linux")
            type(self).is_mobile = plat in ("ios", "android", "android_tv")
        type(self).pyocd_available = App.is_desktop

    # ── 窗口配置 ──────────────────────────────────────────

    def _configure_window(self) -> None:
        self.page.title = f"{APP_TITLE} v{APP_VERSION}"
        if App.is_desktop:
            self.page.window.width = 1024
            self.page.window.height = 768
            self.page.window.min_width = 800
            self.page.window.min_height = 600

    def _configure_page(self) -> None:
        self.page.adaptive = True
        self.page.scroll = ft.ScrollMode.AUTO

    # ── 主题配置 ──────────────────────────────────────────

    def _configure_theme(self) -> None:
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = create_dark_theme()

    # ── 后端初始化 ────────────────────────────────────────

    def _init_backend(self) -> None:
        self.probe_manager = None
        self.target_manager = None
        self.flash_controller = None
        self._backend = None

        if App.pyocd_available:
            try:
                from src.backend.pyocd_backend import PyOCDBackend
                from src.logic.flash_controller import FlashController
                from src.logic.probe_manager import ProbeManager
                from src.logic.target_manager import TargetManager

                backend = PyOCDBackend()
                self._backend = backend
                self.probe_manager = ProbeManager(backend)
                self.target_manager = TargetManager(backend)
                self.flash_controller = FlashController(backend)
                add_log("INFO", "pyOCD 后端已初始化")
            except Exception as e:
                add_log("ERROR", f"pyOCD 后端初始化失败: {e}")
                if self._backend:
                    try:
                        self._backend.disconnect()
                    except Exception:
                        pass
                    self._backend = None

    # ── 日志视图 ──────────────────────────────────────────

    def _init_log_view(self) -> None:
        from src.ui.components.log_view import LogView

        self.log_view = LogView(max_lines=500)
        _Logger().set_callback(
            lambda entry: asyncio.run_coroutine_threadsafe(
                self._on_log_entry(entry), self.loop
            )
        )

    async def _on_log_entry(self, entry) -> None:
        """线程安全的日志回调 — 将日志条目写入 UI LogView。"""
        self.log_view.add_log(entry.level, entry.message)

    # ── UI 构建 ───────────────────────────────────────────

    def _build_tabs(self) -> None:
        tab_labels = ["Flash", "探针", "SWO", "日志", "设置"]
        tab_icons = [
            ft.Icons.FLASH_ON,
            ft.Icons.USB,
            ft.Icons.TERMINAL,
            ft.Icons.LIST_ALT,
            ft.Icons.SETTINGS,
]

        if self.probe_manager and self.target_manager and self.flash_controller:
            from src.ui.tabs.flash_tab import FlashTab
            from src.ui.tabs.log_tab import LogTab
            from src.ui.tabs.probe_tab import ProbeTab
            from src.ui.tabs.settings_tab import SettingsTab
            from src.ui.tabs.swo_tab import SwoTab

            flash_tab = FlashTab(
                page=self.page,
                probe_manager=self.probe_manager,
                target_manager=self.target_manager,
                flash_controller=self.flash_controller,
                log_view=self.log_view,
                loop=self.loop,
            )
            self.flash_tab = flash_tab
            probe_tab = ProbeTab(probe_manager=self.probe_manager)
            swo_tab = SwoTab(
                backend=self.flash_controller._backend,
                loop=self.loop,
                probe_manager=self.probe_manager,
                target_manager=self.target_manager,
            )
            self.swo_tab = swo_tab
            log_tab = LogTab(log_view=self.log_view, page=self.page)
            settings_tab = SettingsTab(page=self.page)

            tab_contents = [
                flash_tab.build(),
                probe_tab.build(),
                swo_tab.build(),
                log_tab.build(),
                settings_tab.build(),
            ]
        else:
            tab_texts = [
                f"Flash — pyOCD 不可用 ({App.platform_name})",
                "Probe — 探针信息区域",
                "Log — 日志输出区域",
                "Settings — 配置与关于",
            ]
            tab_contents = [self._placeholder_content(t) for t in tab_texts]

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            length=5,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label=tab_labels[i], icon=tab_icons[i])
                            for i in range(5)
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=tab_contents,
                    ),
                ],
            ),
        )
        self.page.add(self.tabs)

    @staticmethod
    def _placeholder_content(text: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(text, size=14, italic=True, color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
        )

    # ── 窗口关闭拦截 ─────────────────────────────────────

    def _on_window_event(self, e: ft.WindowEvent) -> None:
        if e.type == ft.WindowEventType.CLOSE:
            asyncio.ensure_future(self._on_close(e))

    async def _on_close(self, e: ft.WindowEvent) -> None:
        if self.flash_controller and self.flash_controller.is_running():
            def close_dlg():
                dlg.open = False
                self.page.update()

            async def force_close(ev):
                self.page.window.prevent_close = False
                self.page.window.on_event = None
                self.page.update()
                await self.page.window.close()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("烧录进行中"),
                content=ft.Text("当前正在进行烧录操作。强制关闭可能导致芯片处于不稳定状态。"),
                actions=[
                    ft.TextButton("等待完成", on_click=lambda ev: close_dlg()),
                    ft.FilledButton("强制关闭", on_click=force_close),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.dialog = dlg
            dlg.open = True
            self.page.update()
        else:
            try:
                await self.page.window.destroy()
            except RuntimeError:
                pass  # 会话已自然关闭，忽略

    # ── 自动扫描探针 ─────────────────────────────────────

    async def _auto_scan_probes(self) -> None:
        if not self.probe_manager:
            add_log("WARN", "后端未就绪，跳过自动探针扫描")
            return

        add_log("INFO", "正在扫描调试探针...")
        await asyncio.to_thread(self.probe_manager.scan_probes)
        count = self.probe_manager.get_probe_count()
        add_log("INFO", f"探针扫描完成，发现 {count} 个")

        if count > 0:
            from src.utils.config import load as cfg_load
            saved_uid = cfg_load().get("probe_uid")
            probes = self.probe_manager.get_probes()
            existing_uids = [p.unique_id for p in probes]
            uid = saved_uid if saved_uid in existing_uids else probes[0].unique_id
            if saved_uid and saved_uid != uid:
                add_log("WARN", f"上次探针不在线，使用 {uid[:12]}...")
            self.flash_tab.set_selected_probe(uid)
