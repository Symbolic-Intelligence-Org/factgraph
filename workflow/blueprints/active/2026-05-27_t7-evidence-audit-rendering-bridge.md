# Task Blueprint: T7 Evidence Audit + Rendering Bridge

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M (scoped bridge: renderer input/large warning + tests/docs)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t7-evidence-audit-rendering-bridge.audit.md`
- Trigger: T6 completed the evidence Phase B design source, including §10 audit channel and §11 rendering. Existing audit runtime already has `EvidenceGraph`, JSON roundtrip, and HTML rendering; T7 maps and bridges shipped behavior to that design before T8 evidence implementation starts.

## 0. Scope Locks

### In scope

T7 is a **design-to-shipped bridge**, not a from-zero implementation. It should
compare current runtime behavior against T6 §10/§11 contracts, then land only
bridge-class runtime, test, and docs changes that make the existing audit layer
honestly match the design.

Candidate bridge areas:

1. **Source-backed gap map** between T6 §10/§11 and shipped `src/factgraph/audit` / `evaluate_result.py` behavior.
2. **Audit envelope layering**: runtime validation or invariant checks for the sessionless three-layer model if Step 4.6 finds a concrete gap.
3. **Metadata consistency**: `EvaluateResult` envelope fields, row `Explanation`, and durable `EvidenceGraph.metadata` consistency checks if currently missing and bridge-sized.
4. **Reference renderer thresholds**: warning / handoff path for `>250` nodes or `>500` edges if absent.
5. **Renderer fallback behavior**: minimal, empty, invalid, and unsupported graph behavior aligned with §11 if gaps are found.
6. **Safe JSON render path**: ensure `from_dict -> render` is the validated path and unsafe direct rendering is not encouraged.
7. **Audit module docs**: align `src/factgraph/audit/docs/02_evidence_graph.md` with the T6 §10/§11 contract.
8. **T8 split mapping**: classify T8-A/B/C/D as T7-in or T7-out; T7 may only take bridge-class pieces.

### Out of scope

- T8 graph construction, engine enrichment, failure localization, or topology work.
- D1/D2 why-not / counterfactual runtime surface.
- v2+ features from §14 such as salience, impact, `/interactions/{sessionID}`, `x-evidence-key`, per-fact ACL, signatures, or session logs.
- D20 match witness API design or implementation.
- `where_eval`, `where_ast`, RuleExpr lowering, `core/store/runtime.py`, or match runtime changes.
- Service / OpenAPI endpoints.
- Database / view runtime.
- Cross-entity match output or `fg.eval.run` deletion.
- Public SDK API shape changes for match / evaluate / explain.
- Release machinery, PyPI, tags, or live release work.
- Dirty baseline cleanup.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- T7 requires changing `EvidenceGraph`'s public schema or breaking JSON roundtrip compatibility.
- Bridge work expands into T8 graph construction, engine enrichment, or failure localization.
- The design requires session ids, session logs, ACL, signatures, or external interaction APIs in v1.
- The renderer contract requires product UI behavior rather than reference diagnostics.
- Fixes require service/OpenAPI or public SDK API shape changes.
- Implementation would touch dirty baseline notebooks/reference docs or unrelated release machinery.

## 1. Problem

T6 made the evidence design source implementable, but the runtime layer predates
that design. The current audit package already has real pieces:

- `EvidenceGraph` DTOs and validation;
- JSON dict roundtrip helpers;
- tree and timeline HTML rendering;
- engine-specific evidence graph tests.

The risk is not absence of runtime. The risk is drift between shipped runtime
behavior and T6's new sessionless audit/rendering contract. T7 should produce a
source-backed map of that drift and land only the small bridges needed before
T8 starts larger evidence implementation work.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §10 | Audit channel contract: sessionless three-layer model, metadata field separation, validation, roundtrip, immutability, and v2 deferrals. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §11 | Rendering contract: reference renderer boundary, layout matrix, fallback cases, large graph warning, safe JSON path, and custom UI obligations. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §14/§15 | Deferred registry and T8-A/B/C/D implementation split proposal. |
| `workflow/blueprints/archive/2026-05-27_t6-evidence-phase-b-design.md` and audit | T6 source inventory and closure rationale. |
| `src/factgraph/audit/evidence_graph.py` | Existing `EvidenceGraph`, node/edge DTOs, validation, roundtrip, and HTML renderer truth. |
| `src/factgraph/audit/dto.py`, `query.py`, `reader.py` | Current audit query/read surface and package boundaries. |
| `src/factgraph/audit/assertions.py`, `authoring_events.py`, `round_events.py`, `proof_frame_diff.py` | Existing audit event/proof-frame support that may inform boundary checks. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Current audit module docs to align with T6. |
| `src/factgraph/application/protocol/evaluate_result.py` | `EvaluateResult`, `Explanation`, evidence metadata bridge, and minimal evidence graph builder. |
| Existing audit/engine tests | Regression baseline for EvidenceGraph, renderers, PyReason/Souffle/ProbLog evidence graphs, proof-frame diff, round events, and annotation evidence. |

## 3. Draft Source Scan

Draft source scan confirms T7 is not from-zero:

- `src/factgraph/audit/evidence_graph.py` already defines `EvidenceNode`,
  `EvidenceEdge`, and frozen `EvidenceGraph` with metadata mapping freeze,
  duplicate id checks, root/endpoint validation, and cycle detection.
- `evidence_graph_to_dict(...)` and `evidence_graph_from_dict(...)` already
  provide a JSON-compatible roundtrip path.
- `render_evidence_graph_html(...)` already dispatches to tree and timeline
  renderers.
- T6 §10 and §11 are now complete enough to act as the comparison source for
  runtime behavior.
- T7 should not invent graph construction or engine enrichment; those belong to
  T8 or later cycles.

This scan is intentionally high level. Step 4.6 must replace it with concrete
file:line-backed shipped/partial/missing classifications.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Shipped vs design gap map | Completed in §4.2. |
| Q2 | Layered metadata consistency | Current row-explain path derives graph metadata from one evaluated context; central metadata sufficiency validator remains T8-A. T7 adds regression tests for the full §10.3 key set and `run_id` envelope-only stance. |
| Q3 | Large graph threshold | Missing in renderer; T7 implements a reference-renderer warning banner for `>250` nodes or `>500` edges. No truncation or refusal. |
| Q4 | Renderer fallback cases | Minimal/invalid/unsupported behavior is mostly shipped; safe-render input guard is partial because the renderer is duck-typed. T7 requires `EvidenceGraph` input before dispatch. |
| Q5 | T8 split mapping | T7-in: only bridge-class renderer/docs/tests. T8-A/B/C/D implementation slices remain out of scope. |
| Q6 | §14 D-series triggers | D12 is touched by large-graph warning. D20 gets docs cross-reference only; no API shape. D1-D11/D13-D19 remain deferred. |
| Q7 | Audit docs alignment | `src/factgraph/audit/docs/02_evidence_graph.md` needs T6 §10/§11 sessionless audit, metadata key, renderer threshold, safe JSON path, and T8/D20 boundary updates. |
| Q8 | Test matrix | Add render threshold/type guard tests and row-explain metadata key coverage; preserve existing audit/engine evidence focused suites. |

## 4.1 Final Scoped Decisions

| Decision | Scoped lock |
|---|---|
| Runtime bridge size | T7 is a small bridge, not T8-A. Runtime changes are limited to `src/factgraph/audit/evidence_graph.py` renderer input validation and large-graph warning banner. |
| Metadata consistency | Do not introduce a central metadata sufficiency checker in T7. Current row-explain builder already derives metadata from one `EvaluateResult`/row context; T7 tests the full §10.3 copied key set and records that central validation belongs to T8-A. |
| Large graph behavior | Add warning HTML when `len(nodes) > 250` or `len(edges) > 500`; still render the graph. No truncation, refusal, logging API, or DTO field. |
| Safe JSON render path | `render_evidence_graph_html(...)` should accept only constructed `EvidenceGraph` instances. External/durable dicts must pass through `evidence_graph_from_dict(...)` first. |
| Fallback behavior | Minimal valid graphs render; empty/invalid graphs fail at constructor/from_dict; unsupported explanations call no renderer. T7 documents and tests these boundaries, but does not add placeholder graph behavior. |
| T8 mapping | T8-A central metadata builder/sufficiency checker, T8-B topology, T8-C engine enrichment, and T8-D product docs remain future T8 work. |
| D-series | D12 large-graph guidance is activated only as a renderer warning. D20 receives docs hygiene cross-reference only. |
| Class | M. The source inventory found bridge-sized runtime work plus docs/tests; no production graph-construction work is needed. |

## 4.2 T6 §10 / §11 Contract Matrix

| Contract area | T6 anchor | Current shipped state | T7 decision |
|---|---|---|---|
| Three-layer sessionless audit | `evidence-tree...:2331-2349` | Partial/shipped: `EvaluateResult` fields and validation exist at `evaluate_result.py:128-181`; `Explanation` status and evidence envelope exist at `:202-272`; `EvidenceGraph.metadata` exists at `evidence_graph.py:59-75`. No session log is present. | No session work. Record as aligned; docs should call it sessionless. |
| Envelope fields | `evidence-tree...:2351-2373` | Shipped: `EvaluateResult` validates `result_id`, `run_id`, engine, digests, view digest, semantics digest, result digest, and rows at `evaluate_result.py:151-181`. | Preserve. `run_id` remains envelope-only. |
| Graph metadata §10.3 fields | `evidence-tree...:2375-2398` | Shipped for passed row graphs: `_evidence_metadata_for_row_result(...)` writes 14 keys at `evaluate_result.py:823-842`; `_build_passed_row_evidence_graph(...)` copies them at `:800-820`. Existing test checks selected keys at `tests/application/protocol/test_evaluate_result_dtos.py:293-312`, but not the full set. | Add regression test for all 14 keys plus absent `run_id`. Central checker deferred to T8-A. |
| Validation / roundtrip | `evidence-tree...:2400-2419` | Shipped DTO validation: layout, duplicate nodes/edges, missing root, endpoints, cycles at `evidence_graph.py:72-115`. Roundtrip helpers are at `:127-187`; tests cover roundtrip at `tests/test_audit_evidence_graph.py:158-197`. | Preserve. Add no new schema. |
| Immutability / signature stance | `evidence-tree...:2421-2438` | Shipped shallow freeze: node/edge engine_meta and graph metadata use `MappingProxyType` at `evidence_graph.py:36-37`, `:53-56`, `:72-75`; tests cover freeze at `tests/test_audit_evidence_graph.py:134-156`. | Preserve; no signature/session/ACL work. |
| Audit package boundary | `evidence-tree...:2440-2461` | Partial/shipped: package reader reads optional `evidence_graphs` and reconstructs via `evidence_graph_from_dict(...)` at `reader.py:192-208`; duplicate candidate ids fail at `:202-207`; docs are stale from 2026-04-30. | Docs update only. |
| Renderer layering | `evidence-tree...:2465-2482` | Shipped entrypoint and tree/timeline dispatch at `evidence_graph.py:118-124`; docs describe standalone fragment at `audit/docs/02_evidence_graph.md:93-113`. | Preserve entrypoint; update docs with reference-vs-product boundary. |
| Layout matrix | `evidence-tree...:2484-2492` | Shipped modes are constants at `evidence_graph.py:8-21`; tree renderer at `:190-269`; timeline at `:272-371`. Existing tests cover both layouts at `tests/test_audit_evidence_graph_render.py:21-150`. | Preserve. |
| Minimal / empty / invalid / unsupported | `evidence-tree...:2527-2537` | Minimal valid graphs render via normal tree/timeline paths. Empty graph impossible because root must be in nodes (`evidence_graph.py:85-87`). Invalid graph constructors/from_dict raise. Unsupported explanation has `evidence=None` by `Explanation` invariant at `evaluate_result.py:218-246`. | Add/adjust focused tests if needed; no placeholder graphs. |
| Large graph guidance | `evidence-tree...:2539-2553` | Missing: renderer has no node/edge threshold scan or warning (`evidence_graph.py:118-124`, `:190-371`). | Implement warning banner; still render graph. |
| Safe JSON renderer path | `evidence-tree...:2555-2565` | Partial: `evidence_graph_from_dict(...)` validates durable dicts (`evidence_graph.py:164-187`), but `render_evidence_graph_html(...)` is duck-typed and current test passes a fake object at `tests/test_audit_evidence_graph_render.py:152-157`. | Require `EvidenceGraph` instance at renderer entry and update tests/docs. |
| Custom UI obligations | `evidence-tree...:2567-2582` | Product UI not implemented in audit runtime. Current docs mention service/static_ui embedding at `audit/docs/02_evidence_graph.md:111-155`. | Docs update; no product UI work. |

## 5. Existing Invariants To Preserve

- `EvidenceGraph` remains frozen and keeps metadata as an immutable mapping.
- Existing node/edge id uniqueness, root existence, endpoint reference checks,
  and cycle detection remain intact.
- `evidence_graph_to_dict(...)` / `evidence_graph_from_dict(...)` remain
  backward-compatible for existing graph dicts.
- `render_evidence_graph_html(...)` keeps its public entrypoint and tree /
  timeline layout names.
- Existing PyReason, Souffle, ProbLog, annotation, proof-frame, and round-event
  tests must not regress.
- T6's v1 audit stance remains sessionless: no session id API, no session log,
  `run_id` stays envelope-level, and no external `/interactions/{sessionID}`
  dependency appears.
- C110 canonical quantitative carrier constraints remain untouched.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four tracked docs/notebooks plus untracked
  `rainbird-ai sdk code/`.

## 6. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | `EvidenceGraph` DTO / validation | Fields at `evidence_graph.py:59-70`; validation at `:72-115`; metadata freeze at `:72-75`; node/edge freeze at `:36-37` and `:53-56`. Shipped and preserved. |
| 2 | Roundtrip | `evidence_graph_to_dict(...)` at `evidence_graph.py:127-161`; `evidence_graph_from_dict(...)` at `:164-187`; roundtrip test at `tests/test_audit_evidence_graph.py:158-197`. Shipped and preserved. |
| 3 | Renderer entrypoints | `render_evidence_graph_html(...)` dispatches at `evidence_graph.py:118-124`; tree layout at `:190-269`; timeline at `:272-371`. Shipped, but lacks type guard and large warning. |
| 4 | Minimal / empty / invalid / unsupported | Minimal graph renders through normal renderer; empty graph cannot satisfy root validation; invalid graph raises in constructor/from_dict; unsupported explanation enforces `evidence=None` at `evaluate_result.py:218-246`. |
| 5 | Result/explanation metadata bridge | `EvaluateResult` fields at `evaluate_result.py:128-143`, validation at `:151-181`; `_explain_live_row(...)` builds checked scope and graph metadata at `:553-630`; metadata writer at `:823-842`. |
| 6 | Audit docs gap | `audit/docs/02_evidence_graph.md` is last updated 2026-04-30 (`:1-5`), predates T6 §10/§11, does not list §10.3 metadata keys, large graph warning, safe JSON path, or T8/D20 boundary. |
| 7 | Focused tests | Existing audit graph/render tests cover validation, roundtrip, tree/timeline render, and duplicate candidate ids. Engine graph tests cover PyReason/Souffle/ProbLog conversions. Focused baseline: 17 audit graph/render OK, 9 engine graph OK, 95 related audit/match OK. |
| 8 | T6 matrix | Completed in §4.2; implementation scope is renderer type guard + large warning + tests/docs. |
| 9 | T8 mapping | T7-in: none of T8-A/B/C/D implementation slices. T7 may record that T8-A should own central metadata sufficiency. T8-out: T8-A metadata builder/checker, T8-B topology, T8-C enrichment, T8-D product docs. |
| 10 | D1-D20 scan | D12 large graph is touched by a renderer warning. D20 match witness seam receives docs cross-reference only. D1-D11 and D13-D19 remain deferred. |
| 11 | Test plan | Extend `tests/test_audit_evidence_graph_render.py` for type guard, no-warning below threshold, warning above node/edge thresholds. Extend `tests/application/protocol/test_evaluate_result_dtos.py` for full §10.3 metadata keys and envelope-only `run_id`. Existing tests cover roundtrip and invalid graph. |
| 12 | Full discover baseline | `PYTHONPATH=src python -m unittest discover tests` ran 2001 tests and failed with 72 failures / 233 errors, matching unrelated frontier/legacy/why_not/redesign-invariant categories; not a T7 gate. |
| 13 | Stop/amend findings | None. No T8 graph construction, service/OpenAPI, SDK API, or release change is required. |
| 14 | Dirty / sacred | Dirty baseline remains four tracked docs/notebooks plus untracked `rainbird-ai sdk code/`; sacred master remains `562c74195df43e933bed92a3ff25de94dd8ce666`. |

## 7. Implementation Split Proposal

Scoped implementation split:

1. **Runtime bridge**: update `src/factgraph/audit/evidence_graph.py` with an
   `EvidenceGraph` type guard at `render_evidence_graph_html(...)` and a
   reference-renderer large-graph warning banner for `>250` nodes or `>500`
   edges. No schema, graph construction, or product UI change.
2. **Tests**: extend renderer tests for type guard and warning/no-warning
   behavior; extend evaluate-result DTO tests for the full §10.3 metadata key
   set and absent `run_id` in graph metadata.
3. **Docs**: update `src/factgraph/audit/docs/02_evidence_graph.md` with T6
   §10/§11 sessionless audit, metadata key, renderer threshold, safe JSON path,
   T8 split, and D20 boundary notes.
4. **Closure**: record shipped/partial/missing map, T8 deferrals, focused
   results, and full-discover baseline.

## 8. Acceptance

- [x] Step 4.6 inventory answers Q1-Q8 with source-backed evidence.
- [x] T6 §10/§11 contract areas are mapped to shipped / partial / missing.
- [x] Any runtime bridge changes are limited to audit/rendering bridge scope.
- [x] Existing `EvidenceGraph` schema and JSON roundtrip remain compatible.
- [x] Reference renderer large-graph and fallback behavior are either shipped or explicitly deferred with rationale.
- [x] T8-A/B/C/D mapping is recorded and does not silently start T8.
- [x] Audit docs align with the final scoped bridge behavior.
- [x] Focused audit/render/engine evidence tests pass.
- [x] Full `unittest discover` status is recorded.
- [x] `ruff` and `git diff --check` pass for touched files.
- [x] Dirty baseline and sacred master are preserved.

## 9. Verification Commands

Draft expected commands, to be finalized after Step 4.6:

```bash
PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render
PYTHONPATH=src python -m unittest tests.test_pyreason_evidence_graph tests.test_souffle_evidence_graph tests.test_problog_evidence_graph
PYTHONPATH=src python -m unittest tests.test_audit_proof_frame_diff tests.test_audit_round_events tests.test_candidate_evidence_steps tests.test_core_annotation_evidence
PYTHONPATH=src python -m unittest tests.test_sdk_read_match_runtime
PYTHONPATH=src python -m unittest discover tests
python -m ruff check src/factgraph/audit tests
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

