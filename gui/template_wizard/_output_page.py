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
        from ._wizard import TemplateWizard
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
