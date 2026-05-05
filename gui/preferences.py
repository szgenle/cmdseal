"""系统设置面板（Preferences）。

入口：主窗口菜单栏 ``cmdseal → Preferences…``（macOS 下会被系统自动
搬到「cmdseal 菜单 → 偏好设置」的标准位置，快捷键 ``⌘,``）。

当前仅暴露 A 档最小版的 3 项：
- 默认输出目录
- 默认文件名前缀
- 试运行超时（秒）

改动只影响下一次打开 TemplateWizard 时的默认值；向导内仍可临时覆盖。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import settings


class PreferencesDialog(QDialog):
    """A 档：3 项偏好的编辑窗口。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(520, 260)

        prefs = settings.load_template_prefs()
        defaults = settings.default_template_prefs()

        # --- 输出目录 ---
        self.output_edit = QLineEdit(str(prefs.output_dir))
        self.output_edit.setPlaceholderText(str(defaults.output_dir))
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._on_browse)
        output_row = QWidget()
        out_lay = QHBoxLayout(output_row)
        out_lay.setContentsMargins(0, 0, 0, 0)
        out_lay.addWidget(self.output_edit, 1)
        out_lay.addWidget(browse_btn)

        # --- 文件名前缀 ---
        self.prefix_edit = QLineEdit(prefs.name_prefix)
        self.prefix_edit.setPlaceholderText(defaults.name_prefix)

        # --- 试运行超时 ---
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setValue(prefs.try_run_timeout_ms // 1000)

        form = QFormLayout()
        form.addRow("默认输出目录：", output_row)
        form.addRow("文件名前缀：", self.prefix_edit)
        form.addRow("试运行超时：", self.timeout_spin)

        hint = QLabel(
            "这些默认值在下一次打开「从命令生成模板」向导时生效。\n"
            "向导内仍可以临时改写，不影响此处的全局默认。"
        )
        hint.setWordWrap(True)
        # 深色模式 #888 对比度够；显式 transparent 防继承父容器背景
        hint.setStyleSheet("QLabel { color: #888; background: transparent; }")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok
            | QDialogButtonBox.Cancel
            | QDialogButtonBox.RestoreDefaults
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            self._on_reset
        )

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addStretch(1)
        lay.addWidget(buttons)

    # --- 槽 ---
    def _on_browse(self) -> None:
        cur = self.output_edit.text().strip()
        if not cur:
            cur = str(settings.default_template_prefs().output_dir)
        chosen = QFileDialog.getExistingDirectory(
            self, "选择默认输出目录", cur
        )
        if chosen:
            self.output_edit.setText(chosen)

    def _on_reset(self) -> None:
        ret = QMessageBox.question(
            self,
            "恢复默认",
            "确定要把这三项设置都恢复为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        p = settings.reset_template_prefs()
        self.output_edit.setText(str(p.output_dir))
        self.prefix_edit.setText(p.name_prefix)
        self.timeout_spin.setValue(p.try_run_timeout_ms // 1000)

    def _on_accept(self) -> None:
        output_dir = self.output_edit.text().strip()
        prefix = self.prefix_edit.text().strip()
        timeout_sec = self.timeout_spin.value()

        if not output_dir:
            QMessageBox.warning(self, "无效", "默认输出目录不能为空")
            return
        # 前缀为空也放行没意义：用户会发现默认文件名直接变原命令名，
        # 放 PATH 里会遮蔽系统同名命令 —— 明确拒绝
        if not prefix:
            QMessageBox.warning(self, "无效", "文件名前缀不能为空")
            return
        # 文件名前缀禁止路径分隔符，避免拼出非法路径
        if "/" in prefix or "\\" in prefix:
            QMessageBox.warning(
                self, "无效", "文件名前缀不能包含 / 或 \\"
            )
            return

        # 目录不存在不强制创建：向导第 1 次保存时会 mkdir -p
        # 但给一个 Path 化的简单可行性检查，早报错好过晚报错
        try:
            Path(output_dir).expanduser()
        except Exception as e:  # noqa: BLE001 — 任意解析异常都拒绝
            QMessageBox.warning(self, "无效", f"目录路径解析失败：{e}")
            return

        settings.save_template_prefs(
            output_dir=output_dir,
            name_prefix=prefix,
            try_run_timeout_sec=timeout_sec,
        )
        self.accept()