## 10.1 Landed artifacts

| Stage | Commit | Scope |
|---|---|---|
| Draft | `c9979476` | Blueprint pair for T7 evidence audit + rendering bridge. |
| Scoped | `5c5187e2` | Source-backed Q1-Q8 inventory, T6 §10/§11 matrix, T8/D-series mapping, and focused/full-discover baseline. |
| Runtime bridge | `c6b76878` | `render_evidence_graph_html(...)` type guard plus large-graph warning banner for tree and timeline layouts. |
| Tests | `04697038` | Renderer type/threshold tests and full §10.3 metadata key regression. |
| Docs | `3d77dc94` | Audit module docs aligned to T6 §10/§11, T8 boundary, and D20 future seam. |

## 10.2 Runtime bridge outcome

T7 landed two bridge-sized runtime changes in
`src/factgraph/audit/evidence_graph.py`:

- `render_evidence_graph_html(...)` now rejects unvalidated non-`EvidenceGraph`
  inputs with `ValueError("graph must be EvidenceGraph")`, aligning the render
  entrypoint with `evidence_graph_to_dict(...)` and `Explanation` evidence type
  checks.
- Tree and timeline renderers now include a reference-renderer warning banner
  when `len(nodes) > 250` or `len(edges) > 500`.

The warning is non-blocking:graphs still render, no nodes/edges are truncated,
and no DTO field or product-UI state is added. The banner uses `role='note'` as
an implementation choice:it is guidance / handoff, not an alert or error.

