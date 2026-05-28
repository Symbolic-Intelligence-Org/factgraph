# Task Blueprint: T10-2-B PyReason Canonical Rule Params

- Status: scoped
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

### 3.1 Canonical Carrier Decision

Decision: use existing `SemanticsProfile.rule_projection["pyreason"]` entries
as the C74 profile carrier. Do not add top-level
`SemanticsProfile.derived_bound` or `SemanticsProfile.atom_bounds` fields.

Source-back:

- `SemanticsProfile` already has the global T10-2-A carrier
  `iteration_count` next to `engine_options`, `uncertainty_projection`,
  `temporal_projection`, and `rule_projection` (`profile.py:39-48`).
- `rule_projection` is the existing per-engine rule-annotation carrier
  (`profile.py:36, :46`) and its normalizer already accepts structured entries
  with non-empty `target` and `kind` (`profile.py:119-139`).
- Existing PyReason lowering emits legacy `head_bound` as `head:0 / interval`
  and `branch_bounds` as `branch:{index} / interval`
  (`sdk/store.py:3376-3385, :3435-3455`).
- Existing PyReason adapter consumption materializes `head:0`,
  `branch:{index}`, and `body_atom:{branch}:{atom}` entries into
  `PyReasonRuleExt` (`rule_ext.py:155-229`).

Rationale: C78 is global, so T10-2-A's top-level `iteration_count` was correct.
C74 is rule/atom-local, and the adapter already consumes rule-local entries
through `rule_projection`. Top-level C74 fields would duplicate this surface.

### 3.2 SDK Field Shape

Add public canonical fields to `PyReasonSemantics`:

- `derived_bound: tuple[float, float] | None = None`
- `atom_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)`

Validation policy:

- Reuse existing interval semantics: two numeric values, bool rejected, and
  `0 <= lower <= upper <= 1`.
- `atom_bounds` keys must be non-empty full atom ids using
  `<rule_id>:atom_<index>`.
- Error messages name `PyReasonSemantics.derived_bound` or
  `PyReasonSemantics.atom_bounds`, not legacy `head_bound`, `branch_bounds`,
  `iteration_count`, or `timestep_delay`.
- Normalize canonical and legacy fields independently, then apply conflict
  policy.

Source-back: public `PyReasonSemantics` currently exposes `timestep_delay`,
`iteration_count`, `head_bound`, `branch_bounds`, `rule_params`,
`temporal_projection`, and `uncertainty_projection`, but no C74 canonical fields
(`sdk/semantics.py:150-176`). Existing `head_bound` / `branch_bounds`
normalization is at `sdk/semantics.py:195-200`.

### 3.3 Atom-ID Conversion Layer

Decision: convert public full atom ids during SDK lowering, then emit existing
PyReason positional profile entries.

Source-back for the three conventions:

- Application Rule DTOs expose full atom ids as `<rule_id>:atom_<index>`
  (`application/protocol/rule.py:98-100`; `application/docs/rule.md:47-49`).
- PyReason profile targets are positional: `head:0`, `branch:{index}`,
  `body_atom:{branch}:{atom}`, and `rule` (`rule_ext.py:173-221`).
- T8-B witness support keys are evidence identifiers generated as
  `b{branch_index}.a{atom_index}:{pred_id}` (`core/store/_support.py:201-212`)
  and must not be reused for C74.

Conversion shape:

- Validate that `atom_bounds` keys use the current rule id and an integer atom
  index.
- For application `Rule` inputs, map `<rule_id>:atom_<index>` to
  `body_atom:0:{index}` because the SDK application Rule bridge accepts AND-only
  where bodies (`sdk/dsl/application_rule.py:85-91`).
- Extend the private `_SemanticsLoweringContext` with source-backed atom id
  information for application Rule inputs. The current context only carries
  name, branch indexes, known rule ids, and branch-specific allowance
  (`sdk/store.py:3357-3363, :3517-3534`), while application Rules expose the
  needed atom ids via `Rule.atom_ids` (`application/protocol/rule.py:98-100`).
