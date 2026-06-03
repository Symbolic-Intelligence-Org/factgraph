# Preflight Audit: EvidenceGraph 3-tier hierarchy Slice eta

- Branch: `v0.2.0-evidence-graph-3tier-preflight-2026-06-03`
- Fork base: `1f7c6d5c` (blueprint Step 4.2 tightening HEAD)
- Blueprint: [`workflow/blueprints/active/2026-06-03_evidence-graph-3tier-slice-eta.md`](../../blueprints/active/2026-06-03_evidence-graph-3tier-slice-eta.md)
- Audit log: [`workflow/blueprints/active/2026-06-03_evidence-graph-3tier-slice-eta.audit.md`](../../blueprints/active/2026-06-03_evidence-graph-3tier-slice-eta.audit.md)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.9 + §6 Slice eta
- Status: Step 4.3 preflight complete; blueprint amendment required

## 1. Scope

This preflight audits Slice eta's proposed layered `EvidenceGraph` vocabulary before implementation:

1. `NODE_RULE_EXPR`, `NODE_RULE`, `NODE_ATOM`
2. `EDGE_DERIVED_BY`, `EDGE_USES`, `EDGE_HAS_ATOM`, `EDGE_SUPPORTED_BY`
3. row-level builders in `evaluate_result.py`
4. ProbLog / native / Souffle / PyReason evidence behavior
5. renderer, service JSON, docs, and tests that consume graph vocabulary

No source code was modified on this branch. The preflight output is this artifact only.

## 2. Method

Rule 1 fresh reads covered:

| Task | Source / command | Result |
| --- | --- | --- |
| A1 direction semantics | `src/factgraph/audit/evidence_graph.py:97-100`, `:194-200` | shipped traversal/rendering treats `to_node_id` as parent/root target and `from_node_id` as supporting child |
| A2 row builders | `src/factgraph/application/protocol/evaluate_result.py:906-993`, `:1041-1125` | fallback / ProbLog bridge / Form 1 native-Souffle builders identified |
| A3 tests | `rg "NODE_CONCLUSION|NODE_PREMISE|NODE_SEED|EDGE_SUPPORTS|EDGE_DERIVES|EDGE_UPDATES|node_kind|edge_kind" tests src/factgraph docs` | exact vocabulary assertions appear across audit renderer, protocol DTO, ProbLog, Souffle, PyReason, SDK rule expr tests |
| A4 docs / wire | same `rg` plus docs spot reads | docs list current 3 node + 3 edge vocabulary; candidate evidence tree taxonomy is separate and out of scope |
| A5 ProbLog | `src/factgraph/adapters/problog/provenance.py:187-216`, `:219-273`; row bridge at `evaluate_result.py:936-993` | adapter graph is already a trace tree rooted at a ProbLog conclusion and linked by `EDGE_DERIVES` |
| A6 native / Souffle support | `src/factgraph/core/store/_support.py:36-63`, `:96-126`; Form 1 builder at `evaluate_result.py:1093-1125`; Souffle adapter at `src/factgraph/adapters/souffle/provenance.py:48-137` | condition keys expose case / condition index for native; Souffle adapter graph has rule_number and child nodes but row-level Souffle path currently uses `ProofReceipt` |
| A7 exports | `src/factgraph/audit/__init__.py:10-25`, `:79-119`; `src/factgraph/audit/evidence_graph.py:11-21` | new constants must be exported from both files; no exact audit `__all__` count found |

## 3. Required Findings

### PF-R1 — Direction convention conflict: parent design direction contradicts shipped renderer/tests

**Finding.** Blueprint §5.2 says:

> `from_node_id` is the explained / supported node; `to_node_id` is the supporting child.

Shipped `EvidenceGraph` does the opposite in all active tree semantics:

- Cycle detection builds `adjacency[edge.to_node_id].append(edge.from_node_id)` (`evidence_graph.py:97-100`).
- Tree rendering groups `incoming_edges[edge.to_node_id].append(edge)` then renders child `edge.from_node_id` below the current node (`evidence_graph.py:194-200`).
- Tests and docs use support edges like `seed/premise -> conclusion`, e.g. `tests/test_audit_evidence_graph_render.py:51-52` and `docs/official/kernel/quickstart/evidence.md:394`.

**Impact if not amended.** Implementing parent §3.9.2 literally would invert every rendered tree and make existing tests misleading. The code would still validate endpoints, so the regression would appear as semantic/rendering drift rather than a simple exception.

**Required amendment.** Step 4.4 must choose one of two explicit paths:

1. **Recommended lock:** preserve shipped physical direction for Slice eta:
   - `from_node_id` = supporting child / cause
   - `to_node_id` = supported parent / conclusion
   - renderer and DFS remain directionally compatible
   - new semantic edge kinds still express hierarchy through current physical direction
2. **Higher-risk alternative:** explicitly authorize renderer / DFS / docs / all exact-direction tests to flip to parent-design direction.

Preflight recommends option 1. It preserves shipped renderer behavior and lets Slice epsilon's walker rely on existing root-to-children traversal.

