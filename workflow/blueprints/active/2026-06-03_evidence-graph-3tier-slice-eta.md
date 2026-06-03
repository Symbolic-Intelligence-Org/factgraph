# Task Blueprint: EvidenceGraph 3-tier hierarchy Slice η

- Status: draft
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.1 draft)
- Owner: Codex (blueprint draft) / Claude review expected — inverted cross-flip, tight gates by default
- Fork base: `b4d80f13` (Slice ζ memory HEAD)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.9 + §6 Slice η

## 1. Problem

Current row-level `EvidenceGraph` is structurally flat. The user-authored model is hierarchical:

1. RuleExpr composition (single / AND / OR)
2. Rule occurrence
3. body atoms
4. seed facts or engine-native proof steps

Shipped graphs currently expose only `NODE_CONCLUSION`, `NODE_PREMISE`, and `NODE_SEED`, with `EDGE_SUPPORTS` / `EDGE_DERIVES` / `EDGE_UPDATES`. The Form 1 builder encodes atom-ish details in `NODE_PREMISE.engine_meta`, and ProbLog reuses adapter trace nodes directly. That loses the explicit RuleExpr → Rule → Atom layer needed by Slice ε's `Explanation.repr` walker.

## 2. Source Anchors

### Related Modules

- `src/factgraph/audit/evidence_graph.py`
  - node kinds currently: `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`
  - edge kinds currently: `EDGE_SUPPORTS`, `EDGE_DERIVES`, `EDGE_UPDATES`
  - validation allowlists: `_VALID_NODE_KINDS`, `_VALID_EDGE_KINDS`
- `src/factgraph/application/protocol/evaluate_result.py`
  - `_build_passed_row_evidence_graph(...)` fallback single-conclusion graph
  - `_build_form1_evidence_graph(...)` native/Souffle Form 1 graph builder
  - `_build_problog_provenance_row_evidence_graph(...)` ProbLog row provenance graph bridge
- Active docs likely touched:
  - `docs/quickstart/evaluate_and_evidence.md`
  - `docs/official/kernel/quickstart/evidence.md`
  - `docs/official/kernel/quickstart/namespace-map.md`
  - `src/factgraph/sdk/docs/00_user_guide.en.md`
  - service docs if wire examples enumerate graph node/edge kinds

### Related Tests

Preflight must enumerate exact test files. Expected families:

- protocol DTO/evidence tests under `tests/application/protocol/`
- ProbLog evidence graph tests
- PyReason evidence graph tests
- candidate provenance timeline tests
- service runtime evidence serialization tests, if any

## 3. Goals

- G1 — Add new node kinds:
  - `NODE_RULE_EXPR = "rule_expr"`
  - `NODE_RULE = "rule"`
  - `NODE_ATOM = "atom"`
- G2 — Add new edge kinds:
  - `EDGE_DERIVED_BY = "derived_by"`
  - `EDGE_USES = "uses"`
  - `EDGE_HAS_ATOM = "has_atom"`
  - `EDGE_SUPPORTED_BY = "supported_by"`
- G3 — Preserve existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, `EDGE_SUPPORTS`, `EDGE_DERIVES`, and `EDGE_UPDATES` as valid vocabulary.
- G4 — Update row-level builders to produce layered graphs where feasible:
  - fallback passed-row graph: conclusion plus minimal `rule_expr` / `rule` layer
  - Form 1 native/Souffle graph: conclusion → rule_expr → rule → atom → seed
  - ProbLog row provenance graph: wrap or enrich candidate graph so row result has conclusion/rule_expr/rule/atom hierarchy without destroying `EDGE_DERIVES` trace information
- G5 — Preserve audit-layer graph validation: unique ids, valid edge endpoints, cycle detection, layout hints.
- G6 — Preserve service JSON compatibility unless Step 4.3 proves a wire-level node/edge vocabulary change is already expected by consumers.
- G7 — Update active docs and tests to teach layered graph vocabulary.

## 4. Non-goals

- N1 — Do not implement Slice ε `Explanation.repr` walker.
- N2 — Do not implement Slice δ query-style head decoupling.
- N3 — Do not redesign `EvaluateRow`, `EvaluateResult`, `ResultFingerprint`, or row bindings shape.
- N4 — Do not remove `NODE_PREMISE`, `EDGE_SUPPORTS`, `EDGE_DERIVES`, or `EDGE_UPDATES`.
- N5 — Do not change Q-PR1 sacred paths.
- N6 — Do not change service wire format unless Step 4.3 makes a Required finding.
- N7 — Do not implement PyReason rich Form 2 timeline hierarchy; keep row-level PyReason fallback safe unless source audit proves a minimal L1/L2 layer can be added without D11 work.
- N8 — Do not touch dirty baseline files.
- N9 — Do not push automatically from Step 4.1.

## 5. Proposed Shape

### 5.1 EvidenceGraph vocabulary

```python
NODE_RULE_EXPR = "rule_expr"
NODE_RULE = "rule"
NODE_ATOM = "atom"

EDGE_DERIVED_BY = "derived_by"
EDGE_USES = "uses"
EDGE_HAS_ATOM = "has_atom"
EDGE_SUPPORTED_BY = "supported_by"
```

Keep existing node/edge constants valid.

### 5.2 Direction convention

