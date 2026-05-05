"""GUI internationalization (i18n) infrastructure.

Qt native approach: source strings are authored in English, translations
live in ``gui/translations/cmdseal_<locale>.qm`` (compiled from ``.ts``
via ``pyside6-lrelease``). The active language is chosen by, in order:

1. User preference in ``QSettings`` (``app/language`` = ``auto``/``en``/``zh_CN``)
2. If ``auto``: system locale via ``QLocale.system()``
3. Fallback: English (no translator installed → source strings shown)

Language switches take effect after restarting the GUI. Keeping it
simple avoids threading a retranslate hook through every QWidget
subclass in this phase-1 rollout.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

from . import settings


#: Languages we ship translations for. ``en`` is identity (source language),
#: so no .qm is loaded for it. Add new entries here + drop matching
#: ``cmdseal_<code>.qm`` into ``gui/translations/``.
SUPPORTED_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("auto", "Auto (System)"),
    ("en", "English"),
    ("zh_CN", "中文（简体）"),
)

#: Languages that have a translation file bundled (excludes ``auto`` and ``en``).
_TRANSLATED = {"zh_CN"}


def _translations_dir() -> Path:
    """Locate the ``translations/`` directory both in dev and inside PyInstaller.

    Dev: next to this file (``gui/translations/``).
    PyInstaller bundle: ``sys._MEIPASS/gui/translations/`` (via ``.spec`` datas).
    """
    here = Path(__file__).resolve().parent / "translations"
    if here.is_dir():
        return here
    # PyInstaller onedir fallback: MEIPASS holds bundled resources
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(meipass) / "gui" / "translations"
        if cand.is_dir():
            return cand
    return here  # may not exist; caller handles missing .qm gracefully


def _resolve_locale(pref: str) -> str:
    """Return the effective locale code given the user preference.

    ``auto`` → system locale mapped to the closest supported bundle.
    Anything else → returned verbatim (caller still guards missing .qm).
    """
    if pref and pref != "auto":
        return pref
    sys_name = QLocale.system().name()  # e.g. "zh_CN", "zh_TW", "en_US"
    if sys_name.startswith("zh"):
        return "zh_CN"
    return "en"


def install_translators(app: QCoreApplication) -> str:
    """Install translators on the given ``QApplication``. Returns the
    effective locale code actually loaded (for logging / about-box).

    Two translators are installed so Qt's own strings (standard dialog
    buttons, etc.) localize too:

    1. ``qtbase_<locale>.qm`` from Qt's install path (best-effort).
    2. ``cmdseal_<locale>.qm`` from ``gui/translations/``.
    """
    pref = settings.load_language()
    locale = _resolve_locale(pref)

    if locale not in _TRANSLATED:
        # English / unknown → no-op; source strings are already English
        return locale

    tdir = _translations_dir()

    # 1) Qt's own translations (standard dialogs, message boxes …). Optional;
    #    absence is fine, just means Qt's builtin strings stay English.
    qt_trans = QTranslator(app)
    qt_trans_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if qt_trans.load(QLocale(locale), "qtbase", "_", qt_trans_path):
        app.installTranslator(qt_trans)

    # 2) Our own bundle
    our = QTranslator(app)
    qm = tdir / f"cmdseal_{locale}.qm"
    if qm.is_file() and our.load(str(qm)):
        app.installTranslator(our)
        # Keep references alive on the app to avoid GC
        app._cmdseal_translators = (qt_trans, our)  # type: ignore[attr-defined]
    return locale
