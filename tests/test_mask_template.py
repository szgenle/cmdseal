#!/usr/bin/env python3
"""mask_template 单元测试（v1.2.1 新规则）。

本测试先于实现编写，作为 TDD 的锚点。规则已通过 prototype 实证
（见会话记录），目标是把 prototype 行为固化为回归网。

规则（将在 cmdseal.py::mask_template 实现）：
  1. 首 token（命令名本体）→ 保留
  2. 含 ``{{arg:N}}`` / ``{{secret:NAME}}`` 占位符的 token → 整体保留
  3. ``--`` 开头（GNU 长 flag）：
       - 含 ``=`` → ``--key=***``
       - 不含 ``=`` → 整体保留
  4. ``-`` 开头（短 flag）：
       - 长度 == 2（如 ``-p`` / ``-r``）→ 保留
       - 长度 >  2（如 ``-pPass`` / ``-xzvf``）→ 取前 2 字符 + ``***``
  5. 其他裸 token（含 ``/`` 开头的绝对路径）→ ``***``

安全目标：
  - 零泄露：Unix 粘连写法（``-ppass`` / ``-Ppass``）被打码
  - 无路径泄露：裸路径（``/tmp/x`` / ``/etc/passwd``）被打码
  - 可接受代价：GNU 组合短选项被打码（``-xzvf`` → ``-x***``）

运行：
    python3 tests/test_mask_template.py
"""

import os
import sys
import unittest

# 让脚本在 tests/ 目录里也能 import 到 cmdseal.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cmdseal  # noqa: E402


class MaskTemplateBasicsTests(unittest.TestCase):
    """空串、单 token、首 token 保留。"""

    def test_empty_string(self):
        self.assertEqual(cmdseal.mask_template(""), "")

    def test_none_input(self):
        """容忍 None（防御式，与 GUI 旧实现一致）。"""
        self.assertEqual(cmdseal.mask_template(None), "")

    def test_whitespace_only(self):
        """纯空白直接回传（与 GUI 旧实现一致）。"""
        self.assertEqual(cmdseal.mask_template("   "), "   ")

    def test_single_token(self):
        self.assertEqual(cmdseal.mask_template("/bin/echo"), "/bin/echo")

    def test_command_name_preserved(self):
        self.assertEqual(
            cmdseal.mask_template("/bin/echo hello"),
            "/bin/echo ***",
        )


class MaskTemplatePlaceholderTests(unittest.TestCase):
    """`{{arg:N}}` / `{{secret:NAME}}` 原样保留。"""

    def test_secret_placeholder_preserved(self):
        self.assertEqual(
            cmdseal.mask_template(
                "zip -P {{secret:PW}} -r out.zip {{arg:1}}"),
            "zip -P {{secret:PW}} -r *** {{arg:1}}",
        )

    def test_arg_placeholder_preserved(self):
        self.assertEqual(
            cmdseal.mask_template("/bin/echo {{arg:1}}"),
            "/bin/echo {{arg:1}}",
        )

    def test_placeholder_in_long_flag_value(self):
        """规则 2 优先于规则 3：--key={{secret:X}} 整体保留。"""
        self.assertEqual(
            cmdseal.mask_template(
                "curl --user={{secret:U}} https://x.com"),
            "curl --user={{secret:U}} ***",
        )


class MaskTemplateUnixTraditionalTests(unittest.TestCase):
    """关键：Unix 粘连写法（flag 紧贴 value）的密码必须被打码。"""

    def test_zip_stuck_password(self):
        self.assertEqual(
            cmdseal.mask_template(
                "zip -Pmypassword -r out.zip {{arg:1}}"),
            "zip -P*** -r *** {{arg:1}}",
        )

    def test_mysql_stuck_user_and_password(self):
        self.assertEqual(
            cmdseal.mask_template("mysql -upadmin -psecret123 db"),
            "mysql -u*** -p*** ***",
        )

    def test_curl_stuck_credential(self):
        self.assertEqual(
            cmdseal.mask_template("curl -usecret:pass https://x.com"),
            "curl -u*** ***",
        )

    def test_sudo_stuck_password(self):
        self.assertEqual(
            cmdseal.mask_template("sudo -Spassword cmd"),
            "sudo -S*** ***",
        )


