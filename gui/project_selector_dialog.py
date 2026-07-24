"""Project Selector — a lightweight dialog for Open Recent / Open Existing /
Create New, sitting on top of cfdauto.project_manager.

This dialog contains no project-management logic of its own: every button
just collects the missing piece of information (a path, picked via
QFileDialog, or a name typed into a QLineEdit) and calls straight into
open_project()/create_project(). The actual open/create handling
(open_path/create_path) is kept separate from the QFileDialog-driven
"browse" slots specifically so tests can exercise it directly without
simulating a native file picker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QMessageBox,
                               QPushButton, QVBoxLayout)

from cfdauto.platform import DEFAULT_TEMPLATE_ID, get_default_registry
from cfdauto.project_manager import (
    ProjectError,
    add_recent_project,
    create_project,
    load_recent_projects,
    open_project,
)
from cfdauto.project_scaffold import scaffold_project


class ProjectSelectorDialog(QDialog):
    """On acceptance, ``self.selected_project_root`` holds the chosen/created
    project's folder — ``None`` if the dialog was cancelled."""

    def __init__(self, parent=None,
                 recents_store_path: Optional[Union[str, Path]] = None):
        super().__init__(parent)
        self.setWindowTitle("Slipstream Projects")
        # None => cfdauto.project_manager's default location. Tests pass an
        # explicit tmp_path here so they never touch a real user profile.
        self._recents_store_path = recents_store_path
        self.selected_project_root: Optional[Path] = None

        v = QVBoxLayout(self)

        v.addWidget(QLabel("Recent projects"))
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(
            lambda _item: self._open_recent_selected())
        v.addWidget(self.recent_list)
        self._reload_recents()

        recent_row = QHBoxLayout()
        open_recent_btn = QPushButton("Open Selected")
        open_recent_btn.clicked.connect(self._open_recent_selected)
        recent_row.addWidget(open_recent_btn)
        recent_row.addStretch(1)
        v.addLayout(recent_row)

        v.addWidget(QLabel("—"))

        open_existing_btn = QPushButton("Open Existing…")
        open_existing_btn.clicked.connect(self._browse_open_existing)
        v.addWidget(open_existing_btn)

        v.addWidget(QLabel("Create new project"))
        form = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Project name")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description (optional)")
        form.addWidget(self.name_edit)
        form.addWidget(self.desc_edit)
        v.addLayout(form)

        # Capability 3: choose which SimulationTemplate the new project uses.
        # Populated from the registry (External Aerodynamics, Internal Flow,
        # and any future template) — the UI stays a renderer of metadata.
        tmpl_row = QHBoxLayout()
        tmpl_row.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        for tmpl in get_default_registry().all():
            self.template_combo.addItem(f"{tmpl.name}", tmpl.id)
        default_ix = self.template_combo.findData(DEFAULT_TEMPLATE_ID)
        if default_ix >= 0:
            self.template_combo.setCurrentIndex(default_ix)
        self.template_combo.setToolTip(
            "The kind of CFD study this project runs. Determines its "
            "workbook columns, study defaults, and execution strategy.")
        tmpl_row.addWidget(self.template_combo, 1)
        v.addLayout(tmpl_row)

        create_btn = QPushButton("Create New…")
        create_btn.clicked.connect(self._browse_create_new)
        v.addWidget(create_btn)

    # ------------------------------------------------------------------ #
    # Recents list
    # ------------------------------------------------------------------ #
    def _reload_recents(self) -> None:
        self.recent_list.clear()
        for path in load_recent_projects(self._recents_store_path):
            self.recent_list.addItem(path)

    def _open_recent_selected(self) -> None:
        item = self.recent_list.currentItem()
        if item is not None:
            self.open_path(Path(item.text()))

    # ------------------------------------------------------------------ #
    # QFileDialog-driven "browse" slots — thin, no logic beyond collecting
    # a path/name and handing off to the testable methods below.
    # ------------------------------------------------------------------ #
    def _browse_open_existing(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Open Slipstream project folder")
        if path:
            self.open_path(Path(path))

    def _browse_create_new(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Project name required",
                                "Enter a project name first.")
            return
        parent_dir = QFileDialog.getExistingDirectory(
            self, "Choose a location for the new project")
        if not parent_dir:
            return
        self.create_path(Path(parent_dir) / name, name,
                         self.desc_edit.text().strip(),
                         template_id=self.template_combo.currentData() or "")

    # ------------------------------------------------------------------ #
    # Directly testable — no QFileDialog involved.
    # ------------------------------------------------------------------ #
    def open_path(self, path: Path) -> bool:
        try:
            open_project(path)
        except ProjectError as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))
            return False
        add_recent_project(path, self._recents_store_path)
        self.selected_project_root = Path(path)
        self.accept()
        return True

    def create_path(self, root: Path, name: str, description: str = "",
                    template_id: str = "") -> bool:
        """Create the project folder + metadata, then scaffold its
        template-specific ``config.yaml`` + workbook so it opens ready to run.
        ``template_id`` empty = the registry default."""
        try:
            create_project(root, name, description, template_id=template_id)
            scaffold_project(root, template_id)
        except ProjectError as exc:
            QMessageBox.critical(self, "Could not create project", str(exc))
            return False
        except Exception as exc:                        # scaffold/openpyxl/yaml
            QMessageBox.critical(self, "Could not set up project", str(exc))
            return False
        add_recent_project(root, self._recents_store_path)
        self.selected_project_root = Path(root)
        self.accept()
        return True
