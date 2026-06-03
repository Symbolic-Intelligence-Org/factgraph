# Task Blueprint: Explanation.repr walker Slice ε — layered EvidenceGraph → multi-line NL

- Status: scoped
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.7 implementation)
- Owner: Claude (blueprint draft) / Codex (review + impl) — Slice 4/5 cross-flip per [[feedback_audit_to_archive_cadence]]
- **Cadence**: tight gates default per Slice η §10 D6 lock (evidence-model slices; behavior-change + state-transition commits require individual report boundaries)
- Fork base: `77cf9762` (Slice η memory commit HEAD)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.7 + §4.7 + §6 Slice ε + §7.3 D21 close
- Predecessors:
  - α / β / γ / ζ (archived) — DTO surface evolution
  - **η** (archived) — layered EvidenceGraph hierarchy (NODE_RULE_EXPR / NODE_RULE / NODE_ATOM + 4 new edges); **ε hard-depends on η layered graph**
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` (Explanation class definition at L277)
  - `src/factgraph/application/protocol/explanation_render.py` (**new module** per parent §4.7 — walker location)
  - `src/factgraph/audit/evidence_graph.py` (post-η node/edge vocabulary; walker reads these)
  - `src/factgraph/application/protocol/__init__.py` (protocol re-export for new walker symbol if exposed)
  - `tests/application/protocol/test_evaluate_result_dtos.py` (Explanation tests)
  - `tests/application/protocol/test_explanation_render.py` (**new** — walker unit tests)
  - `src/service/runtime_v1.py` (service JSON `repr` key if Step 4.3 locks wire-side exposure)
- Related Docs:
  - `docs/quickstart/evaluate_and_evidence.md` (Explanation surface)
  - `docs/official/kernel/quickstart/evidence.md`
  - `docs/official/kernel/quickstart/namespace-map.md`
  - `src/factgraph/sdk/docs/00_user_guide.en.md`
  - `src/factgraph/sdk/docs/04_api_surface.en.md`
  - `src/factgraph/sdk/docs/06_what_if_and_proof.en.md` (if examples mention explain output)
- Audit Log:
  - [2026-06-03_explanation-repr-walker-slice-epsilon.audit.md](./2026-06-03_explanation-repr-walker-slice-epsilon.audit.md)

## 1. Problem

Post-γ `Explanation` carries `row: EvaluateRow | None` direct reference and `evidence: EvidenceGraph | None`, but no `repr` field. Users have no built-in "因为... 所以..." human-readable rendering of the evidence chain.

Parent design §3.7 + §4.7 specifies `Explanation.repr: tuple[str, ...] | None` as multi-line NL walked from the layered EvidenceGraph(η). Walker traverses graph from root (NODE_CONCLUSION) DFS-down through NODE_RULE_EXPR → NODE_RULE → NODE_ATOM → seed,producing one indented line per node with edge-kind-derived connector phrasing.

Slice ε **hard-depends on Slice η** layered graph(now in place at `77cf9762`)。Without η,walker has no L1/L2/L3 nodes to traverse.

Parent design §7.3 records that ε **closes D21 §6.6 path C deferred work**(D21 = `Explanation.desc_lines auto-populate`)。

## 2. Goals

- G1 — Add public `Explanation.repr: tuple[str, ...] | None` **computed property**, not an `__init__` dataclass argument. `None` for `unsupported` / `invalid_request`;non-None tuple for `passed` and for current shipped `failed` paths via a failure-summary fallback.
- G2 — Implement `factgraph.application.protocol.explanation_render.walk_evidence(graph, *, row=None, status="passed", failure_class=None) -> tuple[str, ...]` walker per parent §4.7 algorithm. The walker renders existing `EvidenceNode.label` / `value_summary` first; it must not require `head` because `Explanation` does not carry one.
- G3 — Walker traversal: from `evidence.root_node_id` DFS-down via shipped physical edge direction (per η PF-R1 lock:`adjacency[edge.to_node_id].append(edge.from_node_id)` — children iterated via `adjacency.get(root_node_id, [])`)
- G4 — Edge-kind-to-connector mapping(text rendering):
  - `EDGE_DERIVED_BY` → `"is derived by"`
  - `EDGE_USES` → `"which uses"`
  - `EDGE_HAS_ATOM` → `"which has atom"`
  - `EDGE_SUPPORTED_BY` → `"is supported by"`
  - `EDGE_SUPPORTS` → `"is supported by"`(legacy fallback)
  - `EDGE_DERIVES` → `"derives"`(ProbLog adapter trace fallback)
  - `EDGE_UPDATES` → `"updates"`(PyReason fallback)
- G5 — Failed status repr: current shipped failed paths (`closed_head_false`, `stale_row`, `row_not_in_result`) have `evidence=None` by invariant, so they render a deterministic failure summary tuple(`"NOT concluded"` + `failure_class` + next-step context) rather than graph-walking atoms. Atom-level `unsupport` wording is only in scope if Step 4.3 proves a shipped evidence-carrying failed path and explicitly amends the invariant.
- G6 — Lazy cache pattern:graph walker runs on first `.repr` access for `passed` explanations;result cached via `object.__setattr__` to internal `_repr_cache` field;subsequent reads bypass walker. Failed summaries may be computed directly without invoking graph traversal.
- G7 — Walker tests cover:passed 4-tier walk(parent §3.9.3 example),failed summary fallback under the shipped `evidence=None` invariant,unsupported/invalid_request returns None,detached row safety,empty graph safety
- G8 — Docs cascade: quickstart evaluate_and_evidence + official evidence + SDK example
- G9 — Close D21 §6.6 path C("Explanation.desc_lines auto-populate"deferred);blueprint Outcome cite parent §7.3 D21 close

## 3. Non-goals

- N1 — Slice δ query-style head decoupling
- N2 — Change η EvidenceGraph node/edge vocabulary or builder behavior
- N3 — Modify Slice α/β/γ/ζ artifacts
- N4 — Add new node/edge kinds beyond η's 6+7 vocabulary
- N5 — Service wire protocol breaking change unless Step 4.3 makes a Required finding
- N6 — Implement PyReason Form 2 timeline walker(deferred D11)
- N7 — Sacred-path edits(Q-PR1 5-path)
- N8 — Dirty baseline files
- N9 — Walker output as JSON or structured format other than `tuple[str, ...]` —— parent §4.7 specifies plain text lines

## 4. Current Source Anchors(Step 4.1 fresh read)

- `src/factgraph/application/protocol/evaluate_result.py:277-329` — Explanation class definition + __post_init__ validation
- `src/factgraph/application/protocol/evaluate_result.py:682+` — `_explain_live_row(...)` row-level Explanation construction
- `src/factgraph/audit/evidence_graph.py:11-29` — post-η vocabulary(6 node + 7 edge kinds)
- `src/factgraph/audit/evidence_graph.py:97-100` — shipped DFS adjacency (η PF-R1 locked Option 1)
- `src/factgraph/audit/evidence_graph.py:194-200` — shipped tree rendering (η preserved direction semantics)
- Parent §3.9.3 — 4-tier walk concrete example
- Parent §4.7 — walker algorithm pseudocode

## 5. Proposed Shape(Draft, Not Yet Locked)

### 5.1 Explanation new computed property

```python
@dataclass(frozen=True)
class Explanation:
    status: ExplanationStatus
    evidence: EvidenceGraph | None
    row: EvaluateRow | None
    result_id: str | None
    failure_class: ExplanationFailureClass | None = None
    checked_scope: Mapping[str, Any] | None = None
    suggested_next_steps: tuple[str, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()
    _repr_cache: tuple[str, ...] | None = field(
        default=None, init=False, repr=False, compare=False, hash=False
    )                                          # ← internal cache slot

    @property
    def repr(self) -> tuple[str, ...] | None:
        ...
```

`__post_init__` validation:
- `unsupported` / `invalid_request` → `repr is None` invariant
- keep shipped `status == "passed" iff evidence is not None` unless Step 4.3 explicitly proves a safe failed+evidence path
- `passed` → `repr` populated lazily by walker on first access(not eager at `__post_init__`)
- `failed` with `evidence=None` → `repr` populated by failure-summary fallback, not by graph walker

### 5.2 Walker location and signature

**New module**:`src/factgraph/application/protocol/explanation_render.py`(per parent §4.7)

```python
def walk_evidence(
    graph: EvidenceGraph,
    *,
    row: EvaluateRow | None = None,
    status: ExplanationStatus = "passed",
    failure_class: ExplanationFailureClass | None = None,
) -> tuple[str, ...]:
    """Walk a layered EvidenceGraph from root and produce multi-line NL."""
    lines: list[str] = []
    visit(graph.root_node_id, depth=0, lines=lines, graph=graph, ...)
    return tuple(lines)
```

Walker uses shipped adjacency direction (`adjacency[edge.to_node_id].append(edge.from_node_id)` per η PF-R1 lock) — children of `root_node_id` are nodes pointing TO `root_node_id` via `from_node_id`。

Step 4.2 P1/P2 LOCK: the walker does **not** receive `head`. `NODE_CONCLUSION` should render from `EvidenceNode.value_summary` / `label` first because η builders already put row/result rendering there. `row` is optional context for fallback lines and metadata only.

### 5.3 Walker algorithm(per parent §4.7)

```
visit(node_id, depth, lines, graph, edge_in=None):
    indent = "  " * depth
    label = render_node(node, status, failure_class)
    if edge_in is not None:
        connector = edge_kind_to_connector(edge_in.edge_kind)
        prefix = f"{indent}{connector} "
    else:
        prefix = indent
    lines.append(prefix + label)
    for child_edge in children_of(node_id, graph):
        visit(child_edge.from_node_id, depth + 1, lines, graph, edge_in=child_edge)
```

### 5.4 Node label rendering

- `NODE_CONCLUSION` → existing `node.value_summary` then `node.label`. Do not re-render from `row.bindings` + `result.head.desc` inside the walker; `Explanation` has no direct `EvaluateResult` / `head`, and η builders already fill the conclusion node from row/result context.
- `NODE_RULE_EXPR` → `f"RuleExpr({ast_form})"`from `engine_meta.ast_form`
- `NODE_RULE` → `f"Rule \"{rule_id}\""`from `engine_meta.rule_id`
- `NODE_ATOM` → atom kind / pred_id + `atom_status` annotation(e.g. `"User(u) — support"`)
- `NODE_SEED` → ledger fact description(`f"ledger fact {pred_id}({args})"`)
- `NODE_PREMISE` → legacy fallback,passthrough current `value_summary`

### 5.5 Failed status rendering

For `status == "failed"`:
- Current shipped failed explanations have `evidence=None` (`closed_head_false`, `stale_row`, `row_not_in_result`) because `Explanation.__post_init__` enforces `status == "passed" iff evidence is not None`.
- Default Slice ε behavior: return a deterministic failure summary tuple without walking a graph:
  - `"NOT concluded"`
  - `f"failure_class: {failure_class}"`
  - optional `suggested_next_steps` / checked-scope context
- Atom nodes with `atom_status="unsupport"` are only rendered if Step 4.3 adds an explicit failed+evidence path amendment.

### 5.6 Cadence path locks(per Slice η §10 D6)

- **Tight gates default** for ε(evidence-model continuation)
- Step 4.7 implementation + Step 4.8 closure **individual report boundaries required**
- Step 4.4 / 4.5 / 4.6 / 4.6.5 individual reports per η §5.6 + Codex D6 lock
- Stage 0 source audit folded into this Step 4.1 draft + Step 4.3 preflight verifies

### 5.7 Step 4.3 preflight locks

- **PF-R1 confirmed** — failed graph walking is not implemented in ε. Shipped `Explanation.__post_init__` enforces `status == "passed"` iff `evidence is not None`; active failed paths (`closed_head_false`, `stale_row`, `row_not_in_result`) return `evidence=None`. Slice ε preserves this invariant and renders failed explanations through deterministic summary lines.
- **PF-R2 confirmed** — `Explanation.repr` is a computed property with `_repr_cache`; there is no `repr=` constructor parameter.
- **PF-r1 carry-forward** — parent design wording that says `row.repr` is stale for ε. This slice implements `Explanation.repr`; `EvaluateRow.repr` remains out of scope. Parent-design wording sync is a follow-up, mirroring η D7.
- **PF-r2 export scope** — `walk_evidence(...)` is protocol-layer helper surface by default. Do not add it to `factgraph.sdk.__all__` unless Step 4.7 discovers a concrete user-facing need.

## 6. Boundaries And Invariants

- Must preserve:
  - η EvidenceGraph vocabulary + direction(no changes)
  - current `Explanation` invariant `status == "passed" iff evidence is not None` unless Step 4.3 produces a Required finding to relax it
  - Sacred Q-PR1 5-path 0-diff vs `4c472b50`
  - Dirty baseline preserved
  - Pre-ε Explanation 9-field shape compatibility(adding 1 field + 1 internal slot is additive)
- Explicitly NOT in this slice:
  - New EvidenceGraph node/edge kinds
  - Slice δ query-style head decoupling
- Compatibility constraints:
  - Walker output is per-Explanation deterministic given same graph + status + failure_class
  - `Explanation.repr` is not an `__init__` parameter; existing `Explanation(...)` construction sites remain source-compatible
  - `walk_evidence(...)` defaults to protocol exposure only; SDK `__all__` remains unchanged unless implementation finds an explicit user-facing requirement

### 6.1 Cadence path locks(per Codex D6)

- §5.2 walker location locked at `factgraph.application.protocol.explanation_render`(per parent §4.7)
- §5.6 tight gates default for ε
- Stage 1 audit doc deferred per Slice 4/5 precedent

## 7. Acceptance Criteria(Draft)

- [ ] Step 4.2 review has confirmed §5.4 node label rendering source for each kind
- [ ] Step 4.2 review has locked `Explanation.repr` as computed property rather than constructor dataclass field
- [ ] Step 4.2 review has split failed summaries from graph-walked passed explanations under the shipped `passed iff evidence` invariant
- [ ] Step 4.3 preflight has enumerated walker test cohort + lazy cache pattern + service wire scope
- [ ] Step 4.3 preflight PF-R1/PF-R2 locks are preserved: failed summaries do not graph-walk and no `repr=` constructor parameter exists
- [ ] Step 4.3 preflight PF-r2 export lock is preserved: protocol helper exposure by default, no SDK `__all__` change by default
- [ ] Public `Explanation.repr: tuple[str, ...] | None` computed property added with internal `_repr_cache`; no `repr=` constructor parameter
- [ ] `explanation_render.walk_evidence(...)` walker implemented per parent §4.7 algorithm
- [ ] Walker covers all 7 edge kinds(4 η new + 3 legacy)with appropriate connectors
- [ ] Walker covers all 6 node kinds(3 η new + 3 legacy)with kind-specific labels
- [ ] Lazy cache via `object.__setattr__` on `_repr_cache`;walker runs once per Explanation
- [ ] Failed status output includes `"NOT concluded"` + failure_class line; per-atom `unsupport` wording remains gated on Step 4.3 proving a failed+evidence path
- [ ] `unsupported` / `invalid_request` → `repr is None` invariant
- [ ] Walker tests cover passed 4-tier walk + failed summary fallback + edge cases(empty graph,unknown edge kind)
- [ ] D21 §6.6 path C closed(Outcome cite parent §7.3)
- [ ] Docs cascade: quickstart + official + SDK example
- [ ] Q-PR1 5-path 0-diff vs `4c472b50` preserved
- [ ] Dirty baseline preserved

## 8. Implementation Plan

1. Step 4.2 — Draft review + tightening on blueprint branch. **Required focus**:§5.4 label sources(especially `NODE_CONCLUSION` row desc rendering availability)+ failed status wording lock + cache pattern + service wire scope
2. Step 4.3 — Independent preflight on `v0.2.0-explanation-repr-walker-preflight-2026-06-03`;produce 5-bucket finding table
3. Step 4.4 — Fold preflight findings
4. Step 4.5 — Self-check
5. Step 4.6 — Scope freeze(`draft` → `scoped`)
6. Step 4.6.5 — Pre-impl grep(check `Explanation\(` construction sites,`repr=` constructor usage,`_repr_cache`,`walk_evidence` exports,`tuple\[str` annotations,potential collisions with `repr` builtin / field)
7. Step 4.7 — Implementation on `v0.2.0-impl-explanation-repr-walker-2026-06-03` — protocol DTO + new render module + tests + docs(individual report per D6)
8. Step 4.8 — Closure(individual report per D6)
9. Step 4.9 — Archive

## 9. Pre-Impl Audit Tasks for Step 4.3

- A1 — Confirm walker DFS direction works under η PF-R1 shipped direction(`adjacency[to_node_id].append(from_node_id)` — children iterated correctly from root)
- A2 — Enumerate `Explanation(...)` construction sites that need `repr` parameter(should default `None` so additive)
- A3 — Verify `NODE_CONCLUSION.value_summary` / `label` availability for rendering and confirm no direct `head` dependency is needed in the walker
- A4 — Check whether any test asserts `Explanation` exact field count(post-ε will have 10 + 1 internal)
- A5 — Service wire scope:does `_evaluate_result_to_dict(...)` or explain JSON emit `repr`?Default is no service wire change unless preflight finds an explicit Explanation serializer.
- A6 — Docs cascade enumeration(quickstart + official + SDK + maybe service)
- A7 — Cache field naming collision check(`_repr_cache` not used elsewhere)
- A8 — Walker edge case enumeration:empty graph,cyclic check(should not happen post-η),orphan nodes

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — Slice δ query-style head decoupling
- D2 — PyReason Form 2 timeline walker(D11)
- D3 — Parent design §3.9.2 direction wording sync(from η D7,not in ε scope)
- D4 — Parent design `row.repr` wording sync(PF-r1). Slice ε implements `Explanation.repr`; `EvaluateRow.repr` remains out of scope.
