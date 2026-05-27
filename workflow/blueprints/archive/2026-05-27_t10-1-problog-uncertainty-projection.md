# Task Blueprint: T10-1 ProbLog Uncertainty Projection

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t10-1-problog-uncertainty-projection.audit.md`
- Trigger: T10 inventory selected staged hybrid execution and identified T10-1 C76 ProbLog as the first implementation slice that fully unblocks T8-C-1 ProbLog evidence enrichment.

## 0. Scope Locks

### In scope

This is the T10-1 runtime implementation cycle for C76 ProbLog uncertainty
projection. It should ship the three promised C76 layers together, or explicitly
stop if Step 4.6 finds the shipped state differs from the T10 inventory.

Candidate implementation scope:

1. Source-backed inventory of C76's current three-layer state:
   `ProbLogSemantics` SDK shell, lowering to `SemanticsProfile`, and ProbLog
   adapter consumption of `raw_kind + bound`.
2. Source-backed diagnosis of the two pre-existing ProbLog migration errors
   from legacy `meta[confidence]` fixture writes.
3. Decision on whether the fixture drift is part of T10-1 scope, a prerequisite
   micro-fix, or a known unrelated baseline.
4. Add a `ProbLogSemantics.uncertainty_projection` SDK field if Step 4.6
   confirms the shell is missing.
5. Lower the SDK field into the existing
   `SemanticsProfile.uncertainty_projection` substrate without redesigning the
   substrate.
6. Make the ProbLog adapter consume uncertainty projection for `raw_kind` /
   `bound` inputs according to the scoped policy decision.
7. Focused tests for SDK field construction, lowering, adapter consumption,
   default policy behavior, explicit policy behavior, and existing
   branch-probability regressions.

### Out of scope

- T8-C-1 ProbLog evidence enrichment. T10-1 only ships adapter execution
  semantics; evidence enrichment remains a later cycle.
- T10-2 C74/C78 PyReason work and T10-3 C77 PyReason temporal work.
- PyReason, Souffle, or native adapter behavior changes.
- User-facing quickstart / SDK user-guide updates that would imply ProbLog
  row-level Form 1 evidence is shipped.
- Audit module docs unless Step 4.6 finds a shipped evidence-module contract
  change, which is not expected.
- D20 match witness, failed graph, why-not, counterfactual, service/OpenAPI,
  Database/view, match API, `fg.eval.run`, release, PyPI, tags, or dirty
  baseline cleanup.
- `EvidenceGraph` DTO changes, top-level 14-key metadata changes, or C110
  raw-kind/bound carrier changes.
- Weakening `write_protocol._validate_no_removed_uncertainty_keys(...)` legacy
  `confidence` rejection.
- Weakening T8-A / T8-B / T8-D shipped invariants.
- Governance / workflow files.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- C76's three-layer gap is materially narrower than T10 inventory reported.
- The two ProbLog migration errors are runtime bugs rather than fixture drift.
- Adapter consumption requires redesigning `SemanticsProfile.uncertainty_projection`.
- The implementation needs to weaken C110, the 14-key metadata contract, or
  legacy `confidence` rejection.
- T10-1 cannot fully ship C76's SDK shell, lowering, and adapter consumption in
  one coherent slice.
- Any governance, runtime-unrelated user docs, dirty-baseline, or sacred-master
  edit appears necessary.

## 1. Problem

T10 inventory found that C76 is the narrowest direct unblocker for T8-C-1, but
only the generic core `SemanticsProfile.uncertainty_projection` substrate is
currently present. The C76-specific SDK shell, SDK lowering, and ProbLog adapter
consumption are reported missing.

The main implementation risk is a partial ship: exposing an SDK field without
lowering, or lowering without adapter consumption, would make
`uncertainty_projection` look configured while silently doing nothing. This
cycle should either ship all three layers or stop with a clear reason.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md` §3.2 / §3.4 / §3.5 | T10-1 split decision, C76 per-layer state, and T8-C-1 unblock rule. |
| `workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.audit.md` | Baseline verification and two pre-existing ProbLog migration errors. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1601` | C76 design commitment and v1 default reject schema. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` C110 | Canonical `raw_kind` + `bound` uncertainty carrier. |
| `src/factgraph/sdk/semantics.py` | `ProbLogSemantics` SDK shell target. |
| `src/factgraph/sdk/store.py` | ProbLog semantics lowering target. |
| `src/factgraph/core/semantics/profile.py` | Existing `SemanticsProfile.uncertainty_projection` substrate. |
| `src/factgraph/adapters/problog/engine_eval.py` | ProbLog adapter evaluation and consumption target. |
| `src/factgraph/adapters/problog/rule_ext.py` | Existing ProbLog rule probability extension path. |
| `src/factgraph/core/evidence/write_protocol.py` | C110 write-time rejection of removed uncertainty keys. |
| `tests/test_problog_semantics_profile_migration.py` | Existing ProbLog semantics tests and reported fixture drift. |

