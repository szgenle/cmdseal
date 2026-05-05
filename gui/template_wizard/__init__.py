"""命令模板向导 — 面向普通用户的简化流程（v1.2.2：多段管道）。

四页式 QWizard：
  1. CommandInputPage        — 输入 1~N 段管道命令，整条串跑成功才能下一步
  2. ParameterSelectionPage  — 每段一行 chip，token 切片点选替换为 {{arg:N}}
                               arg 编号跨段全局递增
  3. OutputConfigPage        — 默认输出到 ~/cmdseal/bin/<program_name>
  4. ExecutionPage           — 调 cmdseal.py seal 生成封装

本模块是一个轻量级的包门面：为了在保证向后兼容（`from gui.template_wizard
import TemplateWizard / build_template / ...`）的前提下拆分长文件，真正实现
分散在同目录下的私有子模块中。

多段管道（v1.2.2）：
- 完整管道试运行走 QProcess 链（setStandardOutputProcess），与 runner 自建
  管道的语义等价；不经 shell，用户写的 `|` / `>` / `$VAR` 不会被展开
- chip 点选是本向导的核心交互，多段下保持不变：每段一行 chip、arg 编号
  在所有段中按出现顺序全局递增
"""
from __future__ import annotations

from ._command_page import CommandInputPage, CommandLineEdit
from ._core import (
    DEFAULT_OUTPUT_DIR,
    EXAMPLE_COMMAND,
    MAX_PIPE_SEGMENTS,
    PATH_PREFIX_MARKERS,
    SEALED_NAME_PREFIX,
    TRY_RUN_TIMEOUT_MS,
    build_template,
    build_template_many,
    complete_path,
    validate_command,
)
from ._exec_page import ExecutionPage
from ._output_page import OutputConfigPage
from ._param_page import ParameterSelectionPage
from ._wizard import TemplateWizard

__all__ = [
    "CommandInputPage",
    "CommandLineEdit",
    "DEFAULT_OUTPUT_DIR",
    "EXAMPLE_COMMAND",
    "ExecutionPage",
    "MAX_PIPE_SEGMENTS",
    "OutputConfigPage",
    "PATH_PREFIX_MARKERS",
    "ParameterSelectionPage",
    "SEALED_NAME_PREFIX",
    "TRY_RUN_TIMEOUT_MS",
    "TemplateWizard",
    "build_template",
    "build_template_many",
    "complete_path",
    "validate_command",
]
