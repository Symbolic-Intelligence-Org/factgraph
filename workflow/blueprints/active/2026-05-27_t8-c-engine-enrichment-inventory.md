# Task Blueprint: T8-C Engine Enrichment Inventory

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (design-only planning inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-c-engine-enrichment-inventory.audit.md`
- Trigger: T8-A, T8-B-1, T8-B-2, and T8-D round 2 are shipped; T8-C remains the evidence track's engine-enrichment lane and is gated by T10 or engine-specific semantics locks.

## 0. Scope Locks

### In scope

This is a **T8-C pre-implementation inventory cycle**, not T8-C
implementation. It should quantify ProbLog / PyReason enrichment boundaries
before any runtime blueprint starts.

Candidate planning outputs:

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
6. T8-C-1 / T8-C-2 split decision: ProbLog, PyReason, combined, sequential,
   parallel, or defer.
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

Pause and amend before closure if Step 4.6 shows:

- The reviewer finding is materially wrong: ProbLog or PyReason already creates
  `SupportArtifact` instances for the relevant row-result path.
- A T10 item is a hard prerequisite, not merely a coordination dependency, for
  any credible T8-C implementation slice.
- T8-C requires an `EvidenceGraph` schema change or new node/edge kind.
- PyReason Form 2 must be in scope but the design source is still only sketch /
  deferred.
- Any planning item attempts to edit runtime, tests, dirty baseline files, or
  user-facing docs.

## 1. Problem

T8-B succeeded because native and Souffle row evidence both used
witness-bearing `SupportArtifact` shapes. T8-C is different: the current
reviewer due-diligence finding says ProbLog and PyReason do not create
`SupportArtifact` values and instead use provenance-bearing support kinds.

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

## 3. Draft Source Scan

Draft orientation only:

- T8-C is explicitly described as engine enrichment in evidence §15.2, with a
  prerequisite on T10 or engine-specific semantics locks.
- T10 is adapter-execution semantics work, not the same axis as evidence
  enrichment, but it may define producer/consumer fields that T8-C must not
  pre-empt.
- Reviewer due diligence found that ProbLog and PyReason appear to be
  provenance-bearing rather than witness-bearing; Step 4.6 must verify this
  independently with source refs.
- Existing ProbLog / PyReason converters already produce `EvidenceGraph`
  values, but they are adapter trace/provenance converters, not necessarily
  row-result §10.3 metadata bridges.

This draft scan does not answer Q1-Q12. Step 4.6 must replace it with
source-backed file:line and section-anchor evidence.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Which architecture path should T8-C use: SupportArtifact bridge, provenance-kind row dispatch, adapter-side metadata bridge, or another path? | At least three options with file/test/LOC/risk estimates and selected planning direction. |
| Q2 | What is the current ProbLog adapter evidence shape? | Source-backed inventory of trace converter, graph metadata, multi-path status, §10.3 compatibility, and generic Form 1 compatibility. |
| Q3 | What is the current PyReason adapter evidence shape? | Source-backed inventory of trace converter, timeline/Form 2 status, §10.3 compatibility, and generic/Form 2 compatibility. |
| Q4 | How do T10 C74 / C76 / C77 / C78 affect T8-C-1 and T8-C-2? | Per-C-id mapping: required, nice-to-have, orthogonal, or blocker. |
| Q5 | Should T8-C split into ProbLog and PyReason sub-cycles? | Split/combined/sequential/parallel decision with file/test/LOC estimates and risks. |
| Q6 | Is PyReason Form 2 temporal in T8-C-2 scope or deferred? | Decision citing D11, §8.11/§8.14, and §15.2 T8-C. |
| Q7 | Is C119 ProbLog multi-path DAG in first ProbLog scope or deferred? | Decision citing C119 and current converter/trace capabilities. |
| Q8 | Does T8-C handle C136 aggregate envelope? | Decision: T8-C-1, T8-C-2, separate T8-C-3, or defer. |
| Q9 | What is the engine-meta extension policy? | Per-engine namespace / generic fields / no flattening decision consistent with §15.2 non-goal. |
| Q10 | Is Nemo in any T8-C scope? | Opt-in/defer decision citing §15.2 and D13. |
| Q11 | What durable output shape should this cycle produce? | Design-point note, blueprint-only split plan, or hybrid. |
| Q12 | Are there stop/amend findings? | None or explicit trigger with next action. |

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

Step 4.6 must produce:

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

This cycle is expected to have no runtime/test implementation commit. Likely
commits:

1. Draft blueprint/audit.
2. Scoped source-backed inventory.
3. Optional durable design note if Step 4.6 selects one.
4. Closure.
5. Archive.

## 8. Acceptance

- [ ] Step 4.6 verifies or corrects the ProbLog/PyReason SupportArtifact-free
      finding with source refs.
- [ ] Q1-Q12 are answered with file:line or section-anchor support.
- [ ] T10 dependency is mapped per C74/C76/C77/C78.
- [ ] T8-C-1/T8-C-2 split direction is locked or explicitly deferred.
- [ ] Output shape is selected.
- [ ] No runtime/test/user-doc/dirty-baseline files are edited.
- [ ] Focused no-op baseline and `git diff --check` pass.
- [ ] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_problog_evidence_graph \
  tests.test_pyreason_evidence_graph \
  tests.test_audit_evidence_graph

git diff --check
git status --short --branch
```

Step 4.6 may refine these commands after source-backed inventory.

## 10. Outcome / Deviations

Pending scoped inventory / closure.
