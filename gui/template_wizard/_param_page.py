"""Page 2 — 参数选择(token 切片点选)。

多段(v1.2.2)：每段一行 chip，arg 编号跨段全局递增。
这一策略与 seal_wizard._scan_placeholders_many 对齐，保证运行时 argN 对应的位置无歧义。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from ._core import SEALED_NAME_PREFIX, build_template_many

if TYPE_CHECKING:
    from ._wizard import TemplateWizard


class ParameterSelectionPage(QWizardPage):
    """第 2 步：点选要参数化的 token。"""

    # chip 样式：未选中 = 字面量；选中 = 运行时参数
    _STYLE_LITERAL = (
        "QPushButton { background: #ffffff; color: #333; "
        "border: 1px solid #bbb; border-radius: 4px; padding: 6px 10px; }"
        "QPushButton:hover { border-color: #4a90d9; }"
    )
    _STYLE_ARG = (
        "QPushButton { background: #4a90d9; color: white; "
        "border: 1px solid #357abd; border-radius: 4px; "
        "padding: 6px 10px; font-weight: bold; }"
    )

    def __init__(self, name_prefix: str = SEALED_NAME_PREFIX) -> None:
        super().__init__()
        #: 文件名前缀；供 program_name() 拼默认输出名。由偏好面板控制。
        self._name_prefix = name_prefix
        self.setTitle("选择运行时参数")
        self.setSubTitle(
            "点击命令中的 token 切换「字面量 / 运行时参数」。\n"
            "多段时 argN 编号跨段全局递增：第一个选中的 token 是 arg1，第二个是 arg2……"
        )

        # 垂直容器：每段一行 chip
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(120)
        self._container = QWidget()
        self._segments_layout = QVBoxLayout(self._container)
        self._segments_layout.setSpacing(8)
        self._segments_layout.setContentsMargins(6, 6, 6, 6)
        self._segments_layout.addStretch(1)
        self._scroll.setWidget(self._container)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        self.preview.setFont(mono)
        self.preview.setMaximumBlockCount(64)
        self.preview.setFixedHeight(120)
        self.preview.setStyleSheet(
            "QPlainTextEdit { background: #f5f5f5; color: #222; padding: 8px; "
            "border-radius: 4px; border: 1px solid #ddd; }"
        )

        self.hint = QLabel("—")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("QLabel { color: #888; background: transparent; }")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("命令分解（蓝色 = 运行时参数，白色 = 字面量）："))
        lay.addWidget(self._scroll, 1)
        lay.addWidget(QLabel("模板预览（每段一行）："))
        lay.addWidget(self.preview)
        lay.addWidget(self.hint)

        self._token_groups: list[list[str]] = []
        self._selected: list[set[int]] = []

    def initializePage(self) -> None:
        # 延迟导入避免模块级循环
        from ._wizard import TemplateWizard

        # 清空旧段行（保留尾部 stretch）
        while self._segments_layout.count() > 1:
            item = self._segments_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                # 可能是嵌套 layout
                lay = item.layout()
                if lay is not None:
                    self._clear_layout(lay)

        wiz = self.wizard()
        if not isinstance(wiz, TemplateWizard):
            return
        self._token_groups = wiz.command_page.token_groups()
        # 剩余的空段（当前不允许，但防范）：从 token_groups 滤除空列表
        self._token_groups = [g for g in self._token_groups if g]
        self._selected = [set() for _ in self._token_groups]

        stretch_idx = self._segments_layout.count() - 1
        total = len(self._token_groups)
        for seg_idx, tokens in enumerate(self._token_groups):
            row_widget = QWidget()
            row_lay = QVBoxLayout(row_widget)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(2)

            if total == 1:
                title_text = "段 1："
            else:
                tag = "第一段 / 主命令" if seg_idx == 0 else f"第 {seg_idx + 1} 段 / 读上段 stdout"
                title_text = f"段 {seg_idx + 1}（{tag}）："
            title = QLabel(title_text)
            title.setStyleSheet(
                "QLabel { color: #555; font-weight: bold; background: transparent; }"
            )

            chip_row = QHBoxLayout()
            chip_row.setSpacing(6)
            for tok_idx, tok in enumerate(tokens):
                chip = QPushButton(tok)
                chip.setCheckable(True)
                chip.setStyleSheet(self._STYLE_LITERAL)
                chip.setToolTip(f"段 {seg_idx + 1} token #{tok_idx}：点击切换为运行时参数")

                def _on_toggle(
                    checked: bool,
                    s: int = seg_idx,
                    i: int = tok_idx,
                    b: QPushButton = chip,
                ) -> None:
                    if checked:
                        self._selected[s].add(i)
                        b.setStyleSheet(self._STYLE_ARG)
                    else:
                        self._selected[s].discard(i)
                        b.setStyleSheet(self._STYLE_LITERAL)
                    self._update_preview()
                    self.completeChanged.emit()

                chip.toggled.connect(_on_toggle)
                chip_row.addWidget(chip)
            chip_row.addStretch(1)

            row_lay.addWidget(title)
            row_lay.addLayout(chip_row)
            self._segments_layout.insertWidget(stretch_idx, row_widget)
            stretch_idx += 1

        self._update_preview()

    @staticmethod
    def _clear_layout(lay) -> None:
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _update_preview(self) -> None:
        templates = build_template_many(self._token_groups, self._selected)
        lines = []
        for i, tmpl in enumerate(templates):
            prefix = f"段 {i + 1}: " if len(templates) > 1 else ""
            lines.append(f"{prefix}{tmpl}")
        self.preview.setPlainText("\n".join(lines) if lines else "—")

        total_selected = sum(len(s) for s in self._selected)
        if total_selected == 0:
            self.hint.setText(
                "<span style='color: #c62828;'>⚠ 至少在任意一段选择一个 token 作为运行时参数</span>"
            )
            return
        msg = f"已选 {total_selected} 个运行时参数 → 运行时按 arg1/arg2/… 顺序传入"
        # 首 token（段 1 的 index 0）被参数化：提示必须传可执行绝对路径
        if self._selected and 0 in self._selected[0]:
            msg += "；⚠ 首 token（程序路径）被参数化，运行时必须传入可执行的绝对路径"
        self.hint.setText(msg)

    def isComplete(self) -> bool:
        return any(len(s) > 0 for s in self._selected)

    def templates(self) -> list[str]:
        """返回每段的模板字符串列表。供 ExecutionPage 拼 SealRequest.commands。"""
        return build_template_many(self._token_groups, self._selected)

    def template(self) -> str:
        """向后兼容：返回首段模板。仅用于日志/预览。"""
        templates = self.templates()
        return templates[0] if templates else ""

    def program_name(self) -> str:
        """用于生成默认输出文件名：统一加 ``self._name_prefix`` 前缀以区分原命令。

        特例：
        - 命令本身已以前缀开头（如用户给封装产物再封装）→ 不重复加前缀
        - tokens 为空 → 退化到 “sealed”
        - 多段时以首段首 token 为准（首段是主命令，最代表整条管道的身份）
        """
        if not self._token_groups or not self._token_groups[0]:
            return "sealed"
        base = Path(self._token_groups[0][0]).name or "sealed"
        if self._name_prefix and base.startswith(self._name_prefix):
            return base
        return (self._name_prefix or "") + base
