"""Runner 管理窗口：只读列表，零钥匙串弹窗。

Round 2 MVP 仅展示，不含详情/右键菜单/删除/rotate 等带副作用操作——那些留到
Round 2.5 再做（参见决策：分阶段交付）。

数据源：backend.list_sealed() → cmdseal.py list --json → cmdseal_helper list。
路径已在 NEXT.md §5.19 实证为零弹窗。
"""
from __future__ import annotations

import datetime
import os
import re
import shlex
import subprocess
from pathlib import Path
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
    """将命令模板按规则打码。

    规则（与 cmdseal.py::mask_template 权威实现保持一致；
    新 seal 的 runner comment 里存的已经是打码值，本函数幂等
    再跑一次以兼容 legacy 或旧版本数据）：
      1. 首个 token（命令名本体）保留
      2. 含 ``{{arg:N}}`` / ``{{secret:NAME}}`` 占位符的 token 保留
      3. ``--`` 开头的 GNU 长 flag：
           * 含 ``=`` → ``--key=***``
           * 不含 ``=`` → 整体保留
      4. ``-`` 开头的短 flag：
           * 长度 == 2（如 ``-p``）保留
           * 长度 > 2（如 ``-pPass`` / ``-xzvf``）→ 取前两字符 + ``***``
      5. 其他裸 token（含绝对路径、引号值等）→ ``***``

    shlex 解析失败（引号不闭合等）时降级按空白切分，仍遵守上述
    规则，不得将原值漏出。
    """
    if template is None:
        return ""
    s = template
    if not s.strip():
        return s
    try:
        tokens = shlex.split(s, posix=True)
    except ValueError:
        tokens = s.split()
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if i == 0:
            out.append(tok)
            continue
        if _PLACEHOLDER_RE.search(tok):
            out.append(tok)
            continue
        if tok.startswith("--"):
            if "=" in tok:
                key, _ = tok.split("=", 1)
                out.append(f"{key}=***")
            else:
                out.append(tok)
            continue
        if tok.startswith("-") and len(tok) >= 2:
            if len(tok) == 2:
                out.append(tok)
            else:
                out.append(tok[:2] + "***")
            continue
        out.append("***")
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
        self.setWindowTitle(self.tr("cmdseal · Sealed Runners"))
        self.resize(820, 420)

        self._status = QLabel("—")
        self._status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._btn_refresh = QPushButton(self.tr("Refresh"))
        self._btn_refresh.clicked.connect(self.refresh)

        top = QHBoxLayout()
        top.addWidget(self._status, 1)
        top.addWidget(self._btn_refresh, 0)

        self._table = QTableWidget(0, len(_COLS), self)
        self._table.setHorizontalHeaderLabels([
            self.tr("Label"),
            self.tr("Service"),
            self.tr("Template"),
            self.tr("Created"),
        ])
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

        self._btn_close = QPushButton(self.tr("Close"))
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
        self._status.setText(self.tr("Loading…"))
        self._btn_refresh.setEnabled(False)
        try:
            items = list_sealed()
        except FileNotFoundError as e:
            self._btn_refresh.setEnabled(True)
            self._status.setText(self.tr("Load failed"))
            QMessageBox.critical(self, "cmdseal", str(e))
            return
        except subprocess.CalledProcessError as e:
            self._btn_refresh.setEnabled(True)
            self._status.setText(self.tr("Load failed"))
            QMessageBox.critical(
                self, "cmdseal",
                self.tr("cmdseal.py list failed (rc={rc})\n\n{err}").format(
                    rc=e.returncode, err=e.stderr or ""))
            return
        except Exception as e:  # noqa: BLE001 — UI 兜底
            self._btn_refresh.setEnabled(True)
            self._status.setText(self.tr("Load failed"))
            QMessageBox.critical(self, "cmdseal",
                                 self.tr("Unexpected error: {e}").format(e=e))
            return

        self._populate(items)
        n = len(items)
        legacy = sum(1 for it in items if not it.get("_meta"))
        self._status.setText(
            self.tr("{n} total · {ok} with metadata · {legacy} legacy").format(
                n=n, ok=n - legacy, legacy=legacy)
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
                label = self.tr("(legacy)")
                template = self.tr("(legacy, metadata unknown)")

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
        meta = data.get("_meta")

        menu = QMenu(self._table)

        act_delete = QAction(self.tr("Delete…"), self._table)
        act_delete.triggered.connect(
            lambda _=False, d=data: self._confirm_delete(d))
        menu.addAction(act_delete)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ---- delete ----------------------------------------------------------

    def _confirm_delete(self, item: dict[str, Any]) -> None:
        svc = str(item.get("service") or "?")
        acct = str(item.get("account") or "")
        meta = item.get("_meta") or {}
        label = str(meta.get("label") or self.tr("(legacy)"))
        out = str(meta.get("output_path") or "")

        # 决定磁盘文件联动删除的状态
        #   full    : 有路径且文件存在——会被一并删
        #   missing : 有路径但文件已不在——无需删
        #   legacy  : 没路径（legacy runner 或 comment 缺失）——只删 K
        binary_exists = False
        binary_path: Path | None = None
        if out:
            binary_path = Path(out)
            binary_exists = binary_path.is_file()

        msg = (
            self.tr("Delete runner “{label}”?\n\n").format(label=label)
            + self.tr("service : {svc}\n").format(svc=svc)
            + self.tr("account : {acct}\n").format(acct=acct or "—")
        )
        if out:
            msg += self.tr("binary  : {out}\n").format(out=out)

        if binary_exists:
            action_summary = self.tr(
                "\nThe following actions will run (not reversible):\n"
                "① Remove K from the keychain (ciphertext becomes undecryptable)\n"
                "② Also delete the sealed binary file from disk\n"
                "\nNo system authorization prompt will appear."
                "If the file cannot be removed (e.g. permissions), we will warn;"
                " K is already deleted and cannot be rolled back."
            )
        elif binary_path is not None:
            action_summary = self.tr(
                "\nThe following actions will run (not reversible):\n"
                "① Remove K from the keychain\n"
                "② The binary file is already gone from disk (no cleanup needed)\n"
                "\nNo system authorization prompt will appear."
            )
        else:
            action_summary = self.tr(
                "\nThe following actions will run (not reversible):\n"
                "① Remove K from the keychain\n"
                "⚠️ Legacy runner without output_path metadata; we cannot\n"
                "   automatically delete the sealed binary. If you still know\n"
                "   its location, please remove it manually.\n"
                "\nNo system authorization prompt will appear."
            )
        msg += action_summary

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(self.tr("Delete Runner"))
        box.setText(msg)
        btn_del = box.addButton(self.tr("Delete"), QMessageBox.DestructiveRole)
        box.addButton(self.tr("Cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(btn_del)
        box.exec()
        if box.clickedButton() is not btn_del:
            return

        # --- 步骤①：删 keychain K ---
        try:
            delete_runner(svc, acct)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self, "cmdseal",
                self.tr("Delete failed (rc={rc})\n\n{err}").format(
                    rc=e.returncode, err=e.stderr or ""))
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "cmdseal",
                                 self.tr("Unexpected error: {e}").format(e=e))
            return

        # --- 步骤②：联动删磁盘 binary（失败不回滚，只提示）---
        if binary_exists and binary_path is not None:
            try:
                os.unlink(binary_path)
            except OSError as e:
                QMessageBox.warning(
                    self, "cmdseal",
                    self.tr(
                        "K was deleted but removing the binary failed:\n"
                        "{path}\n\n{err}\n\n"
                        "Please delete this file manually (it can no longer be run)."
                    ).format(path=binary_path, err=e))

        self.refresh()
