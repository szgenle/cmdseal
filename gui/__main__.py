"""Entry point: ``python -m gui`` launches the GUI."""
import sys

from PySide6.QtWidgets import QApplication

from .i18n import install_translators
from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    # setOrganization/ApplicationName must precede QSettings-backed reads
    # (i18n reads language pref from QSettings).
    app.setApplicationName("cmdseal")
    app.setOrganizationName("cmdseal")
    install_translators(app)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
