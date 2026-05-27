# Task Blueprint: T8-A Metadata + Validation Foundation

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M (may split to S/M sub-cycles after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-a-metadata-validation-foundation.audit.md`
- Trigger: T8 split inventory archived at `a872fa5b` recommends T8-A as the first evidence implementation slice and identifies metadata builder / sufficiency checker / validation gate / debug assertion as the foundation before T8-B/T8-C topology and enrichment work.

## 0. Scope Locks

### In scope

This cycle is the first T8 implementation slice. It may land one tightly scoped
runtime tranche if Step 4.6 confirms the current file boundaries remain M-class:

1. Source-backed inventory of the current evidence metadata writer,
   row-explain path, minimal graph builder, and `EvidenceGraph` validation.
2. Decision on whether T8-A ships as one blueprint with two commits or splits
   into T8-A-1 / T8-A-2 before implementation.
3. Central metadata builder boundary for the current 14-key §10.3 graph
   metadata contract.
4. Metadata sufficiency checker boundary for graph metadata produced from
   `EvaluateResult` + `EvaluateRow`.
5. Strict graph validation gate boundary around row explanation graph
   construction and unsupported-result fallback.
6. Debug assertion boundary for envelope/row/graph consistency.
7. Focused tests that preserve the exact 14-key metadata set, `run_id`
   envelope-only stance, existing EvidenceGraph validation/roundtrip behavior,
   and row-explain pass/unsupported behavior.
8. Module docs or design docs only if Step 4.6 finds a narrow shipped-contract
   update is needed.

### Out of scope

- T8-B Native/Souffle success topology.
- T8-C engine enrichment, PyReason Form 2, ProbLog enrichment, or T10 adapter
  semantics.
- T8-D product/user documentation beyond a narrow T8-A shipped-contract note.
- Failed graph, why-not, counterfactual, session log, ACL, signature, salience,
  impact, `x-evidence-key`, or D20 match witness API work.
- Changing the 14-key §10.3 metadata contract unless the blueprint is amended.
- Moving `run_id` into `EvidenceGraph.metadata`.
- Service / OpenAPI, Database / view runtime, match API, `fg.eval.run`
  deletion, release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting candidate evidence tree or adapter provenance surfaces.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- T8-A cannot remain M-class because the metadata builder/checker needs a new
  public schema, durable module boundary, or cross-engine API.
- The 14-key graph metadata set must change.
- `run_id` or session identity must enter graph metadata.
- Strict validation requires graph topology or engine enrichment work that
  belongs to T8-B/T8-C.
- Debug assertion requires always-on behavior that could break existing passed
  explanations in normal runtime.
- Any change touches dirty baseline, service/OpenAPI, release machinery, or
  candidate/adapter evidence tree code.

## 1. Problem

T7 aligned the shipped audit/rendering bridge with T6 §10/§11 and added strict
tests for the current 14-key graph metadata bridge. T8 split inventory then
identified T8-A as the first implementation slice: centralize the metadata
builder, add a reusable sufficiency check, and tighten validation/debug
assertions before topology or engine enrichment work begins.

The current implementation is already functional but localized:
`_evidence_metadata_for_row_result(...)` builds graph metadata inline, row
explanation passes that metadata to `_build_passed_row_evidence_graph(...)`,
and `EvidenceGraph.__post_init__` validates structural graph shape. T8-A should
bridge these surfaces into a clearer foundation without changing public
metadata semantics.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.3 | T8-A four-subitem boundary and LOC estimates. |
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.5 | Dependency graph: T8-A precedes T8-B/T8-C. |
| `workflow/blueprints/archive/2026-05-27_t7-evidence-audit-rendering-bridge.md` §4.2 | T7 12-row contract matrix, especially metadata/validation rows. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §10.3 | Current 14-key graph metadata source of truth. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15 | T8-A/B/C/D split proposal and T8-A-first recommendation. |
| `src/factgraph/application/protocol/evaluate_result.py` | `EvaluateResult`, `Explanation`, metadata writer, row explain path, graph builder. |
| `src/factgraph/audit/evidence_graph.py` | `EvidenceGraph` DTO validation and roundtrip/renderer substrate. |
| `tests/application/protocol/test_evaluate_result_dtos.py` | 14-key metadata and `run_id` envelope-only regression anchor. |
| `tests/test_audit_evidence_graph.py` | EvidenceGraph validation and roundtrip regression anchor. |

## 3. Draft Source Scan

Draft scan confirms only orientation:

- `EvaluateResult` validates envelope fields and row identity in
  `evaluate_result.py`.
- `_explain_live_row(...)` derives metadata from one `EvaluateResult` + row
  context and catches `ValueError` from graph construction as an unsupported
  explanation.
- `_evidence_metadata_for_row_result(...)` currently writes the 14 graph
  metadata keys inline.
- `EvidenceGraph.__post_init__` already enforces structural graph constraints.
- T7 tests enforce exact 14-key graph metadata and absent `run_id`.

This scan does not answer the Step 4.6 questions. Step 4.6 must replace it with
source-backed file:line evidence and final scoped decisions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Should T8-A ship as one blueprint or split into T8-A-1 / T8-A-2? | Decision with rationale and commit/subcycle plan. |
| Q2 | What is the central metadata builder shape? | Choose boundary without changing the 14-key contract; list current callers and backward-compat plan. |
| Q3 | What is the metadata sufficiency checker shape? | Decide callable/helper semantics, exact error type, and whether it is public/internal. |
| Q4 | How should the strict graph validation gate integrate with `_explain_live_row(...)`? | Decide whether validation remains `ValueError -> unsupported` or gains a narrower error path; preserve existing behavior unless justified. |
| Q5 | How should debug assertion be enabled? | Decide always-on vs test-only/helper-only vs explicit debug flag, with risk assessment. |
| Q6 | Which tests are mandatory before implementation? | Matrix mapping each T8-A subitem to existing/new test modules and backwards-compat regression cases. |
| Q7 | Are module docs or design docs required in this cycle? | File list or explicit no-doc decision with rationale. |
| Q8 | What remains deferred to T8-B/T8-C/T8-D? | Explicit non-goals after inventory, including D-series boundaries. |
| Q9 | Are there any stop/amend findings from source inventory? | None or explicit amend trigger. |

## 5. Existing Invariants To Preserve

- `EvidenceGraph.metadata` remains the exact current §10.3 14-key set for
  passed row graphs unless this blueprint is amended.
- `run_id` remains envelope-only and absent from `EvidenceGraph.metadata`.
- `EvidenceGraph` structural validation, JSON roundtrip, renderer type guard,
  and large-graph warning remain compatible with T7 behavior.
- Existing row explanations continue to produce `status="passed"` with an
  `EvidenceGraph` for valid rows and `status="unsupported"` when graph
  construction fails validation.
- T8-A does not add graph topology beyond the current single-node passed-row
  graph.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the current modified docs/notebooks plus untracked
  reference material.

## 6. Step 4.6 Inventory Plan

Fill these with source-backed results before implementation:

1. Exact source refs for `EvaluateResult` fields, validation, and row binding.
2. Exact source refs for `_explain_live_row(...)`, graph-builder injection,
   `ValueError` unsupported fallback, and passed explanation construction.
3. Exact source refs for `_evidence_metadata_for_row_result(...)` and the
   14-key writer.
4. Exact source refs for `_build_passed_row_evidence_graph(...)` and its
   current graph metadata copy.
5. Exact source refs for `EvidenceGraph.__post_init__` structural validation.
6. Current tests that enforce 14-key metadata, `run_id` absence, graph
   validation, roundtrip, and unsupported graph construction behavior.
7. Current callers/importers of `_evidence_metadata_for_row_result(...)` and
   `_build_passed_row_evidence_graph(...)`.
8. Metadata builder/checker candidate shapes with pros/cons and hidden public
   surface risk.
9. Debug assertion candidate shapes with runtime risk.
10. T8-A single-cycle vs split decision.
11. Test matrix and expected files.
12. Docs/design update decision.
13. Stop/amend findings and final class.

## 7. Proposed Implementation Split

Implementation is deliberately hypothetical until Step 4.6:

1. **Metadata foundation**: centralize metadata builder/checker without changing
   the 14-key output or callers' public behavior.
2. **Validation/debug**: add the strict validation gate / debug assertion chosen
   in Step 4.6, preserving existing `unsupported` fallback semantics unless
   scoped otherwise.
3. **Tests**: extend focused protocol/audit graph tests for builder/checker,
   sufficiency failures, validation/debug behavior, exact metadata keys, and
   backwards compatibility.
4. **Docs/closure**: update only the docs that Step 4.6 explicitly scopes.

## 8. Acceptance

- [ ] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [ ] T8-A single-cycle vs split decision is locked.
- [ ] Metadata builder/checker shape is locked without changing the current
      14-key metadata contract.
- [ ] `run_id` remains envelope-only.
- [ ] Strict validation/debug behavior is implemented or explicitly deferred
      with rationale.
- [ ] Focused tests cover all implemented T8-A behavior and existing T7
      metadata/validation regressions.
- [ ] T8-B/T8-C/T8-D and D-series non-goals remain deferred.
- [ ] No service/OpenAPI, release, match, database/view, adapter topology, or
      dirty-baseline changes are made.
- [ ] `git diff --check` passes.
- [ ] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest tests.application.protocol.test_evaluate_result_dtos tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render
PYTHONPATH=src python -m unittest tests.test_pyreason_evidence_graph tests.test_souffle_evidence_graph tests.test_problog_evidence_graph
ruff check src/factgraph/application/protocol/evaluate_result.py src/factgraph/audit/evidence_graph.py tests/application/protocol/test_evaluate_result_dtos.py tests/test_audit_evidence_graph.py
git diff --check
git status --short --branch
```

Step 4.6 must confirm the final focused suite based on scoped file set.

## 10. Outcome / Deviations

Pending implementation / closure.
