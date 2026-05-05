"""命令模板向导 — 面向普通用户的简化流程。

四页式 QWizard：
  1. CommandInputPage        — 输入命令，必须先「真实运行成功」才能下一步
  2. ParameterSelectionPage  — token 切片点选，替换为 {{arg:N}}
  3. OutputConfigPage        — 默认输出到 ~/cmdseal/bin/<program_name>
  4. ExecutionPage           — 调 cmdseal.py seal 生成封装

与 SealWizard 的差异：
- 不暴露 {{secret:NAME}}，需要 secret 的场景请用高级模式
- 输出目录默认在用户专属的 ~/cmdseal/bin/，避免 /usr/local/bin 的写权限坑
- 签名统一 ad-hoc；不暴露 --no-sign
"""
from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from . import backend

#: 默认输出目录：用户专属，避免 /usr/local/bin 的 sudo 依赖
DEFAULT_OUTPUT_DIR = Path.home() / "cmdseal" / "bin"

#: 试运行超时（秒）。太短会误杀正常命令；太长体验差
TRY_RUN_TIMEOUT_MS = 10_000

#: 默认输出文件名前缀。用来与原始命令区分，避免放入 PATH 后遮蔽同名系统命令。
#: 与项目自带 demo `seal_zip` 的命名风格保持一致。
SEALED_NAME_PREFIX = "seal_"

#: 顶部常驻示例命令。故意用不含任何 shell 元字符的形式：
#: sealed 产物以 execv 运行，试运行用 QProcess.start，两者都不走 shell。
#: 如果示例写 $VAR / | / > / *，用户会误以为它们会展开，产生与封装后不一致的预期。
EXAMPLE_COMMAND = 'echo hello world'


