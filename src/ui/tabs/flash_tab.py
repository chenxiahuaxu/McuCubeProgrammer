"""Flash 标签页 — 芯片选择 + 固件选择 + 烧录工作流。"""

from __future__ import annotations

import asyncio
import os

import flet as ft

from src.i18n import t
from src.logic.flash_controller import FlashController, FlashTask, FlashProgress
from src.logic.probe_manager import ProbeManager
from src.logic.target_manager import TargetManager
from src.ui.components.file_picker import FirmwareFilePicker
from src.ui.components.flash_panel import FlashPanel
from src.ui.components.log_view import LogView
from src.ui.components.target_selector import _VENDORS, _match_vendor
from src.ui.theme import Colors, Font, Spacing, section_divider
from src.utils.config import load as load_config, save


class FlashTab:
    """Flash 标签页 — 芯片选择 + 固件选择 + 烧录操作。"""

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        page: ft.Page,
        probe_manager: ProbeManager,
        target_manager: TargetManager,
        flash_controller: FlashController,
        log_view: LogView,
        *,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.page = page
        self.probe_manager = probe_manager
        self.target_manager = target_manager
        self.flash_controller = flash_controller
        self.log_view = log_view
        self.loop = loop

        cfg = load_config()
        self._saved_target: str = cfg.get("target_name", "")

        # ── 基地址输入框 ──
        saved_base = cfg.get("base_address", "0x08000000")
        self._base_ref = ft.Ref[ft.TextField]()
        self._base_address: str = saved_base
        self._base_address_locked: bool = False

        # ── 芯片选择下拉框 ──
        self._vendor_ref = ft.Ref[ft.Dropdown]()
        self._chip_ref = ft.Ref[ft.Dropdown]()

        # ── 子组件 ──
        self.file_picker = FirmwareFilePicker(
            page=page,
            on_file_selected=self._on_file_selected,
        )
        self.flash_panel = FlashPanel(
            on_erase=self._on_erase_click,
            on_flash=self._on_flash_click,
            on_cancel=self._on_cancel_click,
        )

    # ── 构建 ─────────────────────────────────────────────

    def build(self) -> ft.Control:
        vendor_dd = self._build_dropdown(self._vendor_ref)
        vendor_dd.options = [
            ft.dropdown.Option(key=k, text=f"{label} ({k})") for k, label, _ in _VENDORS
        ]
        vendor_dd.on_select = lambda e: self._populate_chips(e.control.value)

        chip_dd = self._build_dropdown(self._chip_ref)
        chip_dd.editable = True
        chip_dd.enable_filter = True
        chip_dd.menu_height = 280
        chip_dd.on_select = self._on_chip_selected

        return ft.Container(
            content=ft.Column(
                tight=True,
                spacing=Spacing.LG,
                controls=[
                    ft.Text(t("targetVendor"), size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY),
                    vendor_dd,
                    ft.Text(t("targetChip"), size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY),
                    chip_dd,
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

    # ── 芯片选择 ─────────────────────────────────────────

    def _build_dropdown(self, ref) -> ft.Dropdown:
        return ft.Dropdown(
            ref=ref,
            dense=True,
            text_size=11,
            bgcolor=Colors.BG_ELEVATED,
            border=ft.Border(
                top=ft.BorderSide(1, Colors.BORDER),
                left=ft.BorderSide(1, Colors.BORDER),
                right=ft.BorderSide(1, Colors.BORDER),
                bottom=ft.BorderSide(1, Colors.BORDER),
            ),
            border_radius=4,
            width=260,
        )

    def _populate_chips(self, vendor_key: str) -> None:
        if not vendor_key:
            return
        prefix = ""
        for k, _, p in _VENDORS:
            if k == vendor_key:
                prefix = p
                break
        all_targets = self.target_manager.list_all_targets()
        if prefix:
            if vendor_key == "OTHER":
                all_prefixes = [p for _, _, p in _VENDORS if p]
                chips = [n for n, _ in all_targets if not any(_match_vendor(n, pp) for pp in all_prefixes)]
            else:
                chips = [n for n, _ in all_targets if _match_vendor(n, prefix)]
        else:
            chips = [n for n, _ in all_targets]
        self._chip_ref.current.options = [
            ft.dropdown.Option(key=name, text=name) for name in chips
        ]
        self._chip_ref.current.hint_text = t("targetCount", count=len(chips))
        self._chip_ref.current.update()

    def _on_chip_selected(self, e: ft.ControlEvent) -> None:
        name = e.control.value
        if name:
            self.target_manager.select_target(name)
            cfg = load_config()
            cfg["target_name"] = name
            save(cfg)

    # ── 固件选择 ─────────────────────────────────────────

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
                    self._base_ref.current.helper_text = t("flashAddressLockedHint")
                    self._base_ref.current.update()
                self.log_view.add_log("INFO", f"从固件文件解析基地址: {self._base_address}")
            else:
                self._base_address_locked = False
        else:
            # .bin 文件 — 允许手动输入
            self._base_address_locked = False
            if self._base_ref.current:
                self._base_ref.current.read_only = False
                self._base_ref.current.helper_text = t("flashAddressManualHint")
                self._base_ref.current.update()

        self._save_selections()

    def _save_selections(self) -> None:
        """保存固件路径和基地址到配置文件。"""
        cfg = load_config()
        if self.file_picker.get_path():
            cfg["firmware_path"] = self.file_picker.get_path()
        cfg["base_address"] = self._base_address
        save(cfg)

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
        except Exception:  # pylint: disable=broad-exception-caught  # OK: UI error handler
            pass

    def _on_cancel_click(self) -> None:
        self.flash_controller.cancel()
        self.flash_panel.set_status(t("flashCancelling"), is_error=True)

    async def _do_erase(self) -> None:
        self.flash_panel.set_running(True)
        self.log_view.add_log("INFO", "正在全片擦除 Flash...")
        try:
            await asyncio.to_thread(self.flash_controller._backend.erase_chip)
            self.log_view.add_log("DONE", "Flash 擦除完成")
            self.flash_panel.set_status(t("flashEraseComplete"), is_error=False)
        except Exception as e:  # pylint: disable=broad-exception-caught  # OK: UI error handler
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
            erase_chip=self.flash_panel.erase_chip,
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
            label=t("flashBaseAddress"),
            value=self._base_address,
            width=200,
            text_size=13,
            read_only=self._base_address_locked,
            on_change=on_change,
            hint_text=t("flashExampleAddress"),
            prefix_icon=ft.Icons.MEMORY,
        )
        return ft.Row(
            controls=[
                tf,
                ft.Text(
                    t("flashAddressNote"),
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
            return t("flashValidateProbe")
        if not self.target_manager.get_selected_target():
            return t("flashValidateChip")
        if not self.file_picker.get_path():
            return t("flashValidateFirmware")
        return None
