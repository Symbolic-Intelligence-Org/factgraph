# Task Blueprint: T8-C Engine Enrichment Inventory

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (design-only planning inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/archive/2026-05-27_t8-c-engine-enrichment-inventory.audit.md`
- Trigger: T8-A, T8-B-1, T8-B-2, and T8-D round 2 are shipped; T8-C remains the evidence track's engine-enrichment lane and is gated by T10 or engine-specific semantics locks.

## 0. Scope Locks

### In scope

This is a **T8-C pre-implementation inventory cycle**, not T8-C
implementation. It quantifies ProbLog / PyReason enrichment boundaries before
any runtime blueprint starts.

Scoped planning outputs:

1. Source-backed inventory of the current ProbLog evidence path: trace shape,
   converter shape, graph metadata, `ProvenanceEnvelope.payload` usage, tests,
   and row-result integration gaps.
2. Source-backed inventory of the current PyReason evidence path: trace shape,
   converter shape, timeline/Form 2 status, payload usage, tests, and
   row-result integration gaps.
3. Independent verification of the reviewer due-diligence finding that ProbLog
   and PyReason are provenance-bearing, not witness-bearing, and do not create
   `SupportArtifact` instances today.
4. Architecture-path comparison for T8-C: bridge through `SupportArtifact`,
   add provenance-kind row dispatch, adapter-side metadata bridge, or another
   explicitly scoped path.
5. T10 dependency map for C74 / C76 / C77 / C78 against ProbLog and PyReason
   evidence enrichment.
6. T8-C-1 / T8-C-2 split decision.
7. Source-backed decisions for PyReason Form 2 temporal scope, ProbLog
   multi-path DAG scope, C136 aggregate envelope, engine-meta extension policy,
   and Nemo opt-in status.
8. Output-shape decision for this planning result.

### Out of scope

- Any runtime code changes.
- Any test code changes.
- Drafting the actual T8-C-1 / T8-C-2 implementation blueprints.
- Implementing T10 C74 / C76 / C77 / C78.
- D20 match witness, failed graph, why-not, counterfactual, service/OpenAPI,
  Database/view, match API, or `fg.eval.run` deletion.
- SDK API shape changes.
- Release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting existing ProbLog / PyReason adapter provenance converters
  wholesale.
- Weakening T8-A metadata validation, T8-B Form 1 behavior, or T8-D docs
  invariants.

### Stop / amend triggers

No trigger fired during Step 4.6. Future T8-C implementation must pause if:

- ProbLog or PyReason starts creating `SupportArtifact` values before T8-C
  implementation begins, invalidating this architecture inventory.
- A T10 item becomes a hard prerequisite for the chosen first implementation
  slice rather than a declared precondition.
- T8-C requires an `EvidenceGraph` schema change or new node/edge kind.
- PyReason Form 2 is pulled into a runtime slice before D11 / Form 2 schema is
  promoted out of sketch status.
- Any planning item attempts to edit runtime, tests, dirty baseline files, or
  user-facing docs.

## 1. Problem

T8-B succeeded because native and Souffle row evidence both used
witness-bearing `SupportArtifact` shapes. T8-C is different: ProbLog and
PyReason currently use provenance-bearing support kinds and adapter trace
converters.

Before opening a runtime T8-C blueprint, we need a source-backed map of the
ProbLog / PyReason evidence surfaces, their relationship to T10 semantics work,
and the smallest credible implementation slices.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15.2 | T8-C row: ProbLog multi-path / probability carrier enrichment, PyReason timeline/Form 2, Nemo opt-in, engine_meta contract/debug split hardening. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §8 / C119 / C136 / D11 / D13 | Form 1/2 topology, ProbLog multi-path, aggregate envelope, PyReason Form 2, Nemo deferrals. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` §3.6 / §6 | T10 C74 / C76 / C77 / C78 semantics adapter anchors and triggers. |
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.4-§4.6 | Existing T8-C split/dependency/D-series planning. |
| `workflow/blueprints/archive/2026-05-27_t8-b-2-souffle-form1-conformance.md` | Cross-flip pattern for verifying reviewer-supplied findings before acting on them. |
| `src/factgraph/core/store/_support.py` | Witness-bearing vs provenance-bearing support-kind taxonomy. |
| `src/factgraph/adapters/problog/provenance.py` | Current ProbLog trace-to-graph and candidate-tree converters. |
| `src/factgraph/adapters/pyreason/provenance.py` | Current PyReason trace parser and timeline graph converter. |
| `tests/test_problog_evidence_graph.py`, `tests/test_pyreason_evidence_graph.py` | Existing adapter evidence regression surfaces. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata gates and T8-B row Form 1 dispatch to preserve. |

## 3. Step 4.6 Inventory Results

### 3.1 Support-Kind Architecture

The reviewer finding is verified: ProbLog and PyReason do not construct
`SupportArtifact` values in their adapter trees.

Reproducible grep:

```bash
rg 'SupportArtifact\(' src/factgraph/adapters/problog/   # no matches
rg 'SupportArtifact\(' src/factgraph/adapters/pyreason/  # no matches
```

Source-backed taxonomy:

| Surface | Source | Finding |
|---|---|---|
| Witness-bearing kinds | `src/factgraph/core/store/_support.py:13-18` | Native + Souffle are witness-bearing: `_WITNESS_BEARING_SUPPORT_KINDS = {"native_binding_v1", SOUFFLE_WITNESS_KIND}`. |
| Provenance-bearing kinds | `_support.py:18-20` | PyReason + ProbLog are provenance-bearing: `_PROVENANCE_BEARING_SUPPORT_KINDS = {PYREASON_PROVENANCE_KIND, PROBLOG_PROVENANCE_KIND}`. |
| `SupportArtifact` shape | `_support.py:97-104` | `SupportArtifact` carries binding items, predicate witnesses, non-fact steps, and rule refs; ProbLog/PyReason adapters do not create it today. |
| Candidate backrefs | `src/factgraph/core/store/_evaluate.py:265-276` | Degraded/provenance support kinds are remembered as candidate support backrefs without witness-artifact lookup. |
| Witness path | `_evaluate.py:277-289` | Only witness-bearing support kinds proceed through witness-artifact support lookup semantics. |

### 3.2 ProbLog Adapter Inventory

| Area | Source | Current state |
|---|---|---|
| Provenance envelope attachment | `src/factgraph/adapters/problog/engine_eval.py:174-195` | Adapter parses raw trace, stores `ProvenanceEnvelope(engine="problog", payload_type="proof_trace")`, and marks candidates with `support_kind=PROBLOG_PROVENANCE_KIND`. |
| Trace parser / model | `src/factgraph/adapters/problog/provenance.py:38-73` | `ProbLogTraceEventV0`, `ProbLogAnswerV0`, `ProbLogTraceV0`, and `parse_problog_trace(...)` define an adapter trace format, not a row-result support artifact. |
| EvidenceGraph converter | `provenance.py:187-297` | `problog_trace_to_evidence_graph(...)` consumes `ProbLogTraceV0` plus candidate anchor fields and returns a tree graph. |
| Node / edge semantics | `provenance.py:249-274` | Root is `NODE_CONCLUSION`; internal calls can be `NODE_PREMISE`; leaves are `NODE_SEED`; edges are `EDGE_DERIVES`, not T8-B Form 1 `EDGE_SUPPORTS`. |
| Metadata | `provenance.py:291-296` | Graph metadata is adapter-local: `event_count`, `answer_count`, `root_goal`, `answer_probability`; it is not the §10.3 14-key row-result bridge. |
| Candidate tree converter | `provenance.py:300-369` | Separate candidate readback path produces candidate evidence tree dicts, not row-level `EvaluateRow.explain()` Form 1 graphs. |
| Tests | `tests/test_problog_evidence_graph.py:45-110` | Tests assert tree layout, `PROBLOG_PROVENANCE_KIND`, `answer_probability`, `EDGE_DERIVES`, synthetic answer anchoring, and missing-anchor rejection. |

§10.3 compatibility: current ProbLog converter metadata has **0 exact field-name
overlap** with the T8-A 14-key metadata set in
`src/factgraph/application/protocol/evaluate_result.py:59-75`. It must be
wrapped or rebuilt through the row-result metadata bridge before it can be used
as live row evidence.

Multi-path status: C119 says ProbLog multi-path DAG is v1 default single-path
and only triggers when the adapter returns multiple candidates with the same
bindings (`evidence-tree...zh.md:2263`, `:2766`). Current tests cover one
selected trace root and one synthetic answer root, not multi-path aggregation
(`tests/test_problog_evidence_graph.py:45-99`).

### 3.3 PyReason Adapter Inventory

| Area | Source | Current state |
|---|---|---|
| Provenance envelope attachment | `src/factgraph/adapters/pyreason/engine_eval.py:166-181` | Adapter stores `ProvenanceEnvelope(engine="pyreason", payload_type="event_log")` and marks candidates with `support_kind=PYREASON_PROVENANCE_KIND`. |
| Trace parser / model | `src/factgraph/adapters/pyreason/provenance.py:30-60` | `PyReasonTraceEventV0`, `PyReasonTraceV0`, and `parse_pyreason_trace(...)` define event-log provenance. |
| EvidenceGraph converter | `provenance.py:113-245` | `pyreason_trace_to_evidence_graph(...)` converts events into an EvidenceGraph with `LAYOUT_TIMELINE`. |
| Node / edge semantics | `provenance.py:179-223` | Matching event becomes `NODE_CONCLUSION`; initial events become `NODE_SEED`; later events become `NODE_PREMISE`; edges use `EDGE_UPDATES`. |
| Metadata | `provenance.py:237-244` | Graph metadata is adapter-local: `timesteps`, event counts, and root component fields; it is not the §10.3 14-key row-result bridge. |
| Tests | `tests/test_pyreason_evidence_graph.py:15-185` | Tests assert timeline layout, `PYREASON_PROVENANCE_KIND`, event-count metadata, `EDGE_UPDATES`, candidate-anchor normalization, and missing-anchor rejection. |

§10.3 compatibility: current PyReason converter metadata has **0 exact field-name
overlap** with the T8-A 14-key metadata set at `evaluate_result.py:59-75`.

Form 2 status: evidence §8.11 is explicitly "sketch only" and defers the
detailed Form 2 schema to D11 (`evidence-tree...zh.md:2068-2095`); §8.14 repeats
that Form 2 PyReason temporal schema is deferred (`:2266-2271`).

### 3.4 T8-A / T8-B Runtime Boundaries To Preserve

| Surface | Source | Preservation requirement |
|---|---|---|
| 14-key metadata | `evaluate_result.py:59-75` | T8-C planning must keep the current row-result graph metadata set intact. |
| Row graph dispatch | `evaluate_result.py:841-849` | `_build_passed_row_evidence_graph(...)` validates metadata before dispatch and delegates only when a row support artifact exists. |
| Form 1 support kinds | `evaluate_result.py:76-77` | `_FORM1_ROW_SUPPORT_KINDS` is protocol-local native + Souffle; T8-C should not widen it during planning. |
| Shared Form 1 helper | `evaluate_result.py:868-1000` | Current helper requires witness-bearing `SupportArtifact` shape; provenance adapters do not satisfy this input. |
| Metadata validation | `evaluate_result.py:1027-1075` | T8-A build/freeze/validate and regenerate-and-compare checks remain the live row-evidence gate. |

### 3.5 Design Anchors

| Anchor | Source | T8-C implication |
|---|---|---|
| Strategy dispatch | `evidence-tree...zh.md:1448-1464`, `:1595` | ProbLog is S1 + S3; PyReason Form 2 is S1 pred-only and not locked. |
| T8-C proposal | `evidence-tree...zh.md:2890-2897` | T8-C covers ProbLog probability/multi-path, PyReason timeline/Form 2, Nemo opt-in, and engine_meta hardening; prerequisite is T10 or engine-specific semantics lock. |
| C119 | `evidence-tree...zh.md:2263`, `:2766` | ProbLog multi-path DAG is deferred unless multiple candidates with same bindings exist. |
| C136 | `evidence-tree...zh.md:2264`, `:2783` | Aggregate premise envelope remains count-only and contributor expansion stays forbidden. |
| D11 | `evidence-tree...zh.md:2858` | PyReason Form 2 evidence requires a separate Form 2 design. |
| D13 | `evidence-tree...zh.md:2860` | Nemo adapter evidence is not part of v1. |
| T10 anchors | `post-t5-completion-roadmap.zh.md:256-259`, `:376-379` | C74/C76/C77/C78 are adapter semantics triggers, not shipped evidence behavior. |

## 4. Open Questions For Step 4.6

| ID | Question | Scoped answer |
|---|---|---|
| Q1 | Which architecture path should T8-C use? | See §4.1. Select **adapter-side metadata bridge / provenance row bridge**, starting with ProbLog after C76 or a ProbLog-specific semantics lock. Reject SupportArtifact bridge for T8-C because current adapters are provenance-bearing and PyReason Form 2 cannot fit witness-bearing Form 1 without schema loss. |
| Q2 | What is the current ProbLog adapter evidence shape? | See §3.2. It is an adapter trace/provenance tree using `EDGE_DERIVES` and adapter-local metadata; it is not §10.3 row-result evidence today. |
| Q3 | What is the current PyReason adapter evidence shape? | See §3.3. It is a timeline graph using `EDGE_UPDATES` and adapter-local event metadata; Form 2 semantics remain sketch/deferred. |
| Q4 | How do T10 C74 / C76 / C77 / C78 affect T8-C-1 and T8-C-2? | See §4.2. C76 is required for ProbLog probability carrier enrichment; C74/C77/C78 are required for PyReason Form 2 claims; cross-engine T8-C should not start before those locks. |
| Q5 | Should T8-C split into ProbLog and PyReason sub-cycles? | Yes. Split into **T8-C-1 ProbLog** and **T8-C-2 PyReason**. T8-C-1 can be scoped after C76 or a ProbLog-specific semantics lock; T8-C-2 should wait for D11/Form 2 and C74/C77/C78. |
| Q6 | Is PyReason Form 2 temporal in T8-C-2 scope or deferred? | Deferred until D11 / Form 2 design is promoted out of sketch status. |
| Q7 | Is C119 ProbLog multi-path DAG in first ProbLog scope or deferred? | Defer full C119 multi-path DAG from the first ProbLog slice unless source inventory proves multiple same-binding candidate paths are already emitted. First ProbLog slice should focus on probability carrier + §10.3 row-result bridge. |
| Q8 | Does T8-C handle C136 aggregate envelope? | No. Keep C136 deferred / separate. It is not unlocked by ProbLog or PyReason provenance converters. |
| Q9 | What is the engine-meta extension policy? | Use per-engine namespaced metadata inside `engine_meta` for future T8-C fields; do not flatten engine-specific fields into generic root-level fields and do not change top-level 14-key graph metadata. |
| Q10 | Is Nemo in any T8-C scope? | No. Nemo stays deferred per D13. |
| Q11 | What durable output shape should this cycle produce? | Option B: blueprint-only split plan. The archived blueprint/audit pair is the durable planning artifact; no separate design-point note is needed. |
| Q12 | Are there stop/amend findings? | None for this planning cycle. Future runtime T8-C work is gated as described above. |

## 4.1 Q1 Architecture Options

| Option | Candidate shape | Estimate | Risk | Decision |
|---|---|---:|---|---|
| A. Force ProbLog/PyReason into `SupportArtifact` / witness path | Create native-like support artifacts for provenance adapters, then reuse `_build_form1_evidence_graph(...)`. | 400-900+ runtime LOC, broad tests | High. Current adapters store `ProvenanceEnvelope` at `engine_eval.py` ProbLog `:181-195` / PyReason `:168-181`; PyReason timeline events do not map cleanly to Form 1 witnesses; this risks schema loss and violates D11 sketch boundary. | Reject. |
| B. Provenance-kind row dispatch in protocol | Add row-result dispatch for `PROBLOG_PROVENANCE_KIND` / `PYREASON_PROVENANCE_KIND`, loading provenance envelopes and wrapping existing converters with §10.3 metadata. | ProbLog 250-550 LOC; PyReason 500-1000+ LOC | Medium for ProbLog; high for PyReason because Form 2 is deferred and converter metadata is adapter-local. | Use as implementation direction only after engine-specific semantics locks; split by engine. |
| C. Adapter-side metadata bridge | Keep adapter converters, add engine-specific row bridge that creates row-result graphs with top-level §10.3 metadata and namespaced engine_meta. | ProbLog 200-450 LOC; PyReason 500-1000+ LOC after Form 2 lock | Medium. Preserves converter boundaries and avoids SupportArtifact coercion, but requires clear producer/consumer fields from T10 or engine-specific blueprint. | Selected planning direction. |
| D. Defer all T8-C until full T10 | No T8-C implementation until all C74/C76/C77/C78 ship. | 0 runtime now | Low technical risk, high delivery delay; blocks useful ProbLog-only planning behind unrelated PyReason semantics. | Reject as too broad; use per-engine gating instead. |

Selected split: **T8-C-1 ProbLog probability/metadata bridge first**, only after
C76 or a ProbLog-specific semantics blueprint locks producer/consumer fields.
**T8-C-2 PyReason Form 2** waits for D11 plus PyReason T10 locks.

## 4.2 Q4 T10 Dependency Matrix

| T10 item | T8-C-1 ProbLog | T8-C-2 PyReason | Source / rationale |
|---|---|---|---|
| C74 PyReason per-rule atom bounds / timestep delay | Orthogonal | Required | C74 is explicitly PyReason (`post-t5...zh.md:256`, `:376`); PyReason evidence must not expose temporal atom bounds before semantics are locked. |
| C76 ProbLog uncertainty projection adapter consumption | Required | Orthogonal | C76 is ProbLog uncertainty (`post-t5...zh.md:257`, `:377`); ProbLog `answer_probability` exists today but producer/consumer semantics must be locked before user-facing enrichment. |
| C77 temporal projection runtime behavior | Orthogonal | Required | C77 triggers time-binned / fact-boundary runtime semantics (`post-t5...zh.md:258`, `:378`); PyReason Form 2 is temporal. |
| C78 PyReason iteration_count execution | Orthogonal | Required if T8-C-2 exposes multi-round inference; otherwise precondition for later PyReason enrichment | C78 is PyReason multi-round execution (`post-t5...zh.md:259`, `:379`). T8-C-2 should either wait or explicitly scope iteration_count out. |

## 4.3 Q5 Split Decision

| Shape | Estimate | Risk | Decision |
|---|---:|---|---|
| Combined ProbLog + PyReason T8-C | 900-1800+ LOC plus broad tests | High. Mixes probability carrier, multi-path DAG, timeline/Form 2, and T10 dependency axes. | Reject. |
| T8-C-1 ProbLog then T8-C-2 PyReason | ProbLog 200-550 LOC after C76; PyReason 500-1000+ LOC after D11/C74/C77/C78 | Moderate and sequenced. | Select. |
| Parallel ProbLog and PyReason cycles | Similar total LOC but competing schema questions | High coordination risk. | Reject until T10 locks exist. |
| Defer both | 0 LOC now | Low immediate risk but loses ProbLog progress after C76. | Reject as default; keep as fallback if C76 is not available. |

## 4.4 Q6-Q10 Scope Decisions

| Item | Decision | Rationale |
|---|---|---|
| PyReason Form 2 temporal | Defer to T8-C-2 after D11 / Form 2 design. | §8.11 says sketch only (`evidence-tree...zh.md:2068-2095`); D11 requires timestamp/component semantics before producer emits timeline graphs (`:2858`). |
| ProbLog C119 multi-path DAG | Defer full multi-path from first T8-C-1 unless adapter inventory proves multiple same-binding paths are already produced. | C119 says v1 default is single-path and multi-path only when ProbLog adapter returns multiple candidates same bindings (`:2263`, `:2766`). |
| C136 aggregate envelope | Defer / separate. | C136 governs aggregate premise topology (`:2264`, `:2783`); current ProbLog/PyReason converter tests do not expose aggregate matched-count substrate. |
| Engine-meta policy | Namespaced per-engine contract/debug fields inside `engine_meta`; no flattening and no new top-level graph metadata keys. | §15.2 T8-C non-goal forbids cross-engine fallback fields and engine_meta flattening (`:2896`). |
| Nemo | Defer completely. | D13 says v1 does not include Nemo adapter evidence (`:2860`). |

## 4.5 Output Shape

Option B, blueprint-only split plan.

Rationale: this cycle is itself the durable T8-C planning artifact, like the T8
split inventory. A separate active design-point note would duplicate the
archived blueprint and risk becoming an implementation design before T10 /
engine-specific semantics are locked.

## 5. Existing Invariants To Preserve

- This cycle is design-only: no runtime/test/user-doc edits unless amended.
- T8-A metadata foundation remains current truth: 14-key graph metadata,
  `run_id` envelope-only, and always-on validation.
- T8-B native + Souffle Form 1 behavior remains current truth.
- T8-D user docs remain current truth for native + Souffle; T8-C planning must
  not teach ProbLog/PyReason enrichment as shipped.
- `_WITNESS_BEARING_SUPPORT_KINDS` and `_FORM1_ROW_SUPPORT_KINDS` must not be
  widened by this planning cycle.
- `EvidenceGraph` DTO schema and node/edge kind vocabulary are not changed.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 3 U` and must not be touched.

## 6. Step 4.6 Inventory Plan

Completed:

1. Exact source refs for support-kind taxonomy in `_support.py`.
2. `rg 'SupportArtifact\('` results for ProbLog and PyReason adapter trees.
3. ProbLog converter/input/output/metadata/test inventory.
4. PyReason converter/input/output/metadata/test inventory.
5. Current row-result bridge / metadata-gate touchpoint inventory.
6. T10 C74/C76/C77/C78 source-anchor map.
7. Evidence C119/C136/D11/D13/Nemo source-anchor map.
8. Q1-Q12 answers with selected split and output shape.
9. No-op baseline result for adapter evidence graph tests.
10. Dirty/sacred status check.

## 7. Proposed Implementation Shape

This cycle has no runtime/test implementation commit. Remaining commits:

1. Closure.
2. Archive.

Future cycles:

1. T8-C-1 ProbLog probability/metadata bridge after C76 or a ProbLog-specific
   semantics lock.
2. T8-C-2 PyReason Form 2 after D11 plus PyReason C74/C77/C78 locks.
3. T8-D follow-up docs only after a T8-C runtime slice ships.

## 8. Acceptance

- [x] Step 4.6 verifies or corrects the ProbLog/PyReason SupportArtifact-free
      finding with source refs.
- [x] Q1-Q12 are answered with file:line or section-anchor support.
- [x] T10 dependency is mapped per C74/C76/C77/C78.
- [x] T8-C-1/T8-C-2 split direction is locked or explicitly deferred.
- [x] Output shape is selected.
- [x] No runtime/test/user-doc/dirty-baseline files are edited.
- [x] Focused no-op baseline and `git diff --check` pass.
- [x] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Completed:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_problog_evidence_graph \
  tests.test_pyreason_evidence_graph \
  tests.test_audit_evidence_graph
# Ran 19 tests in 0.004s - OK

git diff --check
# OK

git status --short --branch
# branch ahead by scoped planning commits; dirty baseline preserved as 4 M + 1 D + 3 U
```

## 10. Outcome / Deviations

Implemented as a design-only inventory cycle.

Cycle chain:

- Draft: `e3bb4ecc`
- Scoped inventory: `17d07d48`
- Closure: `d6b4eed3`

Outcome:

- Verified the reviewer SupportArtifact-free finding with source-backed grep:
  ProbLog and PyReason adapters do not create `SupportArtifact` values and are
  currently provenance-bearing, not witness-bearing.
- Locked the T8-C architecture direction to **adapter-side metadata bridge /
  provenance row bridge**, not T8-B-style SupportArtifact widening.
- Split the future implementation lane:
  - **T8-C-1 ProbLog** after C76 or a ProbLog-specific semantics blueprint
    locks probability producer/consumer fields.
  - **T8-C-2 PyReason** after D11/Form 2 plus C74/C77/C78 locks.
- Deferred full C119 ProbLog multi-path DAG from first ProbLog tranche unless
  the adapter proves multiple same-binding candidate paths are already emitted.
- Deferred C136 aggregate envelope and Nemo.
- Locked future engine-specific metadata policy: namespaced per-engine fields
  inside `engine_meta`, no generic flattening and no top-level 14-key graph
  metadata changes.
- Selected Option B output shape: blueprint-only split plan. No separate active
  design-point note was created.

Verification:

- `PYTHONPATH=src python -m unittest tests.test_problog_evidence_graph tests.test_pyreason_evidence_graph tests.test_audit_evidence_graph`
  - `Ran 19 tests in 0.004s - OK`
- `git diff --check`
  - OK
- Dirty baseline preserved as `4 M + 1 D + 3 U`.
- Sacred master preserved at `562c74195df43e933bed92a3ff25de94dd8ce666`.

No runtime, test, user-doc, release, service/OpenAPI, SDK API, database/view,
dirty-baseline, or sacred-master changes.