Use parent design §3.9.2:

- `from_node_id` is the explained / supported node
- `to_node_id` is the supporting child
- walker traversal follows `from_node_id -> to_node_id`

Example:

```text
conclusion --derived_by--> rule_expr --uses--> rule --has_atom--> atom --supported_by--> seed
```

Step 4.3 must verify whether shipped renderers currently assume the old opposite direction, because `evidence_graph.py` DFS currently builds adjacency as `edge.to_node_id -> edge.from_node_id`.

### 5.3 Form 1 graph target

For native/Souffle row evidence:

- root remains `NODE_CONCLUSION`
- add one `NODE_RULE_EXPR` with `engine_meta.ast_form = "single"`
- add one `NODE_RULE` with `engine_meta.rule_id = result.head.id`
- convert existing predicate witnesses / non-fact steps into `NODE_ATOM`
- existing ledger assertion witnesses remain `NODE_SEED`
- old premise details move into atom `engine_meta` instead of `NODE_PREMISE`

### 5.4 ProbLog graph target

ProbLog currently returns an adapter-native proof graph with `NODE_SEED` / `NODE_PREMISE` / `NODE_CONCLUSION` and `EDGE_DERIVES`. Step 4.3 must decide one of:

- Option P1 — wrap adapter graph under a row-level conclusion/rule_expr/rule/atom prefix and keep adapter trace nodes as proof-chain children.
- Option P2 — reinterpret adapter root premise as `NODE_ATOM` and preserve proof internals below it.
- Option P3 — defer deep ProbLog layering and only add row-level conclusion/rule_expr/rule shell, keeping adapter trace unchanged.

Draft bias: P1, because it preserves proof topology and adds hierarchy without losing trace detail.

### 5.5 Fallback graph target

For detached/no-support row fallback:

- keep a valid graph with root `NODE_CONCLUSION`
- add minimal rule_expr/rule shell only if it does not misrepresent missing support
- if no atom evidence exists, `NODE_ATOM` is omitted or marked `atom_status = "unknown"` per Step 4.3 decision

### 5.6 Tight-gate cadence lock

Slice η is an evidence model redesign, not a mechanical DTO fold. It must use tight gates:

- Step 4.2 review + tightening before preflight
- Step 4.3 independent preflight branch
- Step 4.4 amendment on blueprint branch
- Step 4.5 self-check
- Step 4.6 scoped anchor
- Step 4.6.5 mandatory pre-impl grep
- Step 4.7 implementation as separate report
- Step 4.8 closure as separate report

No β/ζ-style batch report for 4.7/4.8.

## 6. Boundary Checks

- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Q-PR1 5-path diff vs `4c472b50` must stay empty.
- Dirty baseline must remain preserved.
- Existing EvidenceGraph construction invariants must stay enforced.
- Existing service/audit docs may be updated, but service runtime wire change requires Step 4.3 Required finding.

## 7. Acceptance Criteria

- [ ] Step 4.2 review has re-read `evidence_graph.py` and all three row builder paths.
- [ ] Step 4.3 preflight has enumerated builder/test/doc/service consumers.
- [ ] New node/edge constants are exported and validation accepts them.
- [ ] Form 1 row graphs expose rule_expr/rule/atom/seed hierarchy.
- [ ] ProbLog row graphs preserve proof trace detail while adding the locked η hierarchy.
- [ ] Fallback row graphs remain semantically honest for missing support context.
- [ ] Existing graph renderer/tests are updated for direction semantics.
- [ ] Active docs list new node/edge vocabulary and engine capabilities.
- [ ] Full tests pass.
- [ ] Q-PR1 5-path diff vs `4c472b50` remains empty.
- [ ] Dirty baseline remains preserved.

## 8. Implementation Plan

1. Step 4.1 — Draft blueprint + audit pair.
2. Step 4.2 — Review + tightening.
3. Step 4.3 — Independent preflight on `v0.2.0-evidence-graph-3tier-preflight-2026-06-03`.
4. Step 4.4 — Fold preflight findings.
5. Step 4.5 — Self-check.
6. Step 4.6 — Scope freeze.
7. Step 4.6.5 — Mandatory pre-impl grep.
8. Step 4.7 — Implementation on `v0.2.0-impl-evidence-graph-3tier-2026-06-03`.
9. Step 4.8 — Closure.
10. Step 4.9 — Archive.

## 9. Pre-Impl Audit Tasks

- A1 — Verify graph direction semantics in `EvidenceGraph.__post_init__`, renderers, and tests.
- A2 — Enumerate every row-level EvidenceGraph builder and classify fallback/Form1/ProbLog/PyReason behavior.
- A3 — Enumerate tests asserting exact node_kind / edge_kind values or counts.
- A4 — Enumerate docs and service wire examples listing graph vocabulary.
- A5 — Source-check ProbLog adapter graph shape and decide P1/P2/P3.
- A6 — Source-check native/Souffle support artifacts for atom-index/status availability.
- A7 — Confirm SDK/audit exports and `__all__` expectations for new constants.

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — Slice ε `Explanation.repr` walker remains after η.
- D2 — Slice δ query-style head decoupling remains after η/ε.
- D3 — PyReason rich timeline hierarchy remains D11/Form 2 unless Step 4.3 narrows a safe subset.
