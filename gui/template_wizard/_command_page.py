"""Page 1 — 命令输入 + 整条管道真实运行验证（v1.2.2）。

单段时退化为 v1.1/1.2.1 的单进程试运行；多段时用 QProcess.setStandardOutputProcess
把每段 stdout 接入下一段 stdin，与 runner 自建管道的语义等价，不经 shell。
"""
from __future__ import annotations

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from ._core import (
    EXAMPLE_COMMAND,
    MAX_PIPE_SEGMENTS,
    PATH_PREFIX_MARKERS,
    TRY_RUN_TIMEOUT_MS,
    complete_path,
    validate_command,
)


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
    """第 1 步：输入 1~N 段管道命令，整条串跑一次成功才允许下一步。"""

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
