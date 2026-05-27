# Task Blueprint: T8-C-1 ProbLog Evidence Enrichment Inventory

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (design-only planning inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/archive/2026-05-27_t8-c-1-problog-evidence-enrichment-inventory.audit.md`
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

### 3.1 Existing ProbLog End-To-End Provenance Chain

| Stage | Source | Finding |
|---|---|---|
| Adapter entry | `src/factgraph/adapters/problog/engine_eval.py:29-112` | `evaluate_problog(...)` resolves ProbLog engine extension, exports a `.pl` program, runs ProbLog with `trace=True`, parses output into candidates, attaches provenance, and remembers pending probability annotations. |
| C76 projection handoff | `engine_eval.py:97-104` | T10-1 passes `semantics_profile.uncertainty_projection` into `export_problog(...)`; no evidence metadata is produced at this stage. |
| Provenance envelope | `engine_eval.py:173-203` | `_attach_problog_provenance(...)` parses the trace, stores `ProvenanceEnvelope(engine="problog", payload_type="proof_trace", payload=trace_dict)`, computes `support_digest`, and sets candidate `support_kind=PROBLOG_PROVENANCE_KIND`. |
| Store carrier | `src/factgraph/core/store/runtime.py:136-158`, `:399-403` | `Store` keeps provenance envelopes in `_provenance_envelopes`; `explain_provenance(...)` returns only the envelope dict. |
| Support taxonomy | `src/factgraph/core/store/_support.py:12-20`, `:147-162` | ProbLog is provenance-bearing, not witness-bearing: `_PROVENANCE_BEARING_SUPPORT_KINDS` includes `PROBLOG_PROVENANCE_KIND`; `ProvenanceEnvelope` carries `candidate_id`, `engine`, `payload_type`, and `payload`. |
| Candidate backref | `src/factgraph/core/store/_evaluate.py:258-276` | Provenance-bearing candidates are remembered as candidate support backrefs, but not converted into witness-bearing `SupportArtifact`s. |
| Graph converter | `src/factgraph/adapters/problog/provenance.py:187-297` | `problog_trace_to_evidence_graph(...)` converts a `ProbLogTraceV0` plus candidate payload into an adapter-local `EvidenceGraph`. |
| Direct converter call sites | `tests/test_problog_evidence_graph.py:45-110`, `src/service/runtime_v1.py:1973-2040` | Tests and legacy service audit-package materialization call the converter directly. No row-result `EvaluateRow.explain()` path uses it today. |

### 3.2 Candidate Path Versus Row-Result Path

| Path | Current source | Current behavior | T8-C-1 implication |
|---|---|---|---|
| Candidate/provenance readback | `engine_eval.py:173-203`, `runtime.py:399-403`, `provenance.py:187-297` | Candidate support points to a `ProvenanceEnvelope`; callers that know the envelope can convert it to a ProbLog trace graph. | Existing converter is reusable as substrate, but it is not row-result metadata-compliant. |
| Legacy service audit-package materialization | `src/service/runtime_v1.py:1973-2040` | Reads `support_digest`, calls `store.explain_provenance(...)`, and dispatches to `problog_trace_to_evidence_graph(...)` for audit package rows. | Confirms a non-row call site exists; it is service/audit-package materialization, not `EvaluateRow.explain()`. |
| SDK row construction | `src/factgraph/sdk/store.py:2693-2736` | Converts candidates to rows, then passes `_row_support_artifacts` only. | ProbLog provenance is not threaded into `EvaluateResult` today. |
| Row support threading | `sdk/store.py:2742-2754` | `_row_support_artifacts_for_candidates(...)` only admits `_FORM1_ROW_SUPPORT_KINDS` and looks up `SupportArtifact`. | T8-C-1 should add a separate private provenance-row context, not widen the Form 1 witness allowlist. |
| Row graph dispatch | `src/factgraph/application/protocol/evaluate_result.py:841-865` | `_build_passed_row_evidence_graph(...)` validates 14-key metadata, delegates to `_build_form1_evidence_graph(...)` when support artifact exists, otherwise emits a single-node `support_kind="evaluate_row"` graph. | ProbLog rows currently fall back to single-node row evidence because they have provenance envelopes, not support artifacts. |

### 3.3 Projection Decision Memory Channel

| Option | Shape | Estimate | Risk | Decision |
|---|---|---:|---|---|
| A. Trace payload attachment | Extend ProbLog export to produce a structured probability decision table while writing the `.pl` program, then attach it to the `ProvenanceEnvelope.payload` beside the trace. `engine_eval.py:97-104` already owns the export call; `_attach_problog_provenance(...)` at `:173-203` owns payload creation. | 80-180 runtime LOC + focused tests | Medium. Requires changing `export_problog(...)` return shape or adding an output/sink parameter, but the decision is captured at the exact source of truth before information is collapsed to a float at `problog_export.py:95-104`. | **Selected.** It preserves adapter ownership and keeps the decision lifetime coupled to provenance. |
| B. Store / candidate annotation channel | Reuse or extend store-side pending annotations such as `_problog_pending_annotations` from `engine_eval.py:138-170`. | 80-200 runtime LOC + accept-path tests | Medium/high. Existing pending annotations store candidate probability annotations by `run_id` / `candidate_id`, not per-source-fact projection decisions; it risks mixing accept-time annotation state with row evidence state. | Reject for T8-C-1. |
| C. Recompute decisions in row bridge | Row bridge re-reads `raw_kind` / `bound` and re-applies `uncertainty_projection`. | 120-260 runtime LOC | High. The row bridge does not currently carry `SemanticsProfile`; recomputation risks divergence from export-time behavior and default handling. | Reject. |
| D. Store only final point probability | Use `CandidateSet.confidence` / row `raw_kind` and `bound` from `evaluate_result.py:1132-1140`. | Low | Insufficient. This preserves final point probability but not policy, raw carrier, or decision provenance. | Reject. |

Scoped answer: future T8-C-1 should use **trace payload attachment**. The
projection decision table should be produced in the ProbLog adapter where
`_claim_probability(...)` applies C76 (`problog_export.py:137-200`) and
`_claim_raw_uncertainty_probability(...)` applies raw-kind policy
(`:203-265`). The table should be attached to the `ProvenanceEnvelope.payload`
so the row bridge and candidate converter have one adapter-owned provenance
source.

### 3.4 Row Bridge Location

| Option | Shape | Estimate | Risk | Decision |
|---|---|---:|---|---|
| A. Private provenance row context + `_build_passed_row_evidence_graph(...)` branch | Add a private row provenance mapping parallel to `_row_support_artifacts`; SDK result construction looks up `ProvenanceEnvelope`s for `PROBLOG_PROVENANCE_KIND`; `_build_passed_row_evidence_graph(...)` dispatches after its existing metadata validation. | 120-260 runtime LOC + protocol/SDK tests | Medium. Adds a private context field and one row dispatch branch, but preserves T8-A gate ordering. | **Selected.** |
| B. Adapter/evaluate exit injects finished `EvidenceGraph` into rows | Adapter returns graphs or a graph map with candidates; SDK threads finished graphs to result. | 150-320 runtime LOC | Higher. Adapter would need row/result metadata that only exists after `EvaluateResult` construction; likely duplicates T8-A metadata generation. | Reject. |
| C. Widen `_FORM1_ROW_SUPPORT_KINDS` / support artifact path | Treat ProbLog provenance as Form 1 support. | 80-180 runtime LOC | Wrong abstraction: ProbLog uses `ProvenanceEnvelope`, `EDGE_DERIVES`, and adapter trace metadata, not witness-bearing `SupportArtifact`. | Reject. |
| D. Leave row path single-node and document candidate converter only | No row bridge. | 0 LOC | Fails T8-C-1 purpose; does not ship row-result evidence enrichment. | Reject. |

T8-A gate trace for selected option:

1. `_explain_live_row(...)` builds metadata via
   `_evidence_metadata_for_row_result(...)` at `evaluate_result.py:635`.
2. `_build_passed_row_evidence_graph(...)` validates the metadata before any
   dispatch at `evaluate_result.py:841-847`.
3. A future ProbLog provenance branch must return an `EvidenceGraph` with that
   same metadata, after which `_explain_live_row(...)` revalidates at
   `evaluate_result.py:637-640`.

Scoped answer: future T8-C-1 should add a **private provenance row context** and
branch inside `_build_passed_row_evidence_graph(...)`; it must not widen
`_FORM1_ROW_SUPPORT_KINDS`.

### 3.5 Metadata And `engine_meta` Namespacing

| Layer | Current source | Scoped policy |
|---|---|---|
| Row-result top-level graph metadata | `evaluate_result.py:59-75`, `:1027-1075` | Top-level `EvidenceGraph.metadata` must remain exactly the T8-A 14 keys. No ProbLog adapter key may be added at top level. |
| Current ProbLog graph metadata | `provenance.py:291-296` | Current adapter-local keys are `event_count`, `answer_count`, `root_goal`, and `answer_probability`; in row-result graphs they should move under root `engine_meta["problog"]["trace_summary"]` or equivalent namespaced engine metadata. |
| Existing node flat engine_meta | `provenance.py:244-256` | Existing flat keys are `goal`, `goal_name`, `goal_args`, `call_started_seconds`, `location`, `result_terms`, `bindings_text`, `elapsed_seconds`, `event_status`, `synthetic_goal`, and `answer_probability`. |
| Existing edge flat engine_meta | `provenance.py:275-279` | Existing flat edge keys are `parent_goal`, `child_goal`, and `parent_location`. |
| T10-1 projection decision | `problog_export.py:137-200`, `:203-265`; tests at `tests/test_problog_semantics_profile_migration.py:251-290`, `:320-413` | Projection metadata should be namespaced under `engine_meta["problog"]["uncertainty_projection"]` on the relevant seed/premise node when the frame can be tied to a source assertion, with an aggregate count/summary at the root if useful. |

Options considered:

| Option | Shape | Risk | Decision |
|---|---|---|---|
| One-shot migrate existing converter to namespaced metadata | Change `problog_trace_to_evidence_graph(...)` to stop emitting flat keys. | Breaks existing candidate converter tests and readback assumptions. | Reject for first row bridge. |
| Add namespaced fields alongside flat fields in the same converter | Existing tests pass while new fields appear everywhere. | Leaks row-result enrichment fields into candidate/readback path and creates dual truth in the same graph. | Reject as default. |
| Row-result wrapper normalizes metadata, candidate converter stays flat | Future row bridge can call/reuse converter internals and post-process into namespaced row-result graph while leaving existing converter tests unchanged. | Requires thin transformation layer. | **Select.** |

Scoped answer: preserve the current candidate converter shape. Future T8-C-1
should produce a row-result ProbLog graph with T8-A top-level metadata and
namespaced `engine_meta["problog"]` fields, while existing
`test_problog_evidence_graph.py` continues to protect the candidate converter's
flat adapter-local shape unless the implementation blueprint explicitly amends
that test surface.

### 3.6 C119 Single-Path Verification

| Source | Finding |
|---|---|
| `tests/test_problog_evidence_graph.py:45-75` | Baseline converter test uses one nested call tree for one candidate and asserts three nodes / two edges. |
| `tests/test_problog_evidence_graph.py:78-99` | Synthetic answer test uses one root answer and asserts one node / zero edges. |
| `tests/test_problog_evidence_graph.py:101-110` | Missing-anchor test covers rejection, not multi-path. |
| `src/factgraph/adapters/problog/problog_import.py:48-75` | ProbLog result parsing collapses duplicate binding probabilities by max probability and then builds candidates; it does not preserve multiple same-binding candidate paths. |

Scoped answer: C119 full multi-path DAG remains deferred. Current source
surfaces still indicate single selected trace/candidate behavior, and the
import path collapses same-binding probabilities before candidate creation.
T8-C-1 should not attempt multi-path DAG unless a later inventory changes the
adapter import semantics.

### 3.7 Test Matrix Sketch

Future T8-C-1 implementation should cover:

- Existing `tests.test_problog_evidence_graph` converter regressions unchanged.
- Row-result ProbLog `EvaluateRow.explain()` returns multi-node ProbLog
  evidence rather than single-node fallback.
- Row-result graph top-level metadata equals the T8-A 14-key set and excludes
  ProbLog adapter-local keys.
- Row-result graph support kind remains `PROBLOG_PROVENANCE_KIND`; edge kind
  remains `EDGE_DERIVES` for ProbLog trace structure.
- Root/node `engine_meta["problog"]` contains trace summary and namespaced
  trace fields; no new generic flattened ProbLog keys are introduced in
  row-result graphs.
- Midpoint/lower/upper uncertainty projection fixtures record the export-time
  projection decision in row-result engine metadata.
- Default `reject` behavior from T10-1 remains a semantics execution error, not
  a row-evidence graph.
- T8-A/T8-B/T8-D regressions: protocol DTO metadata tests, native/Souffle Form
  1 tests, audit renderer tests, and T10-1 ProbLog semantics tests.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Which projection decision memory channel should T8-C-1 use? | Select trace-payload attachment. Export is where the policy decision is made (`problog_export.py:95-104`, `:137-200`, `:203-265`), and `_attach_problog_provenance(...)` already owns `ProvenanceEnvelope.payload` assembly (`engine_eval.py:173-203`). Reject store/candidate pending annotations because the existing `_problog_pending_annotations` path (`engine_eval.py:138-170`) records derived candidate probability annotations, not source-fact projection decisions. |
| Q2 | Where should the row-result bridge attach? | Select a private provenance row context plus `_build_passed_row_evidence_graph(...)` branch. SDK result construction already maps candidates to rows at `sdk/store.py:2693-2736`; it can add a provenance mapping parallel to `_row_support_artifacts`. `_build_passed_row_evidence_graph(...)` must keep validation before dispatch (`evaluate_result.py:841-847`) and after-builder validation in `_explain_live_row(...)` (`:635-640`). |
| Q3 | How should T8-C-1 assemble metadata? | Top-level graph metadata remains exactly the T8-A 14 keys from `evaluate_result.py:59-75`. Current ProbLog graph metadata (`event_count`, `answer_count`, `root_goal`, `answer_probability` at `provenance.py:291-296`) moves into namespaced root/node `engine_meta["problog"]` for row-result graphs. Projection decisions also live under `engine_meta["problog"]`, not top-level metadata. |
| Q4 | What is the `engine_meta` namespacing strategy? | Preserve the current candidate converter flat shape for existing readback/tests. Future row-result bridge should emit namespaced `engine_meta["problog"]` fields through a wrapper/thin adapter rather than one-shot migrating `problog_trace_to_evidence_graph(...)` and breaking `tests/test_problog_evidence_graph.py:67-99`. |
| Q5 | Does C119 multi-path remain deferred? | Yes. Current converter tests are single selected trace/candidate fixtures (`tests/test_problog_evidence_graph.py:45-110`), and import collapses duplicate bindings by max probability before candidate creation (`problog_import.py:48-75`). Full C119 multi-path DAG remains out of T8-C-1. |
| Q6 | What future implementation test matrix is required? | See §3.7. Add row-result bridge, 14-key metadata, namespaced ProbLog engine_meta, uncertainty projection decision metadata, and no-regression suites while preserving converter tests. |
| Q7 | What is the future T8-C-1 implementation cycle class and file scope? | Class M. Estimated runtime 250-550 LOC plus 150-300 test LOC. Likely files: `adapters/problog/problog_export.py`, `adapters/problog/engine_eval.py`, `adapters/problog/provenance.py`, `application/protocol/evaluate_result.py`, `sdk/store.py`, `tests/test_problog_evidence_graph.py`, `tests/application/protocol/test_evaluate_result_dtos.py` or a new focused protocol test, and T10-1 ProbLog semantics regression tests. |
| Q8 | Does T8-C-1 need any user/audit docs in the implementation cycle? | Future implementation should update audit-module docs because row-level ProbLog evidence behavior changes. User-facing quickstart / SDK guide should remain a follow-up T8-D round 3 after runtime ships. This inventory cycle edits no docs beyond the blueprint pair. |
| Q9 | Are there additional T10 or engine-specific prerequisites after T10-1? | No for first ProbLog row-result bridge/enrichment. C76 is now fully shipped by T10-1. C119 multi-path, C136 aggregate, PyReason C74/C77/C78, and Nemo remain separate gates, not prerequisites for T8-C-1's first tranche. |
| Q10 | Are there stop/amend findings? | None. Option C remains valid; ProbLog remains provenance-bearing, not SupportArtifact-based; C119 remains deferred; no schema or 14-key metadata changes are required. |

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

Durable output is **blueprint-only inventory**. The archived blueprint/audit
pair is the planning artifact for a later T8-C-1 runtime implementation
blueprint. No separate design-point note is needed: Step 4.6 confirmed T8-C
inventory Option C rather than correcting active design.

Future T8-C-1 implementation should likely split into:

1. Projection decision memory producer in the ProbLog adapter.
2. Private row provenance context plumbing from SDK result construction into
   `EvaluateResult`.
3. ProbLog row-result graph bridge / metadata wrapper with T8-A 14-key metadata
   and namespaced `engine_meta["problog"]`.
4. Focused row-result / uncertainty projection tests.
5. Audit docs update only if runtime behavior ships.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q10 answered.
- [x] No runtime/test/user-doc/governance files changed.
- [x] Future T8-C-1 implementation shape recorded.
- [x] T8-A/T8-B/T8-D/T10 invariants preserved.
- [x] `git diff --check` clean.
- [x] Dirty baseline and sacred master preserved.

## 9. Verification Commands

Design-only cycle. Candidate no-op checks:

```bash
PYTHONPATH=src python -m unittest tests.test_problog_evidence_graph tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

Implemented as a design-only inventory cycle. No runtime, test, user-facing
docs, governance, dirty-baseline, or sacred-branch files changed.

Cycle chain:

- Draft: `ab7972df`
- Scoped inventory: `8d3a1634`
- Closure: `bfb5faf1`

Step 4.6 completed the source-backed ProbLog row-enrichment plan:

- Verified that ProbLog remains provenance-bearing, not witness-bearing:
  `PROBLOG_PROVENANCE_KIND` flows through `ProvenanceEnvelope`, not
  `SupportArtifact`, so T8-C inventory Option C remains valid.
- Found one additional non-test converter call site:
  `src/service/runtime_v1.py:1973-2040` uses
  `problog_trace_to_evidence_graph(...)` for legacy service audit-package
  materialization; it is not the row-result `EvaluateRow.explain()` path.
- Selected trace-payload attachment as the future projection-decision memory
  channel, because ProbLog export is where C76 policy is applied before the
  `.pl` program stores only a point probability.
- Selected private provenance row context plus a
  `_build_passed_row_evidence_graph(...)` branch as the future row bridge,
  preserving the T8-A metadata-validation gates and not widening
  `_FORM1_ROW_SUPPORT_KINDS`.
- Locked the row-result metadata policy: exact T8-A 14-key top-level metadata,
  with ProbLog trace summary and uncertainty projection decisions namespaced
  inside `engine_meta["problog"]`.
- Preserved the existing candidate converter's flat adapter-local engine_meta
  shape; future row-result enrichment should use a wrapper/thin adapter rather
  than one-shot migrating `problog_trace_to_evidence_graph(...)`.
- Kept C119 full multi-path DAG deferred. Current tests exercise selected
  single trace/candidate behavior, and ProbLog import collapses duplicate
  bindings by max probability before candidate creation.

Verification:

- `PYTHONPATH=src python -m unittest tests.test_problog_evidence_graph tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph`
  passed with 38 tests OK.
- `git diff --check` clean.
- Sacred `master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline stayed at `4 M + 1 D + 4 U`.

Future implementation pings recorded by reviewer:

- Decide the exact `engine_meta["problog"]["trace_summary"]` and
  `engine_meta["problog"]["uncertainty_projection"]` schema in the runtime
  blueprint.
- Decide whether projection summaries attach only to matched nodes, root
  summary, or both.
- Add a stop trigger in the future runtime blueprint that default `reject`
  remains an execution error and must not be converted into an empty row
  evidence graph.
