"""Sprint 5 — behavioral tests for gui.project_selector_dialog.

These exercise the dialog's actual logic (open_path/create_path) directly,
bypassing QFileDialog entirely — consistent with "keep tests deterministic"
and how this project already tests GUI dialog wiring (Sprint 2's
error-formatting dialog capture). A native file picker is never simulated;
the "browse" slots that call it are thin wrappers this file doesn't need
to touch to prove the dialog is wired correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox            # noqa: E402

from cfdauto.project_manager import create_project, load_recent_projects  # noqa: E402
from gui.project_selector_dialog import ProjectSelectorDialog      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_create_path_creates_project_and_records_it_as_recent(qapp, tmp_path):
    store = tmp_path / "recents.json"
    dlg = ProjectSelectorDialog(recents_store_path=store)

    root = tmp_path / "new_proj"
    ok = dlg.create_path(root, "New Proj", "a description")

    assert ok is True
    assert dlg.selected_project_root == root
    assert (root / "project.json").exists()
    assert load_recent_projects(store) == [str(root.resolve())]


def test_open_path_opens_existing_project_and_records_it_as_recent(qapp, tmp_path):
    store = tmp_path / "recents.json"
    root = tmp_path / "existing_proj"
    create_project(root, name="Existing")

    dlg = ProjectSelectorDialog(recents_store_path=store)
    ok = dlg.open_path(root)

    assert ok is True
    assert dlg.selected_project_root == root
    assert load_recent_projects(store) == [str(root.resolve())]


def test_open_path_on_invalid_project_does_not_accept_or_record(qapp, tmp_path, monkeypatch):
    # open_path() shows a real modal QMessageBox.critical() on failure —
    # monkeypatch it so the test doesn't block waiting for a click that
    # can never come under the offscreen QPA platform.
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)

    store = tmp_path / "recents.json"
    not_a_project = tmp_path / "junk"
    not_a_project.mkdir()

    dlg = ProjectSelectorDialog(recents_store_path=store)
    ok = dlg.open_path(not_a_project)

    assert ok is False
    assert dlg.selected_project_root is None
    assert load_recent_projects(store) == []


def test_dialog_preloads_recent_projects_list_on_construction(qapp, tmp_path):
    store = tmp_path / "recents.json"
    root = tmp_path / "seen_before"
    create_project(root, name="SeenBefore")
    dlg1 = ProjectSelectorDialog(recents_store_path=store)
    dlg1.open_path(root)                      # records it as recent

    dlg2 = ProjectSelectorDialog(recents_store_path=store)
    items = [dlg2.recent_list.item(i).text() for i in range(dlg2.recent_list.count())]
    assert items == [str(root.resolve())]
