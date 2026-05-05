# Third-Party Licenses

> 中文版：[THIRD_PARTY_LICENSES.zh.md](./THIRD_PARTY_LICENSES.zh.md)

`cmdseal` itself is released under the [MIT License](./LICENSE).
This document enumerates the third-party components that ship with
or are required by `cmdseal`, and the licenses under which we use them.

---

## Runtime dependencies (bundled into `cmdseal.app`)

### PySide6

- **Role**: Python bindings for Qt; the GUI (`gui/`) is built on it.
- **Upstream**: <https://pypi.org/project/PySide6/> · <https://www.qt.io/>
- **License (as declared in PyPI metadata)**:
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`
- **License we use**: **LGPL-3.0-only** (with the Qt LGPL exception).
- **Canonical text**: <https://www.gnu.org/licenses/lgpl-3.0.txt>
- **Qt LGPL exception**: <https://doc.qt.io/qt-6/lgpl.html>

### Qt 6

- **Role**: Cross-platform GUI toolkit. Shipped as dynamic libraries
  (`QtCore`, `QtGui`, `QtWidgets`, …) inside PySide6 and, after
  `make app`, inside `cmdseal.app/Contents/Frameworks/`.
- **Upstream**: <https://www.qt.io/>
- **License we use**: **LGPL-3.0-only**.
- **Canonical text**: <https://www.gnu.org/licenses/lgpl-3.0.txt>
- **Note**: "Qt" is a registered trademark of The Qt Company Ltd.

### shiboken6

- **Role**: Binding generator / runtime used by PySide6. Installed
  as a transitive dependency.
- **License**: Same multi-license as PySide6
  (`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`); we use **LGPL-3.0-only**.

---

## LGPL-3.0 compliance notes

`cmdseal` is MIT-licensed and links against PySide6 / Qt 6 **dynamically**.
This section records how we satisfy LGPL-3.0 §4 obligations:

1. **Acknowledgement** — Users are informed that this software uses
   PySide6 and Qt 6 (this file and the README "Third-party" section).
2. **License text** — The full LGPL-3.0 text is available at
   <https://www.gnu.org/licenses/lgpl-3.0.txt>; it is also included
   verbatim inside the PySide6 and Qt distributions shipped with the
   `.app` bundle.
3. **Ability to replace the library** — `cmdseal` does not statically
   link Qt. Both source installs (`pip install PySide6`) and
   `cmdseal.app` (built via PyInstaller in `--onedir` mode, see
   [`cmdseal.spec`](./cmdseal.spec)) keep Qt / PySide6 as separate
   dynamic libraries under `Contents/Frameworks/` and
   `Contents/MacOS/PySide6/`. A user may replace these with a
   different build of the same ABI version of Qt / PySide6.
4. **Source of modifications** — We do **not** patch or modify PySide6
   or Qt. Sources are obtained verbatim from PyPI (PySide6) and Qt
   (as bundled inside PySide6 wheels).

If you redistribute a build of `cmdseal` that includes Qt, you inherit
the same obligations. In particular, do not use PyInstaller's
`--onefile` mode without understanding its implications for LGPL
dynamic-linking compliance.

---

## Build-time / development-only tools

These are **not** shipped in the release artifact and therefore do
not trigger redistribution obligations, but are listed for
completeness:

| Tool         | License         | Role                                       |
| ------------ | --------------- | ------------------------------------------ |
| `uv`         | Apache-2.0 / MIT | Python package / venv manager             |
| `PyInstaller` | GPL-2.0-or-later with bootloader exception | `.app` bundler (the exception explicitly allows shipping the bootloader with any license) |

---

## Trademark

"Qt" and "The Qt Company" are trademarks of The Qt Company Ltd.
`cmdseal` is not affiliated with, endorsed by, or sponsored by The Qt Company.

---

Last reviewed: aligned with `cmdseal 0.2.0`.
