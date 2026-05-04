"""PyInstaller 顶层入口。

不能直接让 pyinstaller 打 `gui/__main__.py`——它会被当作无父包的顶级
脚本执行，里面的 `from .main_window import MainWindow` 会抛
`ImportError: attempted relative import with no known parent package`。

这里通过一个纯绝对 import 的 launcher 绕开该问题；`python -m gui` 的
开发用法保持不变。
"""
from __future__ import annotations

import sys

from gui.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