# ---------------------------------------------------------------------------
# 纯函数（方便单测）
# ---------------------------------------------------------------------------

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
    """
    arg_n = 0
    parts: list[str] = []
    for i, tok in enumerate(tokens):
        if i in selected:
            arg_n += 1
            parts.append(f"{{{{arg:{arg_n}}}}}")
        else:
            parts.append(shlex.quote(tok))
    return " ".join(parts)


#: Tab 补全触发前缀：只有当前 token 以这些字符开头才当作“路径”处理
PATH_PREFIX_MARKERS = ("/", "~", "./", "../")


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


# ---------------------------------------------------------------------------
# Page 1 — 命令输入 + 真实运行验证
# ---------------------------------------------------------------------------

class CommandLineEdit(QPlainTextEdit):
    """带 Tab 路径补全的命令输入框（bash 风格）。

    - 光标前的 token 以 ``/`` / ``~`` / ``./`` / ``../`` 开头时：
        * 单匹配→直接补全，目录尾随 ``/``
        * 多匹配→补到最长公共前缀，连按两次 Tab 在页面上列出候选
        * 无匹配→在页面上提示“无匹配”
    - 非路径 token 的 Tab 走默认（切焦点；已设 setTabChangesFocus(True)）
    """

    #: 向页面报告补全提示文本；空串 = 清空提示
    completionHint = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # 注意：这里不能调 setTabChangesFocus(True)。
        # 它会在 QWidget::event() 层直接用 Tab 切焦点，keyPressEvent 根本收不到事件。
        # 我们自己在 keyPressEvent 里判断“路径补全 vs 焦点切换”。
        #: 记录上一次 Tab 补全后的 token，用于检测“双 Tab 列出候选”
        self._last_completed_token: str | None = None

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() not in (Qt.Key_Tab, Qt.Key_Backtab):
            self._last_completed_token = None
            super().keyPressEvent(event)
            return
        # Shift+Tab 或 Backtab → 反向切焦点
        if event.key() == Qt.Key_Backtab or event.modifiers() & Qt.ShiftModifier:
            self._last_completed_token = None
            self.focusPreviousChild()
            return

        cursor = self.textCursor()
        block = cursor.block()
        col = cursor.positionInBlock()
        before = block.text()[:col]

        # 向前找空白边界，划出当前 token
        token_start = col
        for i in range(col - 1, -1, -1):
            if before[i].isspace():
                token_start = i + 1
                break
            token_start = i
        token = before[token_start:col]

        if not token.startswith(PATH_PREFIX_MARKERS):
            # 非路径→保留“Tab 切焦点”的直觉（跳到下一个控件，如「试运行」按钮）
            self._last_completed_token = None
            self.focusNextChild()
            return

        completed, matches = complete_path(token)
        if not matches:
            self._last_completed_token = None
            self.completionHint.emit(f"⚠ 无匹配：{token}")
            return

        # 用 completed 替换当前 token（仅限光标所在行的那一段）
        abs_start = block.position() + token_start
        abs_end = block.position() + col
        cursor.setPosition(abs_start)
        cursor.setPosition(abs_end, QTextCursor.KeepAnchor)
        cursor.insertText(completed)

        if len(matches) == 1:
            self._last_completed_token = None
            self.completionHint.emit("")
            return

        # 多候选：第二次 Tab 时展示候选列表
        if self._last_completed_token == completed:
            preview = matches[:20]
            more = f"… 共 {len(matches)} 个" if len(matches) > len(preview) else ""
            self.completionHint.emit("候选：" + "  ".join(preview) + more)
        else:
            self.completionHint.emit(f"{len(matches)} 个候选，再按 Tab 查看")
        self._last_completed_token = completed


class CommandInputPage(QWizardPage):
    """第 1 步：输入命令，并真实运行一次成功才允许下一步。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("输入命令")
        self.setSubTitle(
            "输入真实可执行的命令。点击「试运行」确认命令能正常执行后再下一步。\n"
            "注意：试运行会真的执行命令，请先用无副作用的参数测试。"
        )

        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)

        # 顶部常驻示例：始终可见，便于用户照着写；另附一键填入按钮
        self.example_label = QLabel(
            f"<b>示例：</b> <code>{EXAMPLE_COMMAND}</code>"
        )
        self.example_label.setWordWrap(True)
        self.example_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.example_label.setStyleSheet(
            "QLabel { background: #f0f7ff; border: 1px solid #cfe3ff; "
            "border-radius: 4px; padding: 8px; color: #333; }"
        )
        self.example_btn = QPushButton("填入示例")
        self.example_btn.setToolTip("将示例命令填入下方输入框")
        self.example_btn.clicked.connect(self._insert_example)
        example_row = QHBoxLayout()
        example_row.addWidget(self.example_label, 1)
        example_row.addWidget(self.example_btn, 0, Qt.AlignTop)

        self.edit = CommandLineEdit()
        self.edit.setPlaceholderText(
            "在此输入要封装的命令；建议先用无副作用的参数试运行\n"
            "提示：路径 token（以 /、~、./ 开头）可按 Tab 补全"
        )
        self.edit.setFont(mono)

        self.static_hint = QLabel("—")
        self.static_hint.setWordWrap(True)
        self.static_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.completion_hint = QLabel("")
        self.completion_hint.setWordWrap(True)
        self.completion_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.completion_hint.setStyleSheet("color: #555; font-size: 11px;")
        self.edit.completionHint.connect(self.completion_hint.setText)

        self.run_btn = QPushButton("试运行")
        self.run_btn.clicked.connect(self._run)

        self.reset_btn = QPushButton("清除运行结果")
        self.reset_btn.clicked.connect(self._reset_run_state)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(mono)
        self.log.setMaximumBlockCount(5000)
        self.log.setPlaceholderText("此处显示试运行的 stdout/stderr 与退出码")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch(1)

        # “不走 shell”警示条：避免用户写 $VAR/|/>/* 后产生与封装后不一致的预期
        self.shell_warn = QLabel(
            "⚠ 命令直接 execv 执行，<b>不经 shell</b>："
            "环境变量 <code>$VAR</code>、管道 <code>|</code>、"
            "重定向 <code>&gt;</code>、通配符 <code>*</code> 都不会展开。"
        )
        self.shell_warn.setWordWrap(True)
        self.shell_warn.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.shell_warn.setStyleSheet(
            "QLabel { background: #fff8e1; color: #5d4037; "
            "border: 1px solid #ffe0b2; border-radius: 4px; padding: 6px 8px; }"
        )

        lay = QVBoxLayout(self)
        lay.addLayout(example_row)
        lay.addWidget(self.shell_warn)
        lay.addWidget(QLabel("命令（空格/引号按 shell 规则分词，但不执行 shell）："))
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.static_hint)
        lay.addWidget(self.completion_hint)
        lay.addLayout(btn_row)
        lay.addWidget(QLabel("试运行输出："))
        lay.addWidget(self.log, 1)

        # 运行态
        self._proc: QProcess | None = None
        self._run_ok: bool = False
        self._last_validated_cmd: str = ""

        self.edit.textChanged.connect(self._on_text_changed)
        self._on_text_changed()

    def _insert_example(self) -> None:
        """将示例命令填入输入框（覆盖现有内容前先确认）。"""
        current = self.edit.toPlainText().strip()
        if current and current != EXAMPLE_COMMAND:
            reply = QMessageBox.question(
                self, "覆盖当前命令？",
                "输入框中已有命令，填入示例会覆盖现有内容。继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self.edit.setPlainText(EXAMPLE_COMMAND)
        self.edit.setFocus()

    # --- 状态 ---
    def _on_text_changed(self) -> None:
        cmd = self.edit.toPlainText().strip()
        if cmd != self._last_validated_cmd:
            # 命令被改过，旧的试运行结果失效
            self._run_ok = False
        # 用户继续输入会使上一次的补全提示过时，索性清掉
        self.completion_hint.setText("")
        ok, msg, _ = validate_command(cmd)
        if not cmd:
            self.static_hint.setText("—")
            self.run_btn.setEnabled(False)
        elif ok:
            self.static_hint.setText(f"<span style='color: #2e7d32;'>✓ {msg}</span>")
            self.run_btn.setEnabled(self._proc is None)
        else:
            self.static_hint.setText(f"<span style='color: #c62828;'>⚠ {msg}</span>")
            self.run_btn.setEnabled(False)
        self.completeChanged.emit()

    def _reset_run_state(self) -> None:
        self._run_ok = False
        self._last_validated_cmd = ""
        self.log.clear()
        self._on_text_changed()

    # --- 试运行 ---
    def _run(self) -> None:
        cmd = self.edit.toPlainText().strip()
        ok, _, tokens = validate_command(cmd)
        if not ok or not tokens:
            return

        reply = QMessageBox.question(
            self,
            "确认试运行",
            "即将真实执行该命令。\n"
            "请确认命令当前参数不会产生破坏性副作用（删文件、覆盖数据等）。\n\n"
            f"$ {cmd}\n\n继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.log.clear()
        self.log.appendPlainText(f"$ {cmd}")
        self.run_btn.setEnabled(False)

        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        proc.setProcessEnvironment(env)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self._proc = proc
        proc.start(tokens[0], tokens[1:])
        if not proc.waitForStarted(3000):
            self.log.appendPlainText("⚠ 子进程启动失败")
            self._proc = None
            self.run_btn.setEnabled(True)
            return
        # 启动定时器杀超时
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.start(TRY_RUN_TIMEOUT_MS)

    def _on_stdout(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.log.appendPlainText(data.rstrip("\n"))

    def _on_error(self, err: QProcess.ProcessError) -> None:
        self.log.appendPlainText(f"⚠ QProcess 错误：{err}")

    def _on_timeout(self) -> None:
        if self._proc is not None:
            self.log.appendPlainText(f"⚠ 超时（{TRY_RUN_TIMEOUT_MS // 1000}s），已终止")
            self._proc.kill()

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._on_stdout()
        if hasattr(self, "_timer") and self._timer is not None:
            self._timer.stop()
        self.log.appendPlainText(f"[exit {code}, status={status.name}]")
        self._run_ok = (code == 0 and status == QProcess.NormalExit)
        if self._run_ok:
            self._last_validated_cmd = self.edit.toPlainText().strip()
            self.log.appendPlainText("✓ 命令验证通过，可进入下一步")
        else:
            self.log.appendPlainText("✗ 命令执行未成功，请修正后重试")
        self._proc = None
        self.run_btn.setEnabled(True)
        self.completeChanged.emit()

    # --- QWizardPage ---
    def isComplete(self) -> bool:
        cmd = self.edit.toPlainText().strip()
        return bool(cmd) and self._run_ok and cmd == self._last_validated_cmd

    def command(self) -> str:
        return self.edit.toPlainText().strip()

    def tokens(self) -> list[str]:
        _, _, toks = validate_command(self.command())
        return toks


# ---------------------------------------------------------------------------
# Page 2 — 参数选择（token 切片点选）
# ---------------------------------------------------------------------------

class ParameterSelectionPage(QWizardPage):
    """第 2 步：点选要参数化的 token。"""

    # chip 样式：未选中 = 字面量；选中 = 运行时参数
    _STYLE_LITERAL = (
        "QPushButton { background: #ffffff; color: #333; "
        "border: 1px solid #bbb; border-radius: 4px; padding: 6px 10px; }"
        "QPushButton:hover { border-color: #4a90d9; }"
    )
    _STYLE_ARG = (
        "QPushButton { background: #4a90d9; color: white; "
        "border: 1px solid #357abd; border-radius: 4px; "
        "padding: 6px 10px; font-weight: bold; }"
    )

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("选择运行时参数")
        self.setSubTitle("点击命令中的 token 切换「字面量 / 运行时参数」。")

        # 横向滚动区域容纳 chip
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(80)
        self._container = QWidget()
        self._chip_layout = QHBoxLayout(self._container)
        self._chip_layout.setSpacing(6)
        self._chip_layout.setContentsMargins(6, 6, 6, 6)
        self._scroll.setWidget(self._container)

        self.preview = QLabel("—")
        self.preview.setWordWrap(True)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        self.preview.setFont(mono)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 显式指定前景色，避免在 macOS 深色模式下文字被系统默认白色吞进同样的浅底
        self.preview.setStyleSheet(
            "QLabel { background: #f5f5f5; color: #222; padding: 10px; "
            "border-radius: 4px; border: 1px solid #ddd; }"
        )

        self.hint = QLabel("—")
        self.hint.setWordWrap(True)
        # 深色模式下 #555 对比度也足够；但要指定 background: transparent 防止继承父容器
        self.hint.setStyleSheet("QLabel { color: #888; background: transparent; }")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("命令分解（蓝色 = 运行时参数，白色 = 字面量）："))
        lay.addWidget(self._scroll)
        lay.addWidget(QLabel("模板预览："))
        lay.addWidget(self.preview)
        lay.addWidget(self.hint)
        lay.addStretch(1)

        self._tokens: list[str] = []
        self._selected: set[int] = set()

    def initializePage(self) -> None:
        # 清空旧 chip
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        wiz = self.wizard()
        if not isinstance(wiz, TemplateWizard):
            return
        self._tokens = wiz.command_page.tokens()
        self._selected = set()

        for i, tok in enumerate(self._tokens):
            chip = QPushButton(tok)
            chip.setCheckable(True)
            chip.setStyleSheet(self._STYLE_LITERAL)
            chip.setToolTip(f"token #{i}：点击切换为运行时参数")

            def _on_toggle(checked: bool, idx: int = i, b: QPushButton = chip) -> None:
                if checked:
                    self._selected.add(idx)
                    b.setStyleSheet(self._STYLE_ARG)
                else:
                    self._selected.discard(idx)
                    b.setStyleSheet(self._STYLE_LITERAL)
                self._update_preview()
                self.completeChanged.emit()

            chip.toggled.connect(_on_toggle)
            self._chip_layout.addWidget(chip)

        self._chip_layout.addStretch(1)
        self._update_preview()

    def _update_preview(self) -> None:
        tmpl = build_template(self._tokens, self._selected)
        self.preview.setText(tmpl)
        n = len(self._selected)
        if n == 0:
            self.hint.setText("<span style='color: #c62828;'>⚠ 至少选择一个 token 作为运行时参数</span>")
        else:
            msg = f"已选 {n} 个运行时参数 → 运行时将通过位置参数传入"
            if 0 in self._selected:
                msg += "；⚠ 首 token（程序路径）被参数化，运行时必须传入可执行的绝对路径"
            self.hint.setText(msg)

    def isComplete(self) -> bool:
        return len(self._selected) > 0

    def template(self) -> str:
        return build_template(self._tokens, self._selected)

    def program_name(self) -> str:
        """用于生成默认输出文件名：统一加 SEALED_NAME_PREFIX 前缀以区分原命令。

        特例：
        - 命令本身已以前缀开头（如用户给封装产物再封装）→ 不重复加前缀
        - tokens 为空 → 退化到 “sealed”
        """
        if not self._tokens:
            return "sealed"
        base = Path(self._tokens[0]).name or "sealed"
        if base.startswith(SEALED_NAME_PREFIX):
            return base
        return SEALED_NAME_PREFIX + base


# ---------------------------------------------------------------------------
# Page 3 — 输出配置
# ---------------------------------------------------------------------------

class OutputConfigPage(QWizardPage):
    """第 3 步：输出路径。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("保存位置")
        self.setSubTitle("选择封装后的二进制保存到哪里。")

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(str(DEFAULT_OUTPUT_DIR / f"{SEALED_NAME_PREFIX}program"))
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        out_row = QWidget()
        out_lay = QHBoxLayout(out_row)
        out_lay.setContentsMargins(0, 0, 0, 0)
        out_lay.addWidget(self.output_edit, 1)
        out_lay.addWidget(browse)

        self.path_hint = QLabel(
            f"默认文件名为 <code>{SEALED_NAME_PREFIX}&lt;原命令名&gt;</code>，用以与原命令区分。\n"
            f"默认保存到 {DEFAULT_OUTPUT_DIR}/（首次使用会自动创建）。\n"
            "若要全局调用，可手动指定 /usr/local/bin/ 等 PATH 中的目录，"
            "或自建软链接。"
        )
        self.path_hint.setWordWrap(True)
        self.path_hint.setStyleSheet("color: #666; font-size: 11px;")

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("留空则按输出文件名自动生成")

        self.user_edit = QLineEdit(os.environ.get("USER", ""))

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("输出路径：", out_row)
        form.addRow("", self.path_hint)
        form.addRow("Label（可选）：", self.label_edit)
        form.addRow("Keychain 账号：", self.user_edit)

        self.output_edit.textChanged.connect(self.completeChanged)
        self.user_edit.textChanged.connect(self.completeChanged)

    def initializePage(self) -> None:
        """首次进入时，按上一页的程序名填默认路径。"""
        if self.output_edit.text().strip():
            return
        wiz = self.wizard()
        if not isinstance(wiz, TemplateWizard):
            return
        name = wiz.param_page.program_name()
        self.output_edit.setText(str(DEFAULT_OUTPUT_DIR / name))

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出路径",
            self.output_edit.text() or str(DEFAULT_OUTPUT_DIR))
        if path:
            self.output_edit.setText(path)

    def isComplete(self) -> bool:
        return bool(self.output_edit.text().strip() and self.user_edit.text().strip())

    def output_path(self) -> Path:
        return Path(self.output_edit.text()).expanduser()

    def label(self) -> str:
        return self.label_edit.text().strip()

    def user(self) -> str:
        return self.user_edit.text().strip()


# ---------------------------------------------------------------------------
# Page 4 — 执行 cmdseal seal
# ---------------------------------------------------------------------------

class ExecutionPage(QWizardPage):
    """第 4 步：调 cmdseal.py seal 生成封装。"""

    finished_ok = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("生成封装")
        self.setSubTitle("点击「运行」，cmdseal.py 将在子进程中构建并签名二进制。")
        self.setCommitPage(True)

        self._proc: QProcess | None = None
        self._ok = False

        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(mono)
        self.preview.setMaximumBlockCount(2000)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(mono)
        self.log.setMaximumBlockCount(20000)

        self.run_btn = QPushButton("运行生成")
        self.run_btn.clicked.connect(self._run)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("配置预览："))
        lay.addWidget(self.preview)
        lay.addWidget(self.run_btn)
        lay.addWidget(QLabel("日志："))
        lay.addWidget(self.log, 1)

    def initializePage(self) -> None:
        wiz = self.wizard()
        if not isinstance(wiz, TemplateWizard):
            return
        req = self._build_request(wiz)
        # 确保默认目录存在（若用户选了自定义路径则跳过）
        try:
            req.output.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        lines = [
            f"模板    : {req.command}",
            f"输出    : {req.output}",
            f"label   : {req.label or '(auto)'}",
            f"用户    : {req.user}",
            f"签名    : ad-hoc",
        ]
        self.preview.setPlainText("\n".join(lines))
        self.log.clear()
        self.run_btn.setEnabled(True)
        self._ok = False

    def isComplete(self) -> bool:
        return self._ok

    def _build_request(self, wiz: TemplateWizard) -> backend.SealRequest:
        return backend.SealRequest(
            command=wiz.param_page.template(),
            output=wiz.output_page.output_path(),
            secrets={},  # 简化模式不采集 secret
            signing_identity="-",
            no_sign=False,
            user=wiz.output_page.user(),
            label=wiz.output_page.label(),
            rotate=False,
        )

    def _run(self) -> None:
        if self._proc is not None:
            return
        self.run_btn.setEnabled(False)
        try:
            wiz = self.wizard()
            if not isinstance(wiz, TemplateWizard):
                return
            req = self._build_request(wiz)
            argv = backend.build_argv(req)
            self.log.appendPlainText(
                "$ " + " ".join(shlex.quote(x) for x in argv))

            proc = QProcess(self)
            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONUNBUFFERED", "1")
            proc.setProcessEnvironment(env)
            proc.setWorkingDirectory(str(backend.PROJECT_ROOT))
            proc.setProcessChannelMode(QProcess.MergedChannels)
            proc.readyReadStandardOutput.connect(self._on_stdout)
            proc.finished.connect(self._on_finished)
            proc.errorOccurred.connect(self._on_error)
            self._proc = proc
            proc.start(argv[0], argv[1:])
            if not proc.waitForStarted(3000):
                self.log.appendPlainText("⚠ 子进程启动失败")
                self._proc = None
                self.run_btn.setEnabled(True)
                return
            # 简化模式无 secret，直接关闭写通道让 cmdseal.py 立即继续
            proc.closeWriteChannel()
        except Exception as e:
            import traceback
            self.log.appendPlainText(f"⚠ 异常：{e}\n{traceback.format_exc()}")
            self._proc = None
            self.run_btn.setEnabled(True)

    def _on_stdout(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.log.appendPlainText(data.rstrip("\n"))

    def _on_error(self, err: QProcess.ProcessError) -> None:
        self.log.appendPlainText(f"⚠ QProcess 错误：{err}")

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._on_stdout()
        self.log.appendPlainText(f"\n[exit {code}, status={status.name}]")
        self._ok = (code == 0 and status == QProcess.NormalExit)
        self.run_btn.setEnabled(not self._ok)
        self._proc = None
        self.completeChanged.emit()
        self.finished_ok.emit(self._ok)


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

class TemplateWizard(QWizard):
    """从已验证命令生成封装模板。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("cmdseal — 从命令生成模板")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.IndependentPages, False)
        self.resize(840, 640)

        self.command_page = CommandInputPage()
        self.param_page = ParameterSelectionPage()
        self.output_page = OutputConfigPage()
        self.execute_page = ExecutionPage()

        self.addPage(self.command_page)
        self.addPage(self.param_page)
        self.addPage(self.output_page)
        self.addPage(self.execute_page)

        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")
        self.setButtonText(QWizard.NextButton, "下一步 >")
        self.setButtonText(QWizard.BackButton, "< 上一步")
        self.setButtonText(QWizard.CommitButton, "进入执行")
