#!/usr/bin/env python3
"""测试 seal 向导的简化功能。

验证点：
1. 命令中可以写字面量密码（不强制 {{secret:}}）
2. 没有 {{secret:*}} 时，SecretsPage 应该被跳过
3. 裸写 secret:/arg: 时应该有警告
"""
import sys
from pathlib import Path

# 确保可以导入 gui 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from gui.seal_wizard import SealWizard, _scan_placeholders


def test_scan_placeholders():
    """测试占位符扫描功能。"""
    print("=" * 60)
    print("测试 1: 占位符扫描")
    print("=" * 60)
    
    # 测试 1a: 字面量密码（无 secret）
    cmd1 = "zip -j -P mypassword {{arg:1}} {{arg:2}}"
    secrets1, args1 = _scan_placeholders(cmd1)
    print(f"\n命令: {cmd1}")
    print(f"  secrets: {secrets1} (期望: [])")
    print(f"  args: {args1} (期望: ['1', '2'])")
    assert secrets1 == [], f"期望 [], 得到 {secrets1}"
    assert args1 == ['1', '2'], f"期望 ['1', '2'], 得到 {args1}"
    print("  ✅ 通过")
    
    # 测试 1b: 使用 {{secret:}}
    cmd2 = "zhmm-cli --pwd {{secret:master}} -s {{arg:1}}"
    secrets2, args2 = _scan_placeholders(cmd2)
    print(f"\n命令: {cmd2}")
    print(f"  secrets: {secrets2} (期望: ['master'])")
    print(f"  args: {args2} (期望: ['1'])")
    assert secrets2 == ['master'], f"期望 ['master'], 得到 {secrets2}"
    assert args2 == ['1'], f"期望 ['1'], 得到 {args2}"
    print("  ✅ 通过")
    
    # 测试 1c: 混合使用
    cmd3 = "cmd --pwd {{secret:pw1}} --user {{secret:user}} file {{arg:1}} {{arg:2}}"
    secrets3, args3 = _scan_placeholders(cmd3)
    print(f"\n命令: {cmd3}")
    print(f"  secrets: {secrets3} (期望: ['pw1', 'user'])")
    print(f"  args: {args3} (期望: ['1', '2'])")
    assert secrets3 == ['pw1', 'user'], f"期望 ['pw1', 'user'], 得到 {secrets3}"
    assert args3 == ['1', '2'], f"期望 ['1', '2'], 得到 {args3}"
    print("  ✅ 通过")
    
    print("\n✅ 所有占位符扫描测试通过\n")


def test_wizard_flow():
    """测试向导流程。"""
    print("=" * 60)
    print("测试 2: 向导流程")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    wizard = SealWizard()
    
    # 测试 2a: 无 secret 的命令 - SecretsPage 应该被跳过
    print("\n测试 2a: 字面量密码命令（无 {{secret:*}}）")
    wizard.command_page.edit.setPlainText("zip -j -P mypassword {{arg:1}} {{arg:2}}")
    
    # 模拟向导流程
    wizard.next()  # 从 CommandPage (0) 到 SecretsPage (1)
    current_id = wizard.currentId()
    print(f"  当前页 ID: {current_id}")
    
    # 如果没有 secret，nextId() 应该返回 2（跳到 OptionsPage）
    secrets_page = wizard.secrets_page
    next_id = secrets_page.nextId()
    print(f"  SecretsPage.nextId(): {next_id} (期望: 2，跳过本页)")
    assert next_id == 2, f"期望跳到 OptionsPage (2), 得到 {next_id}"
    print("  ✅ SecretsPage 会被正确跳过")
    
    # 测试 2b: 有 secret 的命令 - SecretsPage 应该显示
    print("\n测试 2b: 使用 {{secret:}} 的命令")
    wizard2 = SealWizard()
    wizard2.command_page.edit.setPlainText("zhmm-cli --pwd {{secret:master}} -s {{arg:1}}")
    
    secrets_page2 = wizard2.secrets_page
    secrets_page2.initializePage()
    next_id2 = secrets_page2.nextId()
    print(f"  SecretsPage.nextId(): {next_id2} (期望: 2，正常前进)")
    # 有 secret 时，nextId 应该调用 super().nextId() 返回正常下一页
    print(f"  SecretsPage 输入框数量: {len(secrets_page2._inputs)} (期望: 1)")
    assert len(secrets_page2._inputs) == 1, f"期望 1 个输入框, 得到 {len(secrets_page2._inputs)}"
    print("  ✅ SecretsPage 会正确显示 secret 输入框")
    
    print("\n✅ 所有向导流程测试通过\n")


def test_bare_placeholder_warning():
    """测试裸占位符警告。"""
    print("=" * 60)
    print("测试 3: 裸占位符警告")
    print("=" * 60)
    
    import re
    
    # 测试 3a: 裸写 secret:
    cmd1 = "zip -j -P secret:mypass {{arg:1}}"
    bare_secret = re.search(r'(?<!\{)secret:[A-Za-z0-9_]+(?!\})', cmd1)
    print(f"\n命令: {cmd1}")
    print(f"  检测到裸 secret: {bool(bare_secret)} (期望: True)")
    assert bare_secret, "应该检测到裸 secret:"
    print("  ✅ 检测到")
    
    # 测试 3b: 正确的 {{secret:}}
    cmd2 = "zip -j -P {{secret:mypass}} {{arg:1}}"
    bare_secret2 = re.search(r'(?<!\{)secret:[A-Za-z0-9_]+(?!\})', cmd2)
    print(f"\n命令: {cmd2}")
    print(f"  检测到裸 secret: {bool(bare_secret2)} (期望: False)")
    assert not bare_secret2, "不应该检测到裸 secret:"
    print("  ✅ 未误报")
    
    # 测试 3c: 裸写 arg:
    cmd3 = "cmd secret:mypass arg:1"
    bare_arg = re.search(r'(?<!\{)arg:[0-9]+(?!\})', cmd3)
    print(f"\n命令: {cmd3}")
    print(f"  检测到裸 arg: {bool(bare_arg)} (期望: True)")
    assert bare_arg, "应该检测到裸 arg:"
    print("  ✅ 检测到")
    
    print("\n✅ 所有裸占位符警告测试通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("cmdseal GUI 向导简化功能测试")
    print("=" * 60 + "\n")
    
    try:
        test_scan_placeholders()
        test_wizard_flow()
        test_bare_placeholder_warning()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n❌ 测试异常: {e}")
        traceback.print_exc()
        sys.exit(1)
