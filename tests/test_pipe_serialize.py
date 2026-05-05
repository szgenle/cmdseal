#!/usr/bin/env python3
"""v1.2 管道明文序列化单元测试。

不涉及 keychain / helper / codesign，纯函数测试，CI 可直接运行：

    uv run python tests/test_pipe_serialize.py
    # 或
    python3 tests/test_pipe_serialize.py

覆盖范围（对应 research/DESIGN.pipe.md §3 / §5）：
  1. 单段封装产生的明文与 v1.1 字节级一致（无 \x03 分隔符）
  2. 多段封装在段之间正确插入 \x03 token
  3. {{arg:N}} 占位符被序列化为 \x02arg:N 形式
  4. {{secret:X}} 在生成期被替换为字面量
  5. 空串 token 作为流终止符 (\x00\x00)
  6. tokenize_command 能正确区分 literal / arg / secret
"""

import os
import sys
import unittest

# 让脚本在 tests/ 目录里也能 import 到 cmdseal.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cmdseal  # noqa: E402


class TokenizeCommandTests(unittest.TestCase):
    """tokenize_command 的语义回归。"""

    def test_pure_literal(self):
        toks = cmdseal.tokenize_command("/bin/echo hello world")
        self.assertEqual(
            toks,
            [("literal", "/bin/echo"), ("literal", "hello"), ("literal", "world")],
        )

    def test_arg_placeholder(self):
        toks = cmdseal.tokenize_command("/bin/echo {{arg:1}}")
        self.assertEqual(toks, [("literal", "/bin/echo"), ("arg", "1")])

    def test_secret_placeholder(self):
        toks = cmdseal.tokenize_command("/bin/login {{secret:master}}")
        self.assertEqual(toks, [("literal", "/bin/login"), ("secret", "master")])

    def test_quoted_arg_preserves_whitespace(self):
        # shlex 负责处理引号，tokenize 只是薄包装
        toks = cmdseal.tokenize_command("/bin/echo 'hello world'")
        self.assertEqual(
            toks,
            [("literal", "/bin/echo"), ("literal", "hello world")],
        )


class SerializeSingleSegmentTests(unittest.TestCase):
    """验证单段封装与 v1.1 字节级一致。"""

    def test_no_pipe_token_when_single_segment(self):
        segments = [cmdseal.tokenize_command("/bin/echo hello")]
        blob = cmdseal.serialize_segments(segments, secret_values={})
        # v1.1 布局：每个 token 以 \x00 结尾，整体以额外 \x00 收尾
        self.assertEqual(blob, b"/bin/echo\x00hello\x00\x00")
        # 关键：不得出现任何 \x03（管道分隔符）
        self.assertNotIn(b"\x03", blob)

    def test_single_segment_with_arg_placeholder(self):
        segments = [cmdseal.tokenize_command("/bin/echo {{arg:1}}")]
        blob = cmdseal.serialize_segments(segments, secret_values={})
        # {{arg:1}} → \x02arg:1
        self.assertEqual(blob, b"/bin/echo\x00\x02arg:1\x00\x00")

    def test_single_segment_with_secret_substituted(self):
        segments = [cmdseal.tokenize_command("/bin/login {{secret:master}}")]
        blob = cmdseal.serialize_segments(
            segments, secret_values={"master": "hunter2"}
        )
        # secret 在生成期被替换成字面量，不保留在密文里的占位符
        self.assertEqual(blob, b"/bin/login\x00hunter2\x00\x00")
        self.assertNotIn(b"secret", blob)


class SerializeMultiSegmentTests(unittest.TestCase):
    """验证多段封装在段之间正确插入 \x03 分隔符。"""

    def test_two_segments(self):
        segments = [
            cmdseal.tokenize_command("/bin/echo hello"),
            cmdseal.tokenize_command("/usr/bin/tr a-z A-Z"),
        ]
        blob = cmdseal.serialize_segments(segments, secret_values={})
        # 期望布局：/bin/echo \0 hello \0 \x03 \0 /usr/bin/tr \0 a-z \0 A-Z \0 \0
        self.assertEqual(
            blob,
            b"/bin/echo\x00hello\x00\x03\x00/usr/bin/tr\x00a-z\x00A-Z\x00\x00",
        )
        # 且 \x03 刚好出现一次（两段之间）
        self.assertEqual(blob.count(b"\x03"), 1)

    def test_three_segments(self):
        segments = [
            cmdseal.tokenize_command("/bin/echo a"),
            cmdseal.tokenize_command("/usr/bin/tr a b"),
            cmdseal.tokenize_command("/usr/bin/tr b c"),
        ]
        blob = cmdseal.serialize_segments(segments, secret_values={})
        # 三段之间应有两个 \x03 分隔符
        self.assertEqual(blob.count(b"\x03"), 2)
        # 仍以 \x00\x00 收尾
        self.assertTrue(blob.endswith(b"\x00\x00"))

    def test_arg_placeholder_across_segments(self):
        segments = [
            cmdseal.tokenize_command("/bin/echo {{arg:1}}"),
            cmdseal.tokenize_command("/usr/bin/grep {{arg:2}}"),
        ]
        blob = cmdseal.serialize_segments(segments, secret_values={})
        # 跨段 arg 占位符都被保留为运行期 token
        self.assertIn(b"\x02arg:1", blob)
        self.assertIn(b"\x02arg:2", blob)
        # 分隔符出现在两段之间
        self.assertEqual(blob.count(b"\x03"), 1)


class PipeConstantsTests(unittest.TestCase):
    """确认对外常量与设计文档保持一致（触发回归保护）。"""

    def test_tok_pipe_byte_value(self):
        # 必须与 runner_aead_template.c 中的 TOK_PIPE 0x03 对齐
        self.assertEqual(cmdseal.TOK_PIPE_BYTE, b"\x03")

    def test_max_pipe_segments_cap(self):
        # DESIGN.pipe.md §2.4：硬上限 8 段
        self.assertEqual(cmdseal.MAX_PIPE_SEGMENTS, 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
