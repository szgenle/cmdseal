"""Page 3 — 输出配置。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
    QWizardPage,
)

from ._core import DEFAULT_OUTPUT_DIR, SEALED_NAME_PREFIX

if TYPE_CHECKING:
    from ._wizard import TemplateWizard


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

        self.setTitle(self.tr("Save Location"))
        self.setSubTitle(self.tr("Choose where to save the sealed binary."))

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
            "Default file name is <code>{prefix}&lt;orig-command-name&gt;</code>, to distinguish from the original command.\n"
            "Default save location: {dir}/ (created automatically on first use).\n"
            "For global access, manually choose a directory on PATH like /usr/local/bin/, "
            "or create a symlink yourself."
        ).format(prefix=self._name_prefix, dir=self._output_dir))
        self.path_hint.setWordWrap(True)
        self.path_hint.setStyleSheet("color: #666; font-size: 11px;")

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(self.tr("Auto-generated from output file name if empty"))

        self.user_edit = QLineEdit(os.environ.get("USER", ""))

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow(self.tr("Output path:"), out_row)
        form.addRow("", self.path_hint)
        form.addRow(self.tr("Label (optional):"), self.label_edit)
        form.addRow(self.tr("Keychain account:"), self.user_edit)

        self.output_edit.textChanged.connect(self.completeChanged)
        self.user_edit.textChanged.connect(self.completeChanged)

    def initializePage(self) -> None:
        """首次进入时，按上一页的程序名填默认路径。"""
        if self.output_edit.text().strip():
            return
        from ._wizard import TemplateWizard
        wiz = self.wizard()
        if not isinstance(wiz, TemplateWizard):
            return
        name = wiz.param_page.program_name()
        self.output_edit.setText(str(self._output_dir / name))

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Choose output path"),
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
