"""可复用的单通道波形弹窗 — 示波器风格交互。

通过数据回调解耦，可在任何数据源上复用：
    dlg = WaveformDialog(page, loop)
    await dlg.show("变量名", get_history=lambda: my_data)
    dlg.close()
"""

from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft
import flet_charts as fch

from src.i18n import t
from src.ui.theme import Colors, Font, Spacing

_HORI_DIV = 10
_STD_VALUES = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]


def _nice_interval(span: float, target_ticks: int = 5) -> float:
    """计算对齐到 1/2/5 的刻度间隔"""
    if span <= 0:
        return 1.0
    raw = span / target_ticks
    exp = 10 ** int(__import__("math").log10(raw))
    mantissa = raw / exp
    if mantissa < 1.5:
        nice = 1
    elif mantissa < 3:
        nice = 2
    elif mantissa < 7:
        nice = 5
    else:
        nice = 10
    return nice * exp


class WaveformDialog:
    """单通道波形弹窗。

    特性：
    - sec/Div 工具栏调整时间分辨率
    - 滚轮缩放（不影响时间轴位置）
    - 水平滑块平移（仅在数据超出可视范围时显示，不能拖到数据之外）
    - Auto-scroll / Auto Y
    - Fit 按钮自适应
    """

    def __init__(self, page: ft.Page, loop: asyncio.AbstractEventLoop):
        self._page = page
        self._loop = loop

        # 状态
        self._name: str = ""
        self._get_history: Callable[[], list[tuple[float, float]]] | None = None
        self._time_origin: float = 0.0
        self._sec_div: float = 1.0
        self._scroll_offset: float = 0.0
        self._auto_scroll: bool = True
        self._auto_y: bool = True
        self._min_sec_div: float = 0.1
        self._max_sec_div: float = 30.0  # 根据数据量动态调整

        # 控件
        self._dlg: ft.AlertDialog | None = None
        self._chart: fch.LineChart | None = None
        self._sec_div_label: ft.Text | None = None
        self._slider: ft.Slider | None = None
        self._refreshing: bool = False

    # ── 公开 API ───────────────────────────────────────────

    async def show(
        self,
        name: str,
        get_history: Callable[[], list[tuple[float, float]]],
        time_origin: float = 0.0,
        fixed_y: tuple[float, float] | None = None,
        sample_interval: float = 0.5,
    ) -> None:
        """显示波形弹窗。

        Args:
            name: 标题中显示的名称
            get_history: 数据回调，返回 [(timestamp, value), ...]
            time_origin: 时间原点（用于计算相对时间）
            fixed_y: 固定 Y 轴范围 (min, max)，为 None 时自动计算
            sample_interval: 数据采样间隔（秒），决定 sec/Div 下限和步进
        """
        self._name = name
        self._get_history = get_history
        self._time_origin = time_origin
        self._sample_interval = sample_interval
        self._min_sec_div = max(0.1, sample_interval * 2)  # 至少 2 个采样点可见
        self._sec_div = max(self._min_sec_div, 1.0)
        self._scroll_offset = 0.0
        self._auto_scroll = True
        if fixed_y is not None:
            self._auto_y = False
            self._fixed_y_min, self._fixed_y_max = fixed_y
        else:
            self._auto_y = True
            self._fixed_y_min, self._fixed_y_max = 0.0, 1.0

        self._build_dialog()

        # 固定 Y 轴时立即设范围
        if fixed_y is not None and self._chart:
            self._chart.min_y = fixed_y[0]
            self._chart.max_y = fixed_y[1]

        # 启动自动刷新
        self._loop.create_task(self._auto_refresh_loop())

        await self._refresh()

    def close(self) -> None:
        """关闭弹窗。"""
        self._name = ""
        self._get_history = None
        if self._dlg:
            self._dlg.open = False
            if self._page:
                self._page.update()
            self._dlg = None
        self._chart = None
        self._sec_div_label = None
        self._slider = None

    @property
    def is_open(self) -> bool:
        return self._dlg is not None

    async def _auto_refresh_loop(self) -> None:
        """定时刷新图表，跟随后台数据增长"""
        while self._dlg is not None:
            await asyncio.sleep(0.5)
            if self._dlg is None:
                break
            await self._refresh()

    # ── 构建 ───────────────────────────────────────────────

    def _build_dialog(self) -> None:
        self._sec_div_label = ft.Text(
            "1.0s", size=Font.Size.CAPTION, color=Colors.ACCENT_PRIMARY,
        )
        auto_scroll_cb = ft.Checkbox(
            label=t("waveformAutoScroll"), value=True,
            on_change=lambda e: self._set_auto_scroll(e.control.value),
        )
        auto_y_cb = ft.Checkbox(
            label=t("waveformAutoY"), value=self._auto_y,
            disabled=not self._auto_y,  # fixed_y 时禁选
            on_change=lambda e: self._set_auto_y(e.control.value),
        )
        self._chart = fch.LineChart(
            width=540, height=300,
            interactive=False, data_series=[],
            min_x=0, max_x=10, min_y=-1, max_y=1,
            border=ft.Border.all(1, Colors.TEXT_DIM),
        )
        self._slider = ft.Slider(
            min=0, max=1_000_000, value=0,
            visible=False,
            on_change=self._on_slider,
        )

        content = ft.Column(controls=[
            ft.Row(controls=[
                ft.Text(t("waveformSecDiv") + ":", size=Font.Size.CAPTION, color=Colors.TEXT_SECONDARY),
                self._sec_div_label,
                auto_scroll_cb,
                auto_y_cb,
            ], spacing=Spacing.SM, wrap=True),
            ft.Container(
                content=ft.GestureDetector(
                    content=self._chart,
                    on_scroll=self._on_scroll,
                ),
                width=560, height=300,
            ),
            self._slider,
        ], spacing=Spacing.SM, width=560)

        self._dlg = ft.AlertDialog(
            modal=True,
            open=True,
            title=ft.Text(t("waveformTitle", name=self._name)),
            content=content,
            actions=[
                ft.ElevatedButton(
                    content=ft.Text(t("waveformFit"), size=Font.Size.CAPTION),
                    on_click=lambda _: self._on_fit(),
                ),
                ft.ElevatedButton(
                    content=ft.Text(t("waveformClose")),
                    on_click=lambda _: self.close(),
                ),
            ],
        )
        self._page.show_dialog(self._dlg)
        self._loop.create_task(self._refresh())

    # ── 事件处理 ───────────────────────────────────────────

    def _set_auto_scroll(self, v: bool) -> None:
        self._auto_scroll = v
        self._loop.create_task(self._refresh())

    def _set_auto_y(self, v: bool) -> None:
        self._auto_y = v
        self._loop.create_task(self._refresh())

    def _on_fit(self) -> None:
        history = self._get_history() if self._get_history else []
        if len(history) >= 2:
            total_sec = history[-1][0] - history[0][0]
            if total_sec > 0:
                target = total_sec / _HORI_DIV
                values = _STD_VALUES + [self._max_sec_div]
                best = min(values, key=lambda v: abs(v - target))
                self._sec_div = best
                if self._sec_div_label:
                    self._sec_div_label.value = f"{best:.2f}s"
                    self._sec_div_label.update()
                self._loop.create_task(self._refresh())

    def _on_scroll(self, e: ft.ScrollEvent) -> None:
        """滚轮缩放 — 保持视图中心不动。"""
        # 保存当前中心
        if self._chart:
            old_center = (self._chart.min_x + self._chart.max_x) / 2
        else:
            old_center = self._scroll_offset

        dy = e.scroll_delta.y
        factor = 1.15
        if dy > 0:
            self._sec_div = max(self._min_sec_div, self._sec_div / factor)
        else:
            self._sec_div = min(self._max_sec_div, self._sec_div * factor)

        self._auto_scroll = False
        self._scroll_offset = old_center

        if self._sec_div_label:
            self._sec_div_label.value = f"{self._sec_div:.2f}s"
            self._sec_div_label.update()
        self._loop.create_task(self._refresh())

    def _on_slider(self, e: ft.ControlEvent) -> None:
        try:
            self._scroll_offset = float(e.control.value)
        except (ValueError, AttributeError):
            self._scroll_offset = 0.0
        self._auto_scroll = False
        self._loop.create_task(self._refresh())

    # ── 刷新 ───────────────────────────────────────────────

    async def _refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            if not self._chart or not self._get_history:
                return

            history = self._get_history()
            if not history:
                return

            time_origin = self._time_origin or history[0][0]
            chart = self._chart
            visible_sec = self._sec_div * _HORI_DIV
            half_visible = visible_sec / 2
            latest_x = (history[-1][0] - time_origin) if history else 0.0
            first_x = (history[0][0] - time_origin) if history else 0.0
            total_span = latest_x - first_x

            # 根据数据量动态调整 sec/Div 上限
            self._max_sec_div = max(10.0, total_span / _HORI_DIV)

            # 时间窗口
            if self._auto_scroll:
                chart.max_x = latest_x
                chart.min_x = max(0, latest_x - visible_sec)
                self._scroll_offset = max(half_visible, latest_x - half_visible)
            else:
                center = max(half_visible, self._scroll_offset)
                chart.min_x = max(0, center - half_visible)
                chart.max_x = center + half_visible

            # ── 窗口裁剪到数据范围内，避免空画布 ──
            # 右边不超出最新数据
            if chart.max_x > latest_x:
                delta = chart.max_x - latest_x
                chart.max_x = latest_x
                chart.min_x = max(0, chart.min_x - delta)
            # 左边不超出最早数据
            if chart.min_x < first_x:
                chart.min_x = first_x
                chart.max_x = first_x + visible_sec
            # 确保最小值合法
            if chart.min_x < 0:
                chart.min_x = 0
                chart.max_x = visible_sec

            # 只取可见范围，Y 值钳位，边界插值防止线条溢出
            x_min, x_max = chart.min_x, chart.max_x
            y_min_c, y_max_c = chart.min_y, chart.max_y
            pts_raw = [(ts - time_origin, val) for ts, val in history if val is not None]

            visible = [(x, min(y_max_c, max(y_min_c, y)))
                       for x, y in pts_raw if x_min <= x <= x_max]

            # 边界插值：如果左侧最近有数据点，补一个边界点
            left_of = [(x, y) for x, y in pts_raw if x < x_min]
            if left_of and visible:
                lx, ly = left_of[-1]
                vx0, vy0 = visible[0]
                t = (x_min - lx) / (vx0 - lx) if vx0 != lx else 1
                iy = ly + (vy0 - ly) * t
                visible.insert(0, (x_min, min(y_max_c, max(y_min_c, iy))))

            # 边界插值：右侧最近数据点
            right_of = [(x, y) for x, y in pts_raw if x > x_max]
            if right_of and visible:
                rx, ry = right_of[0]
                vx1, vy1 = visible[-1]
                t = (x_max - vx1) / (rx - vx1) if rx != vx1 else 1
                iy = vy1 + (ry - vy1) * t
                visible.append((x_max, min(y_max_c, max(y_min_c, iy))))

            points = [fch.LineChartDataPoint(x=x, y=y) for x, y in visible]

            # 兜底：窗口内无数据时，用最近两个点填充避免空画布
            if not points and pts_raw:
                pts_raw_sorted = sorted(pts_raw, key=lambda p: abs(p[0] - (x_min + x_max) / 2))
                points = [fch.LineChartDataPoint(x=x, y=min(y_max_c, max(y_min_c, y)))
                          for x, y in pts_raw_sorted[:2]]
            if not points:
                return

            series = fch.LineChartData(
                points=points,
                stroke_width=2,
                color="#26A641",
                curved=False,
                prevent_curve_over_shooting=True,
            )

            # Auto Y / Fixed Y
            if self._auto_y:
                vals = [
                    val for ts, val in history
                    if val is not None
                    and chart.min_x <= (ts - time_origin) <= chart.max_x
                ]
                if vals:
                    dmin, dmax = min(vals), max(vals)
                    span = dmax - dmin
                    pad = span * 0.05 if span != 0 else 1.0
                    chart.min_y = dmin - pad
                    chart.max_y = dmax + pad
            else:
                chart.min_y = self._fixed_y_min
                chart.max_y = self._fixed_y_max

            # data_series 后重设 min/max 防止图表自动缩放
            chart.data_series = [series]
            chart.min_x = chart.min_x
            chart.max_x = chart.max_x
            chart.min_y = chart.min_y
            chart.max_y = chart.max_y

            # ── 坐标轴 ──
            chart.bottom_axis = self._build_time_axis(chart.min_x, chart.max_x)
            chart.left_axis = self._build_value_axis(chart.min_y, chart.max_y)
            chart.horizontal_grid_lines = None
            chart.vertical_grid_lines = None

            chart.update()

            # 滑块可见性与范围
            if self._slider:
                needs_slider = total_span > visible_sec
                self._slider.visible = needs_slider
                if needs_slider:
                    s_min = first_x + half_visible
                    s_max = max(s_min, latest_x - half_visible)
                    sv = s_max if self._auto_scroll else max(s_min, min(s_max, self._slider.value))
                    self._slider.value = sv
                    self._slider.min = s_min
                    self._slider.max = s_max
                self._slider.update()
        finally:
            self._refreshing = False

    # ── 坐标轴生成 ───────────────────────────────────────

    @staticmethod
    def _build_time_axis(x_min: float, x_max: float) -> fch.ChartAxis:
        """生成横轴标签 — 对齐整数刻度，始终包含首尾"""
        span = x_max - x_min
        if span <= 0:
            return fch.ChartAxis(show_labels=False)
        step = _nice_interval(span, 8)
        labels: list[fch.ChartAxisLabel] = []
        labels.append(fch.ChartAxisLabel(
            value=x_min,
            label=ft.Text(f"{x_min:.1f}s", size=10, color=Colors.TEXT_DIM),
        ))
        t = (int(x_min / step) + 1) * step if step > 0 else x_min + step
        while t < x_max:
            labels.append(fch.ChartAxisLabel(
                value=t,
                label=ft.Text(f"{t:.1f}s", size=10, color=Colors.TEXT_DIM),
            ))
            t += step
        labels.append(fch.ChartAxisLabel(
            value=x_max,
            label=ft.Text(f"{x_max:.1f}s", size=10, color=Colors.TEXT_DIM),
        ))
        return fch.ChartAxis(labels=labels, label_size=30)

    @staticmethod
    def _build_value_axis(y_min: float, y_max: float) -> fch.ChartAxis:
        """生成纵轴标签 — 对齐整数刻度，始终包含首尾"""
        span = y_max - y_min
        if span <= 0:
            return fch.ChartAxis(show_labels=False)
        step = _nice_interval(span, 8)
        labels: list[fch.ChartAxisLabel] = []
        labels.append(fch.ChartAxisLabel(
            value=y_min,
            label=ft.Text(f"{y_min:.3f}".rstrip("0").rstrip("."), size=10, color=Colors.TEXT_DIM),
        ))
        v = (int(y_min / step) + 1) * step if step > 0 else y_min + step
        while v < y_max:
            labels.append(fch.ChartAxisLabel(
                value=v,
                label=ft.Text(f"{v:.3f}".rstrip("0").rstrip("."), size=10, color=Colors.TEXT_DIM),
            ))
            v += step
        labels.append(fch.ChartAxisLabel(
            value=y_max,
            label=ft.Text(f"{y_max:.3f}".rstrip("0").rstrip("."), size=10, color=Colors.TEXT_DIM),
        ))
        return fch.ChartAxis(labels=labels, label_size=36)
