"""cmdseal GUI 前端包。

职责：
- 通过 PySide6 提供图形界面
- 调用项目根目录的 cmdseal.py 完成 seal / rotate 操作
- 不重复实现加密逻辑，仅作为 CLI 的前端包装
"""
from __future__ import annotations

import os
import subprocess
import sys


def _ensure_full_path() -> None:
    """从用户 login shell 继承完整 PATH。

    macOS 通过 Finder / Dock 启动的 .app 进程，PATH 默认仅含
    /usr/bin:/bin:/usr/sbin:/sbin，不包含用户在 ~/.zprofile / ~/.zshrc
    等配置的自定义路径（如 ~/.cargo/bin、/usr/local/bin、Homebrew 路径等）。

    本函数在 GUI 包首次加载时执行，仅在 macOS 平台且当前 PATH 看起来
    不完整时生效，通过运行用户的 login shell 获取完整 PATH 并合并。
    """
    if sys.platform != "darwin":
        return

    current_path = os.environ.get("PATH", "")
    # 启发式判断：如果 PATH 已经包含用户 home 下的路径，说明环境完整
    home = os.path.expanduser("~")
    if home in current_path:
        return

    shell = os.environ.get("SHELL", "/bin/zsh")
    try:
        result = subprocess.run(
            [shell, "-l", "-c", 'printf "%s" "$PATH"'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            shell_path = result.stdout.strip()
            # 合并：把 shell 拿到的新路径追加到当前 PATH 中（去重保序）
            existing = set(current_path.split(os.pathsep)) if current_path else set()
            extra_dirs = [
                d for d in shell_path.split(os.pathsep)
                if d and d not in existing
            ]
            if extra_dirs:
                merged = current_path + os.pathsep + os.pathsep.join(extra_dirs) if current_path else os.pathsep.join(extra_dirs)
                os.environ["PATH"] = merged
    except (OSError, subprocess.TimeoutExpired):
        # 非关键路径：获取失败时静默降级，不影响应用启动
        pass


_ensure_full_path()


# 从 pyproject.toml 读版本，避免和源头漂移。
# 注：pyproject.toml 声明了 [tool.uv] package = false，项目不作为 wheel 安装，
# 所以用 importlib.metadata 会拿不到；改为直接解析 pyproject.toml。
def _read_version() -> str:
    import tomllib
    from pathlib import Path
    try:
        pp = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pp.open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        # 打包后（PyInstaller .app）pyproject.toml 可能不在，给个 fallback
        return "0.0.0+unknown"


__version__ = _read_version()
