# Task Blueprint: T8-B-2 Souffle Form 1 Conformance

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M-M pending Step 4.6
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-b-2-souffle-form1-conformance.audit.md`
- Trigger: T8-B-1 native Form 1 topology shipped at `9e9a7f49`; T8-D A+B docs shipped at `22891808`; T8-B scoped inventory deferred Souffle row-result Form 1 alignment to T8-B-2.

## 0. Scope Locks

### In scope

This cycle is the Souffle lane follow-up to T8-B-1. It may land runtime and test
changes only after Step 4.6 verifies Souffle support artifacts, row-result
metadata needs, and the lowest-risk strategy.

Candidate scope:

1. Source-backed inventory of Souffle `SupportArtifact` creation, current
   Souffle proof-tree converter, T8-B-1 native dispatch, and SDK support
   artifact plumbing.
2. Strategy decision among:
   - extending the T8-B-1 Form 1 helper to accept Souffle support artifacts,
   - adding a dedicated Souffle Form 1 helper,
   - reusing/migrating `souffle_proof_tree_to_evidence_graph(...)`.
3. Souffle row-result Form 1 `EvidenceGraph` support if Step 4.6 finds the
   current substrate is compatible.
4. SDK/protocol support-artifact plumbing extension for Souffle, while
   preserving native handling unchanged.
5. Focused tests for Souffle row Form 1, plus regressions for T8-A metadata,
   T8-B-1 native Form 1, Souffle converter, audit graph/render, candidate
   evidence, and non-Souffle adapter evidence tests.
6. Audit module docs only if shipped Souffle row behavior changes the
   user-visible audit contract.

### Out of scope

- ProbLog / PyReason Form 1 or engine enrichment; those remain T8-C.
- T10 semantics adapter execution.
- T8-D user-facing quickstart / SDK docs round 2; record as a follow-up if
  Souffle behavior ships.
- D20 match witness, failed graph, why-not, or counterfactual surfaces.
- Aggregate count-only envelope unless Step 4.6 finds an already-shipped
  matched-count substrate.
- `EvidenceGraph` DTO schema changes or new node/edge kinds.
- Changing the §10.3 14-key metadata contract or moving `run_id` into graph
  metadata.
- Service / OpenAPI, Database / view runtime, match API, `fg.eval.run`
  deletion, release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting candidate evidence tree or Souffle converter wholesale.
- Weakening T8-A validation gates or changing
  `_evidence_metadata_for_row_result(...)` signature.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- Souffle `SupportArtifact` structure is not native-like enough for a
  bridge-class implementation.
- The cycle needs `EvidenceGraph` schema changes, new node/edge kinds, new
  metadata keys, or `run_id` in graph metadata.
- Existing native Form 1 behavior or T8-A metadata validation must regress.
- Existing `tests/test_souffle_evidence_graph.py` must regress to land the
  row-result path.
- Scope touches ProbLog, PyReason, T8-C, D20, dirty baseline, service/OpenAPI,
  release machinery, Database/view, match, or user-facing T8-D docs.

## 1. Problem

T8-B-1 shipped native row-level Form 1 evidence graphs and deliberately deferred
Souffle row-result conformance. Souffle already has a candidate-side proof-tree
to `EvidenceGraph` converter, and reviewer due diligence found that current
Souffle support artifacts may mirror the native support artifact shape.

The risk is under-scoping or over-scoping: Souffle row explanations may require
only a small dispatch/plumbing extension, or they may require adapter-specific
metadata alignment that should remain a separate tranche. Step 4.6 must verify
the actual shipped substrate before choosing a strategy.

## 2. Inputs

| Source | Role |
|---|---|
| `src/factgraph/adapters/souffle/engine_eval.py` | Souffle `SupportArtifact` construction site. |
| `src/factgraph/core/store/_support.py` | `SupportArtifact` dataclass and `SOUFFLE_WITNESS_KIND`. |
| `src/factgraph/adapters/souffle/provenance.py` | Existing Souffle proof-tree to `EvidenceGraph` converter. |
| `tests/test_souffle_evidence_graph.py` | Existing Souffle converter regression baseline. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata gate, T8-B-1 native dispatch, Form 1 helper, and metadata bridge. |
| `src/factgraph/sdk/store.py` | Current `_row_support_artifacts_for_candidates(...)` support-kind filter. |
| `workflow/blueprints/archive/2026-05-27_t8-b-form1-topology.md` §4.4/§4.6 | T8-B-1 scoped Souffle deferral and conformance finding. |
| `workflow/blueprints/archive/2026-05-27_t8-a-metadata-validation-foundation.md` | C135 runtime-enforced metadata foundation. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §8.13 / §10.3 / §15.2 | C115/C117/C118/C129/C136, 14-key metadata, and T8-B design source. |

## 3. Draft Source Scan

Draft orientation only, to be verified by Step 4.6:

- T8-B-1 currently dispatches Form 1 graph construction only for native support
  artifacts.
- `sdk/store.py` currently filters row support artifacts to native support
  kind only.
- Souffle has two relevant surfaces: row-evaluation support artifacts and the
  older proof-tree converter.
- Reviewer due diligence found a likely native-like Souffle `SupportArtifact`
  construction path in `engine_eval.py`, but the Step 4.6 inventory must verify
  exact fields, kind names, atom-key conventions, and metadata implications
  before implementation.

This scan does not answer Q1-Q9.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Which strategy should T8-B-2 use: trivial extension, dedicated Souffle helper, or converter reuse? | Three-option comparison with file/test/LOC estimates, risks, and selected strategy. |
| Q2 | Do native Form 1 `engine_meta` fields apply to Souffle support artifacts? | Per-field compatibility table for premise/seed/root metadata and decision on same-shape vs Souffle-specific additions. |
| Q3 | What is the role of `souffle_proof_tree_to_evidence_graph(...)` after row-result conformance? | Keep/migrate/defer decision with candidate-side vs row-result boundary. |
| Q4 | How should SDK support plumbing admit Souffle artifacts? | Allowlist/denylist/other strategy with rationale and native regression implications. |
| Q5 | How should `_build_passed_row_evidence_graph(...)` dispatch after Souffle support lands? | Dispatch strategy and trace showing T8-A validation gates are preserved. |
| Q6 | What is the test matrix? | Souffle row Form 1 tests plus Souffle converter, native Form 1, T8-A, audit/render, candidate, PyReason, and ProbLog regressions. |
| Q7 | Are audit module docs updated in this cycle? | Docs/no-docs decision based on shipped user-visible audit contract. |
| Q8 | Does Souffle shipping trigger a T8-D round 2 user-docs follow-up? | In-cycle vs follow-up decision with rationale. |
| Q9 | Are there stop/amend findings? | None or explicit scope amendment trigger. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata and `run_id` envelope-only validation remains
  always-on.
- `_evidence_metadata_for_row_result(row, result)` keeps its signature.
- T8-B-1 native Form 1 behavior and SDK end-to-end assertions do not regress.
- `_build_passed_row_evidence_graph(...)` remains the single row graph
  validation/dispatch wrapper unless Step 4.6 explicitly amends it.
- `EvidenceGraph` DTO fields, node kinds, edge kinds, roundtrip, renderer type
  guard, and large-graph warning remain compatible.
- Form 1 uses existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and
  `EDGE_SUPPORTS`; no schema expansion.
- T6 v1 sessionless boundary remains intact: no session ids, session logs,
  `/interactions/{sessionID}`, ACL, signatures, salience, impact, or
  `x-evidence-key`.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four modified tracked docs/notebooks plus
  three untracked reference directories.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce source-backed answers for Q1-Q9 and at least:

1. Exact source refs for Souffle support artifact creation and fields.
2. Exact source refs for `SOUFFLE_WITNESS_KIND` and native support kind usage.
3. Exact source refs for T8-B-1 native Form 1 helper and dispatch.
4. Exact source refs for SDK support artifact filtering/plumbing.
5. Exact source refs for current Souffle proof-tree converter shape and tests.
6. Per-field `engine_meta` compatibility table.
7. Strategy comparison for trivial extension vs dedicated helper vs converter
   reuse.
8. Test matrix and verification commands.
9. Docs update / T8-D follow-up decision.
10. Full-discover baseline comparison plan against the T8-B-1 recorded
    baseline (`2004 tests`, `72 failures`, `233 errors`).
11. Dirty/sacred status.
12. Stop/amend findings and final class.

## 7. Proposed Implementation Shape

Implementation is deliberately hypothetical until Step 4.6.

Likely commit split, if a bridge-class strategy is confirmed:

1. Runtime bridge for the selected Souffle row Form 1 strategy.
2. Focused Souffle row Form 1 tests and native/T8-A regressions.
3. Audit docs only if user-visible audit behavior changes.
4. Closure / archive.

## 8. Acceptance

- [ ] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [ ] Souffle strategy is selected with file/test/LOC/risk rationale.
- [ ] T8-A metadata validation and 14-key contract are preserved.
- [ ] T8-B-1 native Form 1 behavior does not regress.
- [ ] Existing Souffle converter tests remain green or any regression causes
      stop/amend.
- [ ] Focused tests cover any shipped Souffle row Form 1 behavior.
- [ ] No `EvidenceGraph` schema, node/edge kind, metadata-contract, T8-C,
      service/OpenAPI, release, match, database/view, or dirty-baseline changes
      land.
- [ ] `git diff --check` passes.
- [ ] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_souffle_evidence_graph \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_sdk_read_match_runtime \
  tests.test_candidate_evidence_steps \
  tests.test_pyreason_evidence_graph \
  tests.test_problog_evidence_graph

PYTHONPATH=src python -m unittest discover tests

ruff check \
  src/factgraph/adapters/souffle/engine_eval.py \
  src/factgraph/adapters/souffle/provenance.py \
  src/factgraph/application/protocol/evaluate_result.py \
  src/factgraph/sdk/store.py \
  tests/test_souffle_evidence_graph.py \
  tests/application/protocol/test_evaluate_result_dtos.py

git diff --check
git status --short --branch
```

Step 4.6 must confirm final commands after strategy selection.

## 10. Outcome / Deviations

Pending scoped inventory / implementation / closure.
