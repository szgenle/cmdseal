#!/usr/bin/env python3
"""gui.settings 单测。

覆盖：
- 默认值回落（空 QSettings）
- save/load 往返
- 异常值的夹取（timeout 过大/过小/非数字）
- reset 清空后回落到默认
- default_template_prefs() 不受持久化影响

使用隔离的 QSettings 命名空间（OrganizationName = "cmdseal-tests"），
避免污染真实用户偏好；测试结束 clear() 一次兜底。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许从仓库根目录直接运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 必须在导入 gui.settings 前构造 QApplication，且改写 org name 避免污染
from PySide6.QtCore import QCoreApplication, QSettings  # noqa: E402

QCoreApplication.setOrganizationName("cmdseal-tests")
QCoreApplication.setApplicationName("cmdseal-tests")

from gui import settings  # noqa: E402


def _assert(cond: bool, desc: str) -> None:
    mark = "✓" if cond else "✗"
    print(f"  {mark} {desc}")
    if not cond:
        raise AssertionError(desc)


def _clear() -> None:
    QSettings().clear()


def test_defaults_on_empty_settings() -> None:
    print("== defaults ==")
    _clear()
    p = settings.load_template_prefs()
    _assert(p.name_prefix == "seal_", f"默认前缀 seal_ ({p.name_prefix})")
    _assert(p.try_run_timeout_ms == 10_000, f"默认超时 10s ({p.try_run_timeout_ms})")
    _assert(
        str(p.output_dir).endswith("cmdseal/bin"),
        f"默认目录 ~/cmdseal/bin ({p.output_dir})",
    )


def test_round_trip() -> None:
    print("== save/load round trip ==")
    _clear()
    settings.save_template_prefs(
        output_dir="/tmp/cmdseal_test_out",
        name_prefix="cs_",
        try_run_timeout_sec=30,
    )
    p = settings.load_template_prefs()
    _assert(str(p.output_dir) == "/tmp/cmdseal_test_out", f"目录保存成功 ({p.output_dir})")
    _assert(p.name_prefix == "cs_", f"前缀保存成功 ({p.name_prefix})")
    _assert(p.try_run_timeout_ms == 30_000, f"超时保存成功 ({p.try_run_timeout_ms})")


def test_timeout_clamped() -> None:
    print("== timeout 夹取 ==")
    _clear()
    # 保存时就夹取
    settings.save_template_prefs(
        output_dir="/tmp", name_prefix="seal_", try_run_timeout_sec=9999
    )
    p = settings.load_template_prefs()
    _assert(p.try_run_timeout_ms == 300 * 1000, f"上限 300s ({p.try_run_timeout_ms})")

    settings.save_template_prefs(
        output_dir="/tmp", name_prefix="seal_", try_run_timeout_sec=0
    )
    p = settings.load_template_prefs()
    _assert(p.try_run_timeout_ms == 1 * 1000, f"下限 1s ({p.try_run_timeout_ms})")


def test_load_handles_corrupt_timeout() -> None:
    print("== 损坏的 timeout 值回落默认 ==")
    _clear()
    s = QSettings()
    s.setValue(settings.K_TIMEOUT_SEC, "not-a-number")
    s.sync()
    p = settings.load_template_prefs()
    _assert(p.try_run_timeout_ms == 10_000, f"非数字回落到默认 10s ({p.try_run_timeout_ms})")


def test_reset() -> None:
    print("== reset ==")
    settings.save_template_prefs(
        output_dir="/tmp/abc",
        name_prefix="xxx_",
        try_run_timeout_sec=60,
    )
    p = settings.reset_template_prefs()
    defaults = settings.default_template_prefs()
    _assert(p.name_prefix == defaults.name_prefix, "reset 后前缀回到默认")
    _assert(
        p.try_run_timeout_ms == defaults.try_run_timeout_ms, "reset 后超时回到默认"
    )
    _assert(str(p.output_dir) == str(defaults.output_dir), "reset 后目录回到默认")


def test_default_snapshot_not_affected_by_saved() -> None:
    print("== default_template_prefs 不受持久化影响 ==")
    settings.save_template_prefs(
        output_dir="/tmp/foo", name_prefix="YYY_", try_run_timeout_sec=42
    )
    d = settings.default_template_prefs()
    _assert(d.name_prefix == "seal_", f"出厂默认前缀未被覆盖 ({d.name_prefix})")
    _assert(d.try_run_timeout_ms == 10_000, "出厂默认超时未被覆盖")


def main() -> int:
    try:
        test_defaults_on_empty_settings()
        test_round_trip()
        test_timeout_clamped()
        test_load_handles_corrupt_timeout()
        test_reset()
        test_default_snapshot_not_affected_by_saved()
    finally:
        # 清理测试命名空间，避免残留
        _clear()
    print("\nAll settings tests passed ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
