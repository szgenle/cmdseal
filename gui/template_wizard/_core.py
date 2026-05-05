"""纯函数与常量。

把模板向导里与 Qt 无关的逻辑集中在这里，方便单测（tests/test_template_wizard.py
直接 ``from gui.template_wizard import ...`` 即可命中）。
"""
from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path


#: 默认输出目录：用户专属，避免 /usr/local/bin 的 sudo 依赖
DEFAULT_OUTPUT_DIR = Path.home() / "cmdseal" / "bin"

#: 试运行超时（秒）。太短会误杀正常命令；太长体验差
TRY_RUN_TIMEOUT_MS = 10_000

#: 默认输出文件名前缀。用来与原始命令区分，避免放入 PATH 后遮蔽同名系统命令。
#: 与项目自带 demo ``seal_zip`` 的命名风格保持一致。
SEALED_NAME_PREFIX = "seal_"

#: 顶部常驻示例命令。故意用不含任何 shell 元字符的形式：
#: sealed 产物以 execv 运行，试运行用 QProcess.start，两者都不走 shell。
#: 如果示例写 $VAR / | / > / *，用户会误以为它们会展开，产生与封装后不一致的预期。
EXAMPLE_COMMAND = 'echo hello world'

#: 管道段数硬上限。与 cmdseal.py CLI / seal_wizard 高级模式保持一致。
MAX_PIPE_SEGMENTS = 8

#: Tab 补全触发前缀：只有当前 token 以这些字符开头才当作“路径”处理
PATH_PREFIX_MARKERS = ("/", "~", "./", "../")


def validate_command(cmd: str) -> tuple[bool, str, list[str]]:
    """静态验证命令：shlex 可解析 + 首 token 可执行。

    Returns:
        (ok, message, tokens)
    """
    cmd = cmd.strip()
    if not cmd:
        return False, "命令为空", []
    try:
        tokens = shlex.split(cmd)
    except ValueError as e:
        return False, f"命令解析失败：{e}", []
    if not tokens:
        return False, "命令为空", []

    program = tokens[0]
    if program.startswith(("/", "~", ".")):
        resolved = Path(program).expanduser()
        if not resolved.is_file():
            return False, f"程序不存在：{program}", tokens
        if not os.access(resolved, os.X_OK):
            return False, f"程序不可执行：{program}", tokens
    else:
        if not shutil.which(program):
            return False, f"在 PATH 中找不到：{program}", tokens

    return True, f"语法合法（{len(tokens)} 个 tokens）", tokens


def build_template(tokens: list[str], selected: set[int]) -> str:
    """按选中的 token 索引替换为 {{arg:N}}，其余 token 用 shlex.quote 保留。

    - 编号按在命令中出现的位置先后（不是点击顺序）
    - 未选中的 token 经 shlex.quote 保护，避免含空格/特殊字符的字面量被破坏

    v1.2.2：单段便捷包装，内部转调 build_template_many 以保持单一事实来源。
    """
    templates = build_template_many([tokens], [selected])
    return templates[0] if templates else ""


def build_template_many(
    token_groups: list[list[str]],
    selected: list[set[int]],
) -> list[str]:
    """多段版 build_template：arg 编号在所有段中按出现顺序全局递增。

    Args:
        token_groups: 每段的 tokens；len(token_groups) == 段数
        selected:     每段的选中 token 索引集合；长度需与 token_groups 相同

    Returns:
        每段对应的模板字符串列表。CLI 会把每段作为独立 --command 传给 cmdseal.py。

    设计要点：
    - 单段时退化为 v1.1 build_template 行为（编号从 1 开始，逐 token 递增）
    - 多段时 arg 编号跨段连续：段 1 选了 2 个 → 段 2 的首个选中 token 是 {{arg:3}}
      这一策略与 seal_wizard._scan_placeholders_many 对齐，避免用户误以为每段
      都从 1 开始而在运行时传错参数
    """
    if len(token_groups) != len(selected):
        raise ValueError(
            f"token_groups 与 selected 长度不匹配："
            f"{len(token_groups)} vs {len(selected)}"
        )
    arg_n = 0
    result: list[str] = []
    for tokens, sel in zip(token_groups, selected):
        parts: list[str] = []
        for i, tok in enumerate(tokens):
            if i in sel:
                arg_n += 1
                parts.append(f"{{{{arg:{arg_n}}}}}")
            else:
                parts.append(shlex.quote(tok))
        result.append(" ".join(parts))
    return result


def complete_path(prefix: str) -> tuple[str, list[str]]:
    """bash 风格的 Tab 路径补全（纯函数，便于单测）。

    Args:
        prefix: 用户当前 token，例如 ``~/D``、``./s``、``/usr/local/b``

    Returns:
        (completed, matches)
          - completed: 建议的新前缀（最长公共前缀；单匹配时目录追加 ``/``）。
            无匹配时原样返回 prefix。
          - matches: 候选的 basename 列表（按字典序）；无匹配时为空列表。

    设计要点：
    - 如果用户原本写的是 ``~/``，补全后保留 ``~``（不把 HOME 展开进输入框）
    - 单匹配且是目录时追加分隔符，方便用户继续按 Tab 向下钻
    - 目录无权阅读直接当作候选为空，不抛异常
    """
    if not prefix:
        return prefix, []
    original_tilde = prefix.startswith("~")
    expanded = os.path.expanduser(prefix)
    directory, partial = os.path.split(expanded)
    base = directory if directory else "."
    try:
        entries = sorted(os.listdir(base))
    except OSError:
        return prefix, []
    matches = [e for e in entries if e.startswith(partial)]
    if not matches:
        return prefix, []
    common = os.path.commonprefix(matches)
    completed = os.path.join(directory, common) if directory else common
    if len(matches) == 1:
        full = os.path.expanduser(completed)
        if os.path.isdir(full) and not completed.endswith(os.sep):
            completed += os.sep
    if original_tilde:
        home = os.path.expanduser("~")
        if completed == home:
            completed = "~"
        elif completed.startswith(home + os.sep):
            completed = "~" + completed[len(home):]
    return completed, matches
