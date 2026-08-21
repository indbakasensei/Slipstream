# Slipstream Plugin SDK (Architecture Placeholder)

> **Status:** Architecture placeholder — not yet implemented.
> Target: Phase 8G.

## Purpose

The Plugin SDK will allow third-party developers to extend Slipstream with:

- New simulation templates (parameters, metrics, study definitions)
- Custom execution strategies (solver backends)
- Lint rule extensions
- Analytics role extensions

## Architecture (Planned)

```
                    Plugin SDK (Phase 8G)
                         |
          +--------------+--------------+
          |              |              |
    Template Registry  Strategy Registry  Lint Rule Registry
          |              |              |
    SimulationTemplate  ExecutionStrategy  register_lint_rules()
          |              |              |
    +----+----+    +----+----+    +----+----+
    |         |    |         |    |         |
  Parameters Metrics  Mesh   Solver  Rules  Rules
```

## Extension Points

| Extension | Registration | Phase |
|-----------|-------------|-------|
| Template | `register_template(id, factory)` | 8G |
| Execution Strategy | `register_strategy(id, factory)` | 8G (existing internal) |
| Lint Rules | `register_lint_rules(id, fn)` | 8F (implemented) |
| Analytics Roles | `MetricDefinition.analytics_role` | 8D (implemented) |
| Monitor Metrics | `MetricDefinition.monitor_priority` | 8F revision (implemented) |

## Existing Internal Registration

Slipstream already uses registration patterns internally:

- `cfdauto.platform.registry` — template registration
- `cfdauto.execution` — strategy dispatch by template id
- `cfdauto.linter.register_lint_rules()` — lint rule dispatch

The SDK will externalise these same patterns.

## Design Constraints

- No template-id branching in generic code
- All registrations data-driven
- Plugins must not break existing External Aero or Internal Flow
- Version compatibility via `EVENT_SCHEMA_VERSION`
