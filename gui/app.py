"""Application entry: theme + main window + Qt event loop."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.theme import apply_theme


def run_app(config_path: Optional[str] = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Slipstream")
    app.setOrganizationName("Slipstream")
    apply_theme(app)
    win = MainWindow(config_path=config_path)
    win.show()
    return app.exec()
