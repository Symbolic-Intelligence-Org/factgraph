# Q2 Decision: design pillar structure

- Status: adopted
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: design constraint; locks the internal structure, naming, lifecycle, and authority semantics of the `workflow/design/` pillar before Q4 templates and the Phase 1.5 `design/AGENTS.md` author work.
- Inputs:
  - [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](../../../audit/active/2026-05-22_workflow-governance-vs-shipped.md) §3.1 A4, A5; §3.2 I9, I12; §4 Q2
  - [Q1 decision](./2026-05-22_q1-docs-workflow-split.md) — split scope locked; `workflow/design/` exists as a pillar
  - 2026-05-22 design conversation: user lock of design-points naming + 3-condition archive + ADR 4-state semantics with adopted-stays-active
- Outputs / Downstream:
  - [Q4 decision](./2026-05-22_q4-template-centralization.md) — design pillar templates encode Q2 §4.3 + §4.5 state machines
  - [Q5 decision](./2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md) — AGENTS hierarchy locks `workflow/design/AGENTS.md` content per Q2
  - `workflow/design/AGENTS.md` (Phase 1.5)
  - `workflow/templates/design/design-point.md` + `decision.md` (Phase 1.5)
  - Implementing blueprint Phase 2 (decisions mv) + Phase 6 (design-points mv)
- Related:
  - [Q3 decision](./2026-05-22_q3-audit-pillar-structure.md) — parallel pillar; audit synthesis sub-type depends on Q2 ADR semantics
  - [docs/references/working/design-points/readme.md](/Users/zhenzhili/hnsm-backend/docs/references/working/design-points/readme.md) — current partial authority statement to be strengthened during mv
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`

> **Status note**: this decision is opened with `Status: proposed`. ADR 4-state semantics (defined in §4.5 below) are first formally introduced by **this** Q2 decision. Q5 will codify how those ADR states apply across the canonical `workflow/design/decisions/` pillar and govern the Q1-Q5 batch status flip. Until then, Q2 itself uses `proposed` consistent with the Q-ordering convention chosen by the user.

## 1. Inputs

- Audit §3.1 A4 — "`workflow/design/design-points/{active,archive}/`" classified `(b) small gap`; current `docs/references/working/design-points/` has 6 essays without active/archive split.
- Audit §3.1 A5 — "`workflow/design/decisions/{active,archive}/` with ADR 4-state semantics" classified `(c) shape conflict`; current `docs/decisions/` has 8 flat files, no state machine.
- Audit §3.2 I9 — "ADR 4-state decision semantics" classified `(d) genuinely new`; not defined anywhere prior to this slice.
- Audit §3.2 I12 — "design-point authority boundary explicit" classified `(b) small gap`; current `docs/references/working/design-points/readme.md` partially addresses, needs strengthening.
- Audit §4 Q2 — conversational locks summarized: keep `design-points` name; 3-condition archive criteria; decisions ADR 4-state (proposed / adopted / superseded / withdrawn) with only superseded + withdrawn → archive; design-point authority boundary statement.
- 2026-05-22 design conversation: user review explicitly corrected an initial simple `active/archive` proposal for decisions, locking ADR semantics with "adopted stays in active because it is the current constraint".
- Existing [docs/references/working/design-points/readme.md](/Users/zhenzhili/hnsm-backend/docs/references/working/design-points/readme.md) — partial authority statement to be strengthened in the migrated `workflow/design/design-points/README.md`.
- Q1 decision (split scope locks `workflow/design/` placement under `workflow/`).

## 2. Scope

This decision locks:

- The internal structure of `workflow/design/` (two sub-pillars).
- The naming of the design-points sub-pillar (`design-points/`, not "research" or other rename).
- The lifecycle and 3-condition archive criteria for design-points.
- The authority boundary that design-points are **not current behavior**.
- The ADR 4-state lifecycle for decisions (`proposed` / `adopted` / `superseded` / `withdrawn`).
- The directory placement rule for each decision state (`active/` holds `{proposed, adopted}`; `archive/` holds `{superseded, withdrawn}`).
- The triggering boundary between writing a design-point vs writing a decision.

## 3. Non-scope

- Template body structure for design-points and decisions (covered by Q4).
- The 4-level AGENTS hierarchy and which AGENTS file codifies the state machines authored here (covered by Q5; though the relevant file is `workflow/design/AGENTS.md` per Q5 lock-in plan).
- Cross-pillar trigger conditions linking design-points → audit → decisions → blueprint (covered by Q5 soft-trigger flow).
- Migration ordering of existing 6 design-points and 8 decisions into the new pillar (covered by the implementing blueprint's Phase 2 low-cardinality mv plan and Phase 6 design-points mv plan).
- Retrofit **execution details** for existing decisions: Phase 2 mv mechanics, backfilled Decision Record row format, exact commit ordering, mv batching — all covered by the implementing blueprint, not by Q2. The **design constraint** that the 8 existing closed DB/view decisions receive `Status: adopted` at mv time is IN scope of this Q2 decision and is recorded as a constraint in §7.3 + an acceptance gate in §8 item 2.

## 4. Decision

### 4.1 design pillar layout

The `workflow/design/` pillar contains exactly two sub-pillars:

```
workflow/design/
├── README.md                          (introduces both sub-pillars + their interplay)
├── AGENTS.md                          (state machines for both — authored in Phase 1.5)
├── design-points/
│   ├── README.md                      (essay-lifecycle conventions; strengthened authority statement)
│   ├── active/                        (currently-iterating essays)
│   └── archive/                       (essays whose 3 archive conditions are satisfied)
└── decisions/
    ├── README.md                      (ADR conventions; index of adopted decisions)
    ├── active/                        (proposed + adopted decisions)
    └── archive/                       (superseded + withdrawn decisions)
