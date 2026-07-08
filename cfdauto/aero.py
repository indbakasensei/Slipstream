"""Aerodynamic reference math.

The single most common silent error in automated AOA sweeps is a wrong force
direction or a stale reference velocity, which produces plausible-looking but
wrong CL/CD.  All of that logic is concentrated here so it can be unit-tested
without ANSYS.

Two ways to realise an angle of attack
--------------------------------------
``geometry`` mode
    The wing itself is rotated inside a fixed domain (Workbench parameter,
    remesh per AOA).  The freestream stays aligned with the domain X axis, so
    drag is measured along +X and lift along +Y — *independent of AOA*.

``velocity_vector`` mode
    The wing stays fixed at 0 deg and the *flow* is rotated instead: the inlet
    velocity vector becomes (V·cos a, V·sin a, 0).  No geometry update, no
    remesh — one mesh serves the whole sweep.  Lift and drag must then be
    measured in *wind axes*:  drag ∥ freestream, lift ⊥ freestream.

The framework supports both; the force vectors below make either correct.
Convention: X = streamwise, Y = "up", Z = spanwise (rotation axis).  If your
domain is oriented differently, adjust ``base_flow_axis`` / ``base_lift_axis``
in the config.
"""

from __future__ import annotations

import math
from typing import List, Tuple

Vec3 = List[float]

_AXES = {
    "+x": [1.0, 0.0, 0.0], "-x": [-1.0, 0.0, 0.0],
    "+y": [0.0, 1.0, 0.0], "-y": [0.0, -1.0, 0.0],
    "+z": [0.0, 0.0, 1.0], "-z": [0.0, 0.0, -1.0],
}


def _axis(name: str) -> Vec3:
    try:
        return list(_AXES[name.strip().lower()])
    except KeyError:
        raise ValueError(f"Unknown axis '{name}'. Use one of {sorted(_AXES)}") from None


def _rotate(v: Vec3, axis_flow: Vec3, axis_lift: Vec3, angle_deg: float) -> Vec3:
    """Rotate ``v`` by ``angle_deg`` in the plane spanned by flow/lift axes."""
    a = math.radians(angle_deg)
    f = sum(vi * fi for vi, fi in zip(v, axis_flow))   # component along flow axis
    l = sum(vi * li for vi, li in zip(v, axis_lift))   # component along lift axis
    fr = f * math.cos(a) - l * math.sin(a)
    lr = f * math.sin(a) + l * math.cos(a)
    out = [vi - f * fi - l * li for vi, fi, li in zip(v, axis_flow, axis_lift)]
    return [round(oi + fr * fi + lr * li, 12) for oi, fi, li in zip(out, axis_flow, axis_lift)]


def wind_axes(
    aoa_deg: float,
    method: str,
    base_flow_axis: str = "+x",
    base_lift_axis: str = "+y",
) -> Tuple[Vec3, Vec3, Vec3]:
    """Return ``(flow_dir, drag_vector, lift_vector)`` for one case.

    Parameters
    ----------
    aoa_deg:
        Angle of attack for this experiment.
    method:
        ``"geometry"`` (wing rotated, flow fixed) or ``"velocity_vector"``
        (wing fixed, flow rotated).
    """
    flow0 = _axis(base_flow_axis)
    lift0 = _axis(base_lift_axis)

    if method == "geometry":
        # Flow stays on the domain axis; wind axes == domain axes.
        return flow0, flow0, lift0

    if method == "velocity_vector":
        # Positive AOA tilts the incoming flow *up* toward the lift axis so the
        # fixed wing sees a positive incidence.  Wind axes rotate with it.
        flow = _rotate(flow0, flow0, lift0, aoa_deg)
        lift = _rotate(lift0, flow0, lift0, aoa_deg)
        return flow, flow, lift

    raise ValueError(f"Unknown aoa method '{method}' (use 'geometry' or 'velocity_vector')")


def dynamic_pressure(density: float, velocity: float) -> float:
    """q_inf = 1/2 * rho * V^2  [Pa]."""
    return 0.5 * density * velocity * velocity


def coefficient_from_force(force_n: float, density: float, velocity: float, area: float) -> float:
    return force_n / (dynamic_pressure(density, velocity) * area)


def force_from_coefficient(coeff: float, density: float, velocity: float, area: float) -> float:
    return coeff * dynamic_pressure(density, velocity) * area


def relative_mismatch(a: float, b: float) -> float:
    """Symmetric relative difference used for CL↔Lift sanity cross-checks."""
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom
