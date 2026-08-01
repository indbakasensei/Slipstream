"""BrandHeader — the Slipstream identity bar at the top of the sidebar.

Painted logo mark + wordmark + tagline on the left, version chip on the
right. Purely presentational; ``version`` defaults to the running
``cfdauto.__version__`` (imported lazily so widget imports stay light).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui import theme
from gui.widgets.icons import make_icon


def _slipstream_version() -> str:
    try:
        import cfdauto  # noqa: WPS433  (lazy: keeps gui imports light)
        return getattr(cfdauto, "__version__", "dev")
    except Exception:  # pragma: no cover - no cfdauto, show generic
        return "dev"


class BrandHeader(QWidget):
    def __init__(self, name: str = "SLIPSTREAM", tagline: str = "Universal CFD Platform",
                 version: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("brand", True)
        self.setMinimumHeight(theme.BRAND_HEIGHT)

        self.name_lbl = QLabel(name)
        self.name_lbl.setProperty("brandName", True)
        self.tagline_lbl = QLabel(tagline)
        self.tagline_lbl.setProperty("brandTagline", True)
        self.version_lbl = QLabel(version if version is not None
                                  else _slipstream_version())
        self.version_lbl.setProperty("brandVersion", True)

        mark = QLabel()
        mark.setFixedSize(20, 20)
        icon = make_icon("logo", theme.ACCENT, 20)
        if icon is not None:
            mark.setPixmap(icon.pixmap(20, 20))

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(self.name_lbl)
        titles.addWidget(self.tagline_lbl)

        row = QHBoxLayout(self)
        row.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM,
                               theme.SPACE_MD, theme.SPACE_SM)
        row.setSpacing(theme.SPACE_MD)
        row.addWidget(mark)
        row.addLayout(titles)
        row.addStretch(1)
        row.addWidget(self.version_lbl, 0, Qt.AlignTop)
