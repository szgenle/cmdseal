#!/usr/bin/env python3
"""测试 v1.2.1 GUI 多段管道编辑器的核心逻辑。

验证点：
1. backend.build_argv 对 N 段 SealRequest 会产出 N 份 --command
   （与 cmdseal.py 的 action="append" 语义一致）
2. _scan_placeholders_many 跨段合并 secret / arg（去重 + 全局编号）
3. CommandPage 初始 1 段；+/× 受 MAX_PIPE_SEGMENTS 约束；删空后至少
   保留 1 段；首段不可删；下游 commands() 自动剔除空段
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import backend  # noqa: E402
from gui.seal_wizard import (  # noqa: E402
    MAX_PIPE_SEGMENTS,
    CommandPage,
    _scan_placeholders_many,
)


def test_build_argv_multi() -> None:
    print("=" * 60)
    print("测试 1: build_argv 多段")
    print("=" * 60)

    # 单段回归：保持 v1.1 形态（单个 --command）
    req1 = backend.SealRequest(
        commands=["/bin/echo hello"],
        output=Path("/tmp/out"),
    )
    argv1 = backend.build_argv(req1)
    print(f"  argv (1 seg): {argv1}")
    assert argv1.count("--command") == 1, argv1
    assert "/bin/echo hello" in argv1, argv1
    print("  ✅ 单段：--command 出现 1 次")

    # 三段：应有 3 个 --command，且顺序保持
    req3 = backend.SealRequest(
        commands=[
            "/bin/echo hi",
            "/usr/bin/tr a-z A-Z",
            "/usr/bin/rev",
        ],
        output=Path("/tmp/out"),
    )
    argv3 = backend.build_argv(req3)
    print(f"  argv (3 seg): {argv3}")
    assert argv3.count("--command") == 3, argv3
    # 位置关系：--command 后紧接段字符串，且三段顺序保持
    idxs = [i for i, x in enumerate(argv3) if x == "--command"]
    ordered_segs = [argv3[i + 1] for i in idxs]
    assert ordered_segs == [
        "/bin/echo hi",
        "/usr/bin/tr a-z A-Z",
        "/usr/bin/rev",
    ], ordered_segs
    print("  ✅ 多段：3 次 --command 且顺序保持")


def test_scan_many() -> None:
    print("=" * 60)
    print("测试 2: _scan_placeholders_many 跨段合并")
    print("=" * 60)

    cmds = [
        "/usr/local/bin/zhmm-cli --pwd {{secret:master}} -s {{arg:1}}",
        "/usr/bin/tr a-z A-Z",
        "/usr/bin/zip {{arg:2}} -",
    ]
    secrets, args = _scan_placeholders_many(cmds)
    print(f"  secrets={secrets} args={args}")
    assert secrets == ["master"], secrets
    assert args == ["1", "2"], args
    print("  ✅ 跨段合并正确")

    # 空列表安全
    s2, a2 = _scan_placeholders_many([])
    assert s2 == [] and a2 == []
    print("  ✅ 空列表合法")


def test_command_page_segment_ops() -> None:
    print("=" * 60)
    print("测试 3: CommandPage 段增删约束")
    print("=" * 60)
    app = QApplication.instance() or QApplication(sys.argv)
    _ = app  # 避免 F841
    page = CommandPage()

    assert len(page._segments) == 1, "初始应有 1 段"
    print("  ✅ 初始 1 段")

    # 递加直到 MAX
    for _ in range(MAX_PIPE_SEGMENTS + 5):
        page._add_segment()
    assert len(page._segments) == MAX_PIPE_SEGMENTS, len(page._segments)
    print(f"  ✅ 上限 {MAX_PIPE_SEGMENTS}")

    # 逐一删除；末段除首段外都可删；首段不可删
    while len(page._segments) > 1:
        page._remove_segment(page._segments[-1])
    assert len(page._segments) == 1
    # 再次尝试删首段：应被拒绝
    page._remove_segment(page._segments[0])
    assert len(page._segments) == 1
    print("  ✅ 首段不可删")

    # commands() 应剔除空段
    page._add_segment()
    page._segments[0].edit.setPlainText("/bin/echo hi")
    page._segments[1].edit.setPlainText("")  # 空段
    assert page.commands() == ["/bin/echo hi"], page.commands()
    print("  ✅ 空段被剔除")

    # 填满两段后再校验
    page._segments[1].edit.setPlainText("/usr/bin/tr a-z A-Z")
    assert page.commands() == [
        "/bin/echo hi",
        "/usr/bin/tr a-z A-Z",
    ], page.commands()
    assert page.isComplete()
    print("  ✅ 两段 isComplete")


if __name__ == "__main__":
    print()
    try:
        test_build_argv_multi()
        test_scan_many()
        test_command_page_segment_ops()
        print("=" * 60)
        print("✅ 全部通过")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 断言失败: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n❌ 异常: {e}")
        traceback.print_exc()
        sys.exit(1)
