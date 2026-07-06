"""应用配置持久化 — JSON 文件存储用户选择。

配置目录: %APPDATA%/mcu-cube-programmer/config.json (Windows)
          ~/.config/mcu-cube-programmer/config.json (Linux/Mac)
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "mcu-cube-programmer"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = _config_dir() / "config.json"


def load() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    except UnicodeDecodeError:
        # Fallback: old config file may be in system default encoding (e.g. GBK on Windows)
        with open(CONFIG_PATH) as f:  # pylint: disable=unspecified-encoding
            return json.load(f)


def save(data: dict) -> None:
    """合并写入：读取现有配置 → 合并新值 → 写入。"""
    d = load()
    d.update(data)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def load_all() -> dict:
    return load()


def get(key: str, default=None):
    return load().get(key, default)


def set(key: str, value) -> None:
    d = load()
    d[key] = value
    save(d)
