# Task Blueprint Audit: Uncertainty Transmission Layer

- Blueprint: [2026-05-11_uncertainty-transmission-layer.md](./2026-05-11_uncertainty-transmission-layer.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Captures user research on possibility/probability transmission and maps it to current ProbLog, PyReason, Annotation Store, and SDK surfaces. |
| 2026-05-11 | draft | Scope sharpened | User clarified that the task is to address "formal unification is not semantic unification" and to adapt the report to existing project boundaries rather than adopt it wholesale. |
| 2026-05-11 | draft | Data/profile split proposed | User proposed replacing engine-specific data meta with `raw_kind` / `bound`, and carrying engine parameters plus transmission functions in `SemanticsProfile`. |
| 2026-05-11 | draft | PyReason temporal projection added | User proposed mapping business valid time into PyReason timesteps before inference and mapping results back afterward. |
| 2026-05-11 | draft | Storage placement clarified | `raw_kind` values should be lowercase; canonical raw uncertainty should be Annotation Store rows, not `meta_rows`. |
| 2026-05-11 | draft | Phase 1 narrowed | User agreed to start with data contract only and defer code until the workflow scopes it. |
| 2026-05-11 | draft | Compatibility relaxed | User clarified the project is not online, so historical uncertainty compatibility is not required. |

## Decision Notes

- 2026-05-11: Keep this blueprint in `draft`; no runtime code changes are scoped yet.
- 2026-05-11: Store the research as a non-authoritative design-point note under `docs/references/working/design-points/` so future implementation work can cite it without treating it as current behavior.
- 2026-05-11: The durable project direction is semantic-boundary preservation. Reuse the current Annotation Store, adapter lanes, and candidate confidence boundaries; do not collapse probability, possibility, certainty, and hard constraints into one algebra.
- 2026-05-11: Preferred shape is a clean data/profile split: data-layer `raw_kind` / `bound` / `valid_from` / `valid_to`, runtime `SemanticsProfile` for projection and engine-specific options.
- 2026-05-11: PyReason `active_from` / `active_to` should remain adapter-local integer coordinates. Business `valid_from` / `valid_to` should be the stored temporal contract, projected into timesteps per run.
- 2026-05-11: Use lowercase raw kinds (`probabilistic`, `possibilistic`). Store canonical raw uncertainty under `shared/semantic/raw_kind` and `shared/semantic/bound`; `meta` may remain an SDK input convenience, while `meta_rows` stay compatibility material.
- 2026-05-11: Phase 1 will only add `raw_kind` / `bound` data contract support. It should not change ProbLog export, PyReason materialization, candidate confidence, or SemanticsProfile runtime projection.
- 2026-05-11: Do not preserve `probability`, `bound_lower`, or `bound_upper` as parallel user-facing uncertainty write contracts. They may remain internal adapter projection outputs until later phases replace engine materialization.