The existing unsupported-layout `ValueError` after the layout dispatch is now
defensive dead code under normal construction: invalid `layout_hint` is rejected
by `EvidenceGraph.__post_init__`, and non-`EvidenceGraph` inputs are rejected by
the new type guard. It remains as defense in depth.

## 10.3 Test outcome

Tests now enforce the scoped bridge:

- renderer rejects duck-typed fake graph input;
- exactly `250` nodes does not warn;
- `251` nodes warns and still renders the last node;
- `501` edges warns and still renders the last node;
- row-sourced passed explanations produce exactly the 14 §10.3 metadata keys;
- `run_id` remains envelope-only and absent from `EvidenceGraph.metadata`.

Focused verification:

```text
tests.test_audit_evidence_graph + tests.test_audit_evidence_graph_render: 20 OK
tests.test_pyreason_evidence_graph + tests.test_souffle_evidence_graph + tests.test_problog_evidence_graph: 9 OK
tests.test_audit_proof_frame_diff + tests.test_audit_round_events + tests.test_candidate_evidence_steps + tests.test_core_annotation_evidence + tests.test_sdk_read_match_runtime + tests.application.protocol.test_evaluate_result_dtos: 106 OK
```

Full discover baseline remains recorded from Step 4.6:
`PYTHONPATH=src python -m unittest discover tests` ran 2001 tests and failed
with 72 failures / 233 errors in unrelated frontier / legacy / why_not /
redesign-invariant categories. T7 did not use full discover as a pass/fail gate.

