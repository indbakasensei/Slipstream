"""Diagnostic — inspect Fluent's mesh display API on this machine.

Run this after a case has been solved once (a Fluent session must be able to
launch and read the baseline case). It prints every attribute and child
object of the mesh graphics settings so we know exactly which knobs exist
on your Fluent version. Paste the output back to debug the mesh capture.

Usage::

    python tools/inspect_fluent_mesh_api.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cfdauto.config import load_config
from cfdauto.fluent_controller import FluentController, _root


def _describe(obj, prefix="", max_depth=3, depth=0):
    """Recursively list attributes/children of a Fluent settings object."""
    if depth > max_depth:
        return
    for name in sorted(dir(obj)):
        if name.startswith("_"):
            continue
        try:
            child = getattr(obj, name)
        except Exception:
            continue
        type_name = type(child).__name__
        # Skip callable methods that aren't sub-objects
        if callable(child) and not hasattr(child, "child_names"):
            continue
        print(f"{prefix}{name}  ({type_name})")
        # Recurse into settings-tree Groups
        if hasattr(child, "child_names") and depth < max_depth:
            _describe(child, prefix + "    ", max_depth, depth + 1)


def main() -> int:
    cfg_path = Path("config/config.yaml")
    if not cfg_path.exists():
        print("Run this from the slipstream/ folder.")
        return 1
    cfg = load_config(cfg_path)
    fl = FluentController(cfg)
    print("Launching Fluent (may take ~30-60 s)...")
    solver = fl._launch(Path("runs/tmp"))
    try:
        root = _root(solver)
        print("Reading baseline case...")
        fl._read_baseline(root)
        print()
        print("=" * 70)
        print("MESH GRAPHICS API STRUCTURE")
        print("=" * 70)
        gfx = root.results.graphics
        print("\ngfx.mesh:")
        _describe(gfx.mesh, "  ")

        print("\n\ngfx.mesh child object structure (a fresh mesh_2_child):")
        if "cfdauto_probe" not in gfx.mesh.child_names:
            gfx.mesh.create("cfdauto_probe")
        m = gfx.mesh["cfdauto_probe"]
        print(f"  type: {type(m).__name__}")
        print(f"  child_names: {list(m.child_names) if hasattr(m, 'child_names') else 'n/a'}")
        _describe(m, "  ", max_depth=4)
    finally:
        try:
            solver.exit()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())