- For legacy `Inference` / branched SDK inputs, do not invent a new full-atom-id
  surface in T10-2-B. Reject canonical `atom_bounds` unless lowering has an
  application full atom-id mapping. Legacy branch/position carriers remain
  available through `branch_bounds` and direct `SemanticsProfile.rule_projection`.

No adapter-side conversion is needed because the adapter already consumes
positional body atom targets and performs branch/atom validation
(`rule_ext.py:199-218, :245-290`).

### 3.4 SDK Lowering Path

Update both `_preview_public_semantics(...)` and `_lower_public_semantics(...)`
for `PyReasonSemantics`:

- If `derived_bound` is present, emit `head:0 / interval`.
- Else if legacy `head_bound` is present, emit the existing legacy entry.
- Preserve `branch_bounds` lowering to `branch:{index} / interval`.
- Convert each canonical `atom_bounds` full atom id to
  `body_atom:{branch}:{atom} / interval_threshold`.
- `_preview_public_semantics(...)` has no derivation context; it may parse the
  atom index for display-only `body_atom:0:{index}` preview entries, while
  `_lower_public_semantics(...)` performs authoritative rule-id and atom-count
  validation with the extended lowering context.
- Preserve T10-2-A `iteration_count=_pyreason_iteration_count_carrier(value)`
  unchanged (`sdk/store.py:3392, :3462, :3480-3484`).

Omission rule:

| Canonical fields | Legacy fields | Lowering behavior |
|---|---|---|
| default `derived_bound=None`, `atom_bounds={}` | empty legacy | emit no C74 entries |
| default canonical | `head_bound` / `branch_bounds` set | emit legacy entries only |
| canonical non-empty | legacy empty | emit canonical entries |
| canonical non-empty | conflicting legacy set | reject before emitting |

Source-back: current lowering builds `rule_entries` in both preview and runtime
paths before creating `rule_projection["pyreason"]`
(`sdk/store.py:3376-3393, :3435-3463`).

### 3.5 Adapter Consumption

No new adapter carrier is required. Leave `rule_ext.py` behaviorally stable
unless implementation tests reveal a small helper or wording need.

Source-back:

- `resolve_pyreason_engine_ext(...)` already prefers profile materialization over
  explicit `PyReasonRuleExt`, and rejects conflicting profile-vs-explicit
  carriers (`rule_ext.py:73-92`).
- `_materialize_profile_rule_ext(...)` already consumes `head:0`,
  `branch:{index}`, and `body_atom:{branch}:{atom}` entries and returns a
  `PyReasonRuleExt` (`rule_ext.py:155-229`).
- Duplicate positional targets already reject (`rule_ext.py:184-186,
  :194-205`), and body atom targets resolve to predicate ids without witness-key
  helpers (`rule_ext.py:206-218, :272-290`).

Thus "adapter consumption shipped" means the SDK emits the already-supported
adapter-local entries, and tests prove existing adapter consumption handles them.

### 3.6 Conflict Behavior And Compatibility Policy

Policy:

- `derived_bound` + `head_bound` explicitly supplied: reject. They lower to the
  same `head:0` target.
- `atom_bounds` + `branch_bounds`: allow coexistence with explicit tests.
  `atom_bounds` lowers to body-atom interval thresholds, while `branch_bounds`
  lowers to per-branch head intervals. Existing tests already prove global head
  and branch head bounds coexist (`tests/test_pyreason_branch_bounds_carrier.py:228-244`).
- `derived_bound` + `branch_bounds`: allow coexistence, matching existing
  global-head + branch-head behavior.
- Legacy `head_bound` and `branch_bounds` remain accepted through T10-3. T10-3
  may define deprecation/removal; T10-2-B only adds canonical spelling.
- No warnings are introduced; warning behavior is a separate API surface.

### 3.7 Test Matrix

Implementation tests should add focused coverage:

1. `PyReasonSemantics` accepts and normalizes `derived_bound` and `atom_bounds`.
2. Invalid intervals, bools, malformed atom ids, wrong rule id, and out-of-range
   atom indexes reject with canonical field names.