### PF-R2 — EvidenceGraph JSON vocabulary cannot stay "in-process only"

**Finding.** Step 4.2 P1 tightened G6 to say eta node/edge additions are "in-process first" and service JSON vocabulary remains current 3+3 unless Step 4.3 proves otherwise. Source read shows `evidence_graph_to_dict(...)` serializes `node.node_kind` and `edge.edge_kind` directly (`evidence_graph.py:131-164`), and `evidence_graph_from_dict(...)` reconstructs with current allowlists (`evidence_graph.py:168-191`, `:38-58`).

Once row-level `EvidenceGraph` contains `rule_expr` / `rule` / `atom` nodes or new semantic edges, serialized EvidenceGraph JSON necessarily includes those new strings.

**Scope distinction.**

- Candidate evidence tree taxonomy (`candidate_result`, `support_section`, `assertion_fact`, etc.) is a separate core/service structure and remains out of eta scope.
- Audit `EvidenceGraph` JSON vocabulary must expand if eta emits new node/edge kinds.

**Required amendment.** Replace "in-process only" wording with:

- service candidate evidence tree wire remains unchanged;
- audit `EvidenceGraph` JSON wire expands to include eta vocabulary;
- docs must mark old 3+3 values as still valid, not exhaustive.

### PF-R3 — ProbLog layering must wrap trace graph without reinterpreting adapter internals

**Finding.** ProbLog currently builds an adapter-native proof graph in `problog_trace_to_evidence_graph(...)` (`provenance.py:187-216`) and the row bridge copies it through unchanged except for metadata (`evaluate_result.py:936-993`). The adapter graph already has `NODE_CONCLUSION` / `NODE_PREMISE` / `NODE_SEED` and `EDGE_DERIVES`, and its root is selected from trace frames (`provenance.py:205-214`).

Blueprint §5.4 lists P1/P2/P3, with draft bias P1. Preflight confirms P1 is feasible only as **P1-lite**:

- add a row-level `NODE_CONCLUSION -> NODE_RULE_EXPR -> NODE_RULE -> NODE_ATOM` shell using shipped physical direction from PF-R1;
- preserve the adapter trace graph below that atom without rewriting adapter node kinds;
- connect `candidate_graph.root_node_id` as the proof-trace child of the synthetic atom.

**Rejected for eta.**

- Reinterpreting ProbLog adapter root `NODE_CONCLUSION` as `NODE_ATOM` would destroy adapter trace semantics and test expectations.
- Full deep trace remapping is larger than Slice eta and would conflate adapter proof trace with user-authored rule body atoms.

**Required amendment.** Lock ProbLog to P1-lite: row shell added, adapter trace preserved.

### PF-R4 — PyReason row-level fallback can carry only L1/L2 shell; no atom node unless evidence exists

**Finding.** Row-level PyReason currently falls through `_build_passed_row_evidence_graph(...)` to a single `NODE_CONCLUSION` when no support artifact/provenance envelope exists (`evaluate_result.py:906-933`). Adapter-level PyReason timeline graphs exist elsewhere, but they are not returned by row explain in this path.

Step 4.2 P2 clarified that rich PyReason Form 2 timeline hierarchy stays out of eta. Step 4.2 P3 also locked "do not fabricate support atoms".

**Required amendment.** Lock row-level PyReason / no-support fallback shape:

- permitted: `NODE_CONCLUSION` plus minimal `NODE_RULE_EXPR` / `NODE_RULE` shell;
- forbidden: synthetic `NODE_ATOM` with `atom_status="support"`;
- optional: omit atom entirely, or include an atom only with `atom_status="unknown"` if Step 4.7 has a concrete atom source.

This protects semantic honesty while giving Slice epsilon a stable L1/L2 top-level structure.

## 4. Recommended Findings

### PF-r1 — Keep `NODE_PREMISE` and legacy edge constants exported

The blueprint already keeps legacy vocabulary valid. Preflight reinforces that this is not optional:

- ProbLog adapter tests assert `EDGE_DERIVES` and existing node kinds.
- PyReason adapter tests assert `EDGE_UPDATES`.
- Audit renderer tests use `NODE_PREMISE` and `NODE_SEED` directly.

Step 4.4 should state that eta adds vocabulary; it does not make `NODE_PREMISE` deprecated.

### PF-r2 — Add new constants to both `evidence_graph.py` and `factgraph.audit.__all__`

New constants must be imported/re-exported in:

- `src/factgraph/audit/evidence_graph.py`
- `src/factgraph/audit/__init__.py`

No exact audit `__all__` count test was found, but public import paths in docs/tests rely on `from factgraph.audit import ...`.

### PF-r3 — Do not export `atom_status` constants in eta

Parent §3.9.1 defines `atom_status` values inside `EvidenceNode.engine_meta`. Preflight did not find an existing exported constant pattern for engine_meta enum values. Exporting `ATOM_STATUS_SUPPORT` etc. would expand public API beyond the blueprint.

Recommendation: document string values in docs/tests, but do not add top-level exported constants in eta.

## 5. Verified Findings

