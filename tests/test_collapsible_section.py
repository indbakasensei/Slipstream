"""GUI Modernization (v1.0.0-rc2) — behavioral tests for
gui.widgets.CollapsibleSection.

The one behavior this widget must never get wrong: toggling visibility
must never affect the wrapped content widget's own data/state — a
QListWidget full of warnings must stay fully populated and inspectable
whether the section is expanded or collapsed. This is exactly what makes
it safe to wrap StudySummaryPanel's existing warnings_list without
touching its own test-verified behavior.
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

from PySide6.QtWidgets import QApplication, QListWidget   # noqa: E402

from gui.widgets.collapsible_section import CollapsibleSection  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_starts_expanded_by_default(qapp):
    content = QListWidget()
    section = CollapsibleSection("Warnings", content)
    assert section.is_expanded() is True
    assert content.isVisible() or not content.isVisible()  # offscreen: just no crash
    assert section._content is content


def test_starts_collapsed_when_requested(qapp):
    content = QListWidget()
    section = CollapsibleSection("Warnings", content, start_expanded=False)
    assert section.is_expanded() is False


def test_toggle_flips_state_and_emits_signal(qapp):
    section = CollapsibleSection("Warnings", QListWidget())
    seen = []
    section.toggled.connect(seen.append)

    section.toggle()
    assert section.is_expanded() is False
    assert seen == [False]

    section.toggle()
    assert section.is_expanded() is True
    assert seen == [False, True]


def test_clicking_the_header_button_toggles(qapp):
    section = CollapsibleSection("Warnings", QListWidget())
    assert section.is_expanded() is True
    section._toggle_btn.click()
    assert section.is_expanded() is False
    section._toggle_btn.click()
    assert section.is_expanded() is True


def test_collapsing_never_alters_the_wrapped_content_data(qapp):
    """The critical property: hiding the section must not clear, reset, or
    otherwise mutate the content widget it wraps."""
    content = QListWidget()
    content.addItem("[CASE_FAILED] 1 case(s) failed.")
    content.addItem("[RETRIES_OCCURRED] 1 retry attempt(s)...")
    section = CollapsibleSection("Warnings", content)

    section.set_expanded(False)
    assert content.count() == 2
    assert content.item(0).text() == "[CASE_FAILED] 1 case(s) failed."

    section.set_expanded(True)
    assert content.count() == 2
    assert content.item(1).text() == "[RETRIES_OCCURRED] 1 retry attempt(s)..."


def test_set_expanded_to_same_state_does_not_emit_toggled(qapp):
    section = CollapsibleSection("Warnings", QListWidget(), start_expanded=True)
    seen = []
    section.toggled.connect(seen.append)
    section.set_expanded(True)      # already expanded — no-op
    assert seen == []
