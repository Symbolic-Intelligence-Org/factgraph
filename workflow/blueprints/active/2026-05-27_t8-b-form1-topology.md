# Task Blueprint: T8-B Native/Souffle Form 1 Topology

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: L unless Step 4.6 narrows to native-only or Souffle-only
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-b-form1-topology.audit.md`
- Trigger: T8-A metadata/validation foundation shipped at `40a0ce47`, so T8 split inventory's next recommended evidence implementation lane is T8-B Native/Souffle Form 1 topology.

## 0. Scope Locks

### In scope

This cycle is the second T8 implementation slice. It may land runtime topology
work only after Step 4.6 quantifies the Native/Souffle split and confirms a
manageable tranche.

Candidate scope:

1. Source-backed inventory of candidate evidence tree builders, candidate
   evidence traversal/step surfaces, Souffle provenance converter, and current
   passed-row `EvidenceGraph` construction.
2. Narrowing decision: native-only, Souffle-only, both in one cycle, or split
   into T8-B-1 native and T8-B-2 Souffle.
3. Reuse-before-rewrite mapping from existing candidate evidence helpers to
   §15.2 Form 1 topology.
4. Form 1 topology bridge using existing `NODE_CONCLUSION`,
   `NODE_PREMISE`, `NODE_SEED`, and existing `EDGE_SUPPORTS` direction.
5. Seed reuse strategy for repeated facts inside the shipped tranche.
6. Winning-path-only OR semantics for successful explanations, if the scoped
   tranche touches OR-shaped evidence.
7. Minimal aggregate count-only envelope where the current substrate can
   support C136 without expanding contributor facts.
8. Focused tests for the scoped topology tranche plus regressions for T7
   renderer/DTO behavior and T8-A metadata validation.
9. Audit docs only if the shipped topology changes user-visible audit contract.

### Out of scope

- T8-C engine enrichment, ProbLog, PyReason Form 2, Nemo, or T10 adapter
  semantics.
- T8-D product/user docs unless Step 4.6 finds a narrow docs update required by
  shipped T8-B behavior.
- Failed graph, why-not, counterfactual, match witness output, or D20 API work.
- Changing `EvidenceGraph` DTO schema or adding node/edge kinds.
- Changing the 14-key §10.3 metadata contract or moving `run_id` into graph
  metadata.
- Service / OpenAPI, Database / view runtime, match API, `fg.eval.run`
  deletion, release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting the candidate evidence tree wholesale.
- Weakening T8-A validation gates, changing `_evidence_metadata_for_row_result`
  signature, or bypassing C135 runtime enforcement.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- T8-B requires `EvidenceGraph` schema changes or new node/edge kinds.
- The native/Souffle tranche cannot reuse existing candidate evidence or
  Souffle converter surfaces and would become a rewrite.
- The selected tranche needs new metadata keys or `run_id` in graph metadata.
- Existing candidate evidence or Souffle tests must regress to land topology.
- T8-A metadata validation must be weakened or bypassed.
- Scope touches dirty baseline, service/OpenAPI, release machinery, match,
  database/view runtime, or adapter topology beyond the scoped Souffle lane.

## 1. Problem

T6 designed Form 1 evidence topology, T7 aligned the audit/rendering bridge, and
T8-A made the row evidence metadata bridge runtime-enforced. The remaining T8-B
question is whether the existing native candidate evidence tree and Souffle
provenance converter can be bridged into the §15.2 Form 1 shape without
rewriting the evidence substrate.

T8-B is not from-zero evidence graph construction. The highest-risk work is
selecting the right tranche size and proving that "reuse before rewrite" is
real for the current codebase.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15.2 | T8-B row: Native/Souffle success topology, prerequisite, non-goals. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §8 | Form 1 topology, edge direction, seed reuse, OR, and aggregate topology contracts. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` C115/C117/C118/C129/C136 | Commitments for edge direction, 4-layer topology, seed reuse, winning-path-only OR, and aggregate count-only envelope. |
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.4/§4.5 | T8-B reuse-before-rewrite planning and dependency graph. |
| `workflow/blueprints/archive/2026-05-27_t8-a-metadata-validation-foundation.md` | T8-A shipped metadata/validation invariant that T8-B must preserve. |
| `src/factgraph/core/store/_candidate_evidence_tree.py` | Existing native candidate evidence tree builder helpers. |
| `src/factgraph/core/store/_candidate_evidence_tree_steps.py` | Existing traversal and public candidate evidence step builder. |
| `src/factgraph/adapters/souffle/provenance.py` | Existing Souffle proof tree to `EvidenceGraph` converter. |
| `src/factgraph/audit/evidence_graph.py` | Existing node/edge kinds, DTO validation, roundtrip, and renderer behavior. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata gate and current passed-row graph construction. |
| Candidate/Souffle/audit/protocol tests | Existing regression gates and expected new topology test entry points. |

## 3. Draft Source Scan

Draft scan confirms orientation only:

- `EvidenceGraph` already has the 3 node kinds and 3 edge kinds needed by
  Form 1.
- The evidence design already defines Form 1 topology, seed reuse, and
  aggregate count-only boundaries.
- Candidate evidence tree and Souffle converter code already exist and should
  be evaluated as reuse targets before any new construction.
- T8-A validation is now the required metadata foundation for any new graph
  construction path.

