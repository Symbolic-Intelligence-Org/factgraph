# Audit: T8 Implementation Split Inventory

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-implementation-split-inventory.md`
- Stage: scoped
- Class: S/M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `2a7f082f` | T8 split inventory blueprint pair drafted | Triggered after T7 evidence audit/rendering bridge shipped and user selected T8 planning before T8-A runtime. |
| 2026-05-27 | scoped | this commit | Step 4.6 source-backed split inventory recorded | Q1-Q9 answered; T8-A/B/C/D retained; T8-A internal split, T8/T10 dependency, D-series mapping, and Option B output locked. |

## 2. Draft Source Scan

Read-only draft scan findings:

- `evidence-tree-rainbird-style-v1.zh.md` §15.2 already proposes four T8
  slices: T8-A Validator + metadata foundation, T8-B Native/Souffle success
  topology, T8-C Engine enrichment, and T8-D Product/docs alignment.
- §15.3 recommends the first T8 implementation blueprint be T8-A only.
- T7 archived blueprint records a contract matrix and explicitly deferred T8-A
  central metadata sufficiency, T8-B topology, T8-C enrichment, and T8-D product
  docs.
- Current runtime has evidence DTOs, metadata writer, renderer, docs, and tests,
  so Step 4.6 must quantify boundaries against shipped code rather than
  redesigning the split from scratch.

This draft scan is not a Step 4.6 answer. It intentionally avoids answering
Q1-Q9 before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Does §15.2's four-slice proposal still hold after T7? | Yes. Keep T8-A/B/C/D; refine T8-A into optional internal A-1/A-2 sub-steps. |
| Q2 | How do T7 §4.2 contract rows map to T8 slices? | Blueprint §4.2 maps every T7 contract row to shipped / T8-A / T8-C / T8-D / future. |
| Q3 | What is T8-A's real code boundary? | Blueprint §4.3 maps the four sub-items to `evaluate_result.py`, `evidence_graph.py`, and protocol tests with estimates. |
| Q4 | Does T8-A need to split? | Top-level T8-A can remain one blueprint if scoped as two commits; split into T8-A-1/A-2 if schema/helper-module churn appears. |
| Q5 | What is T8-B's real code boundary? | Blueprint §4.4 maps native/candidate tree and Souffle surfaces; reuse before rewrite. |
| Q6 | How does T8-C depend on T10? | Cross-engine T8-C waits for T10 or engine-specific semantics locks; engine-local slices may proceed after their own semantics scope. |
| Q7 | What is the dependency graph? | Blueprint §4.5 records T8-A -> T8-B/T8-C and conditional T8-D edges. |
| Q8 | Which D1-D20 items are triggered by each slice? | Blueprint §4.6 maps D-series. T8-A triggers no D item; T8-B/T8-C may activate D18/D12 or D11/D13/D6/D7 if scoped. |
| Q9 | What durable output shape should this cycle produce? | Option B: blueprint-only split plan, archived as durable planning artifact. |

## 4. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | §15 anchors | §15.1 `evidence-tree...:2881-2888`; §15.2 `:2890-2897`; §15.3 `:2899-2908`; §15.4 `:2910-2919`; §15.5 `:2921-2927`. |
| 2 | T7 anchors | T7 final decisions `t7...md:120-131`; contract matrix `:133-148`; inventory `:169-186`. |
| 3 | T8-A metadata boundary | `EvaluateResult` fields/validation `evaluate_result.py:128-181`; `_explain_live_row(...)` metadata path `:553-630`; `_build_passed_row_evidence_graph(...)` `:800-820`; `_evidence_metadata_for_row_result(...)` `:823-842`. |
| 4 | T8-A validation boundary | `EvidenceGraph.__post_init__` validation `evidence_graph.py:74-117`; graph builder ValueError -> unsupported path `evaluate_result.py:596-618`; tests `tests/test_audit_evidence_graph.py:18-273` and `tests/application/protocol/test_evaluate_result_dtos.py:249-330`. |
| 5 | T8-B candidate/native boundary | Candidate tree builder `_candidate_evidence_tree.py:12-54`; support sections `:103-164`; predicate witness group `:167-185`; step traversal `_candidate_evidence_tree_steps.py:48-116`; public step builder `:231-240`. |
| 6 | T8-B/T8-C engine boundary | Souffle EvidenceGraph converter `adapters/souffle/provenance.py:48-137`; ProbLog converter `adapters/problog/provenance.py:187-297`; ProbLog candidate tree converter `:300-369`; PyReason timeline converter `adapters/pyreason/provenance.py:113-245`. |
| 7 | T8-D docs boundary | Audit docs T7-aligned contract at `audit/docs/02_evidence_graph.md:1-213`; T9 handoff in source design at `evidence-tree...:2921-2927`. |
| 8 | T10 dependency | Roadmap says T10 is cross-cutting but can be parallel if scoped narrowly at `post-t5-completion-roadmap.zh.md:96-97`; T10 scope at `:197-210`; triggers at `:318-321`. |
| 9 | Test fixtures | Evidence graph validation/render tests, evaluate-result DTO metadata test, candidate evidence step fixtures, and engine evidence graph tests are adequate entry points for future T8 slices. |
| 10 | Output shape | Option B. No design-point note; no implementation blueprint drafted. |
| 11 | No-op baseline | `PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render` ran 20 OK. |
| 12 | Dirty / sacred | Dirty baseline preserved; sacred master remains `562c74195df43e933bed92a3ff25de94dd8ce666`. |
| 13 | Stop/amend findings | None for this planning cycle. Future T8-A should still redo Step 4.6 before implementation. |

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| T8 split cycle starts implementation | Scope drift | Confirm no runtime/test/doc edits and choose planning-only output. |
| §15 proposal is treated as binding without re-inventory | Wrong implementation starting point | Re-map against T7 contract matrix and current runtime. |
| T8-A is too large for one cycle | Future cycle stalls | Quantify the four T8-A sub-items and split if needed. |
| T8-C starts before adapter semantics are ready | Adapter churn | Resolve T10 dependency shape. |
| D-series triggers are missed | Hidden future blockers | Map D1-D20 per slice. |
| Dirty baseline is accidentally edited | Workflow violation | Preserve baseline in status checks. |

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] Output shape selected.
- [ ] Closure notes filled.

## 7. Closure Notes

Pending inventory / closure.
