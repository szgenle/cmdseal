#!/usr/bin/env python3
"""template_wizard 多段管道（v1.2.2）冒烟测试。

覆盖：
- build_template_many：跨段 arg 编号全局递增、单段等价 v1.1 build_template
- build_template_many：参数长度错配抛异常
- CommandInputPage（headless）：添加/删除段、首段不可删、上限 8
- ParameterSelectionPage（headless）：从 CommandInputPage 读 token_groups
  后生成每段 chip、templates() 串跨段
- ExecutionPage._build_request：走 commands= 路径不抛 TypeError
  （回归 v1.2.1 遗漏的悬挂引用）

运行：
    uv run python tests/test_template_wizard_multi.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 允许 macOS 无显示器环境下跑
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import backend  # noqa: E402
from gui.template_wizard import (  # noqa: E402
    MAX_PIPE_SEGMENTS,
    CommandInputPage,
    ParameterSelectionPage,
    TemplateWizard,
    build_template,
    build_template_many,
)


def _assert(cond: bool, desc: str) -> None:
    mark = "✓" if cond else "✗"
    print(f"  {mark} {desc}")
    if not cond:
        raise AssertionError(desc)


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------

def test_build_template_many() -> None:
    print("== build_template_many ==")

    # 单段：与 build_template 等价
    groups = [["zip", "-j", "-P", "mypass", "a.txt", "b.txt"]]
    selected = [{4, 5}]
    out = build_template_many(groups, selected)
    _assert(len(out) == 1 and out[0] == "zip -j -P mypass {{arg:1}} {{arg:2}}",
            f"单段等价旧行为: {out}")

    # 兼容：build_template 单段包装
    legacy = build_template(groups[0], selected[0])
    _assert(legacy == out[0], "build_template 单段包装保持兼容")

    # 多段：arg 编号跨段全局递增（段 1 选 2 个 → 段 2 首个选中 = arg3）
    groups = [
        ["zhmm", "--pwd", "X", "-s", "sid"],
        ["tr", "a-z", "A-Z"],
        ["zip", "out.zip", "-"],
    ]
    selected = [{2, 4}, set(), {1}]
    out = build_template_many(groups, selected)
    _assert(out == [
        "zhmm --pwd {{arg:1}} -s {{arg:2}}",
        "tr a-z A-Z",
        "zip {{arg:3}} -",
    ], f"跨段全局编号: {out}")

    # 空段选集：只生成字面量
    out = build_template_many([["ls", "-la"]], [set()])
    _assert(out == ["ls -la"], f"空选集: {out}")

    # 错配长度抛异常
    try:
        build_template_many([["a"], ["b"]], [set()])
    except ValueError as e:
        _assert("不匹配" in str(e), f"长度错配抛 ValueError: {e}")
    else:
        raise AssertionError("长度错配应抛 ValueError")


# ---------------------------------------------------------------------------
# GUI headless
# ---------------------------------------------------------------------------

def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_command_page_segments() -> None:
    print("== CommandInputPage 段增删 ==")
    _ensure_app()
    page = CommandInputPage()

    _assert(len(page._segments) == 1, "初始 1 段")

    # 加满到上限
    for _ in range(MAX_PIPE_SEGMENTS + 3):
        page._add_segment()
    _assert(len(page._segments) == MAX_PIPE_SEGMENTS,
            f"硬上限 {MAX_PIPE_SEGMENTS}")

    # 非首段可删；首段不可删
    while len(page._segments) > 1:
        page._remove_segment(page._segments[-1])
    _assert(len(page._segments) == 1, "删回到 1 段")
    page._remove_segment(page._segments[0])
    _assert(len(page._segments) == 1, "首段不可删（保持 1 段）")

    # 填写两段，验证 commands() / token_groups()
    page._add_segment()
    page._segments[0].edit.setPlainText("/bin/echo hello")
    page._segments[1].edit.setPlainText("/usr/bin/tr a-z A-Z")
    _assert(page.commands() == ["/bin/echo hello", "/usr/bin/tr a-z A-Z"],
            f"commands(): {page.commands()}")
    tg = page.token_groups()
    _assert(tg == [["/bin/echo", "hello"], ["/usr/bin/tr", "a-z", "A-Z"]],
            f"token_groups(): {tg}")

    # 向后兼容：command() / tokens() 返回首段
    _assert(page.command() == "/bin/echo hello", "command() 返回首段")
    _assert(page.tokens() == ["/bin/echo", "hello"], "tokens() 返回首段")


def test_param_page_multi_segment() -> None:
    print("== ParameterSelectionPage 多段 chip ==")
    _ensure_app()
    # 用 TemplateWizard 作为 parent，触发正常 initializePage 流程
    wiz = TemplateWizard()

    # 模拟在 command_page 输入两段
    wiz.command_page._segments[0].edit.setPlainText("/bin/echo hello")
    wiz.command_page._add_segment()
    wiz.command_page._segments[1].edit.setPlainText("/usr/bin/tr a-z A-Z")

    # 直接调 initializePage（不走 wizard 真实导航，避开 try_run gate）
    wiz.param_page.initializePage()
    _assert(len(wiz.param_page._token_groups) == 2,
            f"读到 2 段 token_groups: {wiz.param_page._token_groups}")
    _assert(wiz.param_page._selected == [set(), set()],
            "初始无选中")

    # 模拟用户：段 1 选 "hello"(idx=1) → arg1；段 2 选 "a-z"(idx=1) → arg2
    wiz.param_page._selected = [{1}, {1}]
    templates = wiz.param_page.templates()
    _assert(templates == ["/bin/echo {{arg:1}}", "/usr/bin/tr {{arg:2}} A-Z"],
            f"跨段全局编号: {templates}")

    # 兼容：template() 返回首段
    _assert(wiz.param_page.template() == "/bin/echo {{arg:1}}",
            "template() 返回首段")

    # program_name 仍按首段首 token
    _assert(wiz.param_page.program_name().endswith("echo"),
            f"program_name: {wiz.param_page.program_name()}")


def test_build_request_multi_no_hang() -> None:
    """回归：v1.2.1 改了 SealRequest.command→commands 后，
    template_wizard 的 _build_request 还在用 command= 关键字。
    这个测试确认 _build_request 不再抛 TypeError。"""
    print("== ExecutionPage._build_request 回归 ==")
    _ensure_app()
    wiz = TemplateWizard()
    wiz.command_page._segments[0].edit.setPlainText("/bin/echo hi")
    wiz.command_page._add_segment()
    wiz.command_page._segments[1].edit.setPlainText("/usr/bin/rev")
    wiz.param_page.initializePage()
    wiz.param_page._selected = [{1}, set()]
    wiz.output_page.output_edit.setText("/tmp/seal_out_test")
    wiz.output_page.user_edit.setText("tester")

    req = wiz.execute_page._build_request(wiz)
    _assert(isinstance(req, backend.SealRequest), "返回 SealRequest 实例")
    _assert(req.commands == ["/bin/echo {{arg:1}}", "/usr/bin/rev"],
            f"commands 两段: {req.commands}")
    # build_argv 要能正确展开为 2 次 --command
    argv = backend.build_argv(req)
    _assert(argv.count("--command") == 2,
            f"build_argv --command 次数: {argv.count('--command')}")


if __name__ == "__main__":
    test_build_template_many()
    test_command_page_segments()
    test_param_page_multi_segment()
    test_build_request_multi_no_hang()
    print("\nAll multi-segment tests passed.")
