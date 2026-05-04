"""seal 向导窗（第一版原型）。

四步式 QWizard：
  1. CommandPage  — 填写命令模板，解析 {{secret:*}} / {{arg:*}}
  2. SecretsPage  — 根据上一步扫描出的 secret 名动态生成遮蔽输入
  3. OptionsPage  — 输出路径 / label / 签名身份 / --no-sign
  4. ExecutePage  — 预览 argv，点击按钮后用 QProcess 异步执行
                    cmdseal.py，实时把 stdout/stderr 追加到日志视图

设计约束：
- GUI 不复制任何加密逻辑，一切交给 cmdseal.py（见 backend.py）
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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from . import backend

# 与 cmdseal.py 同款占位符语法；GUI 侧仅用于扫描 + 预览，不做语义判断。
PLACEHOLDER_RE = re.compile(r"\{\{(secret|arg):([A-Za-z0-9_]+)\}\}")


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


def _redact_command(command: str) -> str:
    """把 {{secret:*}} 渲染为 ***，用于安全预览。"""
    return PLACEHOLDER_RE.sub(
        lambda m: "***" if m.group(1) == "secret" else m.group(0),
        command,
    )


# ---------------------------------------------------------------------------
# Page 1 — command template
# ---------------------------------------------------------------------------

class CommandPage(QWizardPage):
    """第 1 步：命令模板。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("命令模板")
        self.setSubTitle(
            "填写要密封的命令。\n"
            "• 可直接写字面量密码（如：zip -j -P mypassword）\n"
            "• 或使用 {{secret:NAME}}（生成时采集，不暴露给 shell history）\n"
            "• 使用 {{arg:N}} 表示运行时参数"
        )

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(
            "例如：zip -j -P mypassword {{arg:1}} {{arg:2}}\n"
            "或：zhmm-cli --pwd {{secret:master}} -s {{arg:1}}"
        )
        self.edit.setTabChangesFocus(True)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        self.edit.setFont(mono)

        self.hint = QLabel("—")
        self.hint.setWordWrap(True)
        self.hint.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("命令（shell 风格，首字段建议绝对路径）："))
        lay.addWidget(self.edit, 1)
        lay.addWidget(QLabel("解析结果："))
        lay.addWidget(self.hint)

        self.edit.textChanged.connect(self._refresh)
        # 注意：QPlainTextEdit 没有 plainText 这个 Q_PROPERTY，无法直接
        # 走 QWizard.registerField 机制；改由 ExecutePage 在需要时显式
        # 调用 self.command() 读取。

    def _refresh(self) -> None:
        cmd = self.edit.toPlainText().strip()
        if not cmd:
            self.hint.setText("—")
        else:
            try:
                tokens = shlex.split(cmd)
            except ValueError as e:
                self.hint.setText(f"⚠ 无法解析 shell 引用：{e}")
                self.completeChanged.emit()
                return
            
            # 检测首 token 是否为占位符或裸程序名
            first_token = tokens[0] if tokens else ""
            path_warning = ""
            if first_token and not first_token.startswith('/'):
                if first_token.startswith('{{'):
                    path_warning = "\n⚠ 首 token 是占位符，请确保运行时传入绝对路径"
                else:
                    path_warning = f"\nℹ 首 token '{first_token}' 将在封存时解析为绝对路径"
            
            secrets, args = _scan_placeholders(cmd)
            parts = [f"tokens={len(tokens)}"]
            parts.append(f"secrets={', '.join(secrets) or '(none)'}")
            parts.append(f"args={', '.join(args) or '(none)'}")
            
            # 检测裸写 secret:/arg: 但未包 {{}} 的情况
            bare_secret = re.search(r'(?<!\{)secret:[A-Za-z0-9_]+(?!\})', cmd)
            bare_arg = re.search(r'(?<!\{)arg:[0-9]+(?!\})', cmd)
            if bare_secret or bare_arg:
                parts.insert(0, "⚠ 检测到未包裹的 secret:/arg:，请用 {{secret:NAME}} 或 {{arg:N}}")
            
            self.hint.setText("  ·  ".join(parts) + path_warning)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        cmd = self.edit.toPlainText().strip()
        if not cmd:
            return False
        try:
            toks = shlex.split(cmd)
        except ValueError:
            return False
        return bool(toks)

    def command(self) -> str:
        return self.edit.toPlainText().strip()


# ---------------------------------------------------------------------------
# Page 2 — secrets
# ---------------------------------------------------------------------------

