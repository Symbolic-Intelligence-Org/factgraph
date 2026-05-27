# Task Blueprint: T8-C-1 ProbLog Evidence Enrichment Inventory

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (design-only planning inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-c-1-problog-evidence-enrichment-inventory.audit.md`
- Trigger: T10-1 shipped C76 ProbLog uncertainty projection at `cde072fa`, satisfying the T8-C inventory prerequisite for T8-C-1 from the ProbLog side. This cycle starts from T8-C inventory §4.1 Option C (adapter-side metadata bridge / provenance row bridge) and §7 trigger guidance, and should verify those assumptions before any runtime T8-C-1 implementation starts.

## 0. Scope Locks

### In scope

This is a **T8-C-1 pre-implementation inventory cycle**, not the T8-C-1
runtime implementation. It should source-back the ProbLog evidence enrichment
surface now that C76 is shipped.

Scoped planning outputs:

1. Source-backed inventory of the existing ProbLog provenance path:
   `evaluate_problog(...)`, `ProvenanceEnvelope`, `problog_trace_to_evidence_graph(...)`,
   current graph metadata, current `engine_meta`, and row-result integration
   gap.
2. Projection decision memory-channel comparison: trace-payload attachment,
   store/candidate annotation channel, or another explicitly scoped path.
3. Row-result bridge location comparison: `_build_passed_row_evidence_graph`
   provenance branch, adapter/evaluate exit injection, or another scoped
   bridge point.
4. Metadata assembly plan for the three layers T8-C-1 must reconcile:
   T8-A 14-key top-level graph metadata, current ProbLog adapter-local graph
   metadata, and T10-1 uncertainty projection decisions.
5. `engine_meta` namespace migration strategy for existing ProbLog converter
   fields and any new T8-C-1 fields.
6. C119 single-path verification and decision on whether full multi-path DAG
   remains deferred.
7. Focused implementation/test matrix sketch for a future T8-C-1 runtime
   blueprint.

### Out of scope

- Any runtime code changes.
- Any test code changes.
- Any T8-C-1 implementation commit.
- PyReason, Nemo, aggregate envelope, C119 full multi-path DAG implementation,
  Form 2, or D11 work.
- T10-2 / T10-3 / C74 / C77 / C78 work.
- D20 match witness, failed graph, why-not, counterfactual, service/OpenAPI,
  Database/view, match API, `fg.eval.run`, release, PyPI, tags, or dirty
  baseline cleanup.
- `EvidenceGraph` DTO schema changes.
- Top-level 14-key graph metadata changes.
- `_FORM1_ROW_SUPPORT_KINDS` or `_WITNESS_BEARING_SUPPORT_KINDS` changes.
- Weakening T8-A 14-key metadata validation.
- Weakening T8-B native/Souffle Form 1 invariants.
- Weakening T8-D user-doc boundaries; user docs still mark ProbLog row-level
  Form 1 evidence as deferred until a runtime T8-C-1 cycle ships it.
- Governance/workflow file changes.
- Sacred `master` changes or dirty baseline changes.

### Stop / amend triggers

Pause and amend before scoped closure if Step 4.6 finds:

- T8-C inventory §4.1 Option C is no longer valid, for example because ProbLog
  now creates `SupportArtifact` values and a T8-B-style witness bridge becomes
  credible.
- Both projection decision memory-channel candidates fail a shipped invariant
  such as EvidenceGraph schema stability, 14-key metadata stability, or T8-A
  validation gates.
- `engine_meta` namespacing cannot be specified without changing existing
  runtime/test behavior in this inventory cycle.
- C119 single-path assumptions are false because the current ProbLog converter
  already emits multiple same-binding candidate paths that require multi-path
  DAG handling in T8-C-1.
- Any runtime, test, user-facing docs, governance, dirty-baseline, or sacred
  branch edit appears necessary.

## 1. Problem

T8-C inventory selected an adapter-side metadata bridge / provenance row bridge
for ProbLog and PyReason. T10-1 has now shipped C76 for ProbLog, so the ProbLog
lane is unblocked from the adapter-semantics side.

Current ProbLog provenance can already produce an `EvidenceGraph` through
`problog_trace_to_evidence_graph(...)`, but that graph is adapter-local
candidate/readback evidence: its top-level metadata has no overlap with the
T8-A 14-key row-result metadata bridge, its engine metadata is not yet
namespaced, and row-level `EvaluateRow.explain()` currently falls back to the
single-node graph because ProbLog does not provide a witness-bearing
`SupportArtifact`.

Before runtime work starts, this cycle should decide the bridge shape and the
metadata ownership boundaries.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t8-c-engine-enrichment-inventory.md` §4.1 / §4.2 / §7 | Selected adapter-side metadata bridge direction and T8-C-1 trigger after C76 / ProbLog semantics lock. |
| `workflow/blueprints/archive/2026-05-27_t10-1-problog-uncertainty-projection.md` | C76 shipped source: SDK shell, lowering, adapter consumption, and uncertainty projection policy behavior. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15.2 / C119 / C136 | T8-C source, ProbLog multi-path deferral, aggregate deferral, and engine_meta hardening direction. |
| `src/factgraph/adapters/problog/engine_eval.py` | ProbLog adapter entry, `ProvenanceEnvelope` producer, and candidate support-kind attachment. |
| `src/factgraph/adapters/problog/provenance.py` | Current ProbLog trace parser and `problog_trace_to_evidence_graph(...)` converter. |
| `src/factgraph/adapters/problog/problog_export.py` | T10-1 probability projection decision point and possible projection-memory producer. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata bridge and T8-B row-result graph dispatch to preserve. |
| `src/factgraph/core/store/_support.py` | Witness-bearing vs provenance-bearing taxonomy to verify. |
| `tests/test_problog_evidence_graph.py` | Existing converter regression baseline and C119 single-path evidence. |
| `tests/test_problog_semantics_profile_migration.py` | T10-1 uncertainty projection behavior tests relevant to future evidence metadata. |

## 3. Step 4.6 Inventory Results

Pending Step 4.6. Required source-backed subsections:

### 3.1 Existing ProbLog End-To-End Provenance Chain

Source-back `evaluate_problog(...)` through `ProvenanceEnvelope` storage,
`PROBLOG_PROVENANCE_KIND`, `support_digest`, and
`problog_trace_to_evidence_graph(...)`. Confirm whether any hidden row-result
call site already uses the converter.

### 3.2 Candidate Path Versus Row-Result Path

Produce a table comparing:

- current candidate/provenance readback path;
- current `EvaluateRow.explain()` row path;
- why ProbLog rows currently fall back to single-node row evidence;
- exact files/functions where a future bridge could attach.

### 3.3 Projection Decision Memory Channel

Compare at least:

- trace payload attachment from `problog_export.py` / `engine_eval.py`;
- store/candidate annotation or pending-state channel;
- any other path Step 4.6 finds.

Each option must include ownership, lifetime, test surface, and failure-mode
analysis.

### 3.4 Row Bridge Location

Compare at least:

- `evaluate_result.py:_build_passed_row_evidence_graph(...)` provenance branch;
- adapter/evaluate exit graph injection;
- other bridge points if source inventory finds one.

The scoped answer must preserve T8-A metadata validation gates.

### 3.5 Metadata And `engine_meta` Namespacing

Inventory current ProbLog graph metadata and the existing flat
`engine_meta` fields. Decide whether future T8-C-1 should migrate existing
fields at once, add only new namespaced fields, or expose a dual-track
compatibility shape.

### 3.6 C119 Single-Path Verification

Source-back whether current ProbLog tests and converter behavior are still
single-path for v1, and whether multi-path DAG remains deferred.

### 3.7 Test Matrix Sketch

Sketch future implementation tests for row bridge, 14-key metadata, converter
regressions, uncertainty-projection metadata, and no-regression behavior.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Which projection decision memory channel should T8-C-1 use? | Compare trace-payload attachment, store/candidate annotation channel, and any discovered alternative with file/test/LOC/risk estimates and selected strategy. |
| Q2 | Where should the row-result bridge attach? | Compare `_build_passed_row_evidence_graph(...)` provenance dispatch, adapter/evaluate exit injection, and any discovered alternative; include T8-A gate preservation trace. |
| Q3 | How should T8-C-1 assemble metadata? | Define ownership for top-level 14-key metadata, current ProbLog adapter-local metadata, and uncertainty projection decisions without changing the 14-key set. |
| Q4 | What is the `engine_meta` namespacing strategy? | Decide how to handle the existing flat ProbLog converter fields and future `engine_meta.problog.*` fields, including compatibility risk for existing tests. |
| Q5 | Does C119 multi-path remain deferred? | Source-back current single-path assumptions and decide whether T8-C-1 keeps full multi-path DAG out of scope. |
| Q6 | What future implementation test matrix is required? | Include baseline converter tests, row-result bridge tests, 14-key metadata tests, uncertainty-projection metadata fixtures, and no-regression suites. |
| Q7 | What is the future T8-C-1 implementation cycle class and file scope? | Estimate runtime/test/docs LOC, file set, and likely commit split for the next implementation blueprint. |
| Q8 | Does T8-C-1 need any user/audit docs in the implementation cycle? | Decide audit-module/user-doc trigger boundaries without editing docs in this inventory cycle. |
| Q9 | Are there additional T10 or engine-specific prerequisites after T10-1? | Confirm whether C76 full ship is sufficient for ProbLog enrichment or whether another semantics lock is needed. |
| Q10 | Are there stop/amend findings? | None or explicit trigger with next action. |

## 5. Existing Invariants To Preserve

- T8-A top-level 14-key metadata and `run_id` envelope-only behavior remain
  unchanged.
- T8-A metadata validation gates in `EvaluateResult` remain always-on.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 row evidence remain
  unchanged.
- T8-D user docs continue to mark ProbLog row-level Form 1 evidence as
  deferred until a runtime T8-C-1 cycle ships it.
- T10-1 C76 adapter execution semantics remain unchanged.
- Current ProbLog converter regressions remain protected; this inventory cycle
  must not rewrite converter behavior.
- `EvidenceGraph` DTO schema and node/edge kind vocabulary remain unchanged.
- `_FORM1_ROW_SUPPORT_KINDS` and `_WITNESS_BEARING_SUPPORT_KINDS` remain
  unchanged.
- C119 multi-path DAG and C136 aggregate envelope remain deferred unless Step
  4.6 records source-backed scope correction.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 4 U` and must not be touched.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce:

1. Reproducible source inventory for the current ProbLog provenance chain.
2. Candidate path versus row-result path comparison.
3. Projection decision memory-channel comparison.
4. Row bridge location comparison with T8-A validation-gate trace.
5. Metadata assembly and `engine_meta` namespacing decisions.
6. C119 single-path / multi-path defer verification.
7. Future implementation test matrix and class estimate.
8. Stop/amend assessment.

Suggested verification commands:

```bash
rg -n "ProvenanceEnvelope|PROBLOG_PROVENANCE_KIND|support_digest|support_kind" src/factgraph/adapters/problog src/factgraph/core src/factgraph/application
rg -n "def problog_trace_to_evidence_graph|metadata=|engine_meta|EDGE_DERIVES|NODE_" src/factgraph/adapters/problog/provenance.py tests/test_problog_evidence_graph.py
rg -n "def _build_passed_row_evidence_graph|_FORM1_ROW_SUPPORT_KINDS|_build_form1_evidence_graph|_evidence_metadata" src/factgraph/application/protocol/evaluate_result.py
rg -n "_claim_probability|_claim_raw_uncertainty_probability|uncertainty_projection|raw_kind|bound" src/factgraph/adapters/problog/problog_export.py src/factgraph/adapters/problog/engine_eval.py tests/test_problog_semantics_profile_migration.py
```

## 7. Proposed Output Shape

Pending Step 4.6. Expected durable output is **blueprint-only inventory**:
the archived blueprint/audit pair should be enough to start a later T8-C-1
implementation blueprint. No separate design-point note is expected unless
Step 4.6 finds a cross-design correction that belongs outside the blueprint
archive.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q10 answered.
- [ ] No runtime/test/user-doc/governance files changed.
- [ ] Future T8-C-1 implementation shape recorded.
- [ ] T8-A/T8-B/T8-D/T10 invariants preserved.
- [ ] `git diff --check` clean.
- [ ] Dirty baseline and sacred master preserved.

## 9. Verification Commands

Design-only cycle. Candidate no-op checks:

```bash
PYTHONPATH=src python -m unittest tests.test_problog_evidence_graph tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

Pending Step 4.6 inventory / closure.
