# Design-Points

Conceptual design essays. Iterative; user-completed in multiple steps over time; substantive but **not current behavior**.

## Authority boundary (per Q2 §4.4)

> A design-point is a **candidate design / non-authoritative reference**. It becomes a constraint **only when cited by**:
>
> - An adopted decision in `workflow/design/decisions/`, OR
> - An implemented blueprint in `workflow/blueprints/archive/`, OR
> - Current module docs at `src/factgraph/*/docs/`, OR
> - `workflow/foundations/architecture_principles.md`
>
> A design-point **cannot directly override shipped behavior**. Implementation must reach the codebase via the downstream consumption chain (decision → blueprint → impl).

Each essay's header includes a verbatim copy of this statement.

## Lifecycle

`active/` — currently-iterating. May produce new questions / decisions / blueprints over weeks to months.

`archive/` — moved when **all three** conditions hold (per Q2 §4.3):

1. All load-bearing questions raised by this design-point are closed in `workflow/design/decisions/` (any closed ADR state: `adopted` / `superseded` / `withdrawn`).
2. All implementation-eligible content has shipped (cited by an `implemented` blueprint) or been explicitly deferred / superseded.
3. No `active`-state blueprint cites this design-point as the live design lens.

A design-point may also be superseded by a newer essay (successor cites predecessor in `Inputs`; predecessor archived).

See [`workflow/design/AGENTS.md`](../AGENTS.md) for full state machine + authority semantics. Template: `workflow/templates/design/design-point.md`.