class SecretsPage(QWizardPage):
    """第 2 步：按需采集 secret。没有 secret 时作为"告知页"直接放行。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Secret 采集")
        self.setSubTitle(
            "生成时一次性采集，封入 AEAD 密文；运行时不会再问。"
        )

        self._host = QWidget(self)
        self._form = QFormLayout(self._host)
        self._form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._inputs: dict[str, QLineEdit] = {}
        self._empty_hint = QLabel("本次命令未使用 {{secret:*}}，直接下一步即可。")
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
        cmd = wiz.command_page.command() if isinstance(wiz, SealWizard) else ""
        names, _ = _scan_placeholders(cmd)
        self._empty_hint.setVisible(not names)

        for name in names:
            row = QWidget()
            rlay = QHBoxLayout(row)
            rlay.setContentsMargins(0, 0, 0, 0)

            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.Password)
            edit.setPlaceholderText(f"值：{name}")
            edit.textChanged.connect(self.completeChanged)

            toggle = QPushButton("显示")
            toggle.setCheckable(True)
            toggle.setFixedWidth(56)

            def _on_toggle(checked: bool, e: QLineEdit = edit,
                           b: QPushButton = toggle) -> None:
                e.setEchoMode(QLineEdit.Normal if checked
                              else QLineEdit.Password)
                b.setText("隐藏" if checked else "显示")

            toggle.toggled.connect(_on_toggle)

            rlay.addWidget(edit, 1)
            rlay.addWidget(toggle)
            self._form.addRow(QLabel(name), row)
            self._inputs[name] = edit

    def nextId(self) -> int:
        # 如果没有 secret，直接跳到 OptionsPage（跳过本页）
        wiz = self.wizard()
        cmd = wiz.command_page.command() if isinstance(wiz, SealWizard) else ""
        names, _ = _scan_placeholders(cmd)
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
    """第 3 步：输出路径 / label / 签名身份。"""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("输出与签名")
        self.setSubTitle("选择生成路径与签名方式。ad-hoc 即 codesign -s -。")

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("/absolute/path/to/sealed_binary")
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        out_row = QWidget()
        out_lay = QHBoxLayout(out_row)
        out_lay.setContentsMargins(0, 0, 0, 0)
        out_lay.addWidget(self.output_edit, 1)
        out_lay.addWidget(browse)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("留空则按输出文件名自动生成")

        self.signing_combo = QComboBox()
        self.signing_combo.setEditable(True)
        self.signing_combo.addItem("- (ad-hoc, dev only)")
        self.signing_combo.addItem("Developer ID Application: YOUR NAME (TEAMID)")
        self.signing_combo.setCurrentIndex(0)

        self.no_sign_box = QCheckBox("跳过 codesign（仅调试用，会失去 Plan D 保护）")

        self.user_edit = QLineEdit(os.environ.get("USER", ""))

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("输出二进制：", out_row)
        form.addRow("Label（可选）：", self.label_edit)
        form.addRow("Keychain 账号：", self.user_edit)
        form.addRow("签名身份：", self.signing_combo)
        form.addRow("", self.no_sign_box)

        # 让 isComplete 随输出/用户变化
        self.output_edit.textChanged.connect(self.completeChanged)
        self.user_edit.textChanged.connect(self.completeChanged)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出路径", self.output_edit.text() or str(Path.home()))
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
        self.setTitle("执行密封")
        self.setSubTitle("点击『运行』后，cmdseal.py 将在子进程中构建二进制。")
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

        self.run_btn = QPushButton("运行 seal")
        self.run_btn.clicked.connect(self._run)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("预览（secret 已脱敏）："))
        lay.addWidget(self.preview, 0)
        lay.addWidget(self.run_btn)
        lay.addWidget(QLabel("日志："))
        lay.addWidget(self.log, 1)

    # --- QWizardPage hooks ---
    def initializePage(self) -> None:
        req = self._build_request()
        lines = [
            f"argv    : {' '.join(shlex.quote(x) for x in backend.build_argv(req))}",
            f"cwd     : {backend.PROJECT_ROOT}",
            f"command : {_redact_command(req.command)}",
            f"output  : {req.output}",
            f"user    : {req.user}",
            f"label   : {req.label or '(auto)'}",
            f"sign    : {'--no-sign' if req.no_sign else req.signing_identity}",
        ]
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
            command=wiz.command_page.command(),
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
                self._append_log("⚠ 子进程启动失败\n")
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
            self._append_log(f"⚠ _run 异常：{e}\n{traceback.format_exc()}\n")
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
        self.setWindowTitle("cmdseal — 新建 seal")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.IndependentPages, False)
        self.resize(820, 620)

        self.command_page = CommandPage()
        self.secrets_page = SecretsPage()
        self.options_page = OptionsPage()
        self.execute_page = ExecutePage()

        self.addPage(self.command_page)
        self.addPage(self.secrets_page)
        self.addPage(self.options_page)
        self.addPage(self.execute_page)

        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")
        self.setButtonText(QWizard.NextButton, "下一步 >")
        self.setButtonText(QWizard.BackButton, "< 上一步")
        self.setButtonText(QWizard.CommitButton, "确认进入执行")
