"""Flash 标签页 — 主烧录工作流编排。

组装 ProbeSelector、TargetSelector、FirmwareFilePicker、FlashPanel，
并将用户操作串联为完整的烧录流程。是唯一允许导入逻辑层的 UI 组件。
"""

from __future__ import annotations

import asyncio
import os

import flet as ft

from src.logic.flash_controller import FlashController, FlashTask, FlashProgress
from src.logic.probe_manager import ProbeManager
from src.logic.target_manager import TargetManager
from src.ui.components.file_picker import FirmwareFilePicker
from src.ui.components.flash_panel import FlashPanel
from src.ui.components.log_view import LogView
from src.ui.components.probe_selector import ProbeSelector
from src.ui.components.target_selector import TargetSelector
from src.ui.theme import Colors, section_divider, Spacing
from src.utils.config import load as load_config, save


class FlashTab:
    """Flash 标签页 — 烧录工作流编排器。

    职责:
      - 组装子组件
      - 连接回调（探针选择→刷新芯片列表→…→烧录）
      - 包装 Pack 安装流程（FilePicker + 确认对话框 + 后台安装）
      - 将 FlashController 的进度回调桥接到 UI 主线程
    """

    def __init__(
        self,
        page: ft.Page,
        probe_manager: ProbeManager,
        target_manager: TargetManager,
        flash_controller: FlashController,
        log_view: LogView,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.page = page
        self.probe_manager = probe_manager
        self.target_manager = target_manager
        self.flash_controller = flash_controller
        self.log_view = log_view
        self.loop = loop

        # ── 基地址输入框 ──
        cfg = load_config()
        saved_base = cfg.get("base_address", "0x08000000")
        self._base_ref = ft.Ref[ft.TextField]()
        self._base_address: str = saved_base
        self._base_address_locked: bool = False

        # ── 子组件 ──
        self.probe_selector = ProbeSelector(
            on_refresh=lambda: probe_manager.scan_probes(),
            on_probe_selected=self._on_probe_selected,
        )
        self.target_selector = TargetSelector(
            targets=[],
            on_target_selected=self._on_target_selected,
            on_pick_pack=self._on_pick_pack,
        )
        self.file_picker = FirmwareFilePicker(
            page=page,
            on_file_selected=self._on_file_selected,
        )
        self.flash_panel = FlashPanel(
            on_erase=self._on_erase_click,
            on_flash=self._on_flash_click,
            on_cancel=self._on_cancel_click,
        )

        # ── Pack 安装用 FilePicker ──
        self._pack_picker = ft.FilePicker()

    # ── 构建 ─────────────────────────────────────────────

    def build(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                tight=True,
                spacing=Spacing.LG,
                controls=[
                    self.probe_selector.build(),
                    section_divider(),
                    self.target_selector.build(),
                    section_divider(),
                    self.file_picker.build(),
                    section_divider(),
                    self._build_base_address(),
                    section_divider(),
                    self.flash_panel.build(),
                ],
            ),
            padding=Spacing.XXL,
            expand=True,
        )

    # ── 回调 ─────────────────────────────────────────────

    def _on_probe_selected(self, unique_id: str) -> None:
        self.probe_manager.select_probe(unique_id)
        probe = self.probe_manager.get_selected_probe()
        if probe:
            self.log_view.add_log("INFO", f"已选择探针: {probe.description}")
        targets = self.target_manager.list_all_targets()
        self.target_selector.update_targets(targets)
        self._save_selections()

    def _on_target_selected(self, name: str) -> None:
        self.target_manager.select_target(name)
        self.log_view.add_log("INFO", f"已选择芯片: {name}")
        self._save_selections()

    def _on_file_selected(self, path: str) -> None:
        self.log_view.add_log("INFO", f"已选择固件: {path}")
        ext = os.path.splitext(path)[1].lower()
        is_addressed = ext in (".hex", ".elf", ".axf")

        if is_addressed:
            # 从文件解析起始地址，锁定输入框
            addr_start, _ = self.flash_controller._parse_addr_range(path, ext)
            if addr_start > 0:
                self._base_address = f"0x{addr_start:08X}"
                self._base_address_locked = True
                if self._base_ref.current:
                    self._base_ref.current.value = self._base_address
                    self._base_ref.current.read_only = True
                    self._base_ref.current.helper_text = "从文件自动解析（不可修改）"
                    self._base_ref.current.update()
                self.log_view.add_log("INFO", f"从固件文件解析基地址: {self._base_address}")
            else:
                self._base_address_locked = False
        else:
            # .bin 文件 — 允许手动输入
            self._base_address_locked = False
            if self._base_ref.current:
                self._base_ref.current.read_only = False
                self._base_ref.current.helper_text = "手动输入烧录地址"
                self._base_ref.current.update()

        self._save_selections()

    def _save_selections(self) -> None:
        """保存当前所有选择到配置文件。"""
        cfg = load_config()
        if self.probe_manager.get_selected_probe():
            cfg["probe_uid"] = self.probe_manager.get_selected_probe().unique_id
        if self.target_manager.get_selected_target():
            cfg["target_name"] = self.target_manager.get_selected_target()
        if self.file_picker.get_path():
            cfg["firmware_path"] = self.file_picker.get_path()
        cfg["base_address"] = self._base_address
        save(cfg)

    async def _on_pick_pack(self) -> None:
        files = await self._pack_picker.pick_files(
            dialog_title="选择 CMSIS-Pack 文件",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pack"],
            allow_multiple=False,
        )
        if files and len(files) > 0:
            pack_path = files[0].path or ""
            self._confirm_pack_install(pack_path)

    def _confirm_pack_install(self, pack_path: str) -> None:
        def close_dlg():
            dlg.open = False
            self.page.update()

        async def do_install():
            close_dlg()
            self.log_view.add_log("INFO", f"正在安装 Pack: {pack_path}")
            self.target_selector.set_loading(True)
            success = await asyncio.to_thread(
                self.target_manager.install_pack, pack_path
            )
            self.target_selector.set_loading(False)
            if success:
                targets = self.target_manager.list_all_targets()
                self.target_selector.update_targets(targets)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("安装 CMSIS-Pack"),
            content=ft.Text(f"确定要安装以下 Pack 吗？\n{pack_path}"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: close_dlg()),
                ft.FilledButton("安装", on_click=lambda e: self.page.run_task(do_install)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    # ── 操作 ─────────────────────────────────────────────

    def _on_erase_click(self) -> None:
        err = self._validate()
        if err:
            self.log_view.add_log("WARN", err)
            return
        # SWO 与烧录互斥
        self._stop_swo()
        self.page.run_task(self._do_erase)

    def _on_flash_click(self) -> None:
        err = self._validate()
        if err:
            self.log_view.add_log("WARN", err)
            return
        # SWO 与烧录互斥
        self._stop_swo()
        self.page.run_task(self._do_flash)

    def _stop_swo(self) -> None:
        try:
            self.flash_controller._backend.swo_stop()
        except Exception:
            pass

    def _on_cancel_click(self) -> None:
        self.flash_controller.cancel()
        self.flash_panel.set_status("正在取消...", is_error=True)

    async def _do_erase(self) -> None:
        self.flash_panel.set_running(True)
        self.log_view.add_log("INFO", "正在全片擦除 Flash...")
        try:
            await asyncio.to_thread(self.flash_controller._backend.erase_chip)
            self.log_view.add_log("DONE", "Flash 擦除完成")
            self.flash_panel.set_status("擦除完成", is_error=False)
        except Exception as e:
            self.log_view.add_log("ERROR", f"擦除失败: {e}")
            self.flash_panel.set_status(str(e), is_error=True)
        finally:
            self.flash_panel.set_running(False)

    async def _do_flash(self) -> None:
        self.flash_panel.set_running(True)

        base_addr = self._parse_base_address()

        task = FlashTask(
            firmware_path=self.file_picker.get_path() or "",
            target_name=self.target_manager.get_selected_target() or "",
            probe_uid=self.probe_manager.get_selected_probe().unique_id
            if self.probe_manager.get_selected_probe()
            else None,
            base_address=base_addr,
            frequency=load_config().get("swd_frequency", 200_000),
            erase_chip=False,
            swv_config={"system_clock": 168_000_000, "swo_clock": 400_000},
        )

        def on_progress(fp: FlashProgress) -> None:
            asyncio.run_coroutine_threadsafe(
                self._update_progress(fp), self.loop
            )

        result = await self.flash_controller.execute(task, on_progress=on_progress)
        self.flash_panel.set_complete(result.success, result.message)

    async def _update_progress(self, fp: FlashProgress) -> None:
        if fp.stage == "error":
            self.flash_panel.set_status(fp.message, is_error=True)
        else:
            self.flash_panel.set_progress(fp.percent, fp.message)

    # ── 校验 ─────────────────────────────────────────────


    def _build_base_address(self) -> ft.Row:
        """构建基地址输入行。"""
        def on_change(e):
            self._base_address = e.control.value.strip()
            self._save_selections()

        tf = ft.TextField(
            ref=self._base_ref,
            label="Flash 烧录基地址",
            value=self._base_address,
            width=200,
            text_size=13,
            read_only=self._base_address_locked,
            on_change=on_change,
            hint_text="例如 0x0800C000",
            prefix_icon=ft.Icons.MEMORY,
        )
        return ft.Row(
            controls=[
                tf,
                ft.Text(
                    "仅 .bin 文件有效，.hex/.elf 从文件内自动读取地址",
                    size=11,
                    color=Colors.TEXT_DIM,
                    italic=True,
                ),
            ],
            spacing=Spacing.MD,
        )

    def _parse_base_address(self) -> int:
        return int(self._base_address, 0)

    def _validate(self) -> str | None:
        if not self.probe_manager.get_selected_probe():
            return "请先选择调试探针"
        if not self.target_manager.get_selected_target():
            return "请先选择目标芯片"
        if not self.file_picker.get_path():
            return "请先选择固件文件"
        return None

    def set_selected_probe(self, unique_id: str) -> None:
        """自动选择探针并刷新芯片列表（启动时自动扫描后调用）。"""
        self.probe_manager.select_probe(unique_id)
        # 先填充探针下拉框，再选中
        probes = self.probe_manager.get_probes()
        dd = self.probe_selector._dropdown_ref.current
        if dd:
            dd.options.clear()
            for p in probes:
                dd.options.append(
                    ft.dropdown.Option(
                        key=p.unique_id,
                        text=f"[{p.probe_type.upper()}] {p.description}",
                    )
                )
            dd.value = unique_id
            dd.disabled = False
            dd.hint_text = "选择调试探针"
            dd.update()
        self.log_view.add_log("INFO", f"自动恢复探针: {unique_id[:12]}...")
        targets = self.target_manager.list_all_targets()
        self.target_selector.update_targets(targets)
        # 恢复上次选择的芯片
        saved_target = load_config().get("target_name")
        if saved_target:
            target_names = [t[0] for t in targets]
            if saved_target in target_names:
                self.target_selector.set_selected(saved_target)
                self.target_manager.select_target(saved_target)
                self.log_view.add_log("INFO", f"自动恢复芯片: {saved_target}")
            else:
                self.log_view.add_log("WARN", f"上次芯片 {saved_target} 不在当前列表中")
        self.file_picker.restore_last()
        self._save_selections()
