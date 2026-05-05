"""seal 向导窗（v1.2.1：CommandPage 支持多段管道）。

四步式 QWizard：
  1. CommandPage  — 填写命令模板，解析 {{secret:*}} / {{arg:*}}
                    支持多段：每段一个编辑框，[+ 添加管道段] 堆叠
                    至最多 MAX_PIPE_SEGMENTS=8 段；段间获得上一段 stdout。
  2. SecretsPage  — 根据上一步扫描出的 secret 名动态生成遮蔽输入
                    （多段间的 secret 合并去重）
  3. OptionsPage  — 输出路径 / label / 签名身份 / --no-sign
  4. ExecutePage  — 预览 argv（各段单独显示），点击按钮后用 QProcess
                    异步执行 cmdseal.py，实时把 stdout/stderr 追加到
                    日志视图

设计约束：
- GUI 不复制任何加密逻辑，一切交给 cmdseal.py（见 backend.py）
- 多段通过 --command 重复追加传给 CLI，GUI 层不用 shell 千预分段
- secret 通过 QProcess stdin 以 NAME=VALUE 行投递，内存里不落盘
- 预览里 secret 一律渲染为 ***，避免泄露到截图 / 日志
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from . import backend, settings

# 与 cmdseal.py 同款占位符语法；GUI 侧仅用于扫描 + 预览，不做语义判断。
PLACEHOLDER_RE = re.compile(r"\{\{(secret|arg):([A-Za-z0-9_]+)\}\}")

# 与 cmdseal.py::MAX_PIPE_SEGMENTS 保持一致。
MAX_PIPE_SEGMENTS = 8


def _scan_placeholders(command: str) -> tuple[list[str], list[str]]:
    """返回 (secret_names_sorted_unique, arg_indices_sorted_unique)。

    解析失败时按"空结果"处理，向导页自行判定 isComplete。
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ([], [])
    secrets: set[str] = set()
    args: set[str] = set()
    for tok in tokens:
        m = PLACEHOLDER_RE.fullmatch(tok)
        if not m:
            continue
        if m.group(1) == "secret":
            secrets.add(m.group(2))
        else:
            args.add(m.group(2))
    return (sorted(secrets), sorted(args, key=lambda s: int(s)))


def _scan_placeholders_many(
    commands: list[str],
) -> tuple[list[str], list[str]]:
    """多段联合扫描：secret 名去重，arg 索引跨段全局收集。

    语义与 cmdseal.py::do_seal 的跨段全局编号保持一致：比如首段
    用 {{arg:1}}、二段用 {{arg:2}}，运行时依次传 ``./bin a b`` 即可。
    """
    secrets: set[str] = set()
    args: set[str] = set()
    for seg in commands:
        s, a = _scan_placeholders(seg)
        secrets.update(s)
        args.update(a)
    return (sorted(secrets), sorted(args, key=lambda s: int(s)))


def _redact_command(command: str) -> str:
    """把 {{secret:*}} 渲染为 ***，用于安全预览。"""
    return PLACEHOLDER_RE.sub(
        lambda m: "***" if m.group(1) == "secret" else m.group(0),
        command,
    )


# ---------------------------------------------------------------------------
# Page 1 — command template (v1.2.1：多段管道)
# ---------------------------------------------------------------------------