## 3. Step 4.6 Inventory Results

### 3.1 Reviewer finding verification

| Finding | Source-backed result | Decision impact |
|---|---|---|
| Two ProbLog migration errors are fixture drift | Running `PYTHONPATH=src python -m unittest tests.test_problog_semantics_profile_migration` yields exactly two errors, both from `_make_sdk()` fixture writes at `tests/test_problog_semantics_profile_migration.py:160-172` using `meta={"confidence": 1.0}`. `src/factgraph/core/evidence/write_protocol.py:268-274` rejects `confidence` with "Use raw_kind / bound for uncertainty inputs." | Treat as C110 fixture drift, not runtime bug. Fix inside T10-1 as first implementation commit so the ProbLog semantics suite becomes a useful regression baseline. |
| C76 SDK shell missing | `src/factgraph/sdk/semantics.py:73-114` defines `ProbLogSemantics` with `branch_probabilities`, `rule_params`, `name`, and `fallback`; no `uncertainty_projection` field. | Add `ProbLogSemantics.uncertainty_projection` in T10-1. |
| C76 lowering missing | `src/factgraph/core/semantics/profile.py:43,66-77,128-147` already normalizes `SemanticsProfile.uncertainty_projection`, but ProbLog lowering at `src/factgraph/sdk/store.py:3385-3414` returns a profile with only `rule_projection` and `fallback`. | Lower the SDK field into the existing substrate; do not redesign `SemanticsProfile`. |
| C76 adapter consumption missing | `src/factgraph/adapters/problog/engine_eval.py:45-51` passes only `semantics_profile` to `resolve_problog_engine_ext(...)`; `src/factgraph/adapters/problog/rule_ext.py:72-117` consumes rule-projection branch probabilities only. `src/factgraph/adapters/problog/problog_export.py:82-100,124-169` materializes fact probabilities from engine-specific/shared `probability` annotations or defaults to `1.0`; it does not read `raw_kind` / `bound`. | Add adapter consumption in the ProbLog export/probability materialization path, where fact probabilities are written into the `.pl` program. |

### 3.2 C76 design anchors

| Anchor | Finding |
|---|---|
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1360-1418` | `ProbLogSemantics` should gain `uncertainty_projection`; schema must follow `SemanticsProfile._normalize_uncertainty_projection`; default rejects `probabilistic` and `possibilistic`; midpoint-like choices require explicit opt-in; all three layers must ship. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1599-1601` | C75 says both `PyReasonSemantics` and `ProbLogSemantics` have `uncertainty_projection`; C76 defines the schema and three-layer promise. |
| `src/factgraph/core/semantics/profile.py:10-21` | Generic policy vocabulary already includes `identity_probability`, `probability_interval`, `possibility_interval`, `lower`, `midpoint`, `upper`, and `reject`; fallback vocabulary already includes `reject_unconfigured`, `warn_default`, and `use_default`. |

### 3.3 Scoped decisions

