# Task Blueprint: T10-2-B PyReason Canonical Rule Params

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: M (runtime implementation)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-2-b-pyreason-canonical-rule-params.audit.md`
- Trigger: T10-2 inventory archived at `f8e08905` selected the split
  T10-2-A C78 before T10-2-B C74 and locked three distinct atom-id
  conventions. T10-2-A shipped at `65cc79a3`, proving the canonical
  carrier/lowering/adapter-consumption pattern for PyReason and leaving C74 as
  the next hot PyReason canonical migration slice.

## 0. Scope Locks

### In scope

This is a runtime implementation cycle for C74 only.

1. SDK shell:
   - Add `PyReasonSemantics.derived_bound: tuple[float, float] | None = None`.
   - Add `PyReasonSemantics.atom_bounds: dict[str, tuple[float, float]]`.
   - Preserve legacy `head_bound` and `branch_bounds` fields until the
     compatibility policy is explicitly changed by this or a later cycle.
2. SDK lowering:
   - Lower canonical `derived_bound` and `atom_bounds` into the Step
     4.6-selected carrier.
   - Design the atom-id conversion layer from full application atom ids
     (`<rule_id>:atom_<index>`) to PyReason positional targets
     (`body_atom:{branch}:{atom}`, `branch:{index}`, or another source-backed
     target shape).
3. `SemanticsProfile` carrier:
   - Decide and implement canonical carrier placement for C74.
   - Candidate carriers include top-level fields such as
     `derived_bound` / `atom_bounds` or an explicit `rule_projection` extension.
   - Validate interval shape and values.
4. Adapter consumption:
   - Update `src/factgraph/adapters/pyreason/rule_ext.py` to consume canonical
     C74 carriers.
   - Prefer canonical C74 when present.
   - Preserve legacy `head_bound` / `branch_bounds` fallback according to the
     Step 4.6 compatibility policy.
5. Conflict behavior and compatibility policy:
   - `derived_bound` and legacy `head_bound` both explicitly supplied must not
     silently choose a winner.
   - `atom_bounds` and legacy `branch_bounds` both explicitly supplied must not
     silently choose a winner unless Step 4.6 records a source-backed exception.
   - Apply the T10-2-A omission-rule pattern where canonical defaults/empty
     values preserve legacy behavior.
6. Focused tests:
   - SDK fields and validation.
   - Lowering and atom-id conversion.
   - Profile carrier validation.
   - Adapter canonical consumption and legacy fallback.
   - Conflict rejection.
   - Omission-rule scenarios.
   - Existing `head_bound` / `branch_bounds` behavior.
   - T10-2-A `iteration_count` behavior.
   - Full discover composition comparison against `2019 / 72F / 231E`.

### Out of scope

- C77 temporal rename / `fact_boundaries` / `time_binned`; T10-3 owns temporal
  projection migration.
- C76 ProbLog / ProbLog adapter work; T10-1 already shipped it.
- T10-2-A C78 `iteration_count` behavior; do not weaken, redo, or roll it back.
- T8-C-2 PyReason evidence enrichment.
- Changes to T10-1, T8-C-1, or T8-D shipped behavior.
- D11 / Form 2 / Nemo / C119 / C136 / aggregate / failed graph / why-not /
  counterfactual / match witness.
- D20 / service / OpenAPI / Database/view / match API / `fg.eval.run` /
  release / PyPI / tags.
- `EvidenceGraph` DTO, 14-key metadata, `_FORM1_ROW_SUPPORT_KINDS`, or
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- T8-A 14-key validation, T8-B Form 1, T8-D round 1/2/3 user docs, or T10-1
  anti-silent-ignore behavior.
- Reusing the T8-B witness key namespace (`b<n>.a<n>:pred_id`) for C74
  canonical atom identity.
- C110 legacy `confidence` rejection.
- Audit module docs; T10-2-B changes adapter execution semantics, not evidence
  module behavior.
- User-facing docs; T8-D round 4 can follow after T10-2-A and T10-2-B ship.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`.
- Reopening T10-2 inventory Q1-Q8 or T10-2-A decisions. If implementation
  contradicts archived decisions, stop and amend the relevant archive instead
  of silently diverging.
- Absorbing or classifying any untracked design-point file.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

1. T10-2 inventory's C74 layer / field classification is materially wrong.
2. A fourth atom-id convention is discovered, or the three known conventions are
   actually the same source with different spellings.
3. SDK shell, lowering, carrier, or adapter consumption requires changing
   14-key metadata, `EvidenceGraph` DTO, or protocol evidence schemas.
4. The selected canonical carrier would break existing `SemanticsProfile` or
   `engine_options` invariants.
5. Conflict handling would require silent winner semantics instead of explicit
   rejection or a clearly recorded compatibility exception.
