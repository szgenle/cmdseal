"""TemplateWizard —— 串起四页。"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QWizard

from .. import settings
from ._command_page import CommandInputPage
from ._exec_page import ExecutionPage
from ._output_page import OutputConfigPage
from ._param_page import ParameterSelectionPage


class TemplateWizard(QWizard):
    """从已验证命令生成封装模板。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("cmdseal — Generate from Command"))
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.IndependentPages, False)
        self.resize(840, 840)

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

        self.setButtonText(QWizard.FinishButton, self.tr("Finish"))
        self.setButtonText(QWizard.CancelButton, self.tr("Cancel"))
        self.setButtonText(QWizard.NextButton, self.tr("Next >"))
        self.setButtonText(QWizard.BackButton, self.tr("< Back"))
        self.setButtonText(QWizard.CommitButton, self.tr("Run"))
