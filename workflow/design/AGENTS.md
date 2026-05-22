# Design Pillar Governance

Governs the `workflow/design/` pillar, which contains two sub-pillars: `design-points/` (conceptual essays) and `decisions/` (ADR-style discrete records). Codifies the state machines locked by Q2 (commit `ae375ce5`).

For the umbrella governance see `workflow/AGENTS.md`. For the canonical methodology see `workflow/CADENCE.md`.

## Layout

```
workflow/design/
├── README.md
├── AGENTS.md             (this file)
├── design-points/
│   ├── README.md
│   ├── active/           (iteratively-evolving essays)
│   └── archive/          (essays satisfying the 3-condition archive criteria)
└── decisions/
    ├── README.md
    ├── active/           (proposed + adopted ADR records)
    └── archive/          (superseded + withdrawn ADR records)
```

## Design-points sub-pillar

### Role
Conceptual design essays that articulate a design area iteratively over time. **Authority: candidate design / non-authoritative reference. Not current behavior.** A design-point becomes a constraint **only when cited by**:

- An adopted decision, OR
- An implemented blueprint, OR
- Current module docs (`src/factgraph/*/docs/`), OR
- `workflow/foundations/architecture_principles.md`

A design-point **cannot directly override shipped behavior**. Implementation must reach the codebase via the downstream consumption chain (decision → blueprint → impl).

### Lifecycle (per Q2 §4.3)

`active/` while the essay is iteratively evolving and may produce new questions / decisions / blueprints.

`archive/` when **all three** conditions hold:

1. All load-bearing questions raised by this design-point have been written into formal decisions in `workflow/design/decisions/`, AND those decisions have reached a closed ADR state (`adopted`, `superseded`, or `withdrawn`).
2. All implementation-eligible content drawn from this design-point has either shipped (referenced by an `implemented`-state blueprint in `workflow/blueprints/archive/`) or been explicitly deferred or superseded by a newer design-point.
3. No `active`-state blueprint cites this design-point as the live design lens for ongoing implementation.

A design-point may also be superseded by a newer essay (successor cites predecessor in `Inputs`; predecessor moves to `archive/` even if conditions 1-3 aren't all met).

Design-points do not require `Status` field transitions; iteration on an active essay is normal. The active/archive directory placement is the canonical lifecycle signal. `Status` may carry a drafting marker like `working` / `mature` / `n/a` for human convenience.

### Header convention

Every design-point file uses the 7-field metadata header per Q4 §4.3, with:

- `Authority: candidate design / non-authoritative reference`
- An adoption-status statement repeating the "becomes constraint only when cited by..." chain above

## Decisions sub-pillar (ADR 4-state, per Q2 §4.5)

### States

| Status | Meaning | Directory |
|---|---|---|
| `proposed` | Under deliberation; not yet a binding constraint | `active/` |
| `adopted` | **Current binding constraint**; downstream blueprints must honor | `active/` |
| `superseded` | Replaced by a newer decision (successor cited in Inputs) | `archive/` |
| `withdrawn` | Cancelled before or after adoption; cite rationale | `archive/` |

**Critical**: `adopted` decisions stay in `active/` because they are current constraints. Moving them to `archive/` would imply they no longer govern current behavior. This differs from `blueprints/` where `implemented` blueprints archive (the blueprint is historical rationale, not a current constraint).

### Allowed transitions

```
proposed → adopted      (via review closure)
proposed → withdrawn    (cancellation before adoption)
adopted  → superseded   (replaced; cite successor)
adopted  → withdrawn    (rare; explicit rationale)
```

### Not allowed

- `adopted → proposed` (re-opening; write a new decision that supersedes instead)
- `superseded → adopted` / `withdrawn → adopted` (write a new decision restoring the constraint)
- `proposed → superseded` (close as `withdrawn` first if never adopted)

### Directory mv on archive transition

A status transition crossing the active/archive boundary (`adopted` → `superseded` or `adopted` → `withdrawn`) is accompanied by `git mv` from `active/` to `archive/` in the same commit, plus the `Status:` field update.

## Trigger boundary between design-point and decision (per Q2 §4.7)

- **Design-point**: articulating a conceptual area, exploring tradeoffs, recording iterative reasoning. Multi-step; iterative; may evolve over weeks.
- **Decision**: locking a specific load-bearing question before downstream work can proceed. Discrete; closed; once `adopted` it is a binding constraint.

A decision may be written without a preceding design-point if the question is narrow enough to articulate from audit findings (e.g., Q-delta-decision pattern from Slice 7C).

## Templates

Authoritative starting points live in `workflow/templates/design/`:

- `design-point.md` — design-point essay template (includes the authority statement)
- `decision.md` — ADR decision template (includes the 4-state record)

Manual drafting (not from template) is discouraged; see `workflow/templates/README.md` §customization policy.

## See also

- `workflow/CADENCE.md` Stage 2 (Q-resolution phase) for how decisions integrate with the broader audit→Q→synthesis→blueprint flow
- `workflow/audit/AGENTS.md` for how the audit pillar's synthesis sub-type re-buckets decisions
