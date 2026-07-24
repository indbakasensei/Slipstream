"""Metadata-driven parameter rendering (Dynamic Template UI, Capability 2).

The single place that turns a :class:`~cfdauto.platform.ParameterDefinition`
into a Qt editing widget and its human-facing chrome — label, unit, tooltip,
numeric range, decimals, default, and validation. Every panel that shows a
parameter (the input form, the queue headers, future editors) renders through
here, so the UI knows *nothing* about specific parameter names: give it a
template's parameters and it draws the right controls for External
Aerodynamics, Internal Flow, or any template added later.

Pure functions of the metadata (plus thin Qt widget factories). Validation is
delegated to :meth:`ParameterDefinition.validate_value` /
:meth:`ExperimentDefinition.validate_row` — there is no second copy of the
limits here.

Engineering rule this enforces: a new template needs *1 metadata file + 1
execution strategy + 0 UI code*.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import QDoubleSpinBox

from cfdauto.platform import ParameterDefinition

# A parameter unbounded on one side (e.g. velocity, `maximum=None`) still needs
# a finite editing cap for the spin box. This is a UI affordance, not a domain
# constraint — the authoritative bounds live in the ParameterDefinition.
GUI_MAX_UNBOUNDED = 5000.0


# --------------------------------------------------------------------------- #
# Text chrome — label, unit, range, tooltip (all from metadata)
# --------------------------------------------------------------------------- #
def label_for(pdef: ParameterDefinition) -> str:
    """The form-row label, e.g. ``"AOA [deg]"`` — or just the display name
    for a dimensionless parameter."""
    return f"{pdef.display_name} [{pdef.unit}]" if pdef.unit else pdef.display_name


def range_text(pdef: ParameterDefinition) -> str:
    """A human sentence describing the parameter's accepted range."""
    lo, hi = pdef.minimum, pdef.maximum
    unit = f" {pdef.unit}" if pdef.unit else ""
    if lo is None and hi is None:
        return "Range: unbounded"
    if lo is not None and hi is not None:
        return f"Range: {lo:g} to {hi:g}{unit}"
    if lo is not None:
        return f"Range: ≥ {lo:g}{unit}"
    return f"Range: ≤ {hi:g}{unit}"


def tooltip_for(pdef: ParameterDefinition) -> str:
    """The rich tooltip shown for a parameter: description, unit, default,
    and range — every field a user needs, straight from the metadata."""
    parts: List[str] = []
    if pdef.description:
        parts.append(pdef.description)
    if pdef.unit:
        parts.append(f"Unit: {pdef.unit}")
    if pdef.default_value is not None:
        unit = f" {pdef.unit}" if pdef.unit else ""
        parts.append(f"Default: {float(pdef.default_value):g}{unit}")
    parts.append(range_text(pdef))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Numeric precision — inferred from the metadata, floored to preserve the
# established 2-dp look of the aero parameters.
# --------------------------------------------------------------------------- #
def _decimals_of(value: Optional[object]) -> int:
    if value is None:
        return 0
    try:
        f = abs(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    if f == 0 or f != f:       # zero or NaN
        return 0
    s = f"{f:.6f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def decimals_for(pdef: ParameterDefinition) -> int:
    """Spin-box decimal places, inferred from the parameter's step / bounds /
    default, floored at 2 (so AOA and Velocity keep their existing 2-dp look)
    and capped at 6 (so tiny values like a viscosity of 1e-3 stay legible)."""
    candidates = [2, _decimals_of(pdef.step),
                  _decimals_of(pdef.minimum), _decimals_of(pdef.default_value)]
    return min(6, max(candidates))


# --------------------------------------------------------------------------- #
# Widget factory
# --------------------------------------------------------------------------- #
def make_spin(pdef: ParameterDefinition,
              value: Optional[float] = None) -> QDoubleSpinBox:
    """A spin box whose range, precision, step, default, and tooltip all come
    from the ParameterDefinition. ``value`` overrides the default (used by the
    selected-row editor, which shows the row's current value)."""
    lo = pdef.minimum if pdef.minimum is not None else -GUI_MAX_UNBOUNDED
    hi = pdef.maximum if pdef.maximum is not None else GUI_MAX_UNBOUNDED
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setDecimals(decimals_for(pdef))
    if pdef.step:
        spin.setSingleStep(float(pdef.step))
    spin.setValue(value if value is not None else float(pdef.default_value or 0.0))
    spin.setKeyboardTracking(False)
    spin.setToolTip(tooltip_for(pdef))
    return spin


def plain_spin(lo: float = -1e6, hi: float = 1e6, dec: int = 3,
               tooltip: str = "") -> QDoubleSpinBox:
    """A metadata-less spin box for free Workbench (WBP) parameters, which
    carry no ParameterDefinition."""
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setDecimals(dec)
    spin.setKeyboardTracking(False)
    if tooltip:
        spin.setToolTip(tooltip)
    return spin


# --------------------------------------------------------------------------- #
# Validation — no second copy of the limits; delegates to the metadata
# --------------------------------------------------------------------------- #
def validate_value(pdef: ParameterDefinition, value: object) -> List[str]:
    """Problems with one value against its definition (empty = acceptable)."""
    return pdef.validate_value(value)


def validate_row(exp_def, values: Dict[str, object]) -> List[str]:
    """Every problem with a name→value input row, via the template-driven
    :meth:`ExperimentDefinition.validate_row`. Reuses the exact same limits the
    engine validates against — the UI adds no rules of its own."""
    return exp_def.validate_row(values)
