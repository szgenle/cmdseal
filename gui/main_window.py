"""主窗口：启动器。

当前两个入口：
  - 新建 seal：拉起 SealWizard
  - 管理 runner：打开 RunnerListWindow（含右键删除/修改模板）

早期版本的独立 “rotate” 按钮已移除：rotate 的自然入口是
管理窗里右键“修改模板…”（按用户决策）。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .runner_list import RunnerListWindow
from .seal_wizard import SealWizard
from .template_wizard import TemplateWizard


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("cmdseal")
        self.resize(520, 320)

        self._wizard: SealWizard | None = None
        self._template_wizard: TemplateWizard | None = None
        self._runner_list: RunnerListWindow | None = None

        title = QLabel("cmdseal")
        title.setAlignment(Qt.AlignCenter)
        f = title.font()
        f.setPointSize(f.pointSize() + 8)
        f.setBold(True)
        title.setFont(f)

        subtitle = QLabel(
            "把一条命令密封进 AEAD 加密的二进制；\n"
            "密钥只存在于 keychain，且仅允许该二进制读取。"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        self.btn_template = QPushButton("从命令生成模板...")
        self.btn_template.setMinimumHeight(40)
        self.btn_template.clicked.connect(self._open_template_wizard)

        self.btn_seal = QPushButton("高级模式...")
        self.btn_seal.setMinimumHeight(40)
        self.btn_seal.clicked.connect(self._open_seal_wizard)

        self.btn_manage = QPushButton("管理 runner...")
        self.btn_manage.setMinimumHeight(40)
        self.btn_manage.clicked.connect(self._open_runner_list)

        btn_row1 = QHBoxLayout()
        btn_row1.addStretch(1)
        btn_row1.addWidget(self.btn_template)
        btn_row1.addWidget(self.btn_seal)
        btn_row1.addStretch(1)

        btn_row2 = QHBoxLayout()
        btn_row2.addStretch(1)
        btn_row2.addWidget(self.btn_manage)
        btn_row2.addStretch(1)

        central = QWidget(self)
        lay = QVBoxLayout(central)
        lay.addStretch(1)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addSpacing(24)
        lay.addLayout(btn_row1)
        lay.addSpacing(12)
        lay.addLayout(btn_row2)
        lay.addStretch(2)
        self.setCentralWidget(central)

    def _open_template_wizard(self) -> None:
        # 保持引用，避免被 GC；关闭时释放
        self._template_wizard = TemplateWizard(self)
        self._template_wizard.finished.connect(self._on_template_wizard_finished)
        self._template_wizard.show()

    def _on_template_wizard_finished(self, _result: int) -> None:
        # 模板生成成功后如果 runner 管理窗开着，顺手刷一下
        if self._runner_list is not None and self._runner_list.isVisible():
            self._runner_list.refresh()
        self._template_wizard = None

    def _open_seal_wizard(self) -> None:
        # 保持引用，避免被 GC；关闭时释放
        self._wizard = SealWizard(self)
        self._wizard.finished.connect(self._on_wizard_finished)
        self._wizard.show()

    def _on_wizard_finished(self, _result: int) -> None:
        # seal 成功后如果 runner 管理窗开着，顺手刷一下
        # （即使向导取消也无所谓，刷新本身零弹窗）
        if self._runner_list is not None and self._runner_list.isVisible():
            self._runner_list.refresh()
        self._wizard = None

    def _open_runner_list(self) -> None:
        # 已打开则唤到前面，不重复开
        if self._runner_list is not None and self._runner_list.isVisible():
            self._runner_list.raise_()
            self._runner_list.activateWindow()
            self._runner_list.refresh()
            return
        self._runner_list = RunnerListWindow(self)
        self._runner_list.destroyed.connect(self._on_runner_list_destroyed)
        self._runner_list.show()

    def _on_runner_list_destroyed(self, *_args) -> None:
        self._runner_list = None