class _SegmentEditor(QWidget):
    """单段命令编辑控件：标题行 + 编辑框 + 行内提示。

    只负责展示和文本解析反馈，“添加 / 删除”由 CommandPage 统一
    调度。信号 textChanged/removeRequested 向外曝露。
    """

    textChanged = Signal()
    removeRequested = Signal(object)  # object=self

    def __init__(self, index: int, can_remove: bool = False) -> None:
        super().__init__()
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)

        self._title = QLabel(self._title_text(index))
        self._title.setStyleSheet("color:#666;")

        self._remove_btn = QPushButton("×")
        self._remove_btn.setFixedWidth(28)
        self._remove_btn.setToolTip(self.tr("Remove this segment"))
        self._remove_btn.setVisible(can_remove)
        self._remove_btn.clicked.connect(
            lambda: self.removeRequested.emit(self))

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._title, 1)
        head.addWidget(self._remove_btn)

        self.edit = QPlainTextEdit()
        self.edit.setTabChangesFocus(True)
        self.edit.setFont(mono)
        self.edit.setFixedHeight(72)
        self.edit.textChanged.connect(self.textChanged)

        self.hint = QLabel("—")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#666;")
        self.hint.setTextInteractionFlags(Qt.TextSelectableByMouse)

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(8, 6, 8, 6)
        inner.addLayout(head)
        inner.addWidget(self.edit)
        inner.addWidget(self.hint)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

    @staticmethod
    def _title_text(index: int) -> str:
        from PySide6.QtCore import QCoreApplication
        if index > 0:
            return QCoreApplication.translate(
                "_SegmentEditor",
                "Segment {i} (receives stdout of previous segment)",
            ).format(i=index + 1)
        return QCoreApplication.translate(
            "_SegmentEditor",
            "Segment {i} (first segment — main command)",
        ).format(i=index + 1)

    def set_index(self, index: int, can_remove: bool) -> None:
        self._title.setText(self._title_text(index))
        self._remove_btn.setVisible(can_remove)
        if index == 0:
            self.edit.setPlaceholderText(self.tr(
                "e.g.: /usr/bin/zip -j -P {{secret:pw}} {{arg:1}}"))
        else:
            self.edit.setPlaceholderText(self.tr(
                "e.g.: /usr/bin/zip {{arg:2}} -    ('-' means read stdin)"))

    def text(self) -> str:
        return self.edit.toPlainText().strip()

    def set_hint(self, text: str, warn: bool = False) -> None:
        self.hint.setText(text)
        self.hint.setStyleSheet(
            "color:#b84700;" if warn else "color:#666;")


