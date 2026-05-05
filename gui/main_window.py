"""主窗口：启动器。

当前两个入口：
  - 新建 seal：拉起 SealWizard
  - 管理 runner：打开 RunnerListWindow（含右键删除/修改模板）

早期版本的独立 “rotate” 按钮已移除：rotate 的自然入口是
管理窗里右键“修改模板…”（按用户决策）。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .preferences import PreferencesDialog
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

        self._build_menu()

        title = QLabel("cmdseal")
        title.setAlignment(Qt.AlignCenter)
        f = title.font()
        f.setPointSize(f.pointSize() + 8)
        f.setBold(True)
        title.setFont(f)

        subtitle = QLabel(
            self.tr(
                "Seal a command into an AEAD-encrypted binary;\n"
                "the key lives only in the keychain and is bound to this binary."
            )
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        self.btn_template = QPushButton(self.tr("Generate from Command…"))
        self.btn_template.setMinimumHeight(40)
        self.btn_template.clicked.connect(self._open_template_wizard)

        self.btn_seal = QPushButton(self.tr("Advanced Mode…"))
        self.btn_seal.setMinimumHeight(40)
        self.btn_seal.clicked.connect(self._open_seal_wizard)

        self.btn_manage = QPushButton(self.tr("Manage Runners…"))
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

    # ------------------------------------------------------------------
    # 菜单栏
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        """搭菜单栏。macOS 下 Qt 会自动识别 Preferences 的 role，
        把它搬到 “cmdseal → 偏好设置…” 标准位置（快捷键 ⌘,）。
        """
        mb = self.menuBar()
        app_menu = mb.addMenu("cmdseal")

        prefs_action = QAction(self.tr("Preferences…"), self)
        # 显式指定 PreferencesRole：确保被搬到 macOS 应用菜单的正确位置
        prefs_action.setMenuRole(QAction.PreferencesRole)
        prefs_action.setShortcut(QKeySequence.Preferences)
        prefs_action.triggered.connect(self._open_preferences)
        app_menu.addAction(prefs_action)

    def _open_preferences(self) -> None:
        dlg = PreferencesDialog(self)
        dlg.exec()