3. Lowering maps `derived_bound` to `head:0 / interval`.
4. Lowering maps `<rule_id>:atom_<index>` to
   `body_atom:0:{index} / interval_threshold` for application Rule-compatible
   inputs.
5. `derived_bound` + `head_bound` rejects.
6. `atom_bounds` + `branch_bounds` coexist and lower to distinct targets.
7. Legacy `head_bound` / `branch_bounds` tests remain passing.
8. T10-2-A `iteration_count` tests remain passing.
9. The T8-B witness-key helper is not imported or called by the C74 conversion.
10. Full discover compares against baseline `2019 tests / 72 failures /
    231 errors`.

Focused Step 4.6 baseline: the agreed four-module PyReason suite runs `84 OK`.
Adding `tests.test_pyreason_branch_bounds_carrier` exposes two pre-existing
C110 `meta[confidence]` errors; use that file as source context, not as a new
focused baseline gate for T10-2-B.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which canonical carrier should C74 use for `derived_bound` / `atom_bounds`? | Use existing `SemanticsProfile.rule_projection["pyreason"]` entries. Top-level C74 fields are rejected because C74 is rule/atom-local and adapter consumption already speaks rule projection. |
| Q2 | What SDK validation should canonical fields use, and how do they coexist with legacy fields? | Use existing interval validation semantics; require `<rule_id>:atom_<index>` keys; normalize canonical and legacy fields independently, then apply conflict policy. |
| Q3 | Where should atom-id conversion happen? | SDK lowering time. Extend private lowering context with application atom ids, then convert full ids to positional `body_atom:{branch}:{atom}` entries. Do not use T8-B witness keys. |
| Q4 | How should SDK lowering implement the omission rule? | Default canonical fields emit no C74 entries; legacy-only lowers as today; canonical-only lowers canonical entries; explicit duplicate head carriers reject. |
| Q5 | How should adapter consumption prioritize canonical vs legacy carriers? | No new adapter priority path. SDK lowering emits one set of adapter-local entries, and existing duplicate-target validation catches direct-profile conflicts. |
| Q6 | What is the conflict behavior for canonical + legacy pairs? | `derived_bound` + `head_bound` rejects. `atom_bounds` + `branch_bounds` is allowed because body atom thresholds and branch head intervals target different adapter fields. |
| Q7 | What is the legacy compatibility policy for `head_bound` / `branch_bounds`? | Both remain accepted through T10-3; no warning in T10-2-B. T10-3 owns any deprecation/removal policy. |
| Q8 | What is the focused test matrix? | Add canonical SDK/lowering/conversion/conflict/coexistence tests; keep four-module PyReason `84 OK`; compare full discover to `2019/72F/231E`. |
| Q9 | What is the implementation commit split? | Three implementation commits: SDK shell, lowering/conversion, tests. No adapter commit unless implementation discovers a small required helper. |
| Q10 | Does T10-2-B change the T8-C-2 unblock map? | It removes C74 only. C77 and D11/Form 2 remain required for T8-C-2 implementation. |
| Q11 | Are there behavior changes that need explicit closure notes? | No default behavior shift is expected. New dual `derived_bound`/`head_bound` input rejects, and `atom_bounds` is a new canonical SDK spelling. |
| Q12 | Are there stop/amend findings? | None. T10-2 inventory and T10-2-A decisions remain valid; no fourth atom-id convention or witness-key reuse need was found. |

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

Scoped candidate commits:

1. `feat(sdk): add PyReasonSemantics derived and atom bounds`
2. `feat(sdk): lower PyReason C74 bounds with atom conversion`
3. `test(pyreason): cover C74 canonical migration`
4. `docs(blueprint): close T10-2-B C74 migration`
5. `docs(blueprint): archive T10-2-B C74 migration`

The draft's profile/adapter commits are intentionally collapsed because Step 4.6
found that the existing `rule_projection["pyreason"]` carrier and adapter
consumption path already cover C74 once SDK lowering emits the correct entries.
This keeps anti-partial-ship intact: SDK shell, lowering/conversion, and tests
remain separate reviewable layers.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed plan completed.
- [x] Q1-Q12 answered.
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

Pending implementation / closure.