| Topic | Selected decision | Rationale |
|---|---|---|
| Fixture drift | Include in T10-1. | It is a local test-fixture C110 migration issue in the same ProbLog semantics suite; leaving it failing would make T10-1 verification noisy. It does not require weakening runtime `confidence` rejection. |
| SDK field shape | Use the same schema as `SemanticsProfile.uncertainty_projection`. | C76 explicitly says the SDK schema strictly follows the `SemanticsProfile` normalizer; a simplified wrapper shape would add translation complexity and new drift surface. |
| Default lowering | `ProbLogSemantics()` lowers the C76 default reject projection: `{"probabilistic": {"policy": "reject"}, "possibilistic": {"policy": "reject"}, "fallback": "reject_unconfigured"}`. | C76 defines conservative reject as the v1 default. Empty profile would recreate silent-ignore risk for raw uncertainty rows. |
| Adapter consumption | ProbLog export must apply the projection when a fact has `shared/semantic/raw_kind` + `shared/semantic/bound` annotations. `reject` raises a `ProbLogExportError`; supported point-projection policies materialize a point probability. | The adapter's probability decision point is `_claim_probability(...)` in `problog_export.py`; explicit reject avoids silently ignoring raw uncertainty. |
| v1 policy support | Support `reject`, `lower`, `midpoint`, and `upper` for both raw kinds. Support `identity_probability` only for probabilistic degenerate intervals `[p, p]`. Reject `probability_interval` and `possibility_interval` in ProbLog v1 because ProbLog export needs a point probability. | This honors the C76 "midpoint requires explicit opt-in" rule while avoiding false support for interval-valued policies that cannot be represented as a ProbLog point probability. |
| Low-level `SemanticsProfile` default | If callers pass a raw `SemanticsProfile(engine="problog")` with empty `uncertainty_projection`, adapter consumption should use the same C76 default reject projection for raw uncertainty rows. | C76 is an adapter semantics commitment, not only an SDK-wrapper convenience; direct profile callers should not get silent ignore. |
| Docs | No user-facing or audit docs update in this cycle. | T10-1 changes adapter execution semantics only. ProbLog row-level Form 1 evidence remains deferred until T8-C-1. |
| T8-C-1 unblock | Full T10-1 ship unblocks T8-C-1 ProbLog from the C76 side, but T8-C-1 still needs its own evidence-enrichment blueprint before runtime evidence changes. | Matches T10 inventory: T8-C-1 requires full C76, not partial. T10-1 is prerequisite, not the evidence implementation itself. |

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Should the two ProbLog migration errors be fixed inside T10-1, before T10-1, or left as known drift? | Include in T10-1 as the first implementation commit. They are test-fixture C110 drift in `tests/test_problog_semantics_profile_migration.py:160-172`, not runtime behavior to preserve. Closure baseline should show these two errors fixed. |
| Q2 | What is the verified C76 three-layer current state? | SDK shell missing, lowering missing, adapter consumption missing; only generic core `SemanticsProfile.uncertainty_projection` substrate ships. See §3.1. |
| Q3 | What SDK field shape should `ProbLogSemantics.uncertainty_projection` expose? | Same schema as `SemanticsProfile.uncertainty_projection`, per C76. |
| Q4 | What is the default lowering policy when SDK callers omit `uncertainty_projection`? | Lower C76 default reject projection, not an empty profile field. |
| Q5 | What adapter consumption semantics should v1 ship? | Explicit consumption in ProbLog export: default / explicit `reject` raises; explicit point-projection policies materialize a point probability; no silent ignore. |
| Q6 | Which policies are supported in v1? | `reject`, `lower`, `midpoint`, `upper`, and degenerate `identity_probability`; reject interval-valued `probability_interval` / `possibility_interval` for ProbLog point export. |
| Q7 | What is the focused test matrix? | Fixture drift fix; field construction/normalization; lowering default and explicit configs; default reject on raw uncertainty facts; explicit midpoint/lower/upper behavior; unsupported interval policies; existing branch-probability/rule-param regressions. |
| Q8 | Does full T10-1 ship unblock T8-C-1? | Yes for the C76 prerequisite after all three layers ship and the two fixture errors are fixed; T8-C-1 still remains a separate evidence-enrichment cycle. |
| Q9 | Do audit docs or user docs change? | No. T10-1 does not ship ProbLog row-level Form 1 evidence or user-facing evidence docs changes. |
| Q10 | Are there stop/amend findings? | None. Findings refine implementation shape but do not require scope expansion beyond T10-1. |

## 5. Existing Invariants To Preserve

- T8-A top-level 14-key metadata and `run_id` envelope-only behavior remain
  unchanged.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 row evidence remain unchanged.
- T8-D user docs still correctly mark ProbLog row-level Form 1 evidence as
  deferred until T8-C-1 ships.
- C110 `raw_kind` + `bound` remains the canonical uncertainty input carrier.
- Legacy `confidence` write-key rejection remains active.
- Existing ProbLog `branch_probabilities` / `rule_params` behavior remains
  additive and non-regressing.