class CommandPage(QWizardPage):
    """第 1 步：命令模板（支持多段管道）。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle(self.tr("Command Template"))
        self.setSubTitle(self.tr(
            "Write the command(s) to seal (up to {max} pipe segments).\n"
            "• Literal passwords allowed; or use {{secret:NAME}} / {{arg:N}}\n"
            "• With multiple segments, each consumes stdout of the previous segment\n"
            "• {{arg:N}} numbers are globally unique and passed in order across all segments"
        ).format(max=MAX_PIPE_SEGMENTS))

        # 段容器——用 QScrollArea 容纳任意段数
        self._segments_host = QWidget()
        self._segments_layout = QVBoxLayout(self._segments_host)
        self._segments_layout.setContentsMargins(0, 0, 0, 0)
        self._segments_layout.setSpacing(8)
        self._segments_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(self._segments_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._add_btn = QPushButton(self.tr("➕  Add pipe segment"))
        self._add_btn.clicked.connect(lambda: self._add_segment())

        self.summary = QLabel("—")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(self.tr("Command segments (shell-style; first field should be absolute path):")))
        lay.addWidget(scroll, 1)
        lay.addWidget(self._add_btn)
        lay.addWidget(QLabel(self.tr("Global parse result:")))
        lay.addWidget(self.summary)

        self._segments: list[_SegmentEditor] = []
        self._add_segment()  # 首段初始存在

    # --- 段增/删管理 ---
    def _add_segment(self) -> None:
        if len(self._segments) >= MAX_PIPE_SEGMENTS:
            return
        seg = _SegmentEditor(index=len(self._segments), can_remove=False)
        seg.textChanged.connect(self._refresh)
        seg.removeRequested.connect(self._remove_segment)
        # 插入到尾部 stretch 前
        self._segments_layout.insertWidget(
            self._segments_layout.count() - 1, seg)
        self._segments.append(seg)
        self._reindex()
        self._refresh()

    def _remove_segment(self, seg: _SegmentEditor) -> None:
        if len(self._segments) <= 1:
            return  # 首段不允许删
        self._segments.remove(seg)
        self._segments_layout.removeWidget(seg)
        seg.deleteLater()
        self._reindex()
        self._refresh()

    def _reindex(self) -> None:
        can_remove = len(self._segments) > 1
        for i, seg in enumerate(self._segments):
            seg.set_index(i, can_remove=can_remove)
        self._add_btn.setEnabled(len(self._segments) < MAX_PIPE_SEGMENTS)

    # --- 解析与预览 ---
    def _refresh(self) -> None:
        total_tokens = 0
        has_error = False
        for i, seg in enumerate(self._segments):
            cmd = seg.text()
            if not cmd:
                seg.set_hint("—")
                continue
            try:
                tokens = shlex.split(cmd)
            except ValueError as e:
                seg.set_hint(self.tr("⚠ Failed to parse shell quoting: {err}").format(err=e), warn=True)
                has_error = True
                continue
            total_tokens += len(tokens)

            first_token = tokens[0] if tokens else ""
            path_warning = ""
            if first_token and not first_token.startswith('/'):
                if first_token.startswith('{{'):
                    path_warning = self.tr("; ⚠ First token is a placeholder; make sure to pass an absolute path at runtime")
                else:
                    path_warning = self.tr(
                        "; ℹ First token '{tok}' will be resolved to absolute path at seal time"
                    ).format(tok=first_token)

            secs, args = _scan_placeholders(cmd)
            parts = [f"tokens={len(tokens)}"]
            parts.append(self.tr("secrets={v}").format(v=', '.join(secs) or self.tr('(none)')))
            parts.append(self.tr("args={v}").format(v=', '.join(args) or self.tr('(none)')))

            bare_secret = re.search(r'(?<!\{)secret:[A-Za-z0-9_]+(?!\})', cmd)
            bare_arg = re.search(r'(?<!\{)arg:[0-9]+(?!\})', cmd)
            if bare_secret or bare_arg:
                parts.insert(
                    0,
                    self.tr("⚠ Unwrapped secret:/arg: detected; use {{secret:NAME}} or {{arg:N}}"),
                )
                has_error = True
            seg.set_hint(
                "  ·  ".join(parts) + path_warning,
                warn=bool(path_warning and '⚠' in path_warning),
            )

        # 全局总览：跨段合并 secret / arg
        cmds = self.commands()
        if not cmds:
            self.summary.setText("—")
        else:
            all_secrets, all_args = _scan_placeholders_many(cmds)
            summary_parts = [f"segments={len(cmds)}/{MAX_PIPE_SEGMENTS}"]
            summary_parts.append(f"total_tokens={total_tokens}")
            summary_parts.append(
                self.tr("secrets={v}").format(v=', '.join(all_secrets) or self.tr('(none)')))
            summary_parts.append(
                self.tr("args={v}").format(v=', '.join(all_args) or self.tr('(none)')))
            self.summary.setText("  ·  ".join(summary_parts))
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        cmds = self.commands()
        if not cmds:
            return False
        if len(cmds) > MAX_PIPE_SEGMENTS:
            return False
        for cmd in cmds:
            try:
                toks = shlex.split(cmd)
            except ValueError:
                return False
            if not toks:
                return False
        return True

    def commands(self) -> list[str]:
        """返回非空段列表；空段自动剔除。"""
        return [seg.text() for seg in self._segments if seg.text()]

    def command(self) -> str:
        """向后兼容：返回首段（仅日志/预览调试使用）。"""
        cmds = self.commands()
        return cmds[0] if cmds else ""


# ---------------------------------------------------------------------------
# Page 2 — secrets
# ---------------------------------------------------------------------------

class SecretsPage(QWizardPage):
    """第 2 步：按需采集 secret。没有 secret 时作为"告知页"直接放行。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle(self.tr("Secret Collection"))
        self.setSubTitle(self.tr(
            "Collected once at seal time and stored in AEAD ciphertext; never prompted again at runtime."
        ))

        self._host = QWidget(self)
        self._form = QFormLayout(self._host)
        self._form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._inputs: dict[str, QLineEdit] = {}
        self._empty_hint = QLabel(self.tr("This command uses no {{secret:*}}; simply proceed."))
        self._empty_hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addWidget(self._empty_hint)
        lay.addWidget(self._host, 1)
        lay.addStretch(1)

    def initializePage(self) -> None:
        # 清空旧控件（再次进入该页时，命令可能已改）
        while self._form.rowCount():
            self._form.removeRow(0)
        self._inputs.clear()

        wiz = self.wizard()
        cmds = (wiz.command_page.commands()
                if isinstance(wiz, SealWizard) else [])
        names, _ = _scan_placeholders_many(cmds)
        self._empty_hint.setVisible(not names)

        for name in names:
            row = QWidget()
            rlay = QHBoxLayout(row)
            rlay.setContentsMargins(0, 0, 0, 0)

            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.Password)
            edit.setPlaceholderText(self.tr("value: {name}").format(name=name))
            edit.textChanged.connect(self.completeChanged)

            toggle = QPushButton(self.tr("Show"))
            toggle.setCheckable(True)
            toggle.setFixedWidth(56)

            def _on_toggle(checked: bool, e: QLineEdit = edit,
                           b: QPushButton = toggle) -> None:
                e.setEchoMode(QLineEdit.Normal if checked
                              else QLineEdit.Password)
                b.setText(self.tr("Hide") if checked else self.tr("Show"))

            toggle.toggled.connect(_on_toggle)

            rlay.addWidget(edit, 1)
            rlay.addWidget(toggle)
            self._form.addRow(QLabel(name), row)
            self._inputs[name] = edit

    def nextId(self) -> int:
        # 如果没有 secret，直接跳到 OptionsPage（跳过本页）
        wiz = self.wizard()
        cmds = (wiz.command_page.commands()
                if isinstance(wiz, SealWizard) else [])
        names, _ = _scan_placeholders_many(cmds)
        if not names:
            # OptionsPage 是第 3 页（索引 2）
            return 2
        return super().nextId()

    def isComplete(self) -> bool:
        # 任一 secret 不能为空
        return all(e.text() != "" for e in self._inputs.values())

    def collected_secrets(self) -> dict[str, str]:
        return {k: e.text() for k, e in self._inputs.items()}


