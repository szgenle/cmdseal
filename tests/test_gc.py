"""Unit tests for `cmdseal gc`.

These cover the *pure* classification logic only — no keychain / no
codesign / no compilation. The CLI dispatch (`do_gc`) itself is
exercised via a thin fake of `kc_list` / `kc_delete` so we can assert
the dry-run / --yes / --json contracts without touching real state.
"""
from __future__ import annotations

import io
import json
import os
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import cmdseal  # noqa: E402


# ----------------------------------------------------------------------
# classify_gc_items — the single source of truth for gc partitioning
# ----------------------------------------------------------------------

def _mk_item(service, *, output_path=None, meta_missing=False,
             label="lbl", account="ws"):
    """Build a kc_list-shaped item for the classifier."""
    if meta_missing:
        meta = None
    else:
        meta = {
            "v": 1,
            "label": label,
            "output_path": output_path,
            "template": "zip -P *** {{arg:1}}",
            "arity": 1,
            "secret_names": [],
            "created_at": "2026-05-01T00:00:00+00:00",
        }
    return {
        "service": service,
        "account": account,
        "label": label,
        "comment": json.dumps(meta) if meta else None,
        "_meta": meta,
    }


def test_classify_live_orphan_legacy(tmp_path):
    live_bin = tmp_path / "live"
    live_bin.write_bytes(b"x")
    missing_bin = tmp_path / "gone"  # intentionally not created

    items = [
        _mk_item("cmdseal.aaa111111111.K", output_path=str(live_bin)),
        _mk_item("cmdseal.bbb222222222.K", output_path=str(missing_bin)),
        # no metadata at all → legacy
        _mk_item("cmdseal.ccc333333333.K", meta_missing=True),
        # metadata exists but output_path empty → legacy
        {
            "service": "cmdseal.ddd444444444.K",
            "account": "ws",
            "comment": json.dumps({"v": 1, "label": "old"}),
            "_meta": {"v": 1, "label": "old"},
        },
    ]
    orphans, live, legacy = cmdseal.classify_gc_items(items)
    assert [x["service"] for x in live] == ["cmdseal.aaa111111111.K"]
    assert [x["service"] for x in orphans] == ["cmdseal.bbb222222222.K"]
    assert sorted(x["service"] for x in legacy) == [
        "cmdseal.ccc333333333.K", "cmdseal.ddd444444444.K"
    ]


def test_classify_blank_service_is_legacy(tmp_path):
    # Defensive: malformed row with empty service should never crash,
    # and must never leak into orphans (we'd have nothing to delete by).
    items = [{"service": "", "comment": None, "_meta": None}]
    orphans, live, legacy = cmdseal.classify_gc_items(items)
    assert orphans == [] and live == []
    assert legacy == items


# ----------------------------------------------------------------------
# do_gc — dispatch-level contracts, using monkeypatched kc_list/kc_delete
# ----------------------------------------------------------------------

class _FakeDeleteTracker:
    def __init__(self):
        self.calls = []

    def __call__(self, service, account):
        self.calls.append((service, account))


