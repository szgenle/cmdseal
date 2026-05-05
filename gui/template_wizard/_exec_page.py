"""Page 4 — 执行 cmdseal seal。"""
from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from PySide6.QtCore import QProcess, QProcessEnvironment, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)

from .. import backend

if TYPE_CHECKING:
    from ._wizard import TemplateWizard


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
        from ._wizard import TemplateWizard
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

    def _build_request(self, wiz: "TemplateWizard") -> backend.SealRequest:
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
            from ._wizard import TemplateWizard
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