- `SemanticsProfile.uncertainty_projection` should be reused, not redesigned.
- `EvidenceGraph` DTO schema and §10.3 metadata vocabulary are not changed.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 4 U` and must not be touched.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce:

1. Reproducible verification of the two ProbLog migration errors and whether
   they are fixture drift or runtime bugs.
2. Source-backed C76 three-layer table.
3. Candidate implementation shapes for SDK field, lowering, and adapter
   consumption.
4. Explicit v1 policy support decision.
5. Focused test matrix and full-discover comparison plan.
6. T8-C-1 unblock statement.
7. Stop/amend assessment.

Suggested verification commands:

```bash
rg -n "confidence|raw_kind|bound" tests/test_problog_semantics_profile_migration.py src/factgraph/core/evidence/write_protocol.py
rg -n "class ProbLogSemantics|uncertainty_projection|branch_probabilities" src/factgraph/sdk/semantics.py src/factgraph/core/semantics/profile.py src/factgraph/sdk/store.py
rg -n "uncertainty_projection|raw_kind|bound|resolve_problog_engine_ext" src/factgraph/adapters/problog src/factgraph/sdk/store.py
```

## 7. Proposed Implementation Split

Pending Step 4.6. Expected shape if Q1-Q10 confirm the current assumptions:

1. Test fixture migration fix: replace legacy `meta[confidence]` writes in the
   ProbLog semantics profile fixture with canonical `raw_kind` + `bound`.
2. SDK shell + lowering: add `ProbLogSemantics.uncertainty_projection`, default
   it to the C76 reject projection, and lower it into
   `SemanticsProfile.uncertainty_projection`.
3. Adapter consumption: thread projection config to ProbLog export and project
   raw uncertainty annotations into fact probabilities with explicit policy
   handling.
4. Focused tests for field/lowering/adapter/default/explicit-policy behavior
   plus existing branch probability regressions.
5. Closure + archive.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q10 answered.
- [x] Scope amended before implementation if any stop trigger fires.
- [x] C76 ships all scoped layers together.
- [x] Focused ProbLog semantics tests pass.
- [x] T8-A/T8-B evidence regressions pass.
- [x] Full discover delta recorded.
- [x] `git diff --check` clean.
- [x] Dirty baseline and sacred master preserved.

## 9. Verification Commands

Pending Step 4.6 exact test matrix. Candidate minimum:

```bash
PYTHONPATH=src python -m unittest tests.test_problog_semantics_profile_migration
PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.application.protocol.test_evaluate_result_dtos
PYTHONPATH=src python -m unittest discover tests
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

Implemented in five runtime/test commits after the draft and scoped commits:

- `4d3ed74e` `fix(test): migrate problog fixtures off legacy confidence`
- `bb619279` `feat(sdk): add problog uncertainty projection lowering`
- `b7823086` `feat(problog): consume uncertainty projection`
- `efcaa36f` `test(problog): cover uncertainty projection policies`
- `e7cad68c` `fix(problog): default direct uncertainty projection`

Shipped C76 as one coherent slice:

- SDK shell: `ProbLogSemantics.uncertainty_projection` now accepts the same
  schema as `SemanticsProfile.uncertainty_projection` and defaults to the C76
  reject projection.
- Lowering: public ProbLog semantics preview/lowering now passes the projection
  into the canonical `SemanticsProfile`.
- Adapter consumption: ProbLog export now consumes `shared/semantic/raw_kind`
  plus `shared/semantic/bound` and applies explicit policy semantics instead
  of silently ignoring raw uncertainty rows.

The two pre-existing ProbLog migration errors were fixture drift from legacy
`meta[confidence]` writes and were fixed without weakening C110 write-time
rejection. Existing `branch_probabilities`, `rule_params`, explicit probability
annotations, T8-A metadata, T8-B native/Souffle Form 1 evidence, and T8-D user
docs remain unchanged.

Verification:

- `PYTHONPATH=src python -m unittest tests.test_problog_export.TestProbLogExportReadsSharedProbability tests.test_problog_semantics_profile_migration`
  passed: 24 tests OK.
- Focused suite including ProbLog export, ProbLog semantics migration, ProbLog
  evidence graph, audit evidence graph, protocol DTOs, and SDK RuleExpr
  evaluation passed: 113 tests OK.
- `python -m ruff check` on the changed runtime/test files passed.
- `git diff --check` passed.
- Full discover now reports 2011 tests with 72 failures and 231 errors.
  Compared with the T10 inventory baseline of 2004 tests / 72 failures /
  233 errors, T10-1 adds seven tests and removes the two ProbLog migration
  errors without introducing replacement errors.

Step 4.7 found and fixed one blocker: `_claim_probability(...)` originally
made `uncertainty_projection` a required keyword-only argument, which broke two
existing direct-call tests in `tests/test_problog_export.py`. The first full
discover run still showed 233 errors because the two fixed fixture errors were
replaced by two new direct-call errors. The amend commit `e7cad68c` made direct
callers default to the same reject projection, restoring the old call shape and
turning the full-discover delta into a real net drop from 233 errors to 231.
Closure records this as a composition-vs-total verification lesson: matching
failure/error counts are insufficient when a cycle fixes known baseline errors.

Residual non-blocking observations:

- The fixture migration briefly moved through `raw_kind` / `bound` before the
  final source-only fixture state; the final state is correct because default
  ProbLog raw uncertainty now rejects unless explicitly projected.
- Defensive error branches for malformed raw uncertainty annotations and some
  unsupported policy shapes remain production-guarded but are not exhaustively
  unit-tested in this slice.
- T10-1 unblocks T8-C-1 from the C76 side only. ProbLog evidence enrichment is
  still a future T8-C-1 cycle and user-facing evidence docs remain accurate.