def _patched_gc(monkeypatch, items, *, flags):
    """Invoke `do_gc` with kc_list / kc_delete / check_platform
    mocked out. Returns (exit_code, stdout_text, delete_tracker)."""
    monkeypatch.setattr(cmdseal, "check_platform_and_tools", lambda: None)
    monkeypatch.setattr(cmdseal, "kc_list", lambda prefix: items)
    tracker = _FakeDeleteTracker()
    monkeypatch.setattr(cmdseal, "kc_delete", tracker)

    args = types.SimpleNamespace(
        prefix="cmdseal.",
        user="ws",
        dry_run=flags.get("dry_run", False),
        yes=flags.get("yes", False),
        json=flags.get("json", False),
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmdseal.do_gc(args)
    return rc, buf.getvalue(), tracker


def _items_with_one_orphan(tmp_path):
    live_bin = tmp_path / "keep"
    live_bin.write_bytes(b"x")
    # Raw shape — do_gc re-parses `comment` into `_meta` itself, so we
    # emit `comment` only (mirrors what kc_list really returns).
    live_meta = {
        "v": 1, "label": "keep", "output_path": str(live_bin),
        "template": "zip ***", "arity": 1,
        "secret_names": [], "created_at": "2026-05-01T00:00:00+00:00",
    }
    dead_meta = {
        "v": 1, "label": "gone", "output_path": str(tmp_path / "missing"),
        "template": "zip ***", "arity": 1,
        "secret_names": [], "created_at": "2026-04-01T00:00:00+00:00",
    }
    return [
        {"service": "cmdseal.aaa111111111.K", "account": "ws",
         "comment": json.dumps(live_meta)},
        {"service": "cmdseal.bbb222222222.K", "account": "ws",
         "comment": json.dumps(dead_meta)},
    ]


def test_dry_run_does_not_delete(tmp_path, monkeypatch):
    items = _items_with_one_orphan(tmp_path)
    rc, out, tracker = _patched_gc(monkeypatch, items, flags={"dry_run": True})
    assert rc == 0
    assert tracker.calls == []
    assert "would delete 1 keychain item" in out
    assert "cmdseal.bbb222222222.K" in out


def test_yes_actually_deletes(tmp_path, monkeypatch):
    items = _items_with_one_orphan(tmp_path)
    rc, out, tracker = _patched_gc(monkeypatch, items, flags={"yes": True})
    assert rc == 0
    assert tracker.calls == [("cmdseal.bbb222222222.K", "ws")]
    assert "✓ deleted cmdseal.bbb222222222.K" in out


def test_json_dry_run_is_implicit_readonly(tmp_path, monkeypatch):
    items = _items_with_one_orphan(tmp_path)
    rc, out, tracker = _patched_gc(monkeypatch, items, flags={"json": True})
    assert rc == 0
    # --json without --yes should NOT touch anything.
    assert tracker.calls == []
    payload = json.loads(out)
    assert payload["would_delete"] is True
    assert [o["service"] for o in payload["orphans"]] == [
        "cmdseal.bbb222222222.K"
    ]
    assert [lv["service"] for lv in payload["live"]] == [
        "cmdseal.aaa111111111.K"
    ]


def test_json_yes_is_destructive(tmp_path, monkeypatch):
    items = _items_with_one_orphan(tmp_path)
    rc, out, tracker = _patched_gc(
        monkeypatch, items, flags={"json": True, "yes": True})
    assert rc == 0
    assert tracker.calls == [("cmdseal.bbb222222222.K", "ws")]


def test_no_orphans_is_noop(tmp_path, monkeypatch):
    live_bin = tmp_path / "keep"
    live_bin.write_bytes(b"x")
    meta = {
        "v": 1, "label": "k", "output_path": str(live_bin),
        "template": "zip", "arity": 0, "secret_names": [],
        "created_at": "2026-05-01T00:00:00+00:00",
    }
    items = [{"service": "cmdseal.aaa111111111.K", "account": "ws",
              "comment": json.dumps(meta)}]
    rc, out, tracker = _patched_gc(monkeypatch, items, flags={"yes": True})
    assert rc == 0
    assert tracker.calls == []
    assert "nothing to do" in out


if __name__ == "__main__":
    # Poor-man's runner: run each test_* function in this module.
    # Use `pytest` instead if installed; this mode is for quick smoke.
    import inspect

    class _MP:
        def __init__(self):
            self._saved = []

        def setattr(self, target, name_or_value, value=None):
            if value is None:  # monkeypatch.setattr(obj, value)
                # Not our shape; only support (module, name, value).
                raise NotImplementedError
            self._saved.append((target, name_or_value,
                                getattr(target, name_or_value)))
            setattr(target, name_or_value, value)

        def undo(self):
            for target, name, orig in reversed(self._saved):
                setattr(target, name, orig)
            self._saved.clear()

    import tempfile
    failed = 0
    for name, fn in list(globals().items()):
        if not (name.startswith("test_") and inspect.isfunction(fn)):
            continue
        sig = inspect.signature(fn)
        kwargs = {}
        mp = None
        tmpdir = None
        if "tmp_path" in sig.parameters:
            tmpdir = tempfile.TemporaryDirectory()
            kwargs["tmp_path"] = Path(tmpdir.name)
        if "monkeypatch" in sig.parameters:
            mp = _MP()
            kwargs["monkeypatch"] = mp
        try:
            fn(**kwargs)
            print(f"  ok   {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERR  {name}: {type(e).__name__}: {e}")
        finally:
            if mp:
                mp.undo()
            if tmpdir:
                tmpdir.cleanup()
    sys.exit(1 if failed else 0)
