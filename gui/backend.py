"""cmdseal CLI 的薄包装。

设计约束：
- GUI 不复制加密逻辑，全部交给项目根目录的 cmdseal.py
- secret 通过 stdin 以 NAME=VALUE 行喂入（见 cmdseal.py --secrets-from-stdin）
- 这里只提供启动子进程与收集输出的辅助函数，实际在主窗口接线时使用
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CMDSEAL_PY = PROJECT_ROOT / "cmdseal.py"


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
        sys.executable,
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
