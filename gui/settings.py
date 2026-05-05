"""用户偏好设置的持久化层。

使用 Qt 自带的 QSettings；macOS 落到 ``~/Library/Preferences/`` 下的 plist，
与 Apple 约定一致，不自造 JSON/INI 配置，避免再维护一套读写/锁/容错。

A 档（最小版）暴露 3 项最常被换的默认值：
- 输出目录（template_wizard 默认保存位置）
- 文件名前缀（默认 ``seal_``）
- 试运行超时秒数

每条设置都带 fallback，fallback 与历史硬编码一致，升级无感。
每次向导内仍可临时覆盖；这里只影响「默认值」。
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QSettings

#: Fallback 默认值 —— 与 template_wizard 中之前的硬编码保持一致
_DEFAULT_OUTPUT_DIR = str(Path.home() / "cmdseal" / "bin")
_DEFAULT_NAME_PREFIX = "seal_"
_DEFAULT_TIMEOUT_SEC = 10

#: 超时合理范围：太短误杀正常命令，太长阻塞用户
_TIMEOUT_MIN_SEC = 1
_TIMEOUT_MAX_SEC = 300

#: QSettings key 常量；前缀分组便于将来扩展其它面板
K_OUTPUT_DIR = "template_wizard/output_dir"
K_NAME_PREFIX = "template_wizard/name_prefix"
K_TIMEOUT_SEC = "template_wizard/try_run_timeout_sec"

#: UI language preference (``auto`` / ``en`` / ``zh_CN``). Effective at next launch.
K_LANGUAGE = "app/language"
_DEFAULT_LANGUAGE = "auto"


class TemplatePrefs(NamedTuple):
    """TemplateWizard 使用的偏好快照；不可变，读一次用完即丢。"""

    output_dir: Path
    name_prefix: str
    try_run_timeout_ms: int


def _coerce_int(value: object, fallback: int) -> int:
    """QSettings 读出的值在不同平台类型不统一（str/int/None），统一转 int。"""
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def load_template_prefs() -> TemplatePrefs:
    """从 QSettings 读取偏好；任何字段缺失或损坏都回落到默认。"""
    s = QSettings()
    output_dir = Path(
        str(s.value(K_OUTPUT_DIR, _DEFAULT_OUTPUT_DIR))
    ).expanduser()
    name_prefix = str(s.value(K_NAME_PREFIX, _DEFAULT_NAME_PREFIX))

    timeout_sec = _coerce_int(
        s.value(K_TIMEOUT_SEC, _DEFAULT_TIMEOUT_SEC), _DEFAULT_TIMEOUT_SEC
    )
    # 夹在合理区间；用户手改 plist 的异常值不会让试运行跑 0 秒或挂一整天
    timeout_sec = max(_TIMEOUT_MIN_SEC, min(timeout_sec, _TIMEOUT_MAX_SEC))

    return TemplatePrefs(
        output_dir=output_dir,
        name_prefix=name_prefix,
        try_run_timeout_ms=timeout_sec * 1000,
    )


def save_template_prefs(
    *,
    output_dir: str,
    name_prefix: str,
    try_run_timeout_sec: int,
) -> None:
    """原子性地写回 3 个字段；调用方应已做过校验。"""
    s = QSettings()
    s.setValue(K_OUTPUT_DIR, output_dir)
    s.setValue(K_NAME_PREFIX, name_prefix)
    s.setValue(
        K_TIMEOUT_SEC,
        max(_TIMEOUT_MIN_SEC, min(int(try_run_timeout_sec), _TIMEOUT_MAX_SEC)),
    )
    s.sync()


def reset_template_prefs() -> TemplatePrefs:
    """删掉 3 个 key，让下次 load_* 完全走 fallback。返回重置后的快照。"""
    s = QSettings()
    for key in (K_OUTPUT_DIR, K_NAME_PREFIX, K_TIMEOUT_SEC):
        s.remove(key)
    s.sync()
    return load_template_prefs()


def default_template_prefs() -> TemplatePrefs:
    """不读 QSettings，直接返回出厂默认。用于「恢复默认」按钮的只读预览。"""
    return TemplatePrefs(
        output_dir=Path(_DEFAULT_OUTPUT_DIR).expanduser(),
        name_prefix=_DEFAULT_NAME_PREFIX,
        try_run_timeout_ms=_DEFAULT_TIMEOUT_SEC * 1000,
    )


# -------- UI language ---------------------------------------------------

def load_language() -> str:
    """Return the UI language code (``auto``/``en``/``zh_CN``). Defaults to ``auto``."""
    s = QSettings()
    code = str(s.value(K_LANGUAGE, _DEFAULT_LANGUAGE) or _DEFAULT_LANGUAGE)
    return code


def save_language(code: str) -> None:
    """Persist the UI language code. Takes effect on next GUI launch."""
    s = QSettings()
    s.setValue(K_LANGUAGE, code or _DEFAULT_LANGUAGE)
    s.sync()
