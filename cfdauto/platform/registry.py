"""Template registry (Universal Platform, Phase 1).

A deliberately small lookup: register a :class:`SimulationTemplate`,
retrieve it by id, list what's available. Future phases add templates by
calling :meth:`TemplateRegistry.register` (or, later, by packaging-based
discovery) — nothing about *this* module needs to change for that.

The module-level default registry is pre-loaded with the built-in templates
via :func:`register_builtin_templates` (Phase 1: External Aerodynamics,
the declared default — matching the fact that today's application *is* that
workflow; Phase 6: Internal Flow). No runtime code consumes the registry
yet (Phase 1 contract); the accessor functions below are the seam future
phases will call.

Phase 8A adds the minimal registration seam, :func:`register_builtin_templates`
— the single, additive place a *new built-in template data file* gets wired
in, without touching the registry, the runtime, or the generic core. Full
plugin discovery (entry points / packaging) is deliberately deferred.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .internal_flow import INTERNAL_FLOW
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
# Built-in registration seam (Phase 8A) + default registry.
# --------------------------------------------------------------------------- #
def register_builtin_templates(
        registry: Optional[TemplateRegistry] = None) -> TemplateRegistry:
    """Register the platform's built-in templates into ``registry`` (a fresh
    one when none is given) and return it.

    The minimal Phase 8A registration seam: a new *built-in* template is
    wired in by editing this one function — the registry, the runtime, and
    the generic core stay untouched. A third-party template (the Phase 8A
    canary) registers itself on its own :class:`TemplateRegistry` instead,
    calling :meth:`TemplateRegistry.register` — also without touching core
    files. Full plugin discovery is explicitly out of scope (Phase 8G).
    """
    if registry is None:
        registry = TemplateRegistry()
    # Phase 1: the original application's workflow, also the declared default
    # (see DEFAULT_TEMPLATE_ID), so every existing runtime path is unaffected.
    registry.register(EXTERNAL_AERODYNAMICS)
    # Phase 6: a second, domain-different template — registered exactly the
    # same way, changing nothing about the registry or the default. Internal
    # Flow is inert until asked for by id.
    registry.register(INTERNAL_FLOW)
    return registry


_default_registry = register_builtin_templates()


def get_default_registry() -> TemplateRegistry:
    """The process-wide registry holding the built-in templates."""
    return _default_registry


def get_default_template() -> SimulationTemplate:
    """The template today's application corresponds to — External
    Aerodynamics. Future phases resolve this per-project instead of
    globally; until then this is the single, unambiguous answer."""
    return _default_registry.get(DEFAULT_TEMPLATE_ID)