This scan does not answer Q1-Q9. Step 4.6 must replace it with source-backed
file:line evidence and final scoped decisions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Should T8-B be native-only, Souffle-only, both in one cycle, or split into T8-B-1 native + T8-B-2 Souffle? | File/test boundaries, LOC estimates, risk comparison, and a selected tranche with rationale. |
| Q2 | How do candidate evidence tree helpers map to §15.2 Form 1 topology? | Reuse / thin-adapter / new-helper table for `_build_support_sections`, `_build_predicate_witness_group`, `_build_assertion_leaf`, traversal, and related helpers. |
| Q3 | Does `souffle_proof_tree_to_evidence_graph(...)` already conform to Form 1? | Source-backed conformance/gap analysis and decision whether Souffle work is hook-up, adapter, or deferred. |
| Q4 | What are the Form 1 node/edge population rules for the selected tranche? | Deterministic rule for `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and edge direction with §8/C115/C117 anchors. |
| Q5 | What is the seed reuse strategy? | Decision on cross-row or intra-graph seed de-duplication, with §8/C118 anchors and test implications. |
| Q6 | How is winning-path-only OR represented? | Source-backed statement of whether the selected tranche touches OR and how C129 is preserved. |
| Q7 | Where does C136 aggregate count-only envelope live? | Decision on `engine_meta` placement or explicit deferral if aggregate substrate is out of tranche. |
| Q8 | What is the test matrix? | Matrix covering selected native/Souffle topology, seed reuse, OR/aggregate if scoped, and T7/T8-A regressions. |
| Q9 | How should `_build_passed_row_evidence_graph(...)` change? | Direct replacement vs new helper selection vs defer; must preserve T8-A validation gates. |

## 5. Existing Invariants To Preserve

- T8-A metadata validation remains always-on and unweakened.
- `_evidence_metadata_for_row_result(row, result)` keeps its signature and
  `run_id` remains envelope-only.
- `EvidenceGraph` DTO fields, node kinds, edge kinds, validation, JSON
  roundtrip, renderer type guard, and large-graph warning remain compatible.
- Form 1 uses existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED` and
  existing edge kinds; no schema expansion without amendment.
- T6 v1 sessionless boundary remains intact: no session ids, session logs,
  `/interactions/{sessionID}`, ACL, signatures, salience, impact, or
  `x-evidence-key`.
- T8-B must be bridge-class work, not a candidate evidence tree rewrite.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four tracked docs/notebooks plus two
  untracked reference directories.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce source-backed answers for Q1-Q9 and at least:

1. Exact source refs for candidate evidence tree builder helpers and their
   current output shape.
2. Exact source refs for candidate evidence traversal / step builder behavior.
3. Exact source refs for Souffle proof tree converter shape and tests.
4. Exact source refs for current `EvidenceGraph` node/edge constants,
   validation, and render/roundtrip invariants.
5. Exact source refs for current `_build_passed_row_evidence_graph(...)` and
   T8-A validation gates.
6. §8/C115/C117/C118/C129/C136 design anchors for edge direction, Form 1,
   seed reuse, winning-path-only OR, and aggregate count-only envelope.
7. Native-only / Souffle-only / combined / split class and LOC estimates.
8. Reuse-before-rewrite mapping table.
9. Test matrix with existing and new test modules.
10. Docs update decision.
11. Full-discover baseline comparison plan.
12. Dirty/sacred status.
13. Stop/amend findings and final class.

## 7. Proposed Implementation Shape

Implementation shape is intentionally provisional until Step 4.6. If scoped as
M/L rather than full L, likely split:

1. Runtime bridge for the selected native/Souffle tranche.
2. Tests for Form 1 topology plus existing candidate/Souffle/audit/protocol
   regression gates.
3. Docs only if user-facing audit contract changes.
4. Closure / archive.

If Step 4.6 finds both native and Souffle are too large together, narrow before
implementation rather than landing a partial hidden split.

## 8. Acceptance

- [ ] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [ ] Narrow decision is locked with LOC/test/risk rationale.
- [ ] Reuse-before-rewrite mapping is complete.
- [ ] Form 1 node/edge/seed/OR/aggregate boundaries are locked for the selected
      tranche or explicitly deferred with rationale.
- [ ] T8-A metadata validation and 14-key contract are preserved.
- [ ] Existing candidate evidence and Souffle tests remain green or any
      regression causes stop/amend.
- [ ] Focused tests cover shipped T8-B behavior.
- [ ] No `EvidenceGraph` schema, node/edge kind, service/OpenAPI, release,
      match, database/view, or dirty-baseline changes land.
- [ ] `git diff --check` passes.
- [ ] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.test_candidate_evidence_steps \
  tests.test_souffle_evidence_graph \
  tests.application.protocol.test_evaluate_result_dtos

PYTHONPATH=src python -m unittest discover tests

ruff check \
  src/factgraph/core/store/_candidate_evidence_tree.py \
  src/factgraph/core/store/_candidate_evidence_tree_steps.py \
  src/factgraph/adapters/souffle/provenance.py \
  src/factgraph/application/protocol/evaluate_result.py \
  tests/test_candidate_evidence_steps.py \
  tests/test_souffle_evidence_graph.py \
  tests/application/protocol/test_evaluate_result_dtos.py

git diff --check
git status --short --branch
```

Step 4.6 must confirm the final suite based on selected tranche.

## 10. Outcome / Deviations

Pending implementation / closure.
