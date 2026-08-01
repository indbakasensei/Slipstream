"""HeroHeader — the project-identity banner atop the Dashboard.

This is the first thing a user sees when the Dashboard is open: it must answer
*"what project am I in, what am I doing, and where can I go from here?"* in one
glance. It shows:

* project name (large), template name and study description;
* a running/progress status line (or an idle hint);
* a Mock / Real mode badge;
* quick action buttons (Run / Open Project / Generate Report / …) wired by the
  caller through the two public signals.

Presentation-only — it never touches AppState or config; ``set_project`` /
``set_status`` / ``set_mock`` are the whole API. Buttons emit ``runClicked`` /
``openProjectClicked`` / ``actionClicked(str)`` and the owner decides what to do.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from gui import theme
from gui.widgets.icons import make_icon


class HeroHeader(QFrame):
    """Hero banner: identity left, status middle, actions right."""

    runClicked = Signal()
    openProjectClicked = Signal()
    actionClicked = Signal(str)          # quick-action id, e.g. "report"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("hero", True)
        self.setMinimumHeight(120)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(theme.SPACE_LG, theme.SPACE_MD,
                                 theme.SPACE_LG, theme.SPACE_MD)
        outer.setSpacing(theme.SPACE_LG)

        # ---- identity column (left) ----------------------------------- #
        identity = QVBoxLayout()
        identity.setSpacing(theme.SPACE_XS)

        self.project_lbl = QLabel("No project loaded")
        self.project_lbl.setProperty("heroTitle", True)
        identity.addWidget(self.project_lbl)

        self.meta_lbl = QLabel("File ▸ Open Project… to load a config.yaml")
        self.meta_lbl.setProperty("heroMeta", True)
        identity.addWidget(self.meta_lbl)

        self.desc_lbl = QLabel("")
        self.desc_lbl.setProperty("heroDesc", True)
        self.desc_lbl.setWordWrap(True)
        identity.addWidget(self.desc_lbl)

        outer.addLayout(identity, 2)

        # ---- status column (middle) ------------------------------------ #
        status = QVBoxLayout()
        status.setSpacing(theme.SPACE_XS)
        status.setAlignment(Qt.AlignTop)

        self.badge_lbl = QLabel("")
        self.badge_lbl.setProperty("mockBadge", True)
        self.badge_lbl.hide()
        status.addWidget(self.badge_lbl, 0, Qt.AlignLeft)

        self.status_lbl = QLabel("")
        self.status_lbl.setProperty("heroDesc", True)
        status.addWidget(self.status_lbl, 0, Qt.AlignLeft)

        self.solver_lbl = QLabel("")
        self.solver_lbl.setProperty("kpiCaption", True)
        status.addWidget(self.solver_lbl, 0, Qt.AlignLeft)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setProperty("kpiCaption", True)
        status.addWidget(self.progress_lbl, 0, Qt.AlignLeft)

        outer.addLayout(status, 1)

        # ---- action buttons (right) ------------------------------------ #
        actions = QVBoxLayout()
        actions.setSpacing(theme.SPACE_SM)
        actions.setAlignment(Qt.AlignTop)

        self.run_btn = self._make_action("Run Study", "run", theme.ACCENT)
        self.run_btn.clicked.connect(self.runClicked)
        actions.addWidget(self.run_btn)

        self.open_btn = self._make_action("Open Project", "open", None)
        self.open_btn.clicked.connect(self.openProjectClicked)
        actions.addWidget(self.open_btn)

        self.report_btn = self._make_action("Generate Report", "results", None)
        self.report_btn.clicked.connect(lambda: self.actionClicked.emit("report"))
        actions.addWidget(self.report_btn)

        outer.addLayout(actions, 0)

    # ------------------------------------------------------------------ #
    def _make_action(self, text: str, icon: Optional[str],
                     color: Optional[str]) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("quickAction", True)
        btn.setCursor(Qt.PointingHandCursor)
        if icon and color:
            ic = make_icon(icon, color, 15)
            if ic is not None:
                btn.setIcon(ic)
                btn.setIconSize(btn.iconSize())
        return btn

    # ------------------------------------------------------------------ #
    def set_project(self, name: str, template: str, description: str = "") -> None:
        """Populate project identity (empty name restores the idle state)."""
        if not name:
            self.project_lbl.setText("No project loaded")
            self.meta_lbl.setText("File ▸ Open Project… to load a config.yaml")
            self.desc_lbl.clear()
            return
        self.project_lbl.setText(name)
        meta = template if template else "—"
        self.meta_lbl.setText(meta)
        self.desc_lbl.setText(description)

    def set_status(self, running: bool, progress_pct: Optional[int] = None) -> None:
        """Update the status + progress line (progress_pct None hides it)."""
        if running:
            self.status_lbl.setText("Study running — solving cases")
        else:
            self.status_lbl.setText("Study idle")
        if progress_pct is not None and progress_pct >= 0:
            self.progress_lbl.setText(f"{int(progress_pct)}% complete")
        else:
            self.progress_lbl.clear()

    def set_solver(self, solver: str) -> None:
        """Show the active solver backend (e.g. ``ansys-fluent``)."""
        self.solver_lbl.setText(solver if solver else "")

    def set_mock(self, is_mock: bool) -> None:
        """Toggle the Mock / Real badge (inline status tint overrides the
        QSS base)."""
        if is_mock:
            self.badge_lbl.setProperty("mockBadge", True)
            self.badge_lbl.setText("MOCK")
            self.badge_lbl.setStyleSheet(
                "background:#453a24; color:#e8a33d;")
        else:
            self.badge_lbl.setProperty("mockBadgeReal", True)
            self.badge_lbl.setText("REAL")
            self.badge_lbl.setStyleSheet(
                "background:#1f3a2c; color:#3fbf7f;")
        self.badge_lbl.show()

    def set_run_enabled(self, enabled: bool) -> None:
        self.run_btn.setEnabled(enabled)
