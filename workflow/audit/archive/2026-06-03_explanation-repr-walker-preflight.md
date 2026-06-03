# Preflight: Explanation.repr walker Slice epsilon

- Blueprint: [`workflow/blueprints/active/2026-06-03_explanation-repr-walker-slice-epsilon.md`](../../blueprints/active/2026-06-03_explanation-repr-walker-slice-epsilon.md)
- Audit log: [`workflow/blueprints/active/2026-06-03_explanation-repr-walker-slice-epsilon.audit.md`](../../blueprints/active/2026-06-03_explanation-repr-walker-slice-epsilon.audit.md)
- Branch: `v0.2.0-explanation-repr-walker-preflight-2026-06-03`
- Fork: `f916cd47` (Step 4.2 review + tightening)
- Date: 2026-06-03
- Status: Step 4.3 preflight artifact

## 1. Scope

This preflight verifies Slice epsilon before implementation. The slice adds a computed
`Explanation.repr` property and a protocol-layer EvidenceGraph walker over the layered graph
introduced in Slice eta.

The preflight specifically checks the Step 4.2 locks:

- failed explanations currently have `evidence=None` by invariant, so failed repr must use a
  deterministic failure summary rather than graph walking;
- `Explanation.repr` must be a computed property backed by `_repr_cache`, not a constructor
  dataclass field;
- the walker must render existing node `value_summary` / `label` and must not require a `head`
  argument;
- service wire remains unchanged unless an explicit Explanation serializer is found.

## 2. Method

Commands were run from `/Users/zhenzhili/hnsm-backend` on the preflight branch. Fresh source
anchors were read with line numbers rather than relying on the Step 4.1 draft text.

Primary source anchors:

| Area | Source anchor | Verified fact |
| --- | --- | --- |
| Explanation shape | `src/factgraph/application/protocol/evaluate_result.py:276-328` | Explanation has 9 public fields today and no `repr`; `__post_init__` enforces shipped invariants. |
| Failed/passed construction | `src/factgraph/application/protocol/evaluate_result.py:682-745` | `row_not_in_result` and `stale_row` return failed + `evidence=None`; passed returns evidence graph. |
| SDK closed-head false | `src/factgraph/sdk/store.py:2493-2499` | manual explain failure returns failed + `evidence=None`. |
| Conclusion labels | `src/factgraph/application/protocol/evaluate_result.py:918-946` | `NODE_CONCLUSION` already has `label` and `value_summary` derived from row/result context. |
| Graph direction | `src/factgraph/audit/evidence_graph.py:106-109` | shipped DFS adjacency is `adjacency[edge.to_node_id].append(edge.from_node_id)`. |
| Service wire | `src/service/runtime_v1.py:2450-2491` | service serializes EvaluateResult and rows, not an Explanation repr field. |
| DTO tests | `tests/application/protocol/test_evaluate_result_dtos.py:720-792` | active tests already exercise Explanation invariants and constructors. |

## 3. Findings

| ID | Bucket | Severity | Finding | Required action |
| --- | --- | --- | --- | --- |
| PF-R1 | Required | P1 | Failed graph walking is not currently possible under shipped invariants. `Explanation.__post_init__` requires `status == "passed"` iff `evidence is not None` at `evaluate_result.py:291-292`, and all active failed construction paths observed return `evidence=None`. | Lock Step 4.2 behavior: failed `repr` uses a deterministic summary tuple, not graph walking. Atom-level failed/unsupport graph rendering remains out of scope unless a later slice changes the invariant. |
| PF-R2 | Required | P1 | `repr` as a dataclass field would introduce a constructor parameter and disrupt existing `Explanation(...)` callsites. No active callsite expects or passes `repr=`, and `_repr_cache` does not exist yet. | Implement `repr` as `@property` with internal `_repr_cache: tuple[str, ...] | None = field(default=None, init=False, repr=False, compare=False, hash=False)`. Acceptance must require no `repr=` constructor parameter. |
| PF-r1 | Recommended | P2 | Parent design has a stale phrasing pocket that says Slice epsilon is for `row.repr`, while the current slice and Step 4.2 locks implement `Explanation.repr`. | Step 4.4 should add a design-side follow-up note or supersession marker: epsilon implements `Explanation.repr`; `EvaluateRow.repr` remains out of scope. |
| PF-r2 | Recommended | P2 | Walker export scope should be explicit. A protocol helper module is needed, but no source-grounded need was found to export `walk_evidence` through `factgraph.sdk.__all__`. | Lock helper exposure to `factgraph.application.protocol` by default; do not change SDK `__all__` unless Step 4.7 finds a direct user-facing need. |
| PF-v1 | Verified | - | Eta shipped direction is stable. The walker should use the same physical graph direction as `EvidenceGraph` validation/rendering: children of a parent are edges whose `to_node_id` is the current node and whose `from_node_id` is the child/supporter. | No new graph-direction logic. |
| PF-v2 | Verified | - | `NODE_CONCLUSION.value_summary` / `label` are already populated by `_row_conclusion_node(...)`; the walker does not need `head`. | Keep Step 4.2 no-head signature. |
| PF-v3 | Verified | - | No explicit Explanation JSON serializer was found in service code. Service wire default no-change remains sound. | No service wire change in Slice epsilon. |
| PF-v4 | Verified | - | `_repr_cache` is not used elsewhere in active source. | Safe internal cache field name. |
| PF-v5 | Verified | - | `unsupported` and `invalid_request` require errors and have no evidence graph. | `repr is None` remains the honest output for these statuses. |
| PF-s1 | Scoped | - | Test scope should include a new walker unit-test file plus existing DTO invariant tests. | Add `tests/application/protocol/test_explanation_render.py`; update `test_evaluate_result_dtos.py` only for the new computed-property behavior. |
| PF-s2 | Scoped | - | Docs cascade is bounded but non-empty. | Update quickstart/official/SDK docs that discuss Explanation and deferred desc/repr rendering. |

