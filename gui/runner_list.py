"""Runner 管理窗口：只读列表，零钥匙串弹窗。

Round 2 MVP 仅展示，不含详情/右键菜单/删除/rotate 等带副作用操作——那些留到
Round 2.5 再做（参见决策：分阶段交付）。

数据源：backend.list_sealed() → cmdseal.py list --json → cmdseal_helper list。
路径已在 NEXT.md §5.19 实证为零弹窗。
"""
from __future__ import annotations

import datetime
import subprocess
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .backend import list_sealed


_COLS = ("Label", "Service", "Template", "Created")


def _format_created(meta: dict[str, Any] | None, raw_epoch: float | None) -> str:
    """优先用 Plan D comment 里的 created_at ISO 字符串；否则降级 SecAttr 的
    created epoch；都没有返回空。"""
    if meta:
        s = meta.get("created_at") or ""
        if s:
            return s
    if raw_epoch:
        try:
            return datetime.datetime.fromtimestamp(
                float(raw_epoch), tz=datetime.timezone.utc
            ).isoformat(timespec="seconds")
        except (ValueError, OSError, TypeError):
            return ""
    return ""


class RunnerListWindow(QWidget):
    """独立窗口，不依赖 parent 生命周期。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        # 独立顶层窗口：传 parent 只为 Qt 对象树回收，不做 modal
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("cmdseal · 已 seal 的 runner")
        self.resize(820, 420)

        self._status = QLabel("—")
        self._status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.clicked.connect(self.refresh)

        top = QHBoxLayout()
        top.addWidget(self._status, 1)
        top.addWidget(self._btn_refresh, 0)

        self._table = QTableWidget(0, len(_COLS), self)
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.setTextElideMode(Qt.ElideRight)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # Label
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)   # Service
        hh.setSectionResizeMode(2, QHeaderView.Stretch)            # Template
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # Created

        self._btn_close = QPushButton("关闭")
        self._btn_close.clicked.connect(self.close)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self._btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._table, 1)
        lay.addLayout(bottom)

        # 首开即加载一次
        self.refresh()

    # ---- public API ------------------------------------------------------

    def refresh(self) -> None:
        """重新从 keychain 拉取并填表。subprocess 同步调用，~10ms 级。"""
        self._status.setText("加载中…")
        self._btn_refresh.setEnabled(False)
        try:
            items = list_sealed()
        except FileNotFoundError as e:
            self._btn_refresh.setEnabled(True)
            self._status.setText("加载失败")
            QMessageBox.critical(self, "cmdseal", str(e))
            return
        except subprocess.CalledProcessError as e:
            self._btn_refresh.setEnabled(True)
            self._status.setText("加载失败")
            QMessageBox.critical(
                self, "cmdseal",
                f"cmdseal.py list 失败（rc={e.returncode}）\n\n{e.stderr or ''}")
            return
        except Exception as e:  # noqa: BLE001 — UI 兜底
            self._btn_refresh.setEnabled(True)
            self._status.setText("加载失败")
            QMessageBox.critical(self, "cmdseal", f"意外错误：{e}")
            return

        self._populate(items)
        n = len(items)
        legacy = sum(1 for it in items if not it.get("_meta"))
        self._status.setText(
            f"共 {n} 条 · {n - legacy} 条带元数据 · {legacy} 条 legacy"
        )
        self._btn_refresh.setEnabled(True)

    # ---- internal --------------------------------------------------------

    def _populate(self, items: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        legacy_brush = QBrush(QColor(0x99, 0x99, 0x99))

        for it in items:
            row = self._table.rowCount()
            self._table.insertRow(row)

            meta = it.get("_meta")
            svc = it.get("service", "?")

            if meta:
                label = str(meta.get("label") or "—")
                template = str(meta.get("template") or "")
            else:
                label = "(legacy)"
                template = "(legacy, metadata unknown)"

            created = _format_created(meta, it.get("created"))

            cells = (label, svc, template, created)
            for col, val in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setToolTip(val)  # 悬停显示完整内容
                if meta is None:
                    cell.setForeground(legacy_brush)
                self._table.setItem(row, col, cell)
