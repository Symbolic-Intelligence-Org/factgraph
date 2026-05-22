# Decisions

ADR-style discrete decision records. Each decision locks one load-bearing design question before downstream blueprint / implementation can proceed.

## ADR 4-state lifecycle (per Q2 §4.5)

| Status | Meaning | Directory |
|---|---|---|
| `proposed` | Under deliberation; not yet binding | `active/` |
| `adopted` | **Current binding constraint**; downstream must honor | `active/` |
| `superseded` | Replaced by a newer decision | `archive/` |
| `withdrawn` | Cancelled; cite rationale | `archive/` |

**`adopted` decisions stay in `active/`** because they remain current constraints. Only `superseded` / `withdrawn` move to `archive/`. This differs from `workflow/blueprints/` where `implemented` blueprints archive (the blueprint is historical rationale; an adopted decision is a current rule).

## Index of currently-adopted decisions

(populated as decisions land)

## See also

- [`workflow/design/AGENTS.md`](../AGENTS.md) — full state machine, allowed transitions, archive mv convention.
- `workflow/templates/design/decision.md` — authoritative starting point for new decisions.
- `workflow/CADENCE.md` Stage 2 — Q-resolution phase in the broader audit→Q→synthesis→blueprint flow.
