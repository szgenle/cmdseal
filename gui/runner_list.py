"""Runner 管理窗口：只读列表，零钥匙串弹窗。

Round 2 MVP 仅展示，不含详情/右键菜单/删除/rotate 等带副作用操作——那些留到
Round 2.5 再做（参见决策：分阶段交付）。

数据源：backend.list_sealed() → cmdseal.py list --json → cmdseal_helper list。
路径已在 NEXT.md §5.19 实证为零弹窗。
"""
from __future__ import annotations

import datetime
import re
import shlex
import subprocess
from typing import Any

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .backend import delete_runner, list_sealed


_COLS = ("Label", "Service", "Template", "Created")

# 占位符检测：token 里**包含** {{arg:N}} / {{secret:NAME}} 的按占位符处理，
# 不打码（占位符本身是结构标记，不是值；真正的敏感值在运行时由用户补）。
_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*(?:arg\s*:\s*\d+|secret\s*:\s*[^}\s]+)\s*\}\}")


def _mask_template(template: str) -> str:
    """将命令模板里的「裸位置参数」打成 ***，保留 flag / 占位符 / 命令名。

    规则（按用户决策）：
      1. 首个 token（命令名本体）保留
      2. 以 ``-`` 开头的 token（Unix flag，含长/短选项及 ``--flag=value``）保留
      3. 以 ``/`` 开头的 token（Windows 风格 flag）保留
      4. 含 ``{{arg:N}}`` / ``{{secret:NAME}}`` 占位符的 token 保留
      5. 其余 token 视为位置参数，整体替换成 ``***``

    例：
      zip -P {{secret:PW}} -r out.zip {{arg:1}}
        → zip -P {{secret:PW}} -r *** {{arg:1}}

      docker run -e K={{secret:DB}} nginx:1.27 my-container
        → docker run -e K={{secret:DB}} *** ***

    shlex 负责处理带引号的 token（如 ``\"hello world\"`` 会被视作单个 token）；
    解析失败（例如引号不闭合）时降级按空白切分——展示容忍轻微失真，但绝
    不能把整串原样漏出。
    """
    s = template or ""
    if not s.strip():
        return s
    try:
        tokens = shlex.split(s, posix=True)
    except ValueError:
        tokens = s.split()
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if i == 0:
            out.append(tok)                         # 命令名本体
        elif tok.startswith("-") or tok.startswith("/"):
            out.append(tok)                         # flag
        elif _PLACEHOLDER_RE.search(tok):
            out.append(tok)                         # 占位符
        else:
            out.append("***")                       # 裸位置参数
    return " ".join(out)


def _format_created(meta: dict[str, Any] | None,
                    raw_epoch: float | None) -> tuple[str, str]:
    """返回 (short, full) 两个时间字符串：

      - short：本地时区 ``YYYY-MM-DD HH:MM``（16 字符），给表格单元格显示
      - full ：完整 ISO（含秒 + 时区），给 tooltip 和可能的调试核对

    优先用 Plan D comment 里的 ``created_at`` ISO 字符串，其次降级
    SecAttr 的 created epoch；都没有返回 (\"\", \"\")。
    """
    dt: datetime.datetime | None = None
    if meta:
        s = meta.get("created_at") or ""
        if s:
            try:
                # Python 3.11+ 支持 ``Z`` 后缀；保险起见手动替换
                dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                dt = None
    if dt is None and raw_epoch:
        try:
            dt = datetime.datetime.fromtimestamp(
                float(raw_epoch), tz=datetime.timezone.utc)
        except (ValueError, OSError, TypeError):
            dt = None
    if dt is None:
        return "", ""
    local = dt.astimezone()
    short = local.strftime("%Y-%m-%d %H:%M")
    full = local.isoformat(timespec="seconds")
    return short, full


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
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

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
                template = _mask_template(str(meta.get("template") or ""))
            else:
                label = "(legacy)"
                template = "(legacy, metadata unknown)"

            created_short, created_full = _format_created(
                meta, it.get("created"))

            cells = (label, svc, template, created_short)
            tooltips = (label, svc, template, created_full or created_short)
            for col, (val, tip) in enumerate(zip(cells, tooltips)):
                cell = QTableWidgetItem(val)
                cell.setToolTip(tip)  # Created 列 tooltip 显示完整 ISO
                if meta is None:
                    cell.setForeground(legacy_brush)
                self._table.setItem(row, col, cell)
            # 把整行原始 dict 存在第一列 UserRole，右键时取回
            self._table.item(row, 0).setData(Qt.UserRole, it)

    # ---- context menu ----------------------------------------------------

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self._table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        anchor = self._table.item(row, 0)
        if anchor is None:
            return
        data = anchor.data(Qt.UserRole) or {}

        menu = QMenu(self._table)
        act_delete = QAction("删除…", self._table)
        act_delete.triggered.connect(lambda _=False, d=data: self._confirm_delete(d))
        menu.addAction(act_delete)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _confirm_delete(self, item: dict[str, Any]) -> None:
        svc = str(item.get("service") or "?")
        acct = str(item.get("account") or "")
        meta = item.get("_meta") or {}
        label = str(meta.get("label") or "(legacy)")
        out = str(meta.get("output_path") or "")

        msg = (
            f"确认删除 runner 「{label}」的钥匙串密钥？\n\n"
            f"service : {svc}\n"
            f"account : {acct or '—'}\n"
        )
        if out:
            msg += f"binary  : {out}\n"
        msg += (
            "\n删除后：\n"
            "• 钥匙串中的 K 将被永久移除，不可恢复。\n"
            "• 磁盘上的 sealed binary 本身不会被删，但将无法再解密运行。\n"
            "• 此操作本身不触发系统授权弹窗。\n"
        )

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("删除 runner")
        box.setText(msg)
        btn_del = box.addButton("删除", QMessageBox.DestructiveRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.setDefaultButton(btn_del)
        box.exec()
        if box.clickedButton() is not btn_del:
            return

        try:
            delete_runner(svc, acct)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self, "cmdseal",
                f"删除失败（rc={e.returncode}）\n\n{e.stderr or ''}")
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "cmdseal", f"意外错误：{e}")
            return

        self.refresh()