6. C74 atom-id conversion requires reusing the T8-B witness key namespace,
   violating T10-2 inventory Q3.
7. Runtime/test/user-doc/governance/sacred/dirty-baseline files outside this
   cycle's planned implementation surface need edits, or existing T10-2-A
   behavior would be weakened.

## 1. Problem

C74 defines canonical PyReason rule-parameter semantics that are only partially
shipped today. Legacy `head_bound` and `branch_bounds` work through positional
PyReason targets, but canonical `derived_bound` and full atom-id keyed
`atom_bounds` are missing. T10-2 inventory also found three distinct atom-id
conventions: application full atom ids (`<rule_id>:atom_<index>`), PyReason
positional profile targets (`head:0`, `branch:{index}`,
`body_atom:{branch}:{atom}`, `rule`), and T8-B witness keys
(`b<n>.a<n>:pred_id`). T10-2-B must add a conversion layer without conflating
those namespaces.

The implementation must avoid a partial ship: SDK shell, canonical carrier,
lowering/conversion, adapter consumption, compatibility policy, and tests must
land coherently.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md` | Parent inventory; C74 state, atom-id conventions, and split order. |
| `workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.audit.md` | Review/audit record for C74/C78 decisions and invariants. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | T10-2-A implementation precedent for optional top-level carrier, lowering, adapter consumption, and conflict testing. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C74 design anchor and C78/C77 boundary context. |
| `src/factgraph/sdk/semantics.py` | Public `PyReasonSemantics` shell. |
| `src/factgraph/sdk/store.py` | Public wrapper -> `SemanticsProfile` lowering and likely atom-id conversion site. |
| `src/factgraph/core/semantics/profile.py` | Candidate carrier location and validation substrate. |
| `src/factgraph/adapters/pyreason/rule_ext.py` | Adapter consumption of PyReason rule projection targets. |
| `src/factgraph/core/store/_support.py` | T8-B witness key helpers; must not be reused as C74 canonical atom ids. |
| `tests/test_pyreason_semantics_profile_migration.py`, `tests/test_pyreason_rule_ext.py`, `tests/test_pyreason_engine_eval.py`, `tests/test_pyreason_evidence_graph.py` | Focused PyReason regression and new C74 coverage. |

## 3. Step 4.6 Source-Backed Implementation Plan

Pending Step 4.6. Required subsections:

### 3.1 Canonical Carrier Decision

Compare:

- Option A: top-level `SemanticsProfile.derived_bound` and
  `SemanticsProfile.atom_bounds`.
- Option B: canonical entries inside `SemanticsProfile.rule_projection`.
- Option C: hybrid carrier, if source-backed by the existing adapter shape.

Step 4.6 must source-back validation impact, existing `rule_projection`
behavior, T10-2-A carrier precedent, and adapter consumption surface before
selecting.

### 3.2 SDK Field Shape

Decide:

- `PyReasonSemantics.derived_bound` shape and validation.
- `PyReasonSemantics.atom_bounds` key/value validation.
- How public errors distinguish canonical `derived_bound` / `atom_bounds` from
  legacy `head_bound` / `branch_bounds`.
- Whether SDK shell should normalize canonical and legacy fields independently
  before conflict policy is applied in lowering.

### 3.3 Atom-ID Conversion Layer

Source-back the three known conventions and decide where conversion happens:

- SDK lowering time.
- Adapter consumption time.
- Shared helper used by both, if needed.

The conversion design must not reuse T8-B witness keys.

### 3.4 SDK Lowering Path

Source-back exactly where `_preview_public_semantics(...)` and
`_lower_public_semantics(...)` should emit canonical carriers, how they coexist
with T10-2-A `iteration_count`, and how the omission rule preserves legacy
`head_bound` / `branch_bounds` users.

### 3.5 Adapter Consumption

Source-back `rule_ext.py` changes:

- Canonical-first consumption.
- Legacy fallback.
- Conversion responsibilities if not performed in SDK lowering.
- Error helper shape for explicit conflicts.

### 3.6 Conflict Behavior And Compatibility Policy

Decide:

- `derived_bound` + `head_bound`: reject vs compatibility exception.
- `atom_bounds` + `branch_bounds`: reject vs compatibility exception.
- Legacy acceptance horizon: T10-2-B vs T10-3 vs later.
- Omission-rule test scenarios.

### 3.7 Test Matrix

At minimum:

- SDK accepts/normalizes `derived_bound` and `atom_bounds`.
- SDK rejects invalid interval shapes and bad atom ids.
- Lowering converts full atom ids to PyReason positional targets or records a
  canonical carrier for adapter-side conversion.
- Adapter consumes canonical `derived_bound` / `atom_bounds`.
- Legacy `head_bound` / `branch_bounds` tests remain passing.
- Explicit conflicts reject.
- T10-2-A `iteration_count` tests remain passing.
- Full discover delta is compared against `2019 tests / 72 failures / 231
  errors`.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which canonical carrier should C74 use for `derived_bound` / `atom_bounds`? | Source-backed selection with tradeoffs and T10-2-A precedent. |
| Q2 | What SDK validation should canonical fields use, and how do they coexist with legacy fields? | Decide interval validation, key validation, and error wording. |
| Q3 | Where should atom-id conversion happen? | SDK lowering vs adapter consumption vs shared helper, with source refs. |
| Q4 | How should SDK lowering implement the omission rule? | Four scenario matrix for canonical defaults/empty maps plus legacy fields. |
| Q5 | How should adapter consumption prioritize canonical vs legacy carriers? | Canonical-first / legacy-fallback or alternate plan with rationale. |
| Q6 | What is the conflict behavior for canonical + legacy pairs? | Reject/winner/exception decision, with test expectations. |
| Q7 | What is the legacy compatibility policy for `head_bound` / `branch_bounds`? | Acceptance horizon and any deprecation/warning decision. |
| Q8 | What is the focused test matrix? | Concrete test list plus regression suite, including T10-2-A isolation. |
| Q9 | What is the implementation commit split? | Commit plan and anti-partial-ship rationale. |
| Q10 | Does T10-2-B change the T8-C-2 unblock map? | Expected: it removes C74 only; C77 and D11/Form 2 remain. |
| Q11 | Are there behavior changes that need explicit closure notes? | Identify default/compatibility changes, if any. |
| Q12 | Are there stop/amend findings? | None or explicit trigger with next action. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3 user docs.
- T10-1 C76 ProbLog semantics and anti-silent-ignore behavior.
- T10-2-A C78 `iteration_count`: SDK field, optional profile carrier, lowering
  omission rule, adapter consumption, conflict helpers, and error wording.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- T10-2 inventory Q1-Q8 decisions, especially the three atom-id conventions,
  the "do not reuse witness keys" boundary, the conversion-layer requirement,
  and Option C split.
- Existing `timestep_delay` behavior.
- Existing legacy `head_bound` / `branch_bounds` behavior unless Step 4.6
  records explicit compatibility policy.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "head_bound|derived_bound|atom_bounds|branch_bounds" src/factgraph workflow/design workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md
rg -n "body_atom|branch:|head:0|atom_<index>|make_pred_atom_key" src/factgraph tests
rg -n "PyReasonSemantics|class SemanticsProfile|_pyreason_iteration_count_carrier|_resolve_iteration_count" src/factgraph/sdk src/factgraph/core/semantics src/factgraph/adapters/pyreason
rg -n "head_bound|branch_bounds" tests/test_pyreason_semantics_profile_migration.py tests/test_pyreason_rule_ext.py
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. Carrier decision.
2. SDK validation decision.
3. Atom-id conversion plan.
4. Lowering and adapter implementation plan.
5. Conflict / compatibility policy.
6. Test matrix.
7. Commit split.
8. Stop/amend assessment.

## 7. Proposed Implementation Split

Candidate commits:

1. `feat(sdk): add PyReasonSemantics derived and atom bounds`
2. `feat(profile): add canonical PyReason C74 carriers`
3. `feat(sdk): lower PyReason C74 carriers with atom conversion`
4. `feat(pyreason): consume canonical C74 bounds`
5. `test(pyreason): cover C74 canonical migration`
6. `docs(blueprint): close T10-2-B C74 migration`
7. `docs(blueprint): archive T10-2-B C74 migration`

If Step 4.6 shows adjacent runtime changes are small, commits 1-2 or 3-4 may be
combined only if the audit records why the anti-partial-ship risk remains
controlled.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed plan completed.
- [ ] Q1-Q12 answered.
- [ ] SDK shell shipped.
- [ ] SDK lowering / carrier shipped.
- [ ] Atom-id conversion shipped without reusing T8-B witness keys.
- [ ] Adapter consumption shipped.
- [ ] Legacy `head_bound` / `branch_bounds` compatibility policy shipped.
- [ ] Canonical + legacy conflict behavior tested.
- [ ] Existing PyReason behavior preserved.
- [ ] T10-2-A behavior preserved.
- [ ] T8-A/B/C-1/D and T10-1 invariants preserved.
- [ ] T10-2 inventory decisions preserved.
- [ ] `git diff --check` clean.
- [ ] Focused PyReason tests pass.
- [ ] Full discover delta compared against `2019 tests / 72 failures / 231 errors`.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Planned implementation verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
python -m unittest discover tests
ruff check src/factgraph/sdk/semantics.py src/factgraph/sdk/store.py src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/rule_ext.py tests/test_pyreason_semantics_profile_migration.py tests/test_pyreason_rule_ext.py
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