class MaskTemplateSpacedFlagTests(unittest.TestCase):
    """带空格写法：flag 整体保留，value 打码。"""

    def test_zip_with_space(self):
        self.assertEqual(
            cmdseal.mask_template(
                "zip -P mypassword -r out.zip {{arg:1}}"),
            "zip -P *** -r *** {{arg:1}}",
        )

    def test_mysql_with_space(self):
        self.assertEqual(
            cmdseal.mask_template("mysql -u admin -p secret123 db"),
            "mysql -u *** -p *** ***",
        )


class MaskTemplateLongFlagTests(unittest.TestCase):
    """`--` 长 flag 处理。"""

    def test_long_flag_with_equals(self):
        self.assertEqual(
            cmdseal.mask_template("curl --user=alice:pw https://x.com"),
            "curl --user=*** ***",
        )

    def test_long_flag_with_space_value(self):
        self.assertEqual(
            cmdseal.mask_template("curl --user alice:pw https://x.com"),
            "curl --user *** ***",
        )

    def test_long_flag_no_value(self):
        self.assertEqual(
            cmdseal.mask_template("myapp --verbose --output /tmp/x"),
            "myapp --verbose --output ***",
        )

    def test_long_flag_empty_value(self):
        """--flag= 等号后为空，仍打成 --flag=***（一致性）。"""
        self.assertEqual(
            cmdseal.mask_template("myapp --flag="),
            "myapp --flag=***",
        )


class MaskTemplatePathLeakTests(unittest.TestCase):
    """裸路径必须被打码——修复 GUI 旧规则 `/` 分支的泄露。"""

    def test_absolute_path_in_argument(self):
        self.assertEqual(
            cmdseal.mask_template("myapp --output /tmp/secret.db"),
            "myapp --output ***",
        )

    def test_home_like_absolute_path(self):
        self.assertEqual(
            cmdseal.mask_template(
                "/bin/cat /Users/alice/secrets/db.sqlite"),
            "/bin/cat ***",
        )

    def test_command_name_with_path_still_preserved(self):
        """首 token 即使是路径也保留（命令名本体）。"""
        self.assertEqual(
            cmdseal.mask_template("/usr/local/bin/tool arg"),
            "/usr/local/bin/tool ***",
        )


class MaskTemplateShortFlagEdgeTests(unittest.TestCase):
    """短 flag 长度判定边界。"""

    def test_two_char_short_flag_preserved(self):
        self.assertEqual(
            cmdseal.mask_template("ls -l /tmp"),
            "ls -l ***",
        )

    def test_combined_short_flags_masked(self):
        """GNU 组合短选项被打码——安全代价可接受。"""
        self.assertEqual(
            cmdseal.mask_template("tar -xzvf archive.tar.gz"),
            "tar -x*** ***",
        )

    def test_three_char_short_flag(self):
        self.assertEqual(
            cmdseal.mask_template("ps -aux"),
            "ps -a***",
        )

    def test_lone_dash_non_head_is_masked(self):
        """非首位的孤立 `-` 走裸 token 分支（代表 stdin 的用法会被打码，可接受）。"""
        self.assertEqual(
            cmdseal.mask_template("cat -"),
            "cat ***",
        )


class MaskTemplateQuotedTokenTests(unittest.TestCase):
    """shlex 带引号 token 行为。"""

    def test_quoted_value_masked(self):
        """`"hello world"` 被 shlex 合并为单 token，按裸 token 打码。"""
        self.assertEqual(
            cmdseal.mask_template('/bin/echo "hello world"'),
            "/bin/echo ***",
        )

    def test_unclosed_quote_fallback_does_not_leak_raw(self):
        """shlex 解析失败时降级按空白切分，但不得把原值漏出。"""
        result = cmdseal.mask_template('/bin/echo "unclosedsecret')
        # 降级后 token 切分未知，但 'unclosedsecret' 这个裸值必须不出现
        # （它不是 flag / 命令名 / 占位符，应当被 *** 掉）
        self.assertNotIn("unclosedsecret", result)


class MaskTemplateStabilityTests(unittest.TestCase):
    """幂等与稳定性：打码结果再次送入 mask_template，应不再发生变化。"""

    def test_idempotent(self):
        once = cmdseal.mask_template(
            "zip -Pmypassword -r out.zip {{arg:1}}")
        twice = cmdseal.mask_template(once)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main(verbosity=2)