# ---------------------------------------------------------------------------
# Page 3 — options
# ---------------------------------------------------------------------------

class OptionsPage(QWizardPage):
    """第 3 步：输出路径 / label / 签名身份。

    v1.2.3 起与 TemplateWizard.OutputConfigPage 行为对齐：
    - 从偏好面板读取 output_dir / name_prefix
    - initializePage() 依据首段首 token 自动回填默认路径
    - 新增 path_hint 说明默认目录
    这样两条向导路径的最后一步只在「签名身份 / --no-sign」上存在
    差异，其余字段的默认值完全一致。
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        name_prefix: str = "seal_",
    ) -> None:
        super().__init__()
        self.setTitle(self.tr("Output & Signing"))
        self.setSubTitle(self.tr("Choose the output path and signing method. ad-hoc means codesign -s -."))

        self._output_dir = (
            Path(output_dir).expanduser() if output_dir
            else Path.home() / "cmdseal" / "bin"
        )
        self._name_prefix = name_prefix or "seal_"

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            str(self._output_dir / f"{self._name_prefix}program")
        )
        browse = QPushButton(self.tr("Browse…"))
        browse.clicked.connect(self._browse)
        out_row = QWidget()
        out_lay = QHBoxLayout(out_row)
        out_lay.setContentsMargins(0, 0, 0, 0)
        out_lay.addWidget(self.output_edit, 1)
        out_lay.addWidget(browse)

        self.path_hint = QLabel(self.tr(
            "Default file name is <code>{prefix}&lt;orig-command-name&gt;</code>, "
            "default save location: {dir}/ (created automatically on first use)."
        ).format(prefix=self._name_prefix, dir=self._output_dir))
        self.path_hint.setWordWrap(True)
        self.path_hint.setStyleSheet("color: #666; font-size: 11px;")

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(self.tr("Auto-generated from output file name if empty"))

        self.signing_combo = QComboBox()
        self.signing_combo.setEditable(True)
        self.signing_combo.addItem(self.tr("- (ad-hoc, dev only)"))
        self.signing_combo.addItem("Developer ID Application: YOUR NAME (TEAMID)")
        self.signing_combo.setCurrentIndex(0)

        self.no_sign_box = QCheckBox(self.tr("Skip codesign (debug only; loses Plan D protection)"))

        self.user_edit = QLineEdit(os.environ.get("USER", ""))

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow(self.tr("Output binary:"), out_row)
        form.addRow("", self.path_hint)
        form.addRow(self.tr("Label (optional):"), self.label_edit)
        form.addRow(self.tr("Keychain account:"), self.user_edit)
        form.addRow(self.tr("Signing identity:"), self.signing_combo)
        form.addRow("", self.no_sign_box)

        # 让 isComplete 随输出/用户变化
        self.output_edit.textChanged.connect(self.completeChanged)
        self.user_edit.textChanged.connect(self.completeChanged)

    def initializePage(self) -> None:
        """首次进入本页时按首段首 token 推断默认路径。

        若用户已手动填过，保留现值；与 OutputConfigPage.initializePage 同策略。
        """
        if self.output_edit.text().strip():
            return
        wiz = self.wizard()
        if not isinstance(wiz, SealWizard):
            return
        name = self._infer_program_name(wiz.command_page.commands())
        self.output_edit.setText(str(self._output_dir / name))

    def _infer_program_name(self, cmds: list[str]) -> str:
        """参考 ParameterSelectionPage.program_name，额外处理占位符首 token。

        SealWizard 首段允许直接写 ``{{arg:1}}`` 或 ``$VAR``，无法映射到一个
        具体的可执行名；这种情况下退化到 ``<prefix>sealed``。
        """
        if not cmds:
            return f"{self._name_prefix}sealed"
        try:
            toks = shlex.split(cmds[0])
        except ValueError:
            return f"{self._name_prefix}sealed"
        if not toks:
            return f"{self._name_prefix}sealed"
        first = toks[0]
        if first.startswith("{{") or first.startswith("$"):
            return f"{self._name_prefix}sealed"
        base = Path(first).name or "sealed"
        if self._name_prefix and base.startswith(self._name_prefix):
            return base
        return f"{self._name_prefix}{base}"

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Choose output path"),
            self.output_edit.text() or str(self._output_dir))
        if path:
            self.output_edit.setText(path)

    def isComplete(self) -> bool:
        return bool(self.output_edit.text().strip()
                    and self.user_edit.text().strip())

    def signing_identity(self) -> str:
        text = self.signing_combo.currentText().strip()
        # 下拉首项的展示文本带注释，取第一个 token 即 "-"
        if text.startswith("-"):
            return "-"
        return text


# ---------------------------------------------------------------------------
# Page 4 — execute
# ---------------------------------------------------------------------------

class ExecutePage(QWizardPage):
    """第 4 步：预览 + 运行。"""

    finished_ok = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setTitle(self.tr("Execute Seal"))
        self.setSubTitle(self.tr("After clicking “Run”, cmdseal.py will build the binary in a subprocess."))
        self.setCommitPage(True)  # 禁止回退修改已提交的 secret

        self._proc: QProcess | None = None
        self._ok = False

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumBlockCount(4000)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        self.preview.setFont(mono)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(mono)
        self.log.setMaximumBlockCount(20000)

        self.run_btn = QPushButton(self.tr("Run seal"))
        self.run_btn.clicked.connect(self._run)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(self.tr("Preview (secrets redacted):")))
        lay.addWidget(self.preview, 0)
        lay.addWidget(self.run_btn)
        lay.addWidget(QLabel(self.tr("Log:")))
        lay.addWidget(self.log, 1)

    # --- QWizardPage hooks ---
    def initializePage(self) -> None:
        req = self._build_request()
        lines = [
            f"argv    : {' '.join(shlex.quote(x) for x in backend.build_argv(req))}",
            f"cwd     : {backend.PROJECT_ROOT}",
        ]
        for i, seg in enumerate(req.commands):
            lines.append(f"seg {i + 1:>2} : {_redact_command(seg)}")
        lines.extend([
            f"output  : {req.output}",
            f"user    : {req.user}",
            self.tr("label   : {l}").format(l=req.label or self.tr('(auto)')),
            f"sign    : {'--no-sign' if req.no_sign else req.signing_identity}",
        ])
        self.preview.setPlainText("\n".join(lines))
        self.log.clear()
        self.run_btn.setEnabled(True)
        self._ok = False

    def isComplete(self) -> bool:
        # 只有 seal 成功才允许 Finish
        return self._ok

    # --- internals ---
    def _build_request(self) -> backend.SealRequest:
        wiz = self.wizard()
        assert isinstance(wiz, SealWizard)
        opts: OptionsPage = wiz.options_page
        secrets = wiz.secrets_page.collected_secrets()
        return backend.SealRequest(
            commands=wiz.command_page.commands(),
            output=Path(opts.output_edit.text()).expanduser(),
            secrets=secrets,
            signing_identity=opts.signing_identity(),
            no_sign=opts.no_sign_box.isChecked(),
            user=opts.user_edit.text().strip() or None,
            label=opts.label_edit.text().strip(),
            rotate=False,
        )

    def _run(self) -> None:
        # 第一条用最朴素的 API 写一行探针，以防 _append_log
        # 自身有 bug 导致界面上“什么都没有”。
        self.log.appendPlainText("[debug] run_btn clicked, entering _run")
        if self._proc is not None:
            self.log.appendPlainText("[debug] previous proc still running, ignored")
            return
        self.run_btn.setEnabled(False)
        try:
            req = self._build_request()
            argv = backend.build_argv(req)
            self._append_log(
                f"$ {' '.join(shlex.quote(x) for x in argv)}\n")

            proc = QProcess(self)
            # PYTHONUNBUFFERED=1：让 cmdseal.py 里的 print 实时穿过管道，
            # 否则 stdout 是 pipe 时会被块缓冲，整段等到进程结束才吐出。
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
                self._append_log(self.tr("⚠ Child process failed to start\n"))
                self._proc = None
                self.run_btn.setEnabled(True)
                return
            # 投递 secret（NAME=VALUE 行）并关闭写端，触发 cmdseal.py 解析
            payload = backend.serialize_secrets(req.secrets).encode("utf-8")
            if payload:
                proc.write(payload)
            proc.closeWriteChannel()
        except Exception as e:  # 任何异常都要落到日志，不可静默
            import traceback
            self._append_log(self.tr("⚠ _run exception: {e}\n{tb}\n").format(e=e, tb=traceback.format_exc()))
            self._proc = None
            self.run_btn.setEnabled(True)

    def _on_stdout(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(
            "utf-8", "replace")
        if data:
            self._append_log(data)

    def _on_error(self, err: QProcess.ProcessError) -> None:
        self._append_log(f"⚠ QProcess error: {err}\n")

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        # 收尾残余输出
        self._on_stdout()
        self._append_log(f"\n[exit {code}, status={status.name}]\n")
        self._ok = (code == 0 and status == QProcess.NormalExit)
        self.run_btn.setEnabled(not self._ok)  # 失败可重试
        self._proc = None
        self.completeChanged.emit()
        self.finished_ok.emit(self._ok)

    def _append_log(self, text: str) -> None:
        # appendPlainText 会自动在尾部加换行，所以先把末尾的
        # 换行剥掉；空串直接忽略。避免以前用 textCursor().End
        # 实例访问枚举时的兼容性坍塌。
        if not text:
            return
        self.log.appendPlainText(text.rstrip("\n"))


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

class SealWizard(QWizard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("cmdseal — New Seal"))
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.IndependentPages, False)
        self.resize(820, 620)

        # 与 TemplateWizard 对称：打开时读一次偏好快照。向导期间改
        # Preferences 不会热生效（关闭重开生效），避免半路换默认目录
        # 导致 OptionsPage 的路径预览/提示文案不一致。
        self.prefs = settings.load_template_prefs()

        self.command_page = CommandPage()
        self.secrets_page = SecretsPage()
        self.options_page = OptionsPage(
            output_dir=self.prefs.output_dir,
            name_prefix=self.prefs.name_prefix,
        )
        self.execute_page = ExecutePage()

        self.addPage(self.command_page)
        self.addPage(self.secrets_page)
        self.addPage(self.options_page)
        self.addPage(self.execute_page)

        self.setButtonText(QWizard.FinishButton, self.tr("Finish"))
        self.setButtonText(QWizard.CancelButton, self.tr("Cancel"))
        self.setButtonText(QWizard.NextButton, self.tr("Next >"))
        self.setButtonText(QWizard.BackButton, self.tr("< Back"))
        self.setButtonText(QWizard.CommitButton, self.tr("Confirm and Run"))
