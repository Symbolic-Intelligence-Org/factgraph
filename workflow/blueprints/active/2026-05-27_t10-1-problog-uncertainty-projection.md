# Task Blueprint: T10-1 ProbLog Uncertainty Projection

- Status: draft
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

## 3. Draft Source Scan

Draft orientation only; Step 4.6 must verify or correct these hints with
source refs:

- `tests/test_problog_semantics_profile_migration.py` appears to contain two
  setup writes that still use legacy `meta={"confidence": ...}`.
- `write_protocol._validate_no_removed_uncertainty_keys(...)` rejects
  `confidence` and points callers to `raw_kind` / `bound`.
- `ProbLogSemantics` appears to expose `branch_probabilities`, `rule_params`,
  `name`, and `fallback`, but not `uncertainty_projection`.
- `SemanticsProfile.uncertainty_projection` appears to exist and normalize /
  validate raw-kind policy mappings.
- The ProbLog adapter appears to consume existing rule probabilities, not
  `uncertainty_projection`.

This scan does not answer Q1-Q10.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Should the two ProbLog migration errors be fixed inside T10-1, before T10-1, or left as known drift? | Three-option decision with source refs and rationale. |
| Q2 | What is the verified C76 three-layer current state? | Source-backed SDK shell / lowering / adapter consumption table. |
| Q3 | What SDK field shape should `ProbLogSemantics.uncertainty_projection` expose? | Same schema as `SemanticsProfile` vs simplified wrapper shape, with rationale. |
| Q4 | What is the default lowering policy when SDK callers omit `uncertainty_projection`? | C76 default reject vs empty profile field, with source-backed rationale. |
| Q5 | What adapter consumption semantics should v1 ship? | Reject vs silent ignore vs midpoint/substitution behavior for `raw_kind` / `bound`. |
| Q6 | Which policies are supported in v1? | Reject-only vs explicit midpoint support, with design and test implications. |
| Q7 | What is the focused test matrix? | Field, lowering, adapter consumption, default behavior, explicit policy behavior, and branch-probability regressions. |
| Q8 | Does full T10-1 ship unblock T8-C-1? | Yes/no with dependency analysis and any remaining preconditions. |
| Q9 | Do audit docs or user docs change? | Docs/no-docs decision with audience rationale. |
| Q10 | Are there stop/amend findings? | None or explicit trigger with next action. |

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

1. Test fixture prerequisite / migration fix, if scoped in.
2. SDK shell + lowering implementation.
3. ProbLog adapter consumption implementation.
4. Focused tests.
5. Closure + archive.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q10 answered.
- [ ] Scope amended before implementation if any stop trigger fires.
- [ ] C76 ships all scoped layers together.
- [ ] Focused ProbLog semantics tests pass.
- [ ] T8-A/T8-B evidence regressions pass.
- [ ] Full discover delta recorded.
- [ ] `git diff --check` clean.
- [ ] Dirty baseline and sacred master preserved.

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

Pending scoped inventory / implementation.
