# 第三方许可

> 英文版：[THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)

`cmdseal` 本身基于 [MIT License](./LICENSE) 发布。
本文件列出随 `cmdseal` 一起发行或其运行所需的第三方组件，
以及我们在使用它们时所遵循的许可证。

---

## 运行时依赖（随 `cmdseal.app` 一同分发）

### PySide6

- **作用**：Qt 的 Python 绑定；GUI（`gui/`）基于它构建。
- **上游**：<https://pypi.org/project/PySide6/> · <https://www.qt.io/>
- **PyPI 元数据中声明的许可**：
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`
- **我们实际采用的许可**：**LGPL-3.0-only**（并适用 Qt 的 LGPL 例外条款）。
- **许可全文**：<https://www.gnu.org/licenses/lgpl-3.0.txt>
- **Qt LGPL 例外**：<https://doc.qt.io/qt-6/lgpl.html>

### Qt 6

- **作用**：跨平台 GUI 工具包。以动态库形式分发
  （`QtCore`、`QtGui`、`QtWidgets` 等），位于 PySide6 内部；
  执行 `make app` 之后也会位于
  `cmdseal.app/Contents/Frameworks/` 之下。
- **上游**：<https://www.qt.io/>
- **我们实际采用的许可**：**LGPL-3.0-only**。
- **许可全文**：<https://www.gnu.org/licenses/lgpl-3.0.txt>
- **说明**："Qt" 是 The Qt Company Ltd. 的注册商标。

### shiboken6

- **作用**：PySide6 使用的绑定生成器 / 运行时，以传递依赖安装。
- **许可**：与 PySide6 相同的多许可方案
  （`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`），
  我们采用 **LGPL-3.0-only**。

---

## LGPL-3.0 合规说明

`cmdseal` 以 MIT 许可发布，并**动态**链接 PySide6 / Qt 6。
本节记录我们如何满足 LGPL-3.0 §4 的各项义务：

1. **声明使用**——用户会被告知本软件使用了
   PySide6 与 Qt 6（本文件以及 README 中的"第三方"小节）。
2. **许可证原文**——LGPL-3.0 完整文本位于
   <https://www.gnu.org/licenses/lgpl-3.0.txt>；随 `.app` 一同分发的
   PySide6 与 Qt 发行包中也逐字包含该文本。
3. **替换库的能力**——`cmdseal` 不对 Qt 做静态链接。无论是通过
   源码安装（`pip install PySide6`）还是使用 `cmdseal.app`（由
   PyInstaller 以 `--onedir` 模式打包，见
   [`cmdseal.spec`](./cmdseal.spec)），Qt / PySide6 都保持为
   `Contents/Frameworks/` 与 `Contents/MacOS/PySide6/` 下独立的
   动态库。用户可以用相同 ABI 版本的另一份 Qt / PySide6 构建进行替换。
4. **修改源码说明**——我们**不**对 PySide6 或 Qt 做任何补丁或
   改动，源码直接取自 PyPI（PySide6）与 Qt（随 PySide6 wheel 分发）。

如果你在自己的构建中再次分发带有 Qt 的 `cmdseal`，则将继承同样的
义务。特别地，在未充分理解 PyInstaller `--onefile` 模式对 LGPL
动态链接合规的影响之前，请不要使用该模式。

---

## 构建期 / 仅开发期工具

这些工具**不**随发行产物一同分发，因此不会触发再分发义务，
此处仅为完整性列出：

| 工具          | 许可证            | 作用                                   |
| ------------- | ----------------- | -------------------------------------- |
| `uv`          | Apache-2.0 / MIT  | Python 包 / 虚拟环境管理工具           |
| `PyInstaller` | GPL-2.0-or-later，附带 bootloader 例外 | `.app` 打包器（该例外明确允许在任何许可下分发 bootloader） |

---

## 商标

"Qt" 与 "The Qt Company" 是 The Qt Company Ltd. 的商标。
`cmdseal` 与 The Qt Company 无任何关联，也未获其赞助或背书。

---

最后复核：对齐 `cmdseal 0.2.0` 版本。
