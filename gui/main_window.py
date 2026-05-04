"""主窗口：当前只是一个启动器，负责拉起 seal 向导。

后续会在这里再接：rotate 向导、最近生成物列表、keychain 体检等。
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

from .seal_wizard import SealWizard


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("cmdseal")
        self.resize(520, 320)

        self._wizard: SealWizard | None = None

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

        self.btn_seal = QPushButton("新建 seal…")
        self.btn_seal.setMinimumHeight(40)
        self.btn_seal.clicked.connect(self._open_seal_wizard)

        self.btn_rotate = QPushButton("rotate（待实现）")
        self.btn_rotate.setMinimumHeight(40)
        self.btn_rotate.setEnabled(False)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_seal)
        btn_row.addWidget(self.btn_rotate)
        btn_row.addStretch(1)

        central = QWidget(self)
        lay = QVBoxLayout(central)
        lay.addStretch(1)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addSpacing(24)
        lay.addLayout(btn_row)
        lay.addStretch(2)
        self.setCentralWidget(central)

    def _open_seal_wizard(self) -> None:
        # 保持引用，避免被 GC；关闭时释放
        self._wizard = SealWizard(self)
        self._wizard.finished.connect(self._on_wizard_finished)
        self._wizard.show()

    def _on_wizard_finished(self, _result: int) -> None:
        self._wizard = None