No abandonment finding was found.

## 4. Task Results

### A1. Walker DFS direction

`EvidenceGraph.__post_init__` builds DFS adjacency as:

```python
adjacency[edge.to_node_id].append(edge.from_node_id)
```

This confirms the eta PF-R1 shipped-direction lock. Slice epsilon should walk from
`graph.root_node_id` using the same physical child lookup. Reversing direction in the walker would
fork render behavior from validation/render-tree semantics.

### A2. Explanation construction sites

Active construction paths do not require a `repr=` constructor parameter:

- `evaluate_result.py:696-704` constructs failed `row_not_in_result`;
- `evaluate_result.py:707-715` constructs failed `stale_row`;
- `evaluate_result.py:724-737` constructs unsupported graph-validation failure;
- `evaluate_result.py:739-745` constructs passed explanation;
- `sdk/store.py:2493-2499` constructs failed `closed_head_false`;
- `sdk/store.py:2504-2511` reconstructs Explanation from a row explanation;
- `tests/application/protocol/test_evaluate_result_dtos.py:749-792` covers direct test constructors.

Conclusion: `repr` must remain additive and computed.

### A3. NODE_CONCLUSION rendering source

`_row_conclusion_node(...)` fills:

- `label=_claim_name_for_row_result(row, result)`;
- `value_summary=_claim_repr_for_row_result(row, result)`;
- `engine_meta["explained_claim_ref"]["claim_repr_cache"]`.

This validates Step 4.2 P3. The walker should render node summaries first and treat `row` as
fallback context only. A `head` parameter would be redundant and unavailable from `Explanation`.

### A4. Test field-count assertions

No shipped source requires a new constructor field. Existing DTO tests focus on invariants,
status/evidence coupling, and constructor validity. The new tests should assert:

- `Explanation(...).repr` is available as a property;
- the constructor rejects/ignores no `repr=` path because the parameter must not exist;
- `_repr_cache` is lazy and not part of dataclass comparison/repr/hash.

### A5. Service wire scope

`src/service/runtime_v1.py` serializes `EvaluateResult` metadata and row fields. It does not expose
an Explanation-specific `repr` today. Slice epsilon should not add service wire fields by default.

If future service endpoints expose Explanation DTOs directly, that should be a separate wire-surface
slice or an explicit Step 4.7 finding.

### A6. Docs cascade

Docs that should be checked during implementation:

- `docs/quickstart/evaluate_and_evidence.md` (currently describes deferred desc/repr rendering);
- `docs/official/kernel/quickstart/evidence.md`;
- `docs/official/kernel/quickstart/namespace-map.md`;
- `src/factgraph/sdk/docs/00_user_guide.en.md`;
- `src/factgraph/sdk/docs/04_api_surface.en.md`;
- `src/factgraph/sdk/docs/06_what_if_and_proof.en.md` if examples mention explain output.

### A7. Cache field naming collision

No active source symbol `_repr_cache` was found. The proposed internal name is safe.

### A8. Walker edge cases

Implementation tests should cover:

- empty graph / root not found behavior through existing `EvidenceGraph` validation rather than
  walker-specific fake states;
- orphan nodes not reachable from root, if valid graph construction allows them;
- legacy edge kinds (`supports`, `derives`, `updates`);
- unknown `atom_status` values falling back to a neutral phrase rather than fabricating support.

## 5. Step 4.4 Amendment Checklist

Apply on blueprint branch `v0.2.0-blueprint-explanation-repr-walker-2026-06-03`, not on this
preflight branch.

- [ ] Add PF-R1 / PF-R2 as preflight-confirmed locks in §5 and §7.
- [ ] Add PF-r1 parent-design wording carry-forward: epsilon implements `Explanation.repr`, not
      `EvaluateRow.repr`.
- [ ] Add PF-r2 export-scope lock: protocol helper exposure by default; no SDK export by default.
- [ ] Refresh docs cascade list in §8 / §9.
- [ ] Add Step 4.6.5 grep requirement for `repr=` constructor usage and `_repr_cache`.
- [ ] Add audit log Event Log row and Decision Notes for Step 4.4.

## 6. Sacred/Invariants Snapshot

- Q-PR1 5 sacred paths remain out of scope and must stay 0-diff vs `4c472b50`.
- Sacred `master` remains an invariant only and must not be modified.
- Dirty baseline entries remain user-owned and must not be staged/reverted.
- No implementation started in Step 4.3.

## 7. Preflight Verdict

PASS with amendment required. No abandonment blocker.

The slice is implementable as drafted after Step 4.4 folds the two Required confirmations and the
two Recommended clarifications. The main implementation risk is avoiding accidental constructor
surface changes while adding a public computed property.
