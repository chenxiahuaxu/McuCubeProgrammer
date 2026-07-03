"""主题配置模块 — 精密实验室仪器 (Precision Lab Instrument) 视觉系统。

设计参考: PCB 阻焊层、铜箔走线、示波器屏幕。
所有颜色通过 Colors 类引用，禁止组件中硬编码 hex 或 ft.Colors。
"""

from __future__ import annotations

import flet as ft

# ── 应用元信息 ─────────────────────────────────────────────

APP_TITLE: str = "MCU Cube Programmer"
APP_VERSION: str = "0.0.1"

# ── 颜色常量 ───────────────────────────────────────────────
# 参考: PCB 阻焊层绿 + 铜箔走线金 + 示波器深色屏幕


class Colors:
    """所有 UI 颜色统一从此处引用。

    设计参考:
        BG_ROOT:    PCB 关机示波器屏幕 → #0A0E14
        BG_SURFACE: 仪器面板铝壳 → #131820
        ACCENT:     PCB 阻焊层绿 → #26A641
        COPPER:     铜箔走线 → #D99A5A
    """

    # 背景色阶
    BG_ROOT = "#0A0E14"
    BG_SURFACE = "#131820"
    BG_ELEVATED = "#1B2330"
    BG_HOVER = "#1F2937"

    # 强调色
    ACCENT_PRIMARY = "#26A641"
    ACCENT_PRIMARY_HOVER = "#2DC84D"
    ACCENT_COPPER = "#D99A5A"
    ACCENT_COPPER_MUTED = "#8B6B4A"

    # 文字色阶
    TEXT_PRIMARY = "#E4E7EB"
    TEXT_SECONDARY = "#8B949E"
    TEXT_DIM = "#636D78"

    # 语义色
    SUCCESS = "#2DC84D"
    ERROR = "#F85149"
    WARNING = "#D29922"
    INFO = "#58A6FF"

    # 分割线/边框
    DIVIDER = "#21262D"
    BORDER = "#30363D"

    # 日志专用色
    LOG_INFO = "#58A6FF"
    LOG_WARN = "#D29922"
    LOG_ERROR = "#F85149"
    LOG_DONE = "#2DC84D"
    LOG_DEBUG = "#636D78"


# ── 间距常量 ───────────────────────────────────────────────
# 以 4px 为基础栅格单位


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24


# ── 字体常量 ───────────────────────────────────────────────


class Font:
    MONO = "Cascadia Code, JetBrains Mono, Consolas, monospace"

    class Size:
        TITLE = 18
        HEADING = 15
        BODY = 14
        CAPTION = 12
        MICRO = 10
        LOG = 12


# ── 公共工具函数 ───────────────────────────────────────────


def section_divider() -> ft.Divider:
    """铜色区块分隔线 — 设计文档的 Signature Element。"""
    return ft.Divider(height=1, color=Colors.ACCENT_COPPER)


def standard_divider() -> ft.Divider:
    """标准深色分隔线。"""
    return ft.Divider(height=1, color=Colors.DIVIDER)


def card_container(*, content: ft.Control, padding: int = Spacing.MD) -> ft.Container:
    """标准卡片容器 — 深色表面 + 1px 边框。"""
    return ft.Container(
        content=content,
        bgcolor=Colors.BG_SURFACE,
        border=ft.Border(
            top=ft.BorderSide(1, Colors.BORDER),
            left=ft.BorderSide(1, Colors.BORDER),
            right=ft.BorderSide(1, Colors.BORDER),
            bottom=ft.BorderSide(1, Colors.BORDER),
        ),
        border_radius=6,
        padding=padding,
    )


# ── 主题创建函数 ───────────────────────────────────────────


def create_app_theme(*, dark: bool) -> ft.Theme:
    """创建应用主题 — PCB 绿色作为 Material 3 seed。"""
    return ft.Theme(
        color_scheme_seed=Colors.ACCENT_PRIMARY,
        use_material3=True,
    )


def create_dark_theme() -> ft.Theme:
    return create_app_theme(dark=True)


def create_light_theme() -> ft.Theme:
    return create_app_theme(dark=False)