```

No other sub-pillar is added under `design/` in this slice.

### 4.2 design-points naming

The directory is named **`design-points/`**, not "research", not "concepts", not any other rename candidate. Rationale:

- `design-points` is already a project-canonical term used in 30+ MEMORY entries, multiple blueprints, and the audit doc itself.
- Each file in this directory focuses on **one specific design point** (entity coordinate semantics, uncertainty transmission, certainty projection, etc.), so the plural form is semantically accurate.
- Renaming would introduce translation cost across decisions, blueprints, and auto-memory pointers with no compensating clarity gain.

### 4.3 design-points lifecycle and 3-condition archive criteria

A design-point file's lifecycle differs from a blueprint's:

- **Blueprint**: scope-frozen at `scoped`, implementation lifetime is days to weeks, archived immediately on implementation completion.
- **Design-point**: iteratively written by the user over weeks to months; remains a live reference lens as long as it informs ongoing design work.

A design-point is **archived only when all three conditions hold**:

1. All load-bearing questions raised by this design-point have been written into formal decisions (`workflow/design/decisions/`), **AND** those decisions have reached a closed ADR state (`adopted`, `superseded`, or `withdrawn`).
2. All implementation-eligible content drawn from this design-point has either:
   - Shipped (referenced by an `implemented`-state blueprint in `workflow/blueprints/archive/`), OR
   - Been explicitly deferred or superseded by a newer design-point.
3. No `active`-state blueprint cites this design-point as the live design lens for ongoing implementation.

When all three hold, the design-point is moved to `archive/` with no content change (no status field flip; the act of moving is the archive event). The file may continue to be cited as historical rationale.

A design-point may also be **superseded by a newer design-point**. The successor must cite the predecessor in its Inputs section, and the predecessor is moved to `archive/` even if conditions 1-3 are not fully met (supersession is itself a closure trigger).

Design-points do **not** require Status field transitions; iteration on an active design-point is normal. The active/archive distinction is the only state distinction.

### 4.4 design-points authority boundary

Each design-point file must include in its header:

```
- Authority: candidate design / non-authoritative reference
- Adoption status: not current behavior; becomes constraint only when cited by an adopted decision, an implemented blueprint, current module docs (src/factgraph/*/docs/), or workflow/foundations/architecture_principles.md
```

**Critical rule**: a design-point cannot directly override shipped behavior. Implementation code must reach the codebase via the downstream consumption chain (decision → blueprint → implementation), not by direct reference to a design-point. This rule will be codified in `workflow/design/AGENTS.md` (Phase 1.5) and enforced by reviewer practice.

The current [docs/references/working/design-points/readme.md](/Users/zhenzhili/hnsm-backend/docs/references/working/design-points/readme.md) partially declares this boundary ("non-authoritative reference"). The migrated `workflow/design/design-points/README.md` and `workflow/design/AGENTS.md` will strengthen the statement with explicit consumption-chain wording per the above.

### 4.5 decisions ADR 4-state lifecycle

A `workflow/design/decisions/` file has exactly one of four `Status:` values at any time:

| Status | Meaning | Directory |
|---|---|---|
| **`proposed`** | Under deliberation; not yet a binding constraint. Downstream work may treat the decision as candidate guidance but must not depend on it. | `active/` |
| **`adopted`** | Current binding constraint. Downstream blueprints and implementations must honor it. | `active/` |
| **`superseded`** | Replaced by a newer decision. The superseding decision must cite this predecessor in its Inputs. No longer a constraint. | `archive/` |
| **`withdrawn`** | Cancelled before adoption, or rescinded after adoption with explicit rationale. No longer a constraint. | `archive/` |

Allowed transitions:

```
proposed → adopted      (via review closure; the canonical promotion path)
proposed → withdrawn    (cancellation before adoption)
adopted  → superseded   (replaced by newer decision; cite successor)
adopted  → withdrawn    (rare; rescinded with explicit rationale)
```

Not allowed:

- `adopted` → `proposed` (re-opening a closed decision; instead, write a new decision that supersedes it).
- `superseded` → `adopted` (un-supersede; instead, write a new decision restoring the constraint).
- `withdrawn` → `adopted` (un-withdraw; instead, write a new decision restoring the constraint).
- Skipping `adopted` (going from `proposed` directly to `superseded` is not a valid transition; close as `withdrawn` first if it was never adopted).

### 4.6 directory placement rule

- `workflow/design/decisions/active/` holds files with `Status: proposed` **or** `Status: adopted`.
- `workflow/design/decisions/archive/` holds files with `Status: superseded` **or** `Status: withdrawn`.

The reason `adopted` stays in `active/`: an adopted decision is a **current binding constraint**. Moving it to `archive/` would imply it no longer governs current behavior, which is incorrect. This is the principal semantic difference between this pillar and `workflow/blueprints/` (where `implemented` blueprints move to `archive/` because the implementation event is complete and the blueprint is historical rationale, not a current constraint).

A Status transition that crosses the active/archive boundary (`adopted` → `superseded` or `adopted` → `withdrawn`) is accompanied by a `git mv` from `active/` to `archive/` in the same commit, plus the `Status:` field update.

### 4.7 trigger boundary between design-point and decision

When deciding whether to write a design-point or a decision:

- **Design-point**: when articulating a conceptual area, exploring tradeoffs, or recording iterative reasoning that has not yet crystallized into specific load-bearing questions. Multi-step; iterative; may evolve over weeks.
- **Decision**: when a specific load-bearing question must be locked before downstream work can proceed. Discrete; closed; once `adopted` it is a binding constraint.

Typical flow:

```
design-point essay
   ↓ (raises question Q1)
audit (vs-shipped)
   ↓ (confirms gap or shape conflict)
decision (proposed → adopted)
   ↓ (locks constraint)
blueprint §4 lock table cites the decision
   ↓
implementation
```

A decision may be written without a preceding design-point if the question is narrow enough to articulate directly from audit findings (the Q-delta-decision multi-sub-issue lock pattern from Slice 7C is an example).

A design-point may produce zero decisions if its reasoning leads only to deferred direction or supersession of an earlier design-point.

## 5. Rejected Alternatives

### Option (a-rename): Rename `design-points/` to "research"

- **Why rejected**: "research" suggests external or exploratory work; design-points are internal, conceptually complete (per user characterization "完整, 由用户多步骤逐渐完成"). The semantic mismatch would mislead readers.

### Option (b-rename): Rename `design-points/` to "concepts"

- **Why rejected**: "concepts" is too abstract; design-points are concrete documents anchored to specific named concerns (`identity-primary-key-coordinate-semantics`, `possibility-probability-transmission`, etc.). The current name is more precise.

### Option (c-lifecycle): Treat design-points like blueprints (active → archive on implementation completion)

- **Why rejected**: design-points may persist as ongoing reference lenses long after the first implementation references them. Forcing archive on first implementation would prematurely terminate iterative reasoning. The 3-condition archive criteria preserves design-point lifetime to match its actual role.

### Option (d-states): Use 2-state lifecycle for decisions (active/archive only, no ADR semantics)

- **Why rejected**: conflates "adopted constraint" with "implemented event". Without ADR semantics, downstream blueprints have no way to distinguish a current binding constraint from a historical decision that has been superseded. The 4-state ADR model is the minimum to preserve this distinction.

### Option (e-states): Use 8-state lifecycle for decisions (mirror blueprints)

- **Why rejected**: over-engineering. Decisions do not have implementation phases (draft / scoped / implementing); they are deliberation followed by adoption followed by optional supersession. The 4-state ADR model is the minimum that covers the actual decision lifecycle.

### Option (f-placement): Move `adopted` decisions to `archive/` along with `superseded` and `withdrawn`

- **Why rejected**: `adopted` decisions are current binding constraints; moving them to `archive/` would semantically imply they no longer govern current behavior, contradicting their actual role. This was the principal user review correction that led to the locked decision in §4.6.

## 6. Supporting Evidence

- Audit §3.1 A4 (design-points small gap) — confirms `active/archive` split is a structural extension, not a content rewrite.
- Audit §3.1 A5 (decisions shape conflict) — confirms current `docs/decisions/` "Status: closed" informal convention is shape-incompatible with ADR semantics.
- Audit §3.2 I9 (ADR 4-state genuinely new) — confirms no prior implementation of these semantics anywhere.
- Audit §3.2 I12 (design-point authority boundary small gap) — confirms strengthening is needed but the foundational statement already exists.
- [/docs/references/working/design-points/readme.md](/Users/zhenzhili/hnsm-backend/docs/references/working/design-points/readme.md) — current partial authority statement.
- 2026-05-22 design conversation: user review explicitly corrected my initial "active/archive only" proposal for decisions; the ADR 4-state lock in §4.5 reflects that correction verbatim.
- Slice 7C Q-delta-decision multi-sub-issue lock pattern — validated that decisions can lock multiple sub-issues in a single document; relevant to §4.7 triggering boundary.

## 7. Consequences

### 7.1 Downstream unblocking

- A4, A5, I9, I12 in audit triage are formally closed by this decision.
- Q4 (templates) can proceed with concrete state-field requirements for both design-point and decision templates.
- Q5 (cadence as primary + AGENTS hierarchy) can codify state machines in `workflow/design/AGENTS.md` (Phase 1.5 of the implementing blueprint) by referencing this decision.

### 7.2 Required follow-up actions in the implementing blueprint

- **Phase 1.5 (AGENTS authoring)**: `workflow/design/AGENTS.md` codifies both state machines verbatim from §4.3 + §4.4 + §4.5 + §4.6 + §4.7.
- **Phase 2 (low-cardinality mv) — existing 8 decisions migration**: each migrated decision file is assigned `Status: adopted` (since they were already closed in their original slices). The implementing blueprint records this retrofit policy in its §10 outcome.
- **Phase 6 (design-points mv) — existing 6 design-points migration**: each migrated essay receives the strengthened authority header per §4.4. No state field flip is required (design-points have no Status transitions, only active/archive).
- **Phase 4 (validator)**: validator enforces decision Status whitelist (`proposed | adopted | superseded | withdrawn`) and active/archive directory placement rule per §4.6.

### 7.3 Existing decision retrofit clarification

The 8 existing decisions (Q1-Q8 from 2026-05-20 DB/view audit) currently in `docs/decisions/` are functionally `adopted` constraints — they were closed in their respective slices and have downstream blueprint citations. The implementing blueprint will:

- Assign `Status: adopted` to all 8 at mv time (Phase 2).
- Backfill each `Decision Record` table with a single retrofit row noting the original closing-commit date and reason for the assigned state, separate from the ADR semantics introduced in this Q2 slice.

This retrofit is a one-time operation; future decisions (including the Q1-Q5 of this slice) will follow the ADR transitions from inception.

### 7.4 Q1-Q5 status batch flip (cross-Q operational note)

After Q5 closes (which itself adopts the ADR semantics introduced here), a single batch commit will flip Q1-Q5 status from `proposed` to `adopted` per the user-locked Q-ordering convention. This batch flip is documented in the implementing blueprint §10 deviations as an explicit cadence note, since it is the first formal use of the ADR 4-state semantics introduced by this very decision.

## 8. Acceptance Criteria

Post-implementing-blueprint, the design pillar must satisfy:

1. `workflow/design/design-points/{active,archive}/` exist; `active/` contains the 6 migrated essays, each carrying the strengthened authority header per §4.4.
2. `workflow/design/decisions/{active,archive}/` exist; `active/` contains the 5 newly-authored Q1-Q5 decisions (post-batch-flip status `adopted`) plus the 8 retrofitted Q1-Q8 decisions (also `adopted`).
3. `workflow/design/AGENTS.md` exists and codifies §4.3-4.7 state machines and rules verbatim or with semantic equivalence.
4. `workflow/design/design-points/README.md` and `workflow/design/decisions/README.md` exist and explain the lifecycle without re-introducing state machine ambiguity (deference to `AGENTS.md`).
5. Validator (Phase 4) passes:
   - Every file in `workflow/design/decisions/active/` has `Status:` ∈ `{proposed, adopted}`.
   - Every file in `workflow/design/decisions/archive/` has `Status:` ∈ `{superseded, withdrawn}`.
   - Every design-point file has the §4.4 authority header line.
6. No design-point file directly overrides shipped behavior (verified by reviewer practice; not automatable).

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-22 | proposed | Decision drafted | Q2 of 5; first decision to define ADR 4-state semantics for this slice's design pillar |
| 2026-05-22 | adopted | Status flip + header retrofit via Q1-Q5 batch commit | Header retrofitted to Q4 §4.3 7-field schema: added `Last Updated` / `Outputs / Downstream` / `Related`; recast `Audit source` and peer `Depends on` (Q1) as `Inputs:` bullets; `Branch` preserved as extension. |

This decision will not be acted upon (no mv operations on design-points or decisions) until **all five Q decisions are closed and the implementing blueprint reaches `Status: scoped`**.
