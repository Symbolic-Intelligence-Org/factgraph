# Task Blueprint: EvidenceGraph 3-tier hierarchy Slice η

- Status: scoped
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.6 scope freeze)
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
  - ProbLog row provenance graph: P1-lite row shell only (`conclusion` / `rule_expr` / `rule` / row-level `atom`) while preserving the adapter proof-trace graph unchanged below the synthetic atom
  - fallback / PyReason row graphs must not fabricate `atom_status = "support"` when no support evidence exists; use `atom_status = "unknown"` or omit `NODE_ATOM`
- G5 — Preserve audit-layer graph validation: unique ids, valid edge endpoints, cycle detection, layout hints.
- G6 — Preserve service candidate-evidence-tree JSON compatibility by default per Slice γ/ζ C2 precedent, but expand audit `EvidenceGraph` JSON vocabulary because `evidence_graph_to_dict(...)` serializes `node_kind` / `edge_kind` directly. Candidate evidence tree node kinds (`candidate_result`, `support_section`, etc.) remain out of scope.
- G7 — Update active docs and tests to teach layered graph vocabulary.

## 4. Non-goals

- N1 — Do not implement Slice ε `Explanation.repr` walker.
- N2 — Do not implement Slice δ query-style head decoupling.
- N3 — Do not redesign `EvaluateRow`, `EvaluateResult`, `ResultFingerprint`, or row bindings shape.
- N4 — Do not remove or deprecate `NODE_PREMISE`, `EDGE_SUPPORTS`, `EDGE_DERIVES`, or `EDGE_UPDATES`.
- N5 — Do not change Q-PR1 sacred paths.
- N6 — Do not change service candidate-evidence-tree wire format. Audit `EvidenceGraph` JSON wire expands to include η node/edge vocabulary per PF-R2.
- N7 — Do not implement PyReason rich Form 2 timeline hierarchy. Row-level PyReason/fallback paths may carry the PF-R4 L1/L2 `rule_expr` / `rule` shell, but must not add a supported atom without actual evidence and must not depend on D11 timeline work.
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

Step 4.3 PF-R1 LOCK: preserve shipped physical edge direction rather than parent design §3.9.2 wording.

- `from_node_id` is the supporting child / cause
- `to_node_id` is the supported parent / conclusion
- shipped renderers and DFS already traverse root-to-children by grouping `edge.to_node_id -> edge.from_node_id`
- parent design §3.9.2 is a design-side wording drift; fixing that design text is carry-forward, not Slice η implementation scope

Example:

```text
seed --supported_by--> atom --has_atom--> rule --uses--> rule_expr --derived_by--> conclusion
```

The edge kind names express semantic relationships, while physical direction stays child-to-parent for compatibility. Docs must explain this explicitly to avoid reading `EDGE_HAS_ATOM` as a physical parent-to-child arrow.

### 5.3 Form 1 graph target

For native/Souffle row evidence:

- root remains `NODE_CONCLUSION`
- add one `NODE_RULE_EXPR` with `engine_meta.ast_form = "single"`
- add one `NODE_RULE` with `engine_meta.rule_id = result.head.id`
- convert existing predicate witnesses / non-fact steps into `NODE_ATOM`
- `NODE_ATOM.engine_meta.atom_index` comes from native/Souffle witness ordering or condition keys; Step 4.3 A6 must confirm source availability for each engine before implementation
- existing ledger assertion witnesses remain `NODE_SEED`
- old premise details move into atom `engine_meta` instead of `NODE_PREMISE`

### 5.4 ProbLog graph target

ProbLog currently returns an adapter-native proof graph with `NODE_SEED` / `NODE_PREMISE` / `NODE_CONCLUSION` and `EDGE_DERIVES`. Step 4.3 PF-R3 LOCKS P1-lite:

- add a row-level `NODE_CONCLUSION` / `NODE_RULE_EXPR` / `NODE_RULE` / synthetic row-level `NODE_ATOM` shell;
- preserve the adapter trace graph unchanged below that atom;
- connect the adapter `candidate_graph.root_node_id` as the proof-trace child of the synthetic atom;
- do not reinterpret ProbLog adapter `NODE_CONCLUSION` / `NODE_PREMISE` internals as user-authored `NODE_ATOM` in this slice.

This preserves proof topology and adds row hierarchy without losing trace detail.

### 5.5 Fallback graph target

For detached/no-support row fallback:

- keep a valid graph with root `NODE_CONCLUSION`
- add minimal `NODE_RULE_EXPR` / `NODE_RULE` shell
- if no atom evidence exists, `NODE_ATOM` is omitted or marked `atom_status = "unknown"`
- never fabricate `atom_status = "support"` in fallback / PyReason row paths without actual support evidence

### 5.6 Engine-meta atom status

`atom_status` remains an engine-meta string, not a new exported API constant family in Slice η. Allowed documented values are:

- `"support"`
- `"unsupport"`
- `"not_visited"`
- `"unknown"`

### 5.7 Legacy vocabulary preservation

`NODE_PREMISE`, `EDGE_SUPPORTS`, `EDGE_DERIVES`, and `EDGE_UPDATES` remain valid and non-deprecated. They are still used by ProbLog adapter traces, PyReason adapter timelines, audit renderer tests, and legacy docs. Slice η adds layered vocabulary; it does not turn old vocabulary into an error.

### 5.8 Tight-gate cadence lock

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
- Existing service/audit docs may be updated. Audit `EvidenceGraph` JSON wire expands per PF-R2; service candidate-evidence-tree wire remains unchanged.

## 7. Acceptance Criteria

- [ ] Step 4.2 review has re-read `evidence_graph.py` and all three row builder paths.
- [ ] Step 4.3 preflight has enumerated builder/test/doc/service consumers.
- [ ] New node/edge constants are exported and validation accepts them.
- [ ] New node/edge constants are re-exported through `factgraph.audit` and direct `evidence_graph.py` imports.
- [ ] Edge physical direction preserves shipped child-to-parent semantics (`from=supporter`, `to=supported`) and renderer/DFS behavior remains compatible.
- [ ] Audit `EvidenceGraph` JSON accepts and emits η vocabulary; candidate evidence tree wire remains unchanged.
- [ ] Form 1 row graphs expose rule_expr/rule/atom/seed hierarchy.
- [ ] ProbLog row graphs use P1-lite: row shell plus preserved adapter trace graph.
- [ ] Fallback/PyReason row graphs remain semantically honest for missing support context and do not fabricate supported atoms.
- [ ] Per-engine fill capability table is verified against parent §3.9.4: native, souffle, problog, and pyreason each produce graphs matching their locked L1/L2/L3/seed coverage.
- [ ] Existing graph renderer/tests preserve shipped child-to-parent direction semantics while accepting layered graph vocabulary.
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
8. Step 4.7 — Implementation on `v0.2.0-impl-evidence-graph-3tier-2026-06-03`:
   - export new constants;
   - preserve shipped edge physical direction and update renderer/direction tests before builder rewrites;
   - update Form 1 native/Souffle builder;
   - update ProbLog P1-lite row shell while preserving adapter trace graph;
   - update fallback/PyReason row shell;
   - update docs/tests for audit EvidenceGraph JSON vocabulary expansion.
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
- D4 — Parent design §3.9.2 edge-direction wording remains design-side follow-up after PF-R1; Slice η preserves shipped physical direction instead.
