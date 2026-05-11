# Task Blueprint Audit: Frozen Assertion View Model

- Blueprint: [2026-05-11_frozen-assertion-view-model.md](./2026-05-11_frozen-assertion-view-model.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Initial scope records candidate model: `View = named frozen assertion-id selection`; separates assertion collection, named view membership, and projection/conflict policy; source-grounding required before any implementation. |
| 2026-05-11 | draft | Frame: non-goals + problem framing | §3 Non-goals strengthened with frozen-only / no dynamic predicate / no runtime-integration first slice bullets. §1 Problem extended with framing: redefining long-term meaning of existing `fg.views`, not a parallel mechanism; current code split between `fg.views` registry and `project_view_facts(...)` is existing design debt not addressed in this slice. |
| 2026-05-11 | draft | §5.1 LOCKED | View identity locked: a FactGraph view is a named frozen assertion-id selection, not a subgraph, not a dynamic predicate, and not a projection policy. This redefines the long-term meaning of existing `fg.views` rather than creating a parallel mechanism; current `ViewSpec` remains legacy projection-policy compatibility pending §5.5 / §5.8. |
| 2026-05-11 | draft | §5.8 LOCKED | Existing `ViewSpec` registry behavior remains compatible in this blueprint. `fg.views.create/update(name, ViewSpec)`, `fg.read.find(..., view=...)`, and `fg.run(..., view=..., return_display_meta=True)` must keep current behavior. `ViewSpec` is documented as legacy projection-policy compatibility; any `ProjectionSpec` rename/migration is deferred. |
| 2026-05-11 | draft | §5.5 LOCKED | Projection policy split locked: view membership is the named visible assertion-id set; `confidence_strategy` / `prefer_source` are projection-policy concerns, not membership. First slice preserves existing `ViewSpec` behavior and defers any `ProjectionSpec` or runtime projection-option migration. |
| 2026-05-11 | draft | §5.7 LOCKED | Rule/runtime integration deferred. Frozen assertion views do not affect `fg.run(rule, view=...)` fact universe, `fg.evaluate(...)`, `project_view_facts(...)`, or application helpers in this slice; current display-meta behavior remains. Closing the SDK `fg.views` registry / core projector split requires a follow-up blueprint. |

## Decision Notes

Append key decisions chronologically, especially:

- scope freeze
- scope expansion or reduction
- implementation blocker
- source-grounding result that changes current view compatibility assumptions
- module docs sync completed
- archive completed
