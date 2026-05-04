"""cmdseal CLI 的薄包装。

设计约束：
- GUI 不复制加密逻辑，全部交给项目根目录的 cmdseal.py
- secret 通过 stdin 以 NAME=VALUE 行喂入（见 cmdseal.py --secrets-from-stdin）
- 这里只提供启动子进程与收集输出的辅助函数，实际在主窗口接线时使用

资产路径解析：
- 开发时（非冻结）：直接用仓库根下的 cmdseal.py；sys.executable 即当前 venv 的 python
- 打包后（sys.frozen）：PyInstaller 把三份资产打到 _MEIPASS/assets/，但
  _MEIPASS 是只读，而 cmdseal.py 要在 SCRIPT_DIR/_build/ 下编译 helper——
  所以首次启动时把三份资产镜像到 ~/Library/Application Support/cmdseal/
  （按 mtime 对比，版本升级时自动覆盖）。sys.executable 指向 app bootloader——
  改走系统 /usr/bin/python3（cmdseal.py 纯 stdlib，无第三方依赖）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 打包后镜像到的用户可写目录（跟 macOS HIG 建议的位置）
_APP_SUPPORT = Path.home() / "Library" / "Application Support" / "cmdseal"
_ASSET_NAMES = ("cmdseal.py", "cmdseal_helper.c", "runner_aead_template.c")


def _sync_asset(src: Path, dst: Path) -> None:
    """按 mtime 和大小决定是否覆盖。避免每次启动都重复拷贝。"""
    if dst.is_file():
        s = src.stat()
        d = dst.stat()
        if s.st_size == d.st_size and int(s.st_mtime) <= int(d.st_mtime):
            return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _resolve_runtime() -> tuple[Path, Path, str]:
    """返回 (PROJECT_ROOT, CMDSEAL_PY, PYTHON_EXE)。

    开发时：直接用仓库根；打包后：用 ~/Library/Application Support/cmdseal/
    作为工作根，用系统 python3 跑 cmdseal.py。
    """
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        asset_dir = meipass / "assets"
        work_root = _APP_SUPPORT
        work_root.mkdir(parents=True, exist_ok=True)
        for name in _ASSET_NAMES:
            src = asset_dir / name
            if src.is_file():
                _sync_asset(src, work_root / name)
        python_exe = shutil.which("python3") or "/usr/bin/python3"
        return work_root, work_root / "cmdseal.py", python_exe

    project_root = Path(__file__).resolve().parent.parent
    return project_root, project_root / "cmdseal.py", sys.executable


PROJECT_ROOT, CMDSEAL_PY, PYTHON_EXE = _resolve_runtime()


@dataclass
class SealRequest:
    command: str
    output: Path
    secrets: dict[str, str] = field(default_factory=dict)
    signing_identity: str = "-"
    no_sign: bool = False
    user: str | None = None
    label: str = ""
    rotate: bool = False


def build_argv(req: SealRequest) -> list[str]:
    sub = "rotate" if req.rotate else "seal"
    argv: list[str] = [
        PYTHON_EXE,
        str(CMDSEAL_PY),
        sub,
        "--command", req.command,
        "--output", str(req.output),
        "--signing-identity", req.signing_identity,
        "--secrets-from-stdin",
    ]
    if req.no_sign:
        argv.append("--no-sign")
    if req.user:
        argv += ["--user", req.user]
    if req.label:
        argv += ["--label", req.label]
    return argv


def serialize_secrets(secrets: dict[str, str]) -> str:
    # NAME=VALUE 一行一条；cmdseal.py 侧由 read_secrets_from_stdin 解析
    return "".join(f"{k}={v}\n" for k, v in secrets.items())


def run_seal_blocking(req: SealRequest) -> subprocess.CompletedProcess[str]:
    """阻塞式调用，主要用于冒烟测试；GUI 主线程请改用 QProcess。"""
    if not CMDSEAL_PY.is_file():
        raise FileNotFoundError(f"cmdseal.py not found at {CMDSEAL_PY}")
    return subprocess.run(
        build_argv(req),
        input=serialize_secrets(req.secrets),
        text=True,
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
    )


def list_sealed(prefix: str = "cmdseal.") -> list[dict]:
    """枚举已 seal 的 runner（零钥匙串弹窗，见 NEXT.md §5.19 实证）。

    返回 `cmdseal.py list --json` 的解析结果。每个 item 的字段可能有：
    service / account / label / comment / created / modified / _meta（
    Plan D comment JSON 解出的 dict，或 None 表示 legacy）。

    失败时抛 CalledProcessError；UI 层自行捕获展示。
    """
    if not CMDSEAL_PY.is_file():
        raise FileNotFoundError(f"cmdseal.py not found at {CMDSEAL_PY}")
    res = subprocess.run(
        [PYTHON_EXE, str(CMDSEAL_PY), "list", "--prefix", prefix, "--json"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
    )
    if res.returncode != 0:
        raise subprocess.CalledProcessError(
            res.returncode, res.args, res.stdout, res.stderr)
    return json.loads(res.stdout or "[]")


def delete_runner(service: str, account: str) -> None:
    """删除单条 runner 的 keychain 密钥。

    只删 keychain item，磁盘上的 sealed binary 不管——调用方自行决定
    是否同步删文件。AEAD 密文不持有 K 不能解密，所以遗留的二进制
    会变成废文件，但不构成秘密泄露。

    失败时抛 CalledProcessError；UI 层自行捕获展示。
    """
    if not CMDSEAL_PY.is_file():
        raise FileNotFoundError(f"cmdseal.py not found at {CMDSEAL_PY}")
    res = subprocess.run(
        [PYTHON_EXE, str(CMDSEAL_PY), "delete",
         "--service", service, "--user", account],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
    )
    if res.returncode != 0:
        raise subprocess.CalledProcessError(
            res.returncode, res.args, res.stdout, res.stderr)
