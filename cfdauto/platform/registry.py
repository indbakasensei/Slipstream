"""Template registry (Universal Platform, Phase 1).

A deliberately small lookup: register a :class:`SimulationTemplate`,
retrieve it by id, list what's available. Future phases add templates by
calling :meth:`TemplateRegistry.register` (or, later, by packaging-based
discovery) — nothing about *this* module needs to change for that.

The module-level default registry is pre-loaded with the one Phase 1
template, External Aerodynamics, which is also the declared default —
matching the fact that today's application *is* that workflow. No runtime
code consumes the registry yet (Phase 1 contract); the accessor functions
below are the seam future phases will call.
"""

from __future__ import annotations

from typing import Dict, List

from .templates import EXTERNAL_AERODYNAMICS, SimulationTemplate

DEFAULT_TEMPLATE_ID = EXTERNAL_AERODYNAMICS.id


class TemplateRegistry:
    """In-memory registry of available simulation templates."""

    def __init__(self) -> None:
        self._templates: Dict[str, SimulationTemplate] = {}

    # ------------------------------------------------------------------ #
    def register(self, template: SimulationTemplate) -> None:
        """Add a template. Re-registering an id raises — silent clobbering
        of one template by another would be a debugging nightmare later,
        exactly the class of drift the ledger's config hashing exists to
        catch elsewhere in this codebase."""
        if template.id in self._templates:
            raise ValueError(
                f"Template id '{template.id}' is already registered.")
        self._templates[template.id] = template

    def get(self, template_id: str) -> SimulationTemplate:
        """Retrieve by id; raises LookupError naming what *is* available
        (an actionable message, per this project's error-formatting
        conventions)."""
        try:
            return self._templates[template_id]
        except KeyError:
            raise LookupError(
                f"Unknown simulation template '{template_id}'. "
                f"Available: {sorted(self._templates) or '(none)'}") from None

    def ids(self) -> List[str]:
        """Registered template ids, sorted for deterministic output."""
        return sorted(self._templates)

    def all(self) -> List[SimulationTemplate]:
        """All registered templates, ordered by id."""
        return [self._templates[i] for i in self.ids()]

    def __contains__(self, template_id: str) -> bool:
        return template_id in self._templates

    def __len__(self) -> int:
        return len(self._templates)


# --------------------------------------------------------------------------- #
# Default registry — built-ins registered at import time.
# --------------------------------------------------------------------------- #
_default_registry = TemplateRegistry()
_default_registry.register(EXTERNAL_AERODYNAMICS)


def get_default_registry() -> TemplateRegistry:
    """The process-wide registry holding the built-in templates."""
    return _default_registry


def get_default_template() -> SimulationTemplate:
    """The template today's application corresponds to — External
    Aerodynamics. Future phases resolve this per-project instead of
    globally; until then this is the single, unambiguous answer."""
    return _default_registry.get(DEFAULT_TEMPLATE_ID)
