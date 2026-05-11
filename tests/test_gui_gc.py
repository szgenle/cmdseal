#!/usr/bin/env python3
"""测试 U2：GUI Manage Runners 面板接入 gc 能力。

验证点：
1. backend.gc_runners() 正确拼接 argv（--json / --dry-run / --yes）并解析返回
2. backend.gc_runners() rc=1 但 stdout 是合法 JSON → 返回 dict + _partial=True
3. backend.gc_runners() rc!=0 且 stdout 不是 JSON → 抛 CalledProcessError
4. runner_list._classify_status 的 live/orphan/legacy 分类与 CLI 端一致
5. RunnerListWindow.refresh() 扫出孤儿后 _btn_gc 可点击；无孤儿时 disabled
6. RunnerListWindow._run_gc() 未勾选 dry-run 时直走 gc_runners(apply=True)
7. RunnerListWindow._run_gc() 勾选 dry-run 时先调 apply=False 做一致性
   校验，一致则追调 apply=True；不一致则中止，且不触发真实删除
8. RunnerListWindow._run_gc() apply 返回 _partial=True → 弹 warning 而非 information

测试不需要 macOS keychain，不需要 subprocess；所有外部调用用 monkeypatch 打掉。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# 必须在任何 Qt widget 构造前拿到 QApplication。
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import backend, runner_list  # noqa: E402


# ---- _classify_status ----------------------------------------------------

def test_classify_live_orphan_legacy(tmp_path: Path) -> None:
    live_bin = tmp_path / "exists"
    live_bin.write_text("ELF")
    gone_bin = tmp_path / "gone"

    live_item = {"service": "cmdseal.a.K",
                 "_meta": {"output_path": str(live_bin)}}
    orphan_item = {"service": "cmdseal.b.K",
                   "_meta": {"output_path": str(gone_bin)}}
    legacy_no_meta = {"service": "cmdseal.c.K", "_meta": None}
    legacy_no_path = {"service": "cmdseal.d.K", "_meta": {"label": "x"}}

    assert runner_list._classify_status(live_item) == "live"
    assert runner_list._classify_status(orphan_item) == "orphan"
    assert runner_list._classify_status(legacy_no_meta) == "legacy"
    assert runner_list._classify_status(legacy_no_path) == "legacy"
    print("  ✅ _classify_status: live / orphan / legacy 三分类一致")


# ---- backend.gc_runners argv 拼接 ---------------------------------------

class _FakeCompleted:
    def __init__(self, stdout: str = "", stderr: str = "",
                 returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.args: list[str] = []


def test_backend_gc_runners_dry_run() -> None:
    captured: dict[str, list[str]] = {"argv": []}

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        captured["argv"] = argv
        res = _FakeCompleted(
            stdout='{"orphans": [], "live": [], "legacy": [], '
                   '"would_delete": true}',
            returncode=0,
        )
        res.args = argv
        return res

    with patch.object(backend.subprocess, "run", side_effect=fake_run):
        report = backend.gc_runners(apply=False)

    assert "--dry-run" in captured["argv"], captured["argv"]
    assert "--yes" not in captured["argv"], captured["argv"]
    assert "--json" in captured["argv"], captured["argv"]
    assert report == {"orphans": [], "live": [], "legacy": [],
                      "would_delete": True}
    print("  ✅ backend.gc_runners(apply=False) 拼 --dry-run --json")


def test_backend_gc_runners_apply() -> None:
    captured: dict[str, list[str]] = {"argv": []}

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        captured["argv"] = argv
        res = _FakeCompleted(
            stdout='{"orphans": [{"service": "cmdseal.x.K"}], '
                   '"live": [], "legacy": [], "would_delete": false}',
            returncode=0,
        )
        res.args = argv
        return res

    with patch.object(backend.subprocess, "run", side_effect=fake_run):
        report = backend.gc_runners(apply=True)

    assert "--yes" in captured["argv"], captured["argv"]
    assert "--dry-run" not in captured["argv"], captured["argv"]
    assert "--json" in captured["argv"], captured["argv"]
    assert report["orphans"] == [{"service": "cmdseal.x.K"}]
    print("  ✅ backend.gc_runners(apply=True) 拼 --yes --json")


def test_backend_gc_runners_partial_failure() -> None:
    """rc=1 但 stdout 是合法 JSON → 返回 dict 带 _partial=True。"""
    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        res = _FakeCompleted(
            stdout='{"orphans": [{"service": "cmdseal.a.K", '
                   '"account": "ws"}], "live": [], "legacy": [], '
                   '"would_delete": false}',
            stderr="helper delete failed for cmdseal.a.K\n",
            returncode=1,
        )
        res.args = argv
        return res

    with patch.object(backend.subprocess, "run", side_effect=fake_run):
        report = backend.gc_runners(apply=True)

    assert report.get("_partial") is True, report
    assert report.get("_rc") == 1, report
    assert "helper delete failed" in report.get("_stderr", ""), report
    assert report["orphans"][0]["service"] == "cmdseal.a.K"
    print("  ✅ backend.gc_runners rc=1+JSON → _partial=True")


def test_backend_gc_runners_rc1_no_json_raises() -> None:
    """rc!=0 且 stdout 不是合法 JSON → 抛 CalledProcessError。"""
    import subprocess as _sp

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompleted:
        res = _FakeCompleted(
            stdout="Traceback: KeychainNotUnlocked\n",
            stderr="fatal\n",
            returncode=2,
        )
        res.args = argv
        return res

    with patch.object(backend.subprocess, "run", side_effect=fake_run):
        raised = False
        try:
            backend.gc_runners(apply=True)
        except _sp.CalledProcessError as e:
            raised = True
            assert e.returncode == 2
        assert raised, "expected CalledProcessError for rc!=0 + bad stdout"
    print("  ✅ backend.gc_runners rc=2+非 JSON → 抛 CalledProcessError")


# ---- RunnerListWindow.refresh() gc 按钮开关 -----------------------------

def _ensure_app() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _mk_items(tmp_path: Path) -> tuple[list[dict], Path]:
    """构造：1 live + 2 orphan + 1 legacy（共 4 条）。"""
    live_bin = tmp_path / "live"
    live_bin.write_text("ELF")

    items = [
        {"service": "cmdseal.live.K", "account": "ws",
         "_meta": {"output_path": str(live_bin), "label": "alive"}},
        {"service": "cmdseal.o1.K", "account": "ws",
         "_meta": {"output_path": str(tmp_path / "nope1"),
                   "label": "gone-1"}},
        {"service": "cmdseal.o2.K", "account": "ws",
         "_meta": {"output_path": str(tmp_path / "nope2"),
                   "label": "gone-2"}},
        {"service": "cmdseal.legacy.K", "account": "ws", "_meta": None},
    ]
    return items, live_bin


def test_refresh_enables_gc_when_orphans_present(tmp_path: Path) -> None:
    _ensure_app()
    items, _ = _mk_items(tmp_path)
    with patch.object(runner_list, "list_sealed", return_value=items):
        w = runner_list.RunnerListWindow()
    assert w._table.rowCount() == 4
    assert w._btn_gc.isEnabled()
    assert len(w._orphans_cache) == 2
    assert "2" in w._status.text()
    w.close()
    print("  ✅ refresh 有孤儿 → _btn_gc enabled，_orphans_cache=2")


def test_refresh_disables_gc_when_no_orphans(tmp_path: Path) -> None:
    _ensure_app()
    live_bin = tmp_path / "alive"
    live_bin.write_text("ELF")
    items = [
        {"service": "cmdseal.a.K", "account": "ws",
         "_meta": {"output_path": str(live_bin), "label": "only"}},
        {"service": "cmdseal.b.K", "account": "ws", "_meta": None},
    ]
    with patch.object(runner_list, "list_sealed", return_value=items):
        w = runner_list.RunnerListWindow()
    assert not w._btn_gc.isEnabled()
    assert len(w._orphans_cache) == 0
    w.close()
    print("  ✅ refresh 无孤儿 → _btn_gc disabled")


# ---- _run_gc 各条路径 ----------------------------------------------------

def test_run_gc_no_dry_run_directly_deletes(tmp_path: Path) -> None:
    _ensure_app()
    items, _ = _mk_items(tmp_path)
    with patch.object(runner_list, "list_sealed", return_value=items):
        w = runner_list.RunnerListWindow()

    calls: list[bool] = []

    def fake_gc(*, apply: bool, prefix: str = "cmdseal.") -> dict:
        calls.append(apply)
        return {"orphans": [
            {"service": "cmdseal.o1.K", "account": "ws"},
            {"service": "cmdseal.o2.K", "account": "ws"},
        ], "live": [], "legacy": [], "would_delete": False}

    with patch.object(runner_list, "gc_runners", side_effect=fake_gc), \
         patch.object(runner_list.QMessageBox, "information"), \
         patch.object(runner_list, "list_sealed", return_value=items):
        w._run_gc(list(w._orphans_cache), dry_run_first=False)

    assert calls == [True], calls
    w.close()
    print("  ✅ _run_gc 未勾 dry-run：仅调一次 apply=True")


def test_run_gc_dry_run_consistent_then_deletes(tmp_path: Path) -> None:
    _ensure_app()
    items, _ = _mk_items(tmp_path)
    with patch.object(runner_list, "list_sealed", return_value=items):
        w = runner_list.RunnerListWindow()

    calls: list[bool] = []

    def fake_gc(*, apply: bool, prefix: str = "cmdseal.") -> dict:
        calls.append(apply)
        return {"orphans": [
            {"service": "cmdseal.o1.K", "account": "ws"},
            {"service": "cmdseal.o2.K", "account": "ws"},
        ], "live": [], "legacy": [], "would_delete": not apply}

    with patch.object(runner_list, "gc_runners", side_effect=fake_gc), \
         patch.object(runner_list.QMessageBox, "information"), \
         patch.object(runner_list.QMessageBox, "warning"), \
         patch.object(runner_list, "list_sealed", return_value=items):
        w._run_gc(list(w._orphans_cache), dry_run_first=True)

    assert calls == [False, True], calls
    w.close()
    print("  ✅ _run_gc 勾 dry-run 且一致：apply=False → apply=True")


def test_run_gc_dry_run_mismatch_aborts(tmp_path: Path) -> None:
    _ensure_app()
    items, _ = _mk_items(tmp_path)
    with patch.object(runner_list, "list_sealed", return_value=items):
        w = runner_list.RunnerListWindow()

    calls: list[bool] = []

    def fake_gc(*, apply: bool, prefix: str = "cmdseal.") -> dict:
        calls.append(apply)
        # 故意返回只有 1 条孤儿，和本地的 2 条不一致
        return {"orphans": [
            {"service": "cmdseal.o1.K", "account": "ws"},
        ], "live": [], "legacy": [], "would_delete": True}

    warnings: list[tuple[Any, str, str]] = []

    def fake_warning(parent: Any, title: str, text: str,
                     *args: Any, **kwargs: Any) -> int:
        warnings.append((parent, title, text))
        return 0

    with patch.object(runner_list, "gc_runners", side_effect=fake_gc), \
         patch.object(runner_list.QMessageBox, "warning",
                      side_effect=fake_warning), \
         patch.object(runner_list.QMessageBox, "information"), \
         patch.object(runner_list, "list_sealed", return_value=items):
        w._run_gc(list(w._orphans_cache), dry_run_first=True)

    assert calls == [False], calls
    assert warnings, "expected a QMessageBox.warning"
    w.close()
    print("  ✅ _run_gc 勾 dry-run 且不一致：apply=False 后中止，弹 warning")


def test_run_gc_apply_partial_failure(tmp_path: Path) -> None:
    """apply 返回 _partial=True → 弹 warning 而非 information。"""
    _ensure_app()
    items, _ = _mk_items(tmp_path)
    with patch.object(runner_list, "list_sealed", return_value=items):
        w = runner_list.RunnerListWindow()

    def fake_gc(*, apply: bool, prefix: str = "cmdseal.") -> dict:
        return {
            "orphans": [
                {"service": "cmdseal.o1.K", "account": "ws"},
                {"service": "cmdseal.o2.K", "account": "ws"},
            ],
            "live": [], "legacy": [], "would_delete": False,
            "_partial": True, "_rc": 1,
            "_stderr": "helper delete failed for cmdseal.o2.K\n",
        }

    warnings: list[str] = []
    infos: list[str] = []

    def fake_warning(parent: Any, title: str, text: str,
                     *args: Any, **kwargs: Any) -> int:
        warnings.append(text)
        return 0

    def fake_info(parent: Any, title: str, text: str,
                  *args: Any, **kwargs: Any) -> int:
        infos.append(text)
        return 0

    with patch.object(runner_list, "gc_runners", side_effect=fake_gc), \
         patch.object(runner_list.QMessageBox, "warning",
                      side_effect=fake_warning), \
         patch.object(runner_list.QMessageBox, "information",
                      side_effect=fake_info), \
         patch.object(runner_list, "list_sealed", return_value=items):
        w._run_gc(list(w._orphans_cache), dry_run_first=False)

    assert warnings, f"expected warning for _partial, got infos={infos}"
    assert not infos, f"should not show success info on partial: {infos}"
    assert "cmdseal.o2.K" in warnings[0], warnings[0]
    w.close()
    print("  ✅ _run_gc apply 部分失败：弹 warning 而非 information")


# ---- runner ---------------------------------------------------------------

_TESTS = [
    ("_classify_status live/orphan/legacy", test_classify_live_orphan_legacy),
    ("backend.gc_runners dry-run argv",     test_backend_gc_runners_dry_run),
    ("backend.gc_runners apply argv",       test_backend_gc_runners_apply),
    ("backend.gc_runners partial failure",  test_backend_gc_runners_partial_failure),
    ("backend.gc_runners rc!=0 non-JSON",   test_backend_gc_runners_rc1_no_json_raises),
    ("refresh 有孤儿启用 gc",               test_refresh_enables_gc_when_orphans_present),
    ("refresh 无孤儿禁用 gc",               test_refresh_disables_gc_when_no_orphans),
    ("_run_gc 未勾 dry-run",                test_run_gc_no_dry_run_directly_deletes),
    ("_run_gc 勾 dry-run 一致",             test_run_gc_dry_run_consistent_then_deletes),
    ("_run_gc 勾 dry-run 不一致中止",       test_run_gc_dry_run_mismatch_aborts),
    ("_run_gc apply 部分失败",              test_run_gc_apply_partial_failure),
]


if __name__ == "__main__":
    import tempfile
    print()
    print("=" * 60)
    print("U2: GUI Manage Runners 接入 gc 能力")
    print("=" * 60)
    failures = 0
    for name, fn in _TESTS:
        print(f"- {name}")
        try:
            import inspect
            sig = inspect.signature(fn)
            if "tmp_path" in sig.parameters:
                with tempfile.TemporaryDirectory() as td:
                    fn(Path(td))
            else:
                fn()
        except AssertionError as e:
            failures += 1
            print(f"  ❌ 断言失败: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            import traceback
            traceback.print_exc()
            print(f"  ❌ 异常: {e}")
    print("=" * 60)
    if failures:
        print(f"❌ 共 {failures} 条失败")
        sys.exit(1)
    print(f"✅ 全部 {len(_TESTS)} 条通过")
    sys.exit(0)
