# Task Blueprint: T7 Evidence Audit + Rendering Bridge

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M/L (design-to-shipped bridge; expected to narrow after Step 4.6)
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
| Q1 | Shipped vs design gap map | For each T6 §10/§11 contract area, classify current runtime as shipped / partial / missing with file:line refs. |
| Q2 | Layered metadata consistency | Decide whether current `EvaluateResult` envelope, row `Explanation`, and durable `EvidenceGraph.metadata` have enough runtime consistency checks; identify the layer where any new invariant belongs. |
| Q3 | Large graph threshold | Determine whether `render_evidence_graph_html(...)` implements `>250` node or `>500` edge warning/handoff; if not, choose bridge-sized behavior and test surface. |
| Q4 | Renderer fallback cases | Classify current minimal, empty, invalid, and unsupported graph render behavior against T6 §11. |
| Q5 | T8 split mapping | Map T8-A/B/C/D to T7-in or T7-out, with explicit deferral for graph construction/enrichment. |
| Q6 | §14 D-series triggers | Identify D1-D20 items touched by T7, if any. D20 match witness seam must remain API-shape deferred unless scoped otherwise. |
| Q7 | Audit docs alignment | List concrete stale or incomplete statements in `src/factgraph/audit/docs/02_evidence_graph.md` and decide docs edits. |
| Q8 | Test matrix | Lock focused tests for metadata consistency, roundtrip metadata preservation, threshold warning, fallback cases, and relevant regressions. |

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

## 6. Step 4.6 Inventory Plan

Step 4.6 must complete a source-backed inventory before implementation:

1. Current `EvidenceGraph` fields, immutability, validation, and roundtrip
   behavior with file:line refs.
2. Current renderer entrypoints, layout behavior, and unsupported-layout
   behavior with file:line refs.
3. Current behavior for minimal, empty, invalid, and large graphs.
4. Current `EvaluateResult`, `Explanation`, and metadata bridge fields with
   file:line refs.
5. Current audit docs claims and gaps against T6 §10/§11.
6. Existing focused test modules and what they already cover.
7. T6 §10/§11 requirement matrix: shipped / partial / missing.
8. T8-A/B/C/D mapping: T7-in bridge work vs T8-out implementation work.
9. D1-D20 triggered item scan.
10. Proposed test matrix and exact test files to add/extend.
11. Verification commands and any known unrelated full-discover failures.
12. Dirty baseline and sacred master preservation check.
13. Stop/amend findings, if any.

## 7. Implementation Split Proposal

Likely split after Step 4.6:

1. **Runtime bridge**: validator/metadata/render warning/safe path work only if
   Step 4.6 finds bridge-sized gaps.
2. **Tests**: focused audit/render/roundtrip/metadata tests for every bridge
   runtime change.
3. **Docs**: update `src/factgraph/audit/docs/02_evidence_graph.md` and, only
   if needed, narrow design cross-links.
4. **Closure**: record shipped/partial/missing map, explicit T8 deferrals, test
   results, and any full-discover status note.

If Step 4.6 finds no runtime gap, implementation may narrow to docs/tests only;
if it finds T8-sized work, stop and amend.

## 8. Acceptance

- [ ] Step 4.6 inventory answers Q1-Q8 with source-backed evidence.
- [ ] T6 §10/§11 contract areas are mapped to shipped / partial / missing.
- [ ] Any runtime bridge changes are limited to audit/rendering bridge scope.
- [ ] Existing `EvidenceGraph` schema and JSON roundtrip remain compatible.
- [ ] Reference renderer large-graph and fallback behavior are either shipped or explicitly deferred with rationale.
- [ ] T8-A/B/C/D mapping is recorded and does not silently start T8.
- [ ] Audit docs align with the final scoped bridge behavior.
- [ ] Focused audit/render/engine evidence tests pass.
- [ ] Full `unittest discover` status is recorded.
- [ ] `ruff` and `git diff --check` pass for touched files.
- [ ] Dirty baseline and sacred master are preserved.

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

Pending implementation.
