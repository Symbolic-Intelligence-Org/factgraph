# Audit: T8-A Metadata + Validation Foundation

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-a-metadata-validation-foundation.md`
- Stage: scoped
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current modified docs/notebooks plus untracked reference material
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `1ad49592` | T8-A metadata/validation foundation blueprint pair drafted | Triggered by T8 split inventory after T7 bridge shipped; Q1-Q9 intentionally pending for Step 4.6. |
| 2026-05-27 | scoped | this commit | Step 4.6 inventory and final scoped decisions recorded | T8-A kept as one M-class blueprint; private builder/checker shape locked; tests and non-goals scoped. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8 split inventory archived at `a872fa5b` recommends T8-A as the first
  evidence implementation slice and identifies two possible internal steps:
  metadata builder/sufficiency checker, then validation/debug assertion.
- `EvaluateResult` currently owns the envelope and row context; graph metadata
  is built inline by `_evidence_metadata_for_row_result(...)`.
- `_explain_live_row(...)` passes metadata into the graph builder and catches
  `ValueError` as unsupported explanation output.
- `EvidenceGraph.__post_init__` already enforces structural graph validation.
- T7 added a strict 14-key metadata test and `run_id` absence check, so T8-A
  starts with an explicit backwards-compat regression anchor.

This draft scan is not a Step 4.6 answer. It intentionally avoids choosing
builder/checker/debug assertion shape before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Should T8-A ship as one blueprint or split into T8-A-1 / T8-A-2? | One M-class blueprint; implement as A-1/A-2 commits unless scope expands. |
| Q2 | What is the central metadata builder shape? | Keep private module-level `_evidence_metadata_for_row_result(...)`; add internal key/checker companion; no public class/method/API. |
| Q3 | What is the metadata sufficiency checker shape? | Private module-level checker, exact-set + value consistency, `ValueError` for existing unsupported fallback. |
| Q4 | How should strict graph validation integrate with `_explain_live_row(...)`? | Preserve `ValueError -> GRAPH_VALIDATION_FAILED`; run validation in the graph-builder/row-explain gate. |
| Q5 | How should debug assertion be enabled? | Always-on internal validation helper; no Python assert, env flag, or test-only path. |
| Q6 | Which tests are mandatory before implementation? | Blueprint §7.1 maps builder/checker/validation/debug/backward compatibility tests. |
| Q7 | Are module docs or design docs required in this cycle? | No docs by default; update only if implementation changes user-visible contract. |
| Q8 | What remains deferred to T8-B/T8-C/T8-D? | Topology, engine enrichment, product docs, D20, and adapter/candidate evidence work remain deferred. |
| Q9 | Are there stop/amend findings from source inventory? | None; class remains M. |

## 4. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | EvaluateResult envelope | Fields at `evaluate_result.py:128-142`; validation at `:151-181`. |
| 2 | Row explain path | `_explain_live_row(...)` type checks `:553-562`, membership/stale checks `:564-594`, metadata and graph builder `:596-599`, `ValueError -> unsupported / GRAPH_VALIDATION_FAILED` `:600-618`, passed return `:620-630`. |
| 3 | Metadata writer | `_evidence_metadata_for_row_result(...)` writes the 14 §10.3 keys at `evaluate_result.py:823-842`. |
| 4 | Passed-row graph builder | `_build_passed_row_evidence_graph(...)` builds one conclusion node and copies provided metadata at `evaluate_result.py:800-820`. |
| 5 | EvidenceGraph validation | Metadata freeze and structural validation are in `EvidenceGraph.__post_init__` at `evidence_graph.py:74-117`. |
| 6 | Existing tests | Exact metadata key/value and `run_id` absence coverage at `test_evaluate_result_dtos.py:249-341`; unsupported fallback at `:520-539`; graph validation/roundtrip at `test_audit_evidence_graph.py:18-197`. |
| 7 | Callers/importers | `rg` found `_evidence_metadata_for_row_result(...)` called only at `evaluate_result.py:596`; `_build_passed_row_evidence_graph(...)` selected only at `:597`; no external importers. `_explain_live_row(...)` is imported by protocol tests and inspected by one SDK quarantine test. |
| 8 | Design anchors | §10.3 metadata table `evidence-tree...:2375-2398`; §10.4 validation/sufficiency `:2400-2419`; C134/C135 `:2781-2782`; T8-A §15.2/§15.3 `:2894` and `:2899-2904`. |
| 9 | Candidate shapes | Blueprint §4.3 records builder/checker/debug candidates with pros/cons and scoped choices. |
| 10 | Focused baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_evaluate_result_dtos tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render` ran 31 OK. |
| 11 | Dirty/sacred | Status shows 4 modified tracked docs/notebooks plus 2 untracked directories; sacred master remains `562c74195df43e933bed92a3ff25de94dd8ce666`. |
| 12 | Stop/amend | None. No T8-B/C/D, service/OpenAPI, release, match, database/view, adapter topology, or dirty-baseline work is needed. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Builder/checker shape becomes accidental public API | Future compatibility risk | Keep helper internal unless explicitly scoped otherwise. |
| Metadata contract drifts from 14 keys | Breaks T7/T6 contract | Use exact set-equality tests and inventory current callers. |
| `run_id` leaks into graph metadata | Violates sessionless envelope/graph separation | Preserve envelope-only invariant in tests. |
| Debug assertion breaks normal runtime | User-facing regression | Decide enablement path before implementation. |
| Validation gate expands into topology | Scope drift into T8-B/T8-C | Keep T8-A to metadata/validation foundation only. |
| Dirty baseline edited accidentally | Workflow violation | Status checks before commit/closure. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] Scope split / implementation shape locked.
- [x] Tests and verification gates locked.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / implementation / closure.