## 10.4 Docs outcome

`src/factgraph/audit/docs/02_evidence_graph.md` now records:

- the v1 sessionless three-layer audit contract;
- `run_id` as envelope-level rather than graph metadata;
- the full 14-key `EvidenceGraph.metadata` bridge;
- safe JSON path: external/durable dicts pass through
  `evidence_graph_from_dict(...)` before rendering;
- reference renderer truthfulness and large-graph guidance;
- T8 ownership for central metadata sufficiency, richer topology, and engine
  enrichment;
- D20 match witness seam as future-only docs hygiene, not an API stub.

## 10.5 Deviations and boundary notes

- §0 listed conditional candidate areas; §4.1 became the scoped source of truth
  after inventory. Runtime narrowed to type guard + large warning only.
- Central metadata sufficiency validation stayed deferred to T8-A; T7 added a
  regression test for the current §10.3 key set instead.
- T8-A/B/C/D were all mapped out of T7 implementation scope.
- No service/OpenAPI, SDK API, database/view runtime, release machinery,
  match/evaluate API, or dirty-baseline files were touched.

## 10.6 Verification

- `python -m ruff check src/factgraph/audit/evidence_graph.py tests/test_audit_evidence_graph_render.py tests/application/protocol/test_evaluate_result_dtos.py` passed.
- `git diff --check` passed.
- Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained the four tracked docs/notebooks plus untracked
  `rainbird-ai sdk code/`.
