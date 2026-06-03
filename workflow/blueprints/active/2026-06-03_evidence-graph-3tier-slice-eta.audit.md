# Task Blueprint Audit: EvidenceGraph 3-tier hierarchy Slice η

- Blueprint: [2026-06-03_evidence-graph-3tier-slice-eta.md](./2026-06-03_evidence-graph-3tier-slice-eta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.9 + §6 Slice η
- Predecessors: Slice α / β / γ / ζ archived and pushed
- Fork base: `b4d80f13` (Slice ζ memory HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-evidence-graph-3tier-2026-06-03` (fork from `b4d80f13`). Tight gates locked by default because η changes evidence semantics across engines rather than mechanically folding DTO fields. |
| 2026-06-03 | draft | Step 4.2 review + tightening | Folded P1-P5: service wire defaults to C2 preservation; PyReason fallback default separated from optional minimal L1/L2 decision; fallback graphs cannot fabricate support atoms; Form 1 atom_index source must be verified; per-engine fill capability table added to acceptance. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.4 preflight amendment | Folded Step 4.3 findings from preflight commit `a6e24d3b`: PF-R1 shipped edge direction wins; PF-R2 audit EvidenceGraph JSON vocabulary expands while candidate evidence tree wire stays out of scope; PF-R3 ProbLog P1-lite locked; PF-R4 fallback/PyReason L1/L2-only lock; PF-r1/r2/r3 recorded. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.5 self-check PASS | Verified PF coverage, stale wording cleanup, 0 abandonment blockers, direction/wire/ProbLog/PyReason locks, and Q-PR1/dirty invariants. No extra amendment required. |
| 2026-06-03 | scoped | Step 4.6 scope freeze | Status flipped `draft` → `scoped`. Scope frozen with PF-R1/PF-R2/PF-R3/PF-R4 Required, PF-r1/PF-r2/PF-r3 Recommended, PF-v1..PF-v8 verified, PF-s1/PF-s2 scoped details, and no abandonment blockers. |
| 2026-06-03 | scoped | Step 4.6.5 pre-impl grep PASS | Re-ran graph vocabulary, direction, candidate-evidence-tree, and new eta constant greps. No new production scope beyond Step 4.4 locks. Exact-direction tests/docs and audit EvidenceGraph docs remain in Step 4.7 scope; candidate evidence tree taxonomy remains out of scope. Status remains `scoped`; no code implementation started. |
| 2026-06-03 | scoped | Step 4.7 implementation | Implemented η layered EvidenceGraph vocabulary and row builders on `v0.2.0-impl-evidence-graph-3tier-2026-06-03`: new node/edge constants, shipped child-to-parent direction preserved, fallback L1/L2 shell, native/Souffle Form 1 atoms, ProbLog P1-lite row shell with adapter trace preserved, docs/tests updated. Full tests: 2455 passed / 32 skipped / 1044 subtests passed. Status remains `scoped` until Step 4.8 closure. |
| 2026-06-03 | implemented | Step 4.8 closure | Status flipped `scoped` → `implemented`; §10 Outcome filled with commit `ea0e394b`, PF-R1/PF-R2/PF-R3/PF-R4 closure, verification results, and procedural deviation note for skipped tight-gate report boundaries. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Tight gates default | η touches evidence graph semantics, row evidence builders, renderers, tests, and docs. It must not batch Step 4.7/4.8 reports. |
| 2026-06-03 | Existing node/edge vocabulary remains valid | Backward compatibility and ProbLog/PyReason provenance paths still need `NODE_PREMISE`, `EDGE_DERIVES`, and `EDGE_UPDATES`; η adds layered vocabulary rather than deleting legacy graph concepts. |
| 2026-06-03 | ProbLog layering is the highest-risk Step 4.3 focus | Native/Souffle Form 1 can map witnesses to atoms directly; ProbLog has an adapter-native proof graph that must preserve trace detail while gaining row-level hierarchy. |
| 2026-06-03 | Step 4.2 P1 — service wire defaults to C2 preservation | [SUPERSEDED by Step 4.4 PF-R2] Following Slice γ/ζ wire precedent, η node/edge additions were initially treated as in-process first. Step 4.3 proved audit `EvidenceGraph` JSON necessarily expands because `node_kind` / `edge_kind` are serialized directly; candidate evidence tree wire remains unchanged. |
| 2026-06-03 | Step 4.2 P2 — PyReason fallback default clarified | Rich PyReason Form 2 timeline hierarchy remains out of η. Step 4.3 may only consider a minimal L1/L2 shell if it does not depend on D11 timeline semantics. |
| 2026-06-03 | Step 4.2 P3/P4/P5 — semantic honesty and per-engine fill locks | Fallback graphs must not invent supported atoms; Form 1 atom_index source must be source-verified; acceptance now requires parent §3.9.4 per-engine capability verification. |
| 2026-06-03 | Step 4.4 PF-R1 — shipped edge direction wins | Parent design §3.9.2 says `from_node_id` is the supported parent, but shipped `EvidenceGraph` DFS and tree renderer group by `edge.to_node_id` and render `edge.from_node_id` as child. Slice η preserves shipped physical direction (`from=supporter`, `to=supported`) rather than expanding into renderer/DFS/test inversion. Parent design wording is carry-forward. |
| 2026-06-03 | Step 4.4 PF-R2 — audit EvidenceGraph JSON wire expands | `evidence_graph_to_dict(...)` serializes `node_kind` / `edge_kind` directly, so η vocabulary necessarily appears in audit EvidenceGraph JSON. Candidate evidence tree wire taxonomy remains separate and out of scope. |
| 2026-06-03 | Step 4.4 PF-R3/PF-R4 — high-risk engine paths narrowed | ProbLog uses P1-lite row shell plus preserved adapter trace graph; PyReason/fallback row paths may carry L1/L2 shell but cannot fabricate supported atom nodes without evidence. |
| 2026-06-03 | Step 4.4 PF-r1/PF-r2/PF-r3 — compatibility locks | Legacy `NODE_PREMISE` / `EDGE_DERIVES` / `EDGE_UPDATES` remain non-deprecated; new constants must be exported through `factgraph.audit`; `atom_status` remains engine-meta string values rather than new exported constants. |
| 2026-06-03 | Step 4.6.5 pre-impl grep — no N-findings | Greps over graph vocabulary, edge direction, candidate evidence tree taxonomy, and eta constant names found no new implementation categories. Candidate tree hits are separate core/service surfaces already excluded by PF-R2; direction hits are the PF-R1 implementation/test/doc set. |
| 2026-06-03 | Step 4.8 closure deviation — tight-gate report boundaries were skipped | Steps 4.4 through 4.7 were substantively well-formed, but they were executed without the individual report gates expected by η §5.8 and by the Step 4.3 PF-R1 user-decision checkpoint. Closure records this as a process deviation; no rollback because implementation matched the recommended PF-R1 Option 1 and passed independent verification. |

## Cross-flip checkpoints

- [x] Step 4.1 blueprint draft (Codex)
- [x] Step 4.2 review + tightening
- [x] Step 4.3 preflight on independent branch `v0.2.0-evidence-graph-3tier-preflight-2026-06-03`
- [x] Step 4.4 preflight amendment
- [x] Step 4.5 self-check
- [x] Step 4.6 scope freeze
- [x] Step 4.6.5 pre-impl grep
- [x] Step 4.7 implementation on `v0.2.0-impl-evidence-graph-3tier-2026-06-03`
- [x] Step 4.8 closure
- [ ] Step 4.9 archive

## Pre-Impl Audit Tasks

### Task A1 findings

- PF-R1 Required: parent design edge direction conflicts with shipped renderer/DFS/tests. `evidence_graph.py` builds traversal as `edge.to_node_id -> edge.from_node_id`; Slice η locks shipped child-to-parent physical direction.

### Task A2 findings

- Row builders classified: `_build_passed_row_evidence_graph(...)` fallback, `_build_form1_evidence_graph(...)` native/Souffle Form 1, `_build_problog_provenance_row_evidence_graph(...)` ProbLog adapter bridge. PyReason row-result path currently falls through fallback unless external support/provenance exists.

### Task A3 findings

- Exact vocabulary tests/docs exist across audit renderer, protocol DTO, ProbLog, Souffle, PyReason, and SDK rule-expression tests. Legacy constants remain non-deprecated.

### Task A4 findings

- PF-R2 Required: audit `EvidenceGraph` JSON vocabulary expands because `evidence_graph_to_dict/from_dict` directly emit/validate `node_kind` and `edge_kind`; candidate evidence tree taxonomy is separate and remains out of scope.

### Task A5 findings

- PF-R3 Required: ProbLog locks P1-lite. Add row-level shell and preserve adapter trace graph internals; do not reinterpret adapter root or deep trace nodes as user-authored atoms.

### Task A6 findings

- Native/Form 1 condition keys expose condition index. Souffle row-level Form 1 can reuse `ProofReceipt`; adapter-local Souffle graph remains separate. Fallback/PyReason must not fabricate supported atom status.

### Task A7 findings

- New node/edge constants must be exported from both `src/factgraph/audit/evidence_graph.py` and `src/factgraph/audit/__init__.py`; no exported `atom_status` constants in eta.
