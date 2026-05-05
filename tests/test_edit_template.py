#!/usr/bin/env python3
"""do_edit_template 错误路径 + 成功路径单元测试。

纯 Python 逻辑回归，mock kc_list / do_seal / check_platform_and_tools，
不涉及真实 keychain / helper / codesign，CI 可直接跑：

    uv run python tests/test_edit_template.py
    # 或
    python3 tests/test_edit_template.py

覆盖范围（对应 cmdseal.py::do_edit_template）：
  1. service 未找到 → sys.exit
  2. legacy item（无 comment） → sys.exit
  3. comment 非合法 JSON → sys.exit
  4. 新模板 secret 集合与旧集合不匹配 → sys.exit
  5. comment 缺 output_path → sys.exit
  6. --command 段数超过 MAX_PIPE_SEGMENTS → sys.exit
  7. happy path：成功委托 do_seal，旧 output/label/account 注入到 args，
     old_service_to_delete 正确传递
"""

import json
import os
import sys
import types
import unittest
from unittest import mock

# 让脚本在 tests/ 目录里也能 import 到 cmdseal.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cmdseal  # noqa: E402


def _make_args(**overrides):
    """伪造 argparse.Namespace。默认值足以让 do_edit_template 走完校验前段。"""
    defaults = dict(
        service="cmdseal.abcdef123456.K",
        command=["/bin/echo hello"],
        user="ws",
        template=str(cmdseal.DEFAULT_TEMPLATE),
        no_sign=False,
        signing_identity="-",
        keep_source=False,
        secrets_from_stdin=False,
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _make_item(service, *, comment=None, account="ws"):
    """伪造一条 kc_list 返回的 item。comment=None → 模拟 legacy。"""
    it = {"service": service, "account": account}
    if comment is not None:
        it["comment"] = comment
    return it


def _good_comment(**overrides):
    payload = {
        "v": 1,
        "label": "cmdseal sealed: demo",
        "template": "/bin/echo hello",
        "output_path": "/tmp/cmdseal_demo",
        "arity": 0,
        "secret_names": [],
        "created_at": "2026-05-05T09:43:00+00:00",
    }
    payload.update(overrides)
    return json.dumps(payload)


class EditTemplateErrorPathTests(unittest.TestCase):
    """6 条 sys.exit 分支的行为回归。"""

    def setUp(self):
        # check_platform_and_tools 在非 macOS / 无 helper 环境会报错；
        # 它与 do_edit_template 的逻辑正交，在单测里全程 no-op。
        self._patches = [
            mock.patch.object(cmdseal, "check_platform_and_tools",
                              return_value=None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def _run_and_capture_exit(self, args):
        with self.assertRaises(SystemExit) as ctx:
            cmdseal.do_edit_template(args)
        msg = str(ctx.exception)
        return msg

    def test_service_not_found(self):
        with mock.patch.object(cmdseal, "kc_list", return_value=[]):
            msg = self._run_and_capture_exit(_make_args())
        self.assertIn("no runner found", msg)

    def test_legacy_item_rejected(self):
        item = _make_item("cmdseal.abcdef123456.K", comment=None)
        with mock.patch.object(cmdseal, "kc_list", return_value=[item]):
            msg = self._run_and_capture_exit(_make_args())
        self.assertIn("legacy", msg)
        self.assertIn("delete and re-create", msg)

    def test_invalid_comment_json(self):
        item = _make_item("cmdseal.abcdef123456.K",
                          comment="{not valid json")
        with mock.patch.object(cmdseal, "kc_list", return_value=[item]):
            msg = self._run_and_capture_exit(_make_args())
        self.assertIn("invalid metadata", msg)

    def test_missing_output_path(self):
        # output_path 被显式抹掉，其它字段合法
        payload = json.loads(_good_comment())
        payload.pop("output_path")
        item = _make_item("cmdseal.abcdef123456.K",
                          comment=json.dumps(payload))
        with mock.patch.object(cmdseal, "kc_list", return_value=[item]):
            msg = self._run_and_capture_exit(_make_args())
        self.assertIn("missing output_path", msg)

    def test_secret_set_mismatch(self):
        # 旧 runner 不含 secret；新模板引入 {{secret:bar}} → 拒绝
        item = _make_item("cmdseal.abcdef123456.K",
                          comment=_good_comment(secret_names=[]))
        args = _make_args(command=["/bin/login {{secret:bar}}"])
        with mock.patch.object(cmdseal, "kc_list", return_value=[item]):
            msg = self._run_and_capture_exit(args)
        self.assertIn("secret set mismatch", msg)
        self.assertIn("bar", msg)

    def test_secret_set_reversed_mismatch(self):
        # 旧 runner 含 {foo}，新模板用 {bar} → 拒绝（即使数量相等）
        item = _make_item("cmdseal.abcdef123456.K",
                          comment=_good_comment(secret_names=["foo"]))
        args = _make_args(command=["/bin/login {{secret:bar}}"])
        with mock.patch.object(cmdseal, "kc_list", return_value=[item]):
            msg = self._run_and_capture_exit(args)
        self.assertIn("secret set mismatch", msg)

    def test_too_many_segments(self):
        item = _make_item("cmdseal.abcdef123456.K",
                          comment=_good_comment())
        too_many = ["/bin/echo x"] * (cmdseal.MAX_PIPE_SEGMENTS + 1)
        args = _make_args(command=too_many)
        with mock.patch.object(cmdseal, "kc_list", return_value=[item]):
            msg = self._run_and_capture_exit(args)
        self.assertIn("too many --command segments", msg)


class EditTemplateHappyPathTests(unittest.TestCase):
    """成功路径：旧字段被注入 args，do_seal 被调用且拿到正确参数。"""

    def test_happy_path_delegates_to_do_seal(self):
        item = _make_item(
            "cmdseal.abcdef123456.K",
            account="ws-old",
            comment=_good_comment(
                label="custom label",
                output_path="/custom/output/path",
                secret_names=["mypass"],
            ),
        )
        args = _make_args(
            service="cmdseal.abcdef123456.K",
            command=["/bin/login {{secret:mypass}}"],
            user="ws",  # 应被旧 account 覆盖
        )

        with mock.patch.object(cmdseal, "check_platform_and_tools",
                               return_value=None), \
             mock.patch.object(cmdseal, "kc_list", return_value=[item]), \
             mock.patch.object(cmdseal, "do_seal", return_value=0) as mseal:
            rc = cmdseal.do_edit_template(args)

        self.assertEqual(rc, 0)
        mseal.assert_called_once()
        call_args, call_kwargs = mseal.call_args

        # 第 1 位是 args（Namespace），应带注入字段
        injected = call_args[0]
        self.assertEqual(injected.output, "/custom/output/path")
        self.assertEqual(injected.label, "custom label")
        self.assertEqual(injected.user, "ws-old")  # 已被旧 account 覆盖

        # old_service_to_delete 必须关键字传入，且等于原 --service
        self.assertEqual(
            call_kwargs.get("old_service_to_delete"),
            "cmdseal.abcdef123456.K",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
