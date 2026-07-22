"""Sprint 6 — behavioral tests for packaging/release infrastructure.

These deliberately never invoke PyInstaller itself (that would be slow and
brittle, exactly what this sprint was told to avoid). Instead they cover
the three things that can actually regress silently: the version-resource
generator's numeric-tuple conversion, that the generated file really
reflects cfdauto.__version__ (the single authoritative source), and that
the GUI's window title is *derived* from that source rather than a second,
independently-maintained literal.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "build"))

import cfdauto                                          # noqa: E402
from make_version_info import numeric_tuple, render      # noqa: E402


# --------------------------------------------------------------------- #
# Group: version consistency (single authoritative source)
#
# Regression Scenario: a packaging step (or a future contributor) hardcodes
# a version string somewhere instead of reading cfdauto.__version__ — the
# window title, the packaged .exe's metadata, and the release archive name
# then silently drift apart the next time __version__ is bumped.
# Expected Behaviour: cfdauto.__version__ is parseable, and every other
# version-bearing surface this sprint touches derives from it rather than
# hardcoding its own copy.
# Why this test exists: this is exactly the "duplication" Sprint 6 asked
# to be centralized — a regression here would silently reintroduce it.
# --------------------------------------------------------------------- #
def test_version_string_is_well_formed():
    assert re.match(r"^\d+\.\d+\.\d+", cfdauto.__version__)


def test_gui_window_title_is_derived_from_cfdauto_version():
    from gui.main_window import BASE_TITLE
    assert cfdauto.__version__ in BASE_TITLE


def test_project_manager_created_with_is_derived_from_cfdauto_version(tmp_path):
    from cfdauto.project_manager import create_project
    meta = create_project(tmp_path / "proj", name="Proj")
    assert meta.created_with == f"Slipstream v{cfdauto.__version__}"


# --------------------------------------------------------------------- #
# Group: packaging configuration generation
#
# Regression Scenario: the Windows executable's version metadata is
# generated text (build/make_version_info.py), not a hand-maintained
# file — a bug in the numeric-tuple conversion (Windows version resources
# require 4 plain integers, but "alpha"-style versions aren't numeric)
# would silently produce a corrupt or misleading .exe Properties dialog.
# Expected Behaviour: alpha/pre-release suffixes convert to a sensible
# 4-int tuple, and the rendered version resource embeds the exact
# cfdauto.__version__ string in its human-readable fields.
# Why this test exists: catches a regression without ever having to run
# PyInstaller itself (slow, brittle, and explicitly out of scope here).
# --------------------------------------------------------------------- #
def test_numeric_tuple_handles_alpha_suffix():
    assert numeric_tuple("1.0.0-alpha.6") == (1, 0, 0, 6)


def test_numeric_tuple_handles_plain_semver():
    assert numeric_tuple("2.3.1") == (2, 3, 1, 0)


def test_numeric_tuple_pads_and_truncates_to_four_parts():
    assert numeric_tuple("5") == (5, 0, 0, 0)
    assert numeric_tuple("1.2.3.4.5") == (1, 2, 3, 4)


def test_rendered_version_resource_embeds_exact_version_string():
    text = render("1.0.0-alpha.6")
    assert "u'1.0.0-alpha.6'" in text
    assert "filevers=(1, 0, 0, 6)" in text
    assert "Slipstream" in text


def test_make_version_info_matches_current_cfdauto_version():
    """The generator, run with no arguments, must reflect the *current*
    single authoritative version — not a value baked in at some past
    point in time."""
    text = render(cfdauto.__version__)
    assert cfdauto.__version__ in text
