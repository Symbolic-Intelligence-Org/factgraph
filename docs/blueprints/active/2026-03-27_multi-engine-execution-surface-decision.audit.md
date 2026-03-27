# Decision Blueprint Audit: Multi-Engine Execution Surface v0

- Blueprint: [2026-03-27_multi-engine-execution-surface-decision.md](./2026-03-27_multi-engine-execution-surface-decision.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | scoped | Blueprint created | Supersedes `2026-03-27_pyreason-execution-surface-v0-decision.md`. Unifies D1-D4 (from old blueprint) + F1-F5 (from office hours redesign session) into 9 frozen decisions. |

## Decision Notes

- Office hours session diagnosed the root cause: PyReason built a shadow pipeline bypassing core entirely
- engine_ext on shared Rule was frozen in assertion-annotation-store-decision but never implemented
- 3 rounds of adversarial design review + 3 rounds of user review converged on: unified interface, not unified implementation
- Key pivot: engine_ext is in-memory only (D5), not serialized — avoids deserialization protocol complexity
- Key pivot: annotation side-channel via Store pending state (D6), not module-level cache or wrapper return type
- Key pivot: v0 fact semantics frozen as attribute existence model (D7), matching tested code
- Key pivot: v0 only needs Derivation.engine_ext (D8), Rule.engine_ext deferred to v1

## Lineage

- Old D1 (EvaluateMode) → new D1 (unchanged)
- Old D2 (no engine_options) → new D2 (unchanged)
- Old D3 (WhereIR compiler) → new D3 (refined: attribute existence model per D7)
- Old D4a (engine_no_witness_v1) → new D4 (unchanged)
- Old D4b (annotation post-accept) → new D6 (Store pending state replaces cache/wrapper)
- New F1 → new D5 (engine_ext as independent kwarg)
- New F2 → new D6 (Store pending state)
- New F3 → new D7 (attribute existence model)
- New F4 → new D8 (Derivation.engine_ext only for v0)
- New F5 → new D9 (EDB default bounds)
