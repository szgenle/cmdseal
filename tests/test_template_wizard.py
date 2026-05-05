#!/usr/bin/env python3
"""template_wizard 纯函数单测。

覆盖：
- validate_command：语法解析 + 首 token 可执行性
- build_template：按出现顺序替换 {{arg:N}}，未选中的 token 用 shlex.quote 保护
- complete_path：bash 风格 Tab 补全的候选查找、最长公共前缀、目录尾斜杠、~ 保留
"""
from __future__ import annotations

import os
import shlex
import sys
import tempfile
from pathlib import Path

# 允许从仓库根目录直接运行：python tests/test_template_wizard.py
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui.template_wizard import (  # noqa: E402
    build_template,
    complete_path,
    validate_command,
)


def _assert(cond: bool, desc: str) -> None:
    mark = "✓" if cond else "✗"
    print(f"  {mark} {desc}")
    if not cond:
        raise AssertionError(desc)


def test_validate_command() -> None:
    print("== validate_command ==")

    ok, msg, toks = validate_command("")
    _assert(not ok and toks == [], f"空命令被拒绝 ({msg})")

    ok, msg, toks = validate_command("'unclosed")
    _assert(not ok, f"未闭合引号被拒绝 ({msg})")

    ok, msg, toks = validate_command("nonexistent_command_xyz arg")
    _assert(not ok, f"PATH 外程序被拒绝 ({msg})")

    # 任意 POSIX 系统上稳定存在的程序
    ok, msg, toks = validate_command("/bin/ls -la /tmp")
    _assert(ok and toks == ["/bin/ls", "-la", "/tmp"], f"绝对路径通过 ({msg})")

    ok, msg, toks = validate_command("ls -la")
    _assert(ok and toks[0] == "ls", f"PATH 内命令通过 ({msg})")

    ok, msg, toks = validate_command('echo "my pass" foo')
    _assert(ok and toks == ["echo", "my pass", "foo"],
            f"带引号参数被 shlex 正确解析 ({toks})")


def test_build_template() -> None:
    print("== build_template ==")

    # 典型：选中末尾两个文件参数
    toks = shlex.split("zip -j -P Demo1234 file1.txt file2.txt")
    out = build_template(toks, {4, 5})
    _assert(out == "zip -j -P Demo1234 {{arg:1}} {{arg:2}}",
            f"zip 场景: {out}")

    # 跳过 flag、按位置顺序编号
    toks = shlex.split("/usr/bin/gpg --symmetric --output secret.gpg input.txt")
    out = build_template(toks, {3, 4})  # secret.gpg, input.txt
    _assert(out == "/usr/bin/gpg --symmetric --output {{arg:1}} {{arg:2}}",
            f"gpg 场景: {out}")

    # 未选中的含空格 token 要被 shlex.quote 保护
    toks = shlex.split('echo "hello world" foo')
    out = build_template(toks, {2})
    _assert(out == "echo 'hello world' {{arg:1}}",
            f"引号保护: {out}")

    # 首 token 也可以被参数化
    toks = shlex.split("zip -r out.zip /data")
    out = build_template(toks, {0, 3})
    _assert(out == "{{arg:1}} -r out.zip {{arg:2}}",
            f"首 token 参数化: {out}")

    # 空选集 → 原样（经 shlex.quote）返回
    toks = shlex.split("ls -la /tmp")
    out = build_template(toks, set())
    _assert(out == "ls -la /tmp", f"空选集: {out}")


def test_complete_path() -> None:
    print("== complete_path ==")

    # 空串 → 原样返回，空候选
    out, m = complete_path("")
    _assert(out == "" and m == [], f"空串不处理 ({out!r}, {m})")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "apple.txt").write_text("x")
        (root / "apricot.txt").write_text("x")
        (root / "banana.txt").write_text("x")
        (root / "backup").mkdir()

        # 单匹配 + 文件 → 完整补全，不追加分隔符
        out, m = complete_path(f"{root}/ban")
        _assert(out == f"{root}/banana.txt" and m == ["banana.txt"],
                f"单文件补全 ({out}, {m})")

        # 单匹配 + 目录 → 尾随分隔符
        out, m = complete_path(f"{root}/bac")
        _assert(out == f"{root}/backup{os.sep}" and m == ["backup"],
                f"目录补全尾随 / ({out}, {m})")

        # 多匹配 → 补到最长公共前缀“ap”
        out, m = complete_path(f"{root}/a")
        _assert(out == f"{root}/ap" and set(m) == {"apple.txt", "apricot.txt"},
                f"最长公共前缀 ({out}, {m})")

        # 无匹配 → 原样返回、空候选
        out, m = complete_path(f"{root}/zzz")
        _assert(out == f"{root}/zzz" and m == [], f"无匹配 ({out}, {m})")

    # ~ 保留：展开后不能把 HOME 嫁回输入框
    home = os.path.expanduser("~")
    # 仅验证前缀保留，不依赖 HOME 里具体有什么；跳过隐藏文件
    entries = [e for e in os.listdir(home) if not e.startswith(".")]
    if entries:
        sample = sorted(entries)[0]
        out, _ = complete_path(f"~/{sample[:1]}")
        _assert(out.startswith("~/") and not out.startswith(home),
                f"~ 前缀保留 ({out})")


if __name__ == "__main__":
    test_validate_command()
    test_build_template()
    test_complete_path()
    print("\nAll tests passed.")
