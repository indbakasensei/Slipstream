"""Universal CFD Platform, Phase 3A — unit tests for StudyDefinition.

These cover the new template-driven study model: the ordered parameter
list, spreadsheet-column metadata, lookup, and the External Aerodynamics
template's study definition (AOA → AOA_deg, Velocity → Velocity_m_s). They
assert *ordering comes from metadata* and that a StudyParameter shares —
does not duplicate — its ParameterDefinition. No runtime wiring is asserted
here (that stays covered, byte-identically, by the unmodified GUI tests).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.platform import (                              # noqa: E402
    EXTERNAL_AERODYNAMICS,
    ParameterDefinition,
    ParameterType,
    StudyDefinition,
    StudyParameter,
    get_default_template,
)
from cfdauto.simulation_context import SimulationContext    # noqa: E402


def _pdef(name: str, display: str) -> ParameterDefinition:
    return ParameterDefinition(id=name, name=name, display_name=display,
                              type=ParameterType.FLOAT, default_value=1.0)


# --------------------------------------------------------------------- #
# Group: StudyParameter delegates to its ParameterDefinition
# --------------------------------------------------------------------- #
def test_study_parameter_delegates_metadata_without_duplicating():
    pdef = _pdef("rpm", "RPM")
    sp = StudyParameter(parameter=pdef, column_name="RPM_col", order=0)
    # display/unit/required/default come straight from the shared def.
    assert sp.name == "rpm"
    assert sp.display_name == "RPM"
    assert sp.required is pdef.required
    assert sp.default_value == pdef.default_value
    # Study-level binding is its own.
    assert sp.column_name == "RPM_col"
    assert sp.editable is True and sp.visible is True


# --------------------------------------------------------------------- #
# Group: ordering comes from metadata, never construction order
# --------------------------------------------------------------------- #
def test_ordered_sorts_by_order_field_not_construction_order():
    a = StudyParameter(_pdef("a", "A"), column_name="A", order=2)
    b = StudyParameter(_pdef("b", "B"), column_name="B", order=0)
    c = StudyParameter(_pdef("c", "C"), column_name="C", order=1)
    sd = StudyDefinition(parameters=(a, b, c))     # deliberately scrambled
    assert [p.name for p in sd.ordered()] == ["b", "c", "a"]
    assert sd.column_names() == ["B", "C", "A"]
    assert sd.display_names() == ["B", "C", "A"]


def test_visible_and_editable_filters_preserve_order():
    a = StudyParameter(_pdef("a", "A"), "A", order=0, visible=False)
    b = StudyParameter(_pdef("b", "B"), "B", order=1, editable=False)
    c = StudyParameter(_pdef("c", "C"), "C", order=2)
    sd = StudyDefinition(parameters=(a, b, c))
    assert [p.name for p in sd.visible()] == ["b", "c"]
    assert [p.name for p in sd.editable()] == ["a", "c"]


def test_lookup_by_name_id_or_column():
    sp = StudyParameter(_pdef("aoa", "AOA"), column_name="AOA_deg", order=0)
    sd = StudyDefinition(parameters=(sp,))
    assert sd.parameter("aoa") is sp
    assert sd.parameter("AOA_deg") is sp        # by column name
    assert sd.parameter("nope") is None


# --------------------------------------------------------------------- #
# Group: spreadsheet metadata (descriptive; no Excel generation)
# --------------------------------------------------------------------- #
def test_spreadsheet_columns_expose_full_ordered_metadata():
    sp = StudyParameter(_pdef("aoa", "AOA"), column_name="AOA_deg", order=0)
    sd = StudyDefinition(parameters=(sp,))
    cols = sd.spreadsheet_columns()
    assert cols == [{
        "column_name": "AOA_deg", "display_name": "AOA", "unit": "",
        "editable": True, "required": True, "order": 0,
    }]


# --------------------------------------------------------------------- #
# Group: External Aerodynamics template's study definition
# --------------------------------------------------------------------- #
def test_external_aero_study_definition_matches_todays_schedule():
    sd = EXTERNAL_AERODYNAMICS.study_definition
    assert sd is not None
    assert [p.name for p in sd.ordered()] == ["aoa", "velocity"]
    # Column names mirror config.ColumnMap defaults (the schedule headers).
    assert sd.column_names() == ["AOA_deg", "Velocity_m_s"]
    assert sd.display_names() == ["AOA", "Velocity"]


def test_study_parameters_share_the_templates_parameter_definitions():
    """No duplication: the StudyParameter references the very same
    ParameterDefinition object exposed via supported_parameters."""
    t = get_default_template()
    aoa_sp = t.study_definition.parameter("aoa")
    assert aoa_sp.parameter is t.parameter("aoa")


# --------------------------------------------------------------------- #
# Group: context exposes template-driven input ordering
# --------------------------------------------------------------------- #
def test_context_input_columns_come_from_study_definition():
    ctx = SimulationContext.default()
    # These are exactly the GUI dataset's input-column keys, byte-identical
    # to the previously-hardcoded ["AOA", "Velocity"].
    assert ctx.input_columns() == ["AOA", "Velocity"]
    assert ctx.study_definition is EXTERNAL_AERODYNAMICS.study_definition


def test_context_input_columns_falls_back_to_supported_parameters():
    """A template with no study_definition still resolves input columns —
    the ordering seam degrades gracefully for future templates."""
    from cfdauto.platform import SimulationTemplate
    bare = SimulationTemplate(
        id="bare", name="Bare",
        supported_parameters=(_pdef("x", "X"), _pdef("y", "Y")))
    ctx = SimulationContext(template=bare)
    assert ctx.study_definition is None
    assert ctx.input_columns() == ["X", "Y"]
