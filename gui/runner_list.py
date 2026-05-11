"""Runner 管理窗口：只读列表 + 孤儿 keychain 条目可视化 + 批量 gc。

数据源：backend.list_sealed() → cmdseal.py list --json → cmdseal_helper list。
路径已在 NEXT.md §5.19 实证为零弹窗。

Status 列与 CLI `cmdseal gc` 的三分类语义对齐（classify_gc_items）：
  🟢 live    — output_path 对应的文件存在
  🟡 orphan  — output_path 已填但文件已消失，gc 会清掉
  ⚫ legacy  — 没有元数据（v1.1 之前的条目），永不自动 gc

批量 gc 按钮仅当存在孤儿时可用；确认对话框提供 "Dry run first" 复选框，
勾选时先调 ``cmdseal gc --dry-run --json`` 做一次外部一致性校验，再
调 ``--yes --json`` 真正执行，降低 keychain 期间被其它进程改动的风险。
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
    QCheckBox,
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

from .backend import delete_runner, gc_runners, list_sealed


_COLS = ("Status", "Label", "Service", "Template", "Created")

# Runner 状态展示文案。圆点用 Unicode（免 Qt icon 资源依赖）。
# 与 CLI 端 `cmdseal gc` 的三分类语义对齐（classify_gc_items）。
_STATUS_LIVE    = "🟢 live"
_STATUS_ORPHAN  = "🟡 orphan"
_STATUS_LEGACY  = "⚫ legacy"

# 孤儿行的前景色：琥珀/橙色，比 legacy 灰更醒目，但不做背景色以保持克制。
_ORPHAN_FG = QColor(0xC2, 0x71, 0x0C)

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


def _classify_status(item: dict[str, Any]) -> str:
    """与 CLI 端 ``classify_gc_items`` 语义一致的单条判定。

    返回 ``"live" | "orphan" | "legacy"``。只走 ``os.path.exists``
    做文件存在性检查（不触发 ACL 弹窗）。
    """
    meta = item.get("_meta")
    out = (meta or {}).get("output_path") if meta else None
    if not out:
        return "legacy"
    return "live" if os.path.exists(out) else "orphan"


class RunnerListWindow(QWidget):
    """独立窗口，不依赖 parent 生命周期。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        # 独立顶层窗口：传 parent 只为 Qt 对象树回收，不做 modal
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(self.tr("cmdseal · Sealed Runners"))
        self.resize(900, 440)

        self._status = QLabel("—")
        self._status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._btn_refresh = QPushButton(self.tr("Refresh"))
        self._btn_refresh.clicked.connect(self.refresh)

        # 批量 gc 按钮。孤儿数 == 0 时 disabled；refresh() 末尾更新。
        self._btn_gc = QPushButton(self.tr("Garbage collect…"))
        self._btn_gc.setToolTip(self.tr(
            "Scan for orphaned keychain items (whose sealed binary "
            "on disk is gone) and delete them in bulk."))
        self._btn_gc.setEnabled(False)
        self._btn_gc.clicked.connect(self._on_gc_clicked)

        top = QHBoxLayout()
        top.addWidget(self._status, 1)
        top.addWidget(self._btn_gc, 0)
        top.addWidget(self._btn_refresh, 0)

        self._table = QTableWidget(0, len(_COLS), self)
        self._table.setHorizontalHeaderLabels([
            self.tr("Status"),
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
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # Status
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)   # Label
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Service
        hh.setSectionResizeMode(3, QHeaderView.Stretch)            # Template
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)   # Created

        self._btn_close = QPushButton(self.tr("Close"))
        self._btn_close.clicked.connect(self.close)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self._btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self._table, 1)
        lay.addLayout(bottom)

        # 缓存上次 refresh 扫出的 orphan 条目（按 (service, account) 指纹），
        # gc 对话框直接用，无需重算。Dry run 时与 CLI 返回的集合对比来
        # 检测 keychain 期间的并发变动。
        self._orphans_cache: list[dict[str, Any]] = []

        # 首开即加载一次
        self.refresh()

    # ---- public API ------------------------------------------------------

    def refresh(self) -> None:
        """重新从 keychain 拉取并填表。subprocess 同步调用，~10ms 级。"""
        self._status.setText(self.tr("Loading…"))
        self._btn_refresh.setEnabled(False)
        self._btn_gc.setEnabled(False)
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

        # 汇总三分类统计 + 更新状态栏 + gc 按钮开关
        n = len(items)
        live = sum(1 for it in items if _classify_status(it) == "live")
        orphans = [it for it in items if _classify_status(it) == "orphan"]
        legacy = sum(1 for it in items if _classify_status(it) == "legacy")
        self._orphans_cache = orphans
        self._status.setText(
            self.tr("{n} total · {live} live · {orphan} orphan · "
                    "{legacy} legacy").format(
                n=n, live=live, orphan=len(orphans), legacy=legacy)
        )
        self._btn_refresh.setEnabled(True)
        self._btn_gc.setEnabled(len(orphans) > 0)

    # ---- internal --------------------------------------------------------

    def _populate(self, items: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        legacy_brush = QBrush(QColor(0x99, 0x99, 0x99))
        orphan_brush = QBrush(_ORPHAN_FG)

        for it in items:
            row = self._table.rowCount()
            self._table.insertRow(row)

            meta = it.get("_meta")
            svc = it.get("service", "?")
            status = _classify_status(it)

            if status == "live":
                status_text = _STATUS_LIVE
            elif status == "orphan":
                status_text = _STATUS_ORPHAN
            else:
                status_text = _STATUS_LEGACY

            if meta:
                label = str(meta.get("label") or "—")
                template = _mask_template(str(meta.get("template") or ""))
            else:
                label = self.tr("(legacy)")
                template = self.tr("(legacy, metadata unknown)")

            created_short, created_full = _format_created(
                meta, it.get("created"))

            cells = (status_text, label, svc, template, created_short)
            # tooltip：Status 给出判定依据；其他列沿用原值
            out_path = (meta or {}).get("output_path") or ""
            if status == "orphan":
                status_tip = self.tr(
                    "Binary missing on disk:\n{path}").format(path=out_path)
            elif status == "legacy":
                status_tip = self.tr(
                    "No metadata; cannot be auto-gc'd. "
                    "Use right-click Delete if you know this runner.")
            else:
                status_tip = self.tr(
                    "Binary exists:\n{path}").format(path=out_path)
            tooltips = (
                status_tip, label, svc, template,
                created_full or created_short)

            for col, (val, tip) in enumerate(zip(cells, tooltips)):
                cell = QTableWidgetItem(val)
                cell.setToolTip(tip)  # Created 列 tooltip 显示完整 ISO
                if status == "legacy":
                    cell.setForeground(legacy_brush)
                elif status == "orphan":
                    cell.setForeground(orphan_brush)
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

    # ---- gc --------------------------------------------------------------

    def _on_gc_clicked(self) -> None:
        """批量 gc 入口：确认对话框 → (可选 dry-run 校验) → 执行删除 → 刷新。"""
        orphans = list(self._orphans_cache)
        if not orphans:
            # 理论上不会触发（按钮已 disabled），兜底防御。
            QMessageBox.information(
                self, "cmdseal",
                self.tr("No orphaned items to garbage-collect."))
            return

        # 构造清单文案：最多列 10 条，超出折叠为 "…and N more"。
        preview_lines = []
        shown = orphans[:10]
        for it in shown:
            meta = it.get("_meta") or {}
            lab = str(meta.get("label") or "—")
            svc = str(it.get("service") or "?")
            preview_lines.append(f"  • {lab}  [{svc}]")
        if len(orphans) > len(shown):
            preview_lines.append(self.tr("  …and {n} more").format(
                n=len(orphans) - len(shown)))
        preview = "\n".join(preview_lines)

        msg = (
            self.tr("Garbage-collect {n} orphaned keychain item(s)?\n\n"
                    "These items' sealed binaries are no longer on disk, "
                    "so the keychain entries cannot be used.\n\n"
                    "Items to delete:\n{preview}\n").format(
                n=len(orphans), preview=preview)
        )

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(self.tr("Garbage collect"))
        box.setText(msg)
        # Dry run first 复选框：默认勾选。先调 `gc --dry-run --json` 让 CLI
        # 侧独立确认一次，再跑 `--yes`；若 dry-run 看到的孤儿集合与本地
        # 缓存不一致（keychain 期间被改动），中止并提示刷新。
        chk = QCheckBox(self.tr(
            "Dry run first (cross-check with cmdseal before deleting)"))
        chk.setChecked(True)
        chk.setToolTip(self.tr(
            "If checked, run `cmdseal gc --dry-run --json` first and verify "
            "the orphan set hasn't changed since the table was populated; "
            "only then delete. Safer when the keychain may be modified "
            "concurrently by another tool."))
        box.setCheckBox(chk)
        btn_del = box.addButton(
            self.tr("Delete"), QMessageBox.DestructiveRole)
        box.addButton(self.tr("Cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(btn_del)
        box.exec()
        if box.clickedButton() is not btn_del:
            return

        self._run_gc(orphans, dry_run_first=chk.isChecked())

    def _run_gc(self, expected_orphans: list[dict[str, Any]],
                *, dry_run_first: bool) -> None:
        """执行批量 gc。``expected_orphans`` 是 UI 表格当前看到的孤儿集合。"""
        self._btn_gc.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        try:
            if dry_run_first:
                # 1) 先 dry-run，读 CLI 看到的孤儿集合
                try:
                    report = gc_runners(apply=False)
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(
                        self, "cmdseal",
                        self.tr(
                            "cmdseal gc --dry-run failed (rc={rc})\n\n"
                            "{err}").format(
                            rc=e.returncode, err=e.stderr or ""))
                    return

                cli_orphans = [
                    (o.get("service"), o.get("account"))
                    for o in report.get("orphans") or []
                ]
                local_orphans = [
                    (it.get("service"), it.get("account"))
                    for it in expected_orphans
                ]
                if sorted(cli_orphans) != sorted(local_orphans):
                    QMessageBox.warning(
                        self, "cmdseal",
                        self.tr(
                            "Keychain state changed since the table was "
                            "populated.\n\n"
                            "Displayed orphans : {a}\n"
                            "CLI now reports   : {b}\n\n"
                            "Nothing was deleted. Please click Refresh and "
                            "try again.").format(
                            a=len(local_orphans), b=len(cli_orphans)))
                    return

            # 2) 真删
            try:
                report = gc_runners(apply=True)
            except subprocess.CalledProcessError as e:
                # 部分失败也会走这里（cmdseal gc --yes --json 在有删除失败
                # 时 rc=1）；尽量把部分结果展示出来。
                QMessageBox.critical(
                    self, "cmdseal",
                    self.tr(
                        "cmdseal gc --yes failed (rc={rc})\n\n"
                        "{err}").format(
                        rc=e.returncode, err=e.stderr or ""))
                return

            deleted = len(report.get("orphans") or [])
            QMessageBox.information(
                self, "cmdseal",
                self.tr("Garbage collect complete: {n} item(s) deleted.\n\n"
                        "Run `cmdseal gc --dry-run` from the terminal for a "
                        "second opinion.").format(n=deleted))
        finally:
            # refresh() 会自己 re-enable 这些按钮
            self.refresh()
