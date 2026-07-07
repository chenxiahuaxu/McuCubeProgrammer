"""i18n 多语言支持 — 基于 flet_l10n 的封装模块。

用法::

    from src.i18n import get_l10n, t

    # 初始化（App 启动时调用一次）
    l10n = get_l10n(locales_dir="locales")

    # UI 中使用
    label = t("probeSelectHint")
    count_label = t("targetCount", count=5)

    # 手动切换
    l10n.set_locale("en")

    # 注册语言变更回调
    l10n.on_locale_change(lambda lang: rebuild_ui())
"""

from __future__ import annotations

from flet_l10n import Localizations

_L10N: Localizations | None = None


def get_l10n(locales_dir: str = "locales") -> Localizations:
    """获取或初始化全局 L10n 单例。"""
    global _L10N  # pylint: disable=global-statement
    if _L10N is None:
        _L10N = Localizations(
            arb_dir=locales_dir,
            default_locale=None,  # auto-detect system language
            fallback_locale="zh",
        )
    return _L10N


def t(key: str, **kwargs) -> str:
    """翻译查找快捷函数。等价于 get_l10n().t(key, **kwargs)。"""
    if _L10N is None:
        return key  # 未初始化时返回 key 本身
    return _L10N.t(key, **kwargs)
