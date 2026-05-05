"""cmdseal GUI 前端包。

职责：
- 通过 PySide6 提供图形界面
- 调用项目根目录的 cmdseal.py 完成 seal / rotate 操作
- 不重复实现加密逻辑，仅作为 CLI 的前端包装
"""
from __future__ import annotations

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
