"""命令模板向导 — 面向普通用户的简化流程（v1.2.2：多段管道）。

四页式 QWizard：
  1. CommandInputPage        — 输入 1~N 段管道命令，整条串跑成功才能下一步
  2. ParameterSelectionPage  — 每段一行 chip，token 切片点选替换为 {{arg:N}}
                               arg 编号跨段全局递增
  3. OutputConfigPage        — 默认输出到 ~/cmdseal/bin/<program_name>
  4. ExecutionPage           — 调 cmdseal.py seal 生成封装

与 SealWizard 的差异：
- 不暴露 {{secret:NAME}}，需要 secret 的场景请用高级模式
- 输出目录默认在用户专属的 ~/cmdseal/bin/，避免 /usr/local/bin 的写权限坑
- 签名统一 ad-hoc；不暴露 --no-sign

多段管道（v1.2.2）：
- 完整管道试运行走 QProcess 链（setStandardOutputProcess），与 runner 自建
  管道的语义等价；不经 shell，用户写的 `|` / `>` / `$VAR` 不会被展开
- chip 点选是本向导的核心交互，多段下保持不变：每段一行 chip、arg 编号
  在所有段中按出现顺序全局递增
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
    QFrame,
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
from . import settings

#: 以下三项仍保留作为 fallback / 测试导入来源；真正的默认值由 settings.py 提供
#: 的 QSettings 驱动。详见 TemplateWizard.__init__ 中的 load_template_prefs()。

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

#: 管道段数硬上限。与 cmdseal.py CLI / seal_wizard 高级模式保持一致。
MAX_PIPE_SEGMENTS = 8


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
# Page 1 — 命令输入 + 整条管道真实运行验证（v1.2.2）
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


class _PipeSegment(QFrame):
    """单段管道编辑器：段头标题 + × 按钮 + CommandLineEdit + 段级提示。

    外部使用协议：
    - ``text()``         返回当前编辑框内容（符号化 strip）
    - ``set_title(i,n)`` 刷新段头文案（根据位置与总段数）
    - ``set_removable`` 控制 × 按钮可用性；首段不可删
    - ``update_hint()`` 根据 validate_command 更新段级静态提示
    - ``textChanged``    任何段修改后向父页报告，用于失效试运行结果
    - ``removeRequested(seg)`` 点 × 时向父页报告
    """

    textChanged = Signal()
    removeRequested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)

        self.title = QLabel("段 1")
        self.title.setStyleSheet(
            "QLabel { color: #555; font-weight: bold; background: transparent; }"
        )
        self.remove_btn = QPushButton("×")
        self.remove_btn.setFixedWidth(28)
        self.remove_btn.setToolTip("删除此段")
        self.remove_btn.clicked.connect(lambda: self.removeRequested.emit(self))

        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.remove_btn)

        self.edit = CommandLineEdit()
        self.edit.setFont(mono)
        self.edit.setFixedHeight(70)
        self.edit.setPlaceholderText(
            "路径 token（以 /、~、./ 开头）可按 Tab 补全"
        )
        self.edit.textChanged.connect(self.textChanged)

        self.hint = QLabel("—")
        self.hint.setWordWrap(True)
        self.hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hint.setStyleSheet("QLabel { background: transparent; }")

        self.completion_hint = QLabel("")
        self.completion_hint.setWordWrap(True)
        self.completion_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.completion_hint.setStyleSheet(
            "QLabel { color: #555; font-size: 11px; background: transparent; }"
        )
        self.edit.completionHint.connect(self.completion_hint.setText)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)
        lay.addLayout(header)
        lay.addWidget(self.edit)
        lay.addWidget(self.hint)
        lay.addWidget(self.completion_hint)

    def text(self) -> str:
        return self.edit.toPlainText().strip()

    def set_title(self, idx: int, total: int) -> None:
        if idx == 0:
            tag = "第一段 — 主命令"
        else:
            tag = f"第 {idx + 1} 段 — 从上段 stdout 读取"
        self.title.setText(f"段 {idx + 1}（{tag}）")

    def set_removable(self, removable: bool) -> None:
        self.remove_btn.setEnabled(removable)
        self.remove_btn.setToolTip("删除此段" if removable else "首段不可删除")

    def update_hint(self) -> None:
        cmd = self.text()
        if not cmd:
            self.hint.setText("<span style='color: #888;'>—</span>")
            return
        ok, msg, _ = validate_command(cmd)
        if ok:
            self.hint.setText(f"<span style='color: #2e7d32;'>✓ {msg}</span>")
        else:
            self.hint.setText(f"<span style='color: #c62828;'>⚠ {msg}</span>")


class CommandInputPage(QWizardPage):
    """第 1 步：输入 1~N 段管道命令，整条串跑一次成功才允许下一步。

    单段时退化为 v1.1/1.2.1 的单进程试运行；多段时用 QProcess.setStandardOutputProcess
    把每段 stdout 接入下一段 stdin，与 runner 自建管道的语义等价，不经 shell。
    """

    def __init__(self, timeout_ms: int = TRY_RUN_TIMEOUT_MS) -> None:
        super().__init__()
        #: 试运行超时（毫秒）。由偏好面板控制；未传则沿用历史硬编码。
        self._timeout_ms = timeout_ms
        self.setTitle("输入命令")
        self.setSubTitle(
            "输入真实可执行的命令；点击「➕ 添加管道段」可扩展为多段管道。\n"
            "点击「试运行整条管道」确认成功后再下一步。\n"
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
        self.example_btn.setToolTip("将示例命令填入第一段输入框")
        self.example_btn.clicked.connect(self._insert_example)
        example_row = QHBoxLayout()
        example_row.addWidget(self.example_label, 1)
        example_row.addWidget(self.example_btn, 0, Qt.AlignTop)

        # “不走 shell”警示条：避免用户写 $VAR/|/>/* 后产生与封装后不一致的预期
        self.shell_warn = QLabel(
            "⚠ 每段直接 execv 执行，<b>不经 shell</b>："
            "环境变量 <code>$VAR</code>、管道 <code>|</code>、"
            "重定向 <code>&gt;</code>、通配符 <code>*</code> 都不会展开；\n"
            "管道拼接请用「➕ 添加管道段」而非在单段里写 <code>|</code>。"
        )
        self.shell_warn.setWordWrap(True)
        self.shell_warn.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.shell_warn.setStyleSheet(
            "QLabel { background: #fff8e1; color: #5d4037; "
            "border: 1px solid #ffe0b2; border-radius: 4px; padding: 6px 8px; }"
        )

        # 段容器（可滚动）
        self._segments: list[_PipeSegment] = []
        self._segments_host = QWidget()
        self._segments_layout = QVBoxLayout(self._segments_host)
        self._segments_layout.setContentsMargins(0, 0, 0, 0)
        self._segments_layout.setSpacing(6)
        self._segments_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._segments_host)

        self.add_seg_btn = QPushButton("➕ 添加管道段")
        self.add_seg_btn.clicked.connect(self._add_segment)

        self.summary = QLabel("—")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("QLabel { color: #555; background: transparent; }")

        self.run_btn = QPushButton("试运行整条管道")
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

        lay = QVBoxLayout(self)
        lay.addLayout(example_row)
        lay.addWidget(self.shell_warn)
        lay.addWidget(QLabel("命令（多段按顺序串联为管道）："))
        lay.addWidget(self._scroll, 1)
        lay.addWidget(self.add_seg_btn, 0, Qt.AlignLeft)
        lay.addWidget(self.summary)
        lay.addLayout(btn_row)
        lay.addWidget(QLabel("试运行输出（最后一段 stdout）："))
        lay.addWidget(self.log, 1)

        # 运行态：多进程链
        self._procs: list[QProcess] = []
        self._run_ok: bool = False
        self._last_validated_cmds: list[str] = []

        self._add_segment()  # 初始 1 段

    # --- 示例 / 增删段 ---
    def _insert_example(self) -> None:
        """将示例命令填入首段输入框（覆盖现有内容前先确认）。"""
        if not self._segments:
            return
        seg0 = self._segments[0]
        current = seg0.text()
        if current and current != EXAMPLE_COMMAND:
            reply = QMessageBox.question(
                self, "覆盖当前命令？",
                "第一段输入框中已有命令，填入示例会覆盖现有内容。继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        seg0.edit.setPlainText(EXAMPLE_COMMAND)
        seg0.edit.setFocus()

    def _add_segment(self) -> None:
        if len(self._segments) >= MAX_PIPE_SEGMENTS:
            return
        seg = _PipeSegment()
        seg.textChanged.connect(self._on_text_changed)
        seg.removeRequested.connect(self._remove_segment)
        # 插入到 stretch 之前
        idx = self._segments_layout.count() - 1
        self._segments_layout.insertWidget(idx, seg)
        self._segments.append(seg)
        self._reindex()
        self._on_text_changed()
        seg.edit.setFocus()

    def _remove_segment(self, seg: _PipeSegment) -> None:
        if len(self._segments) <= 1:
            return
        try:
            self._segments.remove(seg)
        except ValueError:
            return
        seg.setParent(None)
        seg.deleteLater()
        self._reindex()
        self._on_text_changed()

    def _reindex(self) -> None:
        n = len(self._segments)
        for i, seg in enumerate(self._segments):
            seg.set_title(i, n)
            # 首段不可删（必须保留主命令）；其余段仅在总段数>1 时可删
            seg.set_removable(n > 1 and i > 0)
        self.add_seg_btn.setEnabled(n < MAX_PIPE_SEGMENTS)
        if n >= MAX_PIPE_SEGMENTS:
            self.add_seg_btn.setToolTip(f"已达硬上限 {MAX_PIPE_SEGMENTS} 段")
        else:
            self.add_seg_btn.setToolTip(f"添加新管道段（当前 {n}/{MAX_PIPE_SEGMENTS}）")

    # --- 状态 ---
    def _on_text_changed(self) -> None:
        current = [seg.text() for seg in self._segments]
        if current != self._last_validated_cmds:
            # 任一段改过 → 旧试运行结果失效
            self._run_ok = False

        for seg in self._segments:
            seg.update_hint()

        empty_count = sum(1 for c in current if not c)
        all_valid = bool(current) and all(
            validate_command(c)[0] for c in current if c
        )
        n = len(current)

        if not current or empty_count == n:
            self.summary.setText("—")
            self.run_btn.setEnabled(False)
        elif empty_count > 0:
            self.summary.setText(
                f"<span style='color: #c62828;'>⚠ 存在 {empty_count} 个空段，请填写或删除</span>"
            )
            self.run_btn.setEnabled(False)
        elif all_valid:
            msg = f"✓ {n}/{MAX_PIPE_SEGMENTS} 段全部合法"
            if n >= 2:
                msg += "；将以管道串联试运行"
            self.summary.setText(f"<span style='color: #2e7d32;'>{msg}</span>")
            self.run_btn.setEnabled(not self._procs)
        else:
            self.summary.setText(
                "<span style='color: #c62828;'>⚠ 存在非法段，请查看每段红色提示</span>"
            )
            self.run_btn.setEnabled(False)

        self.completeChanged.emit()

    def _reset_run_state(self) -> None:
        self._run_ok = False
        self._last_validated_cmds = []
        self.log.clear()
        self._on_text_changed()

    # --- 试运行 ---
    def _run(self) -> None:
        current = [seg.text() for seg in self._segments]
        if not current or any(not c for c in current):
            return
        token_groups: list[list[str]] = []
        for c in current:
            ok, _, toks = validate_command(c)
            if not ok or not toks:
                return
            token_groups.append(toks)

        preview = " | ".join(current)
        reply = QMessageBox.question(
            self,
            "确认试运行",
            "即将真实执行该整条管道。\n"
            "请确认命令当前参数不会产生破坏性副作用（删文件、覆盖数据等）。\n\n"
            f"$ {preview}\n\n继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.log.clear()
        self.log.appendPlainText(f"$ {preview}")
        self.run_btn.setEnabled(False)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")

        procs = [QProcess(self) for _ in token_groups]
        for p in procs:
            p.setProcessEnvironment(env)
        # 串联：procs[i].stdout → procs[i+1].stdin
        for i in range(len(procs) - 1):
            procs[i].setStandardOutputProcess(procs[i + 1])
        # 最后一段 stdout+stderr 合并并先帮到 log；中间段 stderr单独抽掉
        # （避免中间段 stderr 混进下段 stdin）
        for p in procs[:-1]:
            p.setProcessChannelMode(QProcess.SeparateChannels)
        procs[-1].setProcessChannelMode(QProcess.MergedChannels)
        procs[-1].readyReadStandardOutput.connect(self._on_stdout)
        procs[-1].finished.connect(self._on_finished)
        for p in procs:
            p.errorOccurred.connect(self._on_error)

        self._procs = procs
        # Qt 推荐后向前启动：后继段先就绪才能接前段的 stdout
        for i in range(len(procs) - 1, -1, -1):
            toks = token_groups[i]
            procs[i].start(toks[0], toks[1:])
        for p in procs:
            if not p.waitForStarted(3000):
                self.log.appendPlainText("⚠ 子进程启动失败")
                for q in procs:
                    q.kill()
                self._procs = []
                self.run_btn.setEnabled(True)
                return

        # 首段无上游 stdin，关闭写通道让其不等 stdin
        procs[0].closeWriteChannel()

        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.start(self._timeout_ms)

    def _on_stdout(self) -> None:
        if not self._procs:
            return
        last = self._procs[-1]
        data = bytes(last.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.log.appendPlainText(data.rstrip("\n"))

    def _on_error(self, err: QProcess.ProcessError) -> None:
        self.log.appendPlainText(f"⚠ QProcess 错误：{err}")

    def _on_timeout(self) -> None:
        if self._procs:
            self.log.appendPlainText(
                f"⚠ 超时（{self._timeout_ms // 1000}s），已终止整条管道"
            )
            for p in self._procs:
                p.kill()

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._on_stdout()
        if hasattr(self, "_timer") and self._timer is not None:
            self._timer.stop()
        # 等待所有段完成（中间段可能晚一点退出）
        codes: list[tuple[int, int, QProcess.ExitStatus]] = []
        for i, p in enumerate(self._procs):
            if p.state() != QProcess.NotRunning:
                p.waitForFinished(1000)
            codes.append((i + 1, p.exitCode(), p.exitStatus()))
        status_parts = [f"seg{i}=exit {c}" for i, c, _ in codes]
        self.log.appendPlainText("[" + ", ".join(status_parts) + "]")
        # pipefail 等价：任一段失败 → 整体失败
        all_ok = all(c == 0 and s == QProcess.NormalExit for _, c, s in codes)
        self._run_ok = all_ok
        if all_ok:
            self._last_validated_cmds = [seg.text() for seg in self._segments]
            self.log.appendPlainText("✓ 整条管道验证通过，可进入下一步")
        else:
            self.log.appendPlainText("✗ 管道中至少一段失败，请修正后重试")
        self._procs = []
        self.run_btn.setEnabled(True)
        self.completeChanged.emit()

    # --- QWizardPage ---
    def isComplete(self) -> bool:
        current = [seg.text() for seg in self._segments]
        if not current or any(not c for c in current):
            return False
        return self._run_ok and current == self._last_validated_cmds

    def commands(self) -> list[str]:
        """返回每段当前文本（保持顺序；不剪空段）。"""
        return [seg.text() for seg in self._segments]

    def token_groups(self) -> list[list[str]]:
        """返回每段的 tokens；非法段返回空列表。"""
        groups: list[list[str]] = []
        for seg in self._segments:
            _, _, toks = validate_command(seg.text())
            groups.append(toks)
        return groups

    def command(self) -> str:
        """向后兼容：返回首段文本。"""
        cmds = self.commands()
        return cmds[0] if cmds else ""

    def tokens(self) -> list[str]:
        """向后兼容：返回首段 tokens。"""
        groups = self.token_groups()
        return groups[0] if groups else []


# ---------------------------------------------------------------------------
# Page 2 — 参数选择（token 切片点选）
# ---------------------------------------------------------------------------

class ParameterSelectionPage(QWizardPage):
    """第 2 步：点选要参数化的 token。

    多段（v1.2.2）：每段一行 chip，arg 编号跨段全局递增。
    这一策略与 seal_wizard._scan_placeholders_many 对齐，保证运行时 argN 对应的位置无歧义。
    """

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

    def __init__(self, name_prefix: str = SEALED_NAME_PREFIX) -> None:
        super().__init__()
        #: 文件名前缀；供 program_name() 拼默认输出名。由偏好面板控制。
        self._name_prefix = name_prefix
        self.setTitle("选择运行时参数")
        self.setSubTitle(
            "点击命令中的 token 切换「字面量 / 运行时参数」。\n"
            "多段时 argN 编号跨段全局递增：第一个选中的 token 是 arg1，第二个是 arg2……"
        )

        # 垂直容器：每段一行 chip
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(120)
        self._container = QWidget()
        self._segments_layout = QVBoxLayout(self._container)
        self._segments_layout.setSpacing(8)
        self._segments_layout.setContentsMargins(6, 6, 6, 6)
        self._segments_layout.addStretch(1)
        self._scroll.setWidget(self._container)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        self.preview.setFont(mono)
        self.preview.setMaximumBlockCount(64)
        self.preview.setFixedHeight(120)
        self.preview.setStyleSheet(
            "QPlainTextEdit { background: #f5f5f5; color: #222; padding: 8px; "
            "border-radius: 4px; border: 1px solid #ddd; }"
        )

        self.hint = QLabel("—")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("QLabel { color: #888; background: transparent; }")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("命令分解（蓝色 = 运行时参数，白色 = 字面量）："))
        lay.addWidget(self._scroll, 1)
        lay.addWidget(QLabel("模板预览（每段一行）："))
        lay.addWidget(self.preview)
        lay.addWidget(self.hint)

        self._token_groups: list[list[str]] = []
        self._selected: list[set[int]] = []

    def initializePage(self) -> None:
        # 清空旧段行（保留尾部 stretch）
        while self._segments_layout.count() > 1:
            item = self._segments_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                # 可能是嵌套 layout
                lay = item.layout()
                if lay is not None:
                    self._clear_layout(lay)

        wiz = self.wizard()
        if not isinstance(wiz, TemplateWizard):
            return
        self._token_groups = wiz.command_page.token_groups()
        # 剩余的空段（当前不允许，但防范）：从 token_groups 滤除空列表
        self._token_groups = [g for g in self._token_groups if g]
        self._selected = [set() for _ in self._token_groups]

        stretch_idx = self._segments_layout.count() - 1
        total = len(self._token_groups)
        for seg_idx, tokens in enumerate(self._token_groups):
            row_widget = QWidget()
            row_lay = QVBoxLayout(row_widget)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(2)

            if total == 1:
                title_text = "段 1："
            else:
                tag = "第一段 / 主命令" if seg_idx == 0 else f"第 {seg_idx + 1} 段 / 读上段 stdout"
                title_text = f"段 {seg_idx + 1}（{tag}）："
            title = QLabel(title_text)
            title.setStyleSheet(
                "QLabel { color: #555; font-weight: bold; background: transparent; }"
            )

            chip_row = QHBoxLayout()
            chip_row.setSpacing(6)
            for tok_idx, tok in enumerate(tokens):
                chip = QPushButton(tok)
                chip.setCheckable(True)
                chip.setStyleSheet(self._STYLE_LITERAL)
                chip.setToolTip(f"段 {seg_idx + 1} token #{tok_idx}：点击切换为运行时参数")

                def _on_toggle(
                    checked: bool,
                    s: int = seg_idx,
                    i: int = tok_idx,
                    b: QPushButton = chip,
                ) -> None:
                    if checked:
                        self._selected[s].add(i)
                        b.setStyleSheet(self._STYLE_ARG)
                    else:
                        self._selected[s].discard(i)
                        b.setStyleSheet(self._STYLE_LITERAL)
                    self._update_preview()
                    self.completeChanged.emit()

                chip.toggled.connect(_on_toggle)
                chip_row.addWidget(chip)
            chip_row.addStretch(1)

            row_lay.addWidget(title)
            row_lay.addLayout(chip_row)
            self._segments_layout.insertWidget(stretch_idx, row_widget)
            stretch_idx += 1

        self._update_preview()

    @staticmethod
    def _clear_layout(lay) -> None:
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _update_preview(self) -> None:
        templates = build_template_many(self._token_groups, self._selected)
        lines = []
        for i, tmpl in enumerate(templates):
            prefix = f"段 {i + 1}: " if len(templates) > 1 else ""
            lines.append(f"{prefix}{tmpl}")
        self.preview.setPlainText("\n".join(lines) if lines else "—")

        total_selected = sum(len(s) for s in self._selected)
        if total_selected == 0:
            self.hint.setText(
                "<span style='color: #c62828;'>⚠ 至少在任意一段选择一个 token 作为运行时参数</span>"
            )
            return
        msg = f"已选 {total_selected} 个运行时参数 → 运行时按 arg1/arg2/… 顺序传入"
        # 首 token（段 1 的 index 0）被参数化：提示必须传可执行绝对路径
        if self._selected and 0 in self._selected[0]:
            msg += "；⚠ 首 token（程序路径）被参数化，运行时必须传入可执行的绝对路径"
        self.hint.setText(msg)

    def isComplete(self) -> bool:
        return any(len(s) > 0 for s in self._selected)

    def templates(self) -> list[str]:
        """返回每段的模板字符串列表。供 ExecutionPage 拼 SealRequest.commands。"""
        return build_template_many(self._token_groups, self._selected)

    def template(self) -> str:
        """向后兼容：返回首段模板。仅用于日志/预览。"""
        templates = self.templates()
        return templates[0] if templates else ""

    def program_name(self) -> str:
        """用于生成默认输出文件名：统一加 ``self._name_prefix`` 前缀以区分原命令。

        特例：
        - 命令本身已以前缀开头（如用户给封装产物再封装）→ 不重复加前缀
        - tokens 为空 → 退化到 “sealed”
        - 多段时以首段首 token 为准（首段是主命令，最代表整条管道的身份）
        """
        if not self._token_groups or not self._token_groups[0]:
            return "sealed"
        base = Path(self._token_groups[0][0]).name or "sealed"
        if self._name_prefix and base.startswith(self._name_prefix):
            return base
        return (self._name_prefix or "") + base


# ---------------------------------------------------------------------------
# Page 3 — 输出配置
# ---------------------------------------------------------------------------

class OutputConfigPage(QWizardPage):
    """第 3 步：输出路径。"""

    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        name_prefix: str = SEALED_NAME_PREFIX,
    ) -> None:
        super().__init__()
        #: 默认输出目录；由偏好面板控制（带 mkdir 延迟到实际使用时）
        self._output_dir = Path(output_dir).expanduser()
        #: 文件名前缀；仅用于提示文案。实际拼名在 ParameterSelectionPage.program_name() 完成
        self._name_prefix = name_prefix

        self.setTitle("保存位置")
        self.setSubTitle("选择封装后的二进制保存到哪里。")

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            str(self._output_dir / f"{self._name_prefix}program")
        )
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        out_row = QWidget()
        out_lay = QHBoxLayout(out_row)
        out_lay.setContentsMargins(0, 0, 0, 0)
        out_lay.addWidget(self.output_edit, 1)
        out_lay.addWidget(browse)

        self.path_hint = QLabel(
            f"默认文件名为 <code>{self._name_prefix}&lt;原命令名&gt;</code>，用以与原命令区分。\n"
            f"默认保存到 {self._output_dir}/（首次使用会自动创建）。\n"
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
        self.output_edit.setText(str(self._output_dir / name))

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出路径",
            self.output_edit.text() or str(self._output_dir))
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
        lines: list[str] = []
        if len(req.commands) == 1:
            lines.append(f"模板    : {req.commands[0]}")
        else:
            for i, seg in enumerate(req.commands):
                lines.append(f"模板段{i + 1}  : {seg}")
        lines += [
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
            commands=wiz.param_page.templates(),  # v1.2.2：多段模板列表
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

        # 从偏好面板读当前默认值，快照存入向导实例。
        # 读一次用到底：向导打开期间修改 Preferences 不会热生效（关闭重开生效），
        # 避免半路换默认目录导致第 3 页的提示文案/路径不一致。
        self.prefs = settings.load_template_prefs()

        self.command_page = CommandInputPage(
            timeout_ms=self.prefs.try_run_timeout_ms,
        )
        self.param_page = ParameterSelectionPage(
            name_prefix=self.prefs.name_prefix,
        )
        self.output_page = OutputConfigPage(
            output_dir=self.prefs.output_dir,
            name_prefix=self.prefs.name_prefix,
        )
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