| ID | Verification | Result |
| --- | --- | --- |
| PF-v1 | Current audit vocabulary is exactly 3 node kinds + 3 edge kinds | `evidence_graph.py:11-21` verified |
| PF-v2 | Cycle detection and tree rendering share child-to-parent physical edge direction | `evidence_graph.py:97-100`, `:194-200` verified |
| PF-v3 | Native Form 1 builder already has condition index source | `_condition_index_from_key(...)` used in `evaluate_result.py:1105-1108` and support condition keys exist in `_support.py` |
| PF-v4 | Souffle row-level path can reuse Form 1 `ProofReceipt`; adapter-local Souffle graph remains separate | `SOUFFLE_WITNESS_KIND` and `ProofReceipt` verified; `adapters/souffle/provenance.py` is adapter-local |
| PF-v5 | ProbLog row bridge preserves adapter graph root today | `evaluate_result.py:984-993` verified |
| PF-v6 | Candidate evidence tree taxonomy is separate from audit EvidenceGraph | `core/store/_candidate_evidence_tree*.py` uses independent node_kind values |
| PF-v7 | No abandonment blocker | Findings require blueprint tightening, not slice stop |
| PF-v8 | Sacred invariants unaffected by preflight | This artifact is doc-only on independent branch |

## 6. Scoped Details

### PF-s1 — Direction naming for new edge kinds

If Step 4.4 preserves shipped physical direction, edge names should be read as child-supports-parent:

| Semantic relationship | Physical edge under PF-R1 recommended lock |
| --- | --- |
| rule_expr derives conclusion | `from=rule_expr`, `to=conclusion`, `edge_kind=EDGE_DERIVED_BY` or equivalent |
| rule used by rule_expr | `from=rule`, `to=rule_expr`, `edge_kind=EDGE_USES` |
| atom part of rule | `from=atom`, `to=rule`, `edge_kind=EDGE_HAS_ATOM` |
| seed supports atom | `from=seed`, `to=atom`, `edge_kind=EDGE_SUPPORTED_BY` |

This is slightly awkward English for `has_atom` but keeps renderer semantics stable. Step 4.4 may rename edge constants if it wants physical-direction wording; otherwise docs must explain the convention.

### PF-s2 — Per-engine fill capability table after preflight

| Engine / path | L1 rule_expr | L2 rule | L3 atom | seed/proof detail | Eta lock |
| --- | --- | --- | --- | --- | --- |
| fallback / no support | yes | yes | omit or unknown only | none | PF-R4 |
| native Form 1 | yes | yes | yes | seed assertions | G4 + PF-v3 |
| Souffle row Form 1 | yes | yes | yes | seed assertions via ProofReceipt | G4 + PF-v4 |
| ProbLog row provenance | yes | yes | one row-level atom shell | preserve adapter trace graph | PF-R3 |
| PyReason row fallback | yes | yes | omit/unknown only | timeline deferred | PF-R4 |
| PyReason adapter timeline | out of row-level eta | out of row-level eta | adapter-local | `EDGE_UPDATES` remains valid | N7 / PF-r1 |

## 7. Abandonment Findings

None.

The design assumption is still valid: shipped evidence data can support an explicit RuleExpr / Rule / Atom layer for native/Souffle, and a row-level wrapper for ProbLog/fallback/PyReason. The required amendments are direction/wire/scope locks, not stop-the-slice findings.

## 8. Step 4.4 Amendment Checklist

Apply on blueprint branch `v0.2.0-blueprint-evidence-graph-3tier-2026-06-03`, not this preflight branch.

1. PF-R1: Replace parent-direction lock in §5.2 with shipped physical direction preservation, or explicitly authorize renderer/DFS/test rewrite. Recommended: preserve shipped direction.
2. PF-R2: Replace "in-process only" service wording with audit EvidenceGraph JSON vocabulary expansion + candidate evidence tree non-goal.
3. PF-R3: Lock ProbLog to P1-lite row shell + preserved adapter trace graph.
4. PF-R4: Lock fallback/PyReason row graph to L1/L2 shell only; no fabricated support atom.
5. PF-r1: Explicitly keep `NODE_PREMISE`, `EDGE_DERIVES`, and `EDGE_UPDATES` non-deprecated.
6. PF-r2: Add exports acceptance for `factgraph.audit` and `evidence_graph.py`.
7. PF-r3: State `atom_status` values are engine_meta strings, not exported constants in eta.
8. §7 acceptance: update direction, wire, ProbLog, PyReason/fallback, exports, and per-engine table checks.
9. §8 implementation plan: add renderer/direction test update step before builder rewrites.
10. Audit log: add Step 4.4 Event Log row and Decision Notes for PF-R1 through PF-R4.

## 9. Final Distribution

| Bucket | Count |
| --- | ---: |
| Required | 4 |
| Recommended | 3 |
| Verified | 8 |
| Scoped-detail | 2 |
| Abandonment | 0 |

Distribution is intentionally at the Required upper bound because eta changes graph semantics across rendering, JSON serialization, and multiple engine bridges.
