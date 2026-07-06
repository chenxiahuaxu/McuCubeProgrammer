"""MCU Cube Programmer — 应用入口。

通过 Flet 框架启动 Material Design 3 应用，支持桌面/Web/移动端。

用法:
    python src/main.py              # 桌面原生窗口（默认）
    python src/main.py --web        # Web 模式 → http://localhost:8550
    python src/main.py --web -p 9000  # Web 模式 → http://localhost:9000
"""

import argparse
import io
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import flet as ft

# 将项目根目录加入 sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.app import App  # noqa: E402
from src.utils.logger import add_log  # noqa: E402

# ── 抑制 pyOCD 噪音：Board ID / CoreSight ──
logging.getLogger("pyocd").setLevel(logging.ERROR)

# SVD 文件 BOM 兼容修复
try:
    from pyocd.debug.svd import parser as _svd_parser

    def _patched_for_xml_file(path, remove_reserved=True):
        if isinstance(path, str):
            with open(path, "rb") as f:
                raw = f.read()
        else:
            try:
                path.seek(0)
            except Exception:  # pylint: disable=broad-exception-caught  # OK: top-level error handler
                pass
            raw = path.read()
        # 跳过 BOM 或前置垃圾字节，找到 XML 声明
        idx = raw.find(b"<")
        if idx > 0:
            raw = raw[idx:]
        return _svd_parser.SVDParser(ET.parse(io.BytesIO(raw)), remove_reserved)

    _svd_parser.SVDParser.for_xml_file = staticmethod(_patched_for_xml_file)
except Exception:  # pylint: disable=broad-exception-caught  # OK: top-level error handler
    pass

DEFAULT_WEB_PORT = 8550


def main(page: ft.Page) -> None:
    """Flet 应用入口函数。"""
    App(page)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCU Cube Programmer — 跨平台 MCU 烧录工具")
    parser.add_argument("--web", action="store_true", help="以 Web 模式启动")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_WEB_PORT,
                        help=f"Web 端口（默认 {DEFAULT_WEB_PORT}）")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.web:
        APP_URL = f"http://localhost:{args.port}"
        add_log("INFO", f"[Web] 服务已启动 → {APP_URL}")
        add_log("INFO", "请勿关闭此窗口，关闭将停止服务")
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=args.port)
    else:
        add_log("INFO", "[Desktop] 桌面模式已启动 (窗口大小 1024x768)")
        ft.run(main)
