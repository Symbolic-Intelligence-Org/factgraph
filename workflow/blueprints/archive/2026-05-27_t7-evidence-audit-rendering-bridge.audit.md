# Audit: T7 Evidence Audit + Rendering Bridge

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t7-evidence-audit-rendering-bridge.md`
- Stage: implemented
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `c9979476` | T7 blueprint pair drafted | Triggered by user selection after T6 design published and T11.2.10 OR match runtime completed. |
| 2026-05-27 | scoped | `5c5187e2` | Step 4.6 source-backed inventory recorded | Q1-Q8 answered; renderer type guard / large warning bridge, metadata tests, docs updates, T8 deferrals, D12/D20 handling, and full-discover baseline locked. |
| 2026-05-27 | implementation | `c6b76878` | Runtime bridge landed | `render_evidence_graph_html(...)` now rejects non-`EvidenceGraph` input and emits non-blocking large-graph guidance for tree/timeline layouts. |
| 2026-05-27 | implementation | `04697038` | Focused tests landed | Renderer type/threshold cases plus §10.3 metadata key and envelope-only `run_id` regression. |
| 2026-05-27 | implementation | `3d77dc94` | Audit docs aligned | `audit/docs/02_evidence_graph.md` updated for sessionless contract, metadata keys, safe JSON path, renderer threshold, T8 boundary, and D20 future seam. |
| 2026-05-27 | closure | this commit | T7 closure recorded | Outcome, deviations, verification, and reviewer observations recorded. |

## 2. Draft Source Scan

Read-only draft scan findings:

- `src/factgraph/audit/evidence_graph.py` already contains the primary runtime
  artifacts: `EvidenceNode`, `EvidenceEdge`, `EvidenceGraph`,
  `evidence_graph_to_dict(...)`, `evidence_graph_from_dict(...)`, and
  `render_evidence_graph_html(...)`.
- `EvidenceGraph` construction already validates enum layout, duplicate
  node/edge ids, root membership, edge endpoints, and graph cycles.
- The renderer already has `tree` and `timeline` dispatch paths.
- T6 `evidence-tree-rainbird-style-v1.zh.md` §10 and §11 now define the
  design-side audit and renderer contracts that T7 should compare against.
- The initial scan did not answer Q1-Q8. Those answers must be produced in
  Step 4.6 with source-backed file:line refs.

## 3. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | `EvidenceGraph` DTO fields | `EvidenceNode` fields at `evidence_graph.py:24-35`; `EvidenceEdge` at `:42-51`; `EvidenceGraph` at `:59-70`. Metadata/engine_meta are shallow-frozen through `MappingProxyType` at `:36-37`, `:53-56`, and `:72-75`. |
| 2 | DTO validation | `EvidenceGraph.__post_init__` rejects unsupported layout, duplicate node ids, duplicate edge ids, missing root, bad edge endpoints, and cycles at `evidence_graph.py:72-115`. |
| 3 | JSON roundtrip | `evidence_graph_to_dict(...)` is at `evidence_graph.py:127-161`; `evidence_graph_from_dict(...)` is at `:164-187`; current roundtrip test is `tests/test_audit_evidence_graph.py:158-197`. |
| 4 | Renderer entrypoints | `render_evidence_graph_html(...)` dispatches at `evidence_graph.py:118-124`; tree layout is `:190-269`; timeline layout is `:272-371`; header renderer is `:437-453`. |
| 5 | Renderer current gaps | No large-graph threshold exists in runtime. Renderer is duck-typed: `tests/test_audit_evidence_graph_render.py:152-157` passes a fake object with `layout_hint="dag"` and expects a layout error. T7 should require constructed `EvidenceGraph` input. |
| 6 | Minimal / empty / invalid / unsupported | Minimal graphs render normally. Empty graphs fail root validation (`evidence_graph.py:85-87`). Invalid dicts fail through `evidence_graph_from_dict(...)` and graph construction. Unsupported explanations cannot carry evidence by `Explanation.__post_init__` at `evaluate_result.py:218-246`. |
| 7 | Evaluate result envelope | `EvaluateResult` fields are `result_id/run_id/rows/head/engine/engine_version/adapter_version/expr_digest/rule_set_digest/view_snapshot_digest/semantics_digest/evaluated_at/result_digest` at `evaluate_result.py:128-143`; validation is `:151-181`. |
| 8 | Explanation / graph metadata bridge | `_explain_live_row(...)` builds checked scope and graph metadata at `evaluate_result.py:553-630`; `_build_passed_row_evidence_graph(...)` copies metadata to the minimal graph at `:800-820`; `_evidence_metadata_for_row_result(...)` writes 14 §10.3 keys at `:823-842`. |
| 9 | Existing metadata tests | `tests/application/protocol/test_evaluate_result_dtos.py:293-312` checks passed Explanation and selected metadata keys, but not the full §10.3 key set or absent `run_id`. |
| 10 | Audit docs gap | `src/factgraph/audit/docs/02_evidence_graph.md:1-5` is last updated 2026-04-30; data model and renderer sections exist at `:28-113`, but the doc predates T6 §10/§11 and lacks the sessionless contract, §10.3 metadata keys, large warning, safe JSON path, T8 split, and D20 boundary. |
| 11 | Focused baseline | `tests.test_audit_evidence_graph` + `tests.test_audit_evidence_graph_render`: 17 OK. PyReason/Souffle/ProbLog evidence graph tests: 9 OK. Proof-frame/round-events/candidate/core-annotation/match regression group: 95 OK. |
| 12 | Full discover baseline | `PYTHONPATH=src python -m unittest discover tests` ran 2001 tests and failed with 72 failures / 233 errors. Observed categories include existing frontier evaluator arity errors, SDK redesign invariant mismatches, and legacy why_not path assertions. This is baseline status, not T7-specific. |
| 13 | T6 §10/§11 matrix | Filled in the blueprint §4.2. Runtime gap is limited to renderer type guard and large warning; metadata central sufficiency checker is T8-A, not T7. |
| 14 | T8 mapping | T7-in: no T8 slice implementation. T7 may mention bridge boundaries in docs. T8-out: T8-A central metadata builder/sufficiency checker, T8-B topology, T8-C engine enrichment, T8-D product docs. |
| 15 | D-series scan | D12 is touched by large graph warning. D20 gets docs cross-reference only; no witness API shape. D1-D11/D13-D19 stay deferred. |
| 16 | Test plan | Extend `tests/test_audit_evidence_graph_render.py` for type guard, below-threshold no warning, node-threshold warning, edge-threshold warning. Extend `tests/application/protocol/test_evaluate_result_dtos.py` for all §10.3 keys and absent `run_id`. |
| 17 | Stop/amend findings | None. No T8 graph construction, service/OpenAPI, SDK API, release, or dirty-baseline change is needed. |
| 18 | Dirty / sacred | Dirty baseline remains four tracked docs/notebooks plus untracked `rainbird-ai sdk code/`; sacred master remains `562c74195df43e933bed92a3ff25de94dd8ce666`. |

## 4. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Does current `EvidenceGraph` DTO + JSON roundtrip + renderer fully cover T6 §10 sessionless three-layer metadata contract? | Partial. DTO/roundtrip/metadata bridge exist; renderer threshold and safe-render input guard are missing; central metadata sufficiency checker remains T8-A. |
| Q2 | Is there runtime layered consistency checking between `EvaluateResult`, row `Explanation`, and `EvidenceGraph.metadata`; if not, where should it live? | Current row-explain path derives graph metadata from one result/row context; T7 adds tests for the full key set. Reusable sufficiency checker belongs to T8-A. |
| Q3 | Does `render_evidence_graph_html(...)` implement the §11 `>250` node / `>500` edge warning or handoff path? | No. T7 implements a warning banner and keeps rendering; no truncation/refusal. |
| Q4 | What is current minimal / empty / invalid / unsupported render behavior, and does it match §11? | Minimal and invalid behavior aligns; empty is impossible under DTO validation; unsupported means no renderer call. Type guard gap exists because renderer is duck-typed. |
| Q5 | Which T8-A/B/C/D slices, if any, are bridge-class T7 scope? | None. T7 only clarifies and tests bridge boundaries. |
| Q6 | Which D1-D20 items are triggered by T7? | D12 renderer large-graph warning; D20 docs cross-reference only. |
| Q7 | What must change in `src/factgraph/audit/docs/02_evidence_graph.md`? | Add sessionless contract, §10.3 metadata keys, renderer threshold, safe JSON path, T8 split boundary, and D20 future seam note. |
| Q8 | What exact tests cover metadata consistency, roundtrip, threshold warning, fallback cases, and relevant regressions? | Renderer type/threshold tests plus evaluate-result metadata full-key test; focused audit/engine suites remain regression gates. |

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| T7 expands into T8 graph construction | L-class implementation drift | Explicitly map T8-A/B/C/D to T7-in or T7-out. |
| Runtime bridge breaks existing graph dict compatibility | Audit package regression | Inventory current dict shape and add roundtrip regression tests if touched. |
| Session/audit v2 features leak into v1 | Violates T6 sessionless boundary | Keep session logs, signatures, ACL, and interactions out of scope. |
| Renderer starts making product UI promises | Overclaims reference renderer | Lock reference-vs-product boundary from §11. |
| Metadata checks are placed at the wrong layer | Confusing or duplicated invariants | Source-map `EvaluateResult`, `Explanation`, and graph metadata first. |
| Full test discovery failures obscure T7 signal | Closure ambiguity | Record focused results and full-discover status separately. |

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q8 answered.
- [x] Runtime bridge changes reviewed, if any.
- [x] Tests reviewed.
- [x] Docs/design updates reviewed.
- [x] Closure notes filled.

## 7. Closure Notes

T7 landed as a narrow audit/rendering bridge rather than a T8 implementation
cycle.

Landed scope:

- `c6b76878` added the renderer bridge: `render_evidence_graph_html(...)`
  rejects non-`EvidenceGraph` inputs and emits a non-blocking large-graph warning
  when a graph has more than 250 nodes or more than 500 edges.
- `04697038` added focused tests for renderer type guard, threshold boundaries,
  non-truncating warning behavior, the full §10.3 graph metadata key set, and
  envelope-only `run_id`.
- `3d77dc94` aligned `src/factgraph/audit/docs/02_evidence_graph.md` with T6
  §10/§11, including sessionless layering, safe JSON path, T8 boundary, and D20
  future match witness seam.

Verification:

- `tests.test_audit_evidence_graph` + `tests.test_audit_evidence_graph_render`:
  20 OK.
- `tests.test_pyreason_evidence_graph` + `tests.test_souffle_evidence_graph` +
  `tests.test_problog_evidence_graph`: 9 OK.
- `tests.test_audit_proof_frame_diff` + `tests.test_audit_round_events` +
  `tests.test_candidate_evidence_steps` + `tests.test_core_annotation_evidence`
  + `tests.test_sdk_read_match_runtime` +
  `tests.application.protocol.test_evaluate_result_dtos`: 106 OK.
- `ruff` passed for touched runtime/test files.
- `git diff --check` passed.

Boundary notes:

- The large-graph banner uses `role='note'`, an implementation choice matching
  guidance/handoff semantics rather than alert/error semantics.
- The existing unsupported-layout `ValueError` after renderer dispatch is now
  defensive dead code under normal construction because `EvidenceGraph` validates
  layout hints and the renderer now rejects non-`EvidenceGraph` inputs first. It
  remains as defense in depth.
- Central metadata sufficiency remains deferred to T8-A. T7 only added a strict
  regression test for the current 14-key §10.3 graph metadata contract.
- T8-A/B/C/D, service/OpenAPI, SDK API shape, database/view runtime, release
  machinery, and dirty-baseline cleanup stayed out of scope.

Sacred master remained `562c74195df43e933bed92a3ff25de94dd8ce666`; dirty
baseline remained the four tracked docs/notebooks plus untracked
`rainbird-ai sdk code/`.
