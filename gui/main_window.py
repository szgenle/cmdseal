"""主窗口骨架。

当前仅提供最小可见窗口，后续迭代再逐步填充：
- 命令模板输入
- secret 采集（遮蔽输入 + 二次确认）
- 输出路径选择
- 签名身份下拉
- 调用 backend.seal / backend.rotate 并流式回显日志
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("cmdseal")
        self.resize(720, 480)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("cmdseal GUI — skeleton"))
        layout.addWidget(
            QLabel(
                "TODO: seal / rotate 表单、secret 输入、日志视图",
            )
        )
        layout.addStretch(1)
        self.setCentralWidget(central)
