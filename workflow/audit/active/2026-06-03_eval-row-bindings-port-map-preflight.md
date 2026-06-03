# Step 4.3 Preflight: Eval-row bindings port-map Slice ζ

- Blueprint branch HEAD: `c3c89be7`
- Preflight branch: `v0.2.0-eval-row-bindings-port-map-preflight-2026-06-03`
- Artifact date: 2026-06-03
- Blueprint: [`workflow/blueprints/active/2026-06-03_eval-row-bindings-port-map-slice-zeta.md`](../../blueprints/active/2026-06-03_eval-row-bindings-port-map-slice-zeta.md)
- Scope: parent design §3.6 / Slice ζ, changing in-process `EvaluateRow.bindings` from legacy `{pred_id, terms[]}` payload to `{port_name: term}` map while preserving locked service/provenance compatibility paths.

## 1. Method

Ran the six blueprint §9 audit tasks against post-Slice-γ HEAD:

- A1 — `_candidate_set_to_evaluate_row(...)` construction sites and port-name source.
- A2 — `row.bindings` consumers across `src/`, `tests/`, and active docs.
- A3 — legacy `pred_id` / `terms` accessors, manually bucketed by row-derived vs ledger/core/candidate-payload contexts.
- A4 — canonical bytes schema bump blast radius.
- A5 — service/provenance legacy payload compatibility scope.
- A6 — docs cascade.

## 2. Findings Summary

| Bucket | Count | IDs |
| --- | ---: | --- |
| Required | 3 | PF-R1, PF-R2, PF-R3 |
| Recommended | 2 | PF-r1, PF-r2 |
| Verified | 7 | PF-v1..PF-v7 |
| Scoped-detail | 3 | PF-s1..PF-s3 |
| Abandonment | 0 | — |

Healthy distribution: 3R / 2r / 7v / 3s / 0A. Required count stays within the healthy band because ζ is a user-facing row-shape slice with service/provenance compatibility gates.

## 3. Required Findings

### PF-R1 — Legacy candidate payload helper is required for row-derived ProbLog provenance

Step 4.2 P1-3 was correct and should remain locked, with a narrow implementation target.

Shipped row-derived path:

- `src/factgraph/application/protocol/evaluate_result.py:927` calls `problog_trace_to_evidence_graph(..., candidate_payload=dict(row.bindings), ...)`.
- `src/factgraph/adapters/problog/provenance.py:503-509` `_resolve_candidate_info(...)` requires `candidate_payload.pred_id` and `candidate_payload.terms`.
- `src/factgraph/adapters/problog/provenance.py:768-771` `_candidate_binding_from_payload(...)` also requires `candidate_payload.terms`.

Implication:

- After ζ, `dict(row.bindings)` becomes `{port_name: term}` and will no longer satisfy ProbLog provenance helpers.
- Step 4.7 must introduce a row/result helper such as `_legacy_candidate_payload_for_row_result(row, result)` and use it in `_build_problog_provenance_row_evidence_graph(...)`.
- The helper should produce `{"pred_id": result.head.id, "terms": [...]}` with terms ordered by `result.head.ports`.

### PF-R2 — Production construction sites can pass `head`; preflight found no hidden production constructor

Step 4.2 P1-1 is complete: `CandidateSet` does not carry `head`, but all production row construction sites already have `head` in scope.

Construction sites:

| Site | Current call | Head source |
| --- | --- | --- |
| `src/factgraph/sdk/store.py:2691` | `_candidate_set_to_evaluate_row(...)` | local `head` argument in `_candidate_sets_to_evaluate_result(...)` |
| `src/service/runtime_v1.py:2359` | `_candidate_set_to_evaluate_row(...)` | local `head = _head_rule_for_compiled_plans(...)` |
| `tests/application/protocol/test_evaluate_result_dtos.py:993` | `_candidate_set_to_evaluate_row(...)` | test can pass the `_result_parts()` head |

Implementation lock:

- Change `_candidate_set_to_evaluate_row(candidate, *, head, ...)`.
- Change `_bindings_from_candidate(candidate, *, head)`.
- Do not create or infer `candidate.head`.

### PF-R3 — Schema-v2 canonical bytes need explicit test/doc updates

Step 4.2 P1-2 locks v2 schema labels. Preflight confirms the blast radius is mostly protocol tests and docs rather than external code branches.

Relevant source anchors:

- `src/factgraph/application/protocol/evaluate_result.py:377-381` `row_id_for(...)` currently uses `evaluate_row_id_v1`.
- `src/factgraph/application/protocol/evaluate_result.py:384-389` `claim_digest_for(...)` currently uses `evaluate_claim_v1`.
- `src/factgraph/application/protocol/evaluate_result.py:461-489` `_row_digest_for(...)` currently uses `evaluate_row_digest_v1` and embeds `row.bindings` plus claim arguments.

Test/doc anchors:

- `tests/application/protocol/test_evaluate_result_digests.py:49-57` asserts deterministic row id / claim digest behavior, but does not pin literal digest bytes.
- `tests/application/protocol/test_evaluate_result_dtos.py` constructs rows with direct bindings dictionaries and compares `row.digest` to `claim_digest_for(...)`; these tests must be migrated to the new map shape and v2 semantics.
- Active docs mention row digest/row id as stable replay/audit anchors but do not currently promise cross-version byte equality.

Implementation lock:

- Update schema labels to v2 for row id / claim digest / row digest.
- Preserve algorithm discipline (`canonical_bytes_for_evaluate` + SHA token/hex validation).
- Preserve `evidence_ref_id_for(...)` v1 label, with derivative output changes only through `row_id` / `row.digest`.

## 4. Recommended Findings

### PF-r1 — Keep `_binding_value_for_head_port(...)` dual-shape fallback during ζ

`src/factgraph/application/protocol/evaluate_result.py:779-789` already supports both:

- new `row.bindings[port_name]` access, and
- legacy `row.bindings["terms"]` fallback in head-port order.

Recommendation:

- Keep this dual-shape fallback during ζ.
- It makes `row.close()` robust for detached/test rows and reduces migration brittleness.
- Do not let the fallback imply that production `EvaluateRow.bindings` may continue to emit legacy shape.

### PF-r2 — Keep `_claim_arguments_for_row(row)` as pass-through helper for one slice

Step 4.2 already locked `_claim_arguments_for_row(row)` as a trivial pass-through helper.

Recommendation:

- Keep it in Step 4.7.
- It remains a named compatibility seam for service wire `claim.arguments`, `_row_digest_for(...)`, and tests.
- Deleting it can be considered after ζ once row binding shape has settled.

## 5. Verified Findings

### PF-v1 — CandidateSet carries no `head`

`src/factgraph/core/derivation/candidates.py:14-21` defines `CandidateSet` with `target` and `payload`; no `head` field exists.

### PF-v2 — Current `_bindings_from_candidate(...)` is payload-only

`src/factgraph/application/protocol/evaluate_result.py:1297-1302` reads `candidate.payload`, returns `payload["bindings"]` if present, otherwise freezes the whole payload. This explains why the test harness already passes when payload contains a pre-shaped `bindings` map.

### PF-v3 — Current candidate payload canonical content remains legacy and out of ζ in-process row scope

`src/factgraph/core/derivation/candidates.py:126-136` canonicalizes fact candidates as `{"pred_id": pred_id, "terms": normalized_terms}`. ζ should not mutate core CandidateSet payload canonicalization; it changes application-protocol `EvaluateRow.bindings`.

### PF-v4 — Service row serializer is the only row-derived service wire binding emitter

`src/service/runtime_v1.py:2468-2488` `_evaluate_row_to_dict(...)` emits `"bindings": _to_jsonable(row.bindings)`. Step 4.7 must replace this with the legacy payload helper for service wire compatibility.

### PF-v5 — Direct `row.bindings` test consumers are mostly string/roundtrip checks

Representative active tests:

- `tests/sdk/test_rule_expr_evaluate.py` asserts values appear or internal keys do not appear in `str(result[0].bindings)`.
- `tests/application/protocol/test_evaluate_result_dtos.py` asserts direct dict equality in the protocol harness.
- `tests/test_pyreason_e2e.py:140` aliases `candidate.bindings` as `claim_arguments`.

These are implementation/test migration sites, not blockers.

### PF-v6 — Documentation cascade is concentrated and expected

Active docs with direct row bindings statements:

- `docs/quickstart/evaluate_and_evidence.md`
- `docs/official/kernel/quickstart/evidence.md`
- `src/factgraph/sdk/docs/01_concepts.en.md`
- `src/service/docs/06_frontend_integration.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `docs/api/openapi.yaml` if service wire schema is represented

### PF-v7 — Q-PR1 sacred paths not implicated

All sources and docs found by A1-A6 are outside the Q-PR1 sacred paths. The Q-PR1 5-path diff remains empty at preflight.

## 6. Scoped Details

### PF-s1 — PyReason/core provenance helpers expect legacy payloads, but not from row.bindings

Preflight found legacy candidate payload expectations in:

- `src/factgraph/adapters/pyreason/provenance.py:339-345`
- `src/factgraph/core/store/_candidate_provenance_timeline.py:467-476`

These functions expect `pred_id` + `terms`, but their service/direct callers pass independent candidate payloads, not `dict(row.bindings)`. They remain important compatibility examples, but they do not add new Step 4.7 row-derived implementation scope unless a later grep finds a row-derived caller.

### PF-s2 — Service candidate evidence tree paths are not EvaluateRow bindings paths

`src/service/runtime_v1.py` has multiple candidate payload helpers around candidate evidence tree endpoints. Those helpers derive payloads from ledger claims or candidate records and should keep legacy payload shape. They are out of ζ's in-process `EvaluateRow.bindings` migration except as compatibility precedents.

### PF-s3 — Core/frontier `bindings` are unrelated

Many `bindings` hits are native where/frontier/query bindings (`NativeWhereFrontierEvaluation.bindings`, why-not runtime, fact overlay diffs). They are not `EvaluateRow.bindings` and must not be swept into ζ.

## 7. Abandonment

None.

No finding invalidates ζ. The slice remains implementable with the Step 4.2 locks plus the narrowed PF-R1/PF-R2/PF-R3 details above.

## 8. Amendment Checklist for Step 4.4

Fold the following back into the blueprint branch:

1. PF-R1: narrow legacy-payload helper language to row-derived ProbLog provenance plus service row serializer; do not over-broaden to all candidate payload helpers.
2. PF-R2: explicitly list the two production construction sites and one test construction site that must pass `head`.
3. PF-R3: record exact v2 labels for `evaluate_row_id_v2`, `evaluate_claim_v2`, and `evaluate_row_digest_v2`; keep `evaluate_evidence_ref_v1`.
4. PF-r1: preserve `_binding_value_for_head_port(...)` dual-shape fallback during ζ.
5. PF-r2: keep `_claim_arguments_for_row(row)` pass-through helper.
6. PF-s1/PF-s2/PF-s3: add carve-outs so Step 4.7 does not migrate unrelated candidate payload or frontier bindings.

## 9. Verification Snapshot

- Branch: `v0.2.0-eval-row-bindings-port-map-preflight-2026-06-03`
- Blueprint source: `c3c89be7`
- Sacred master: unchanged at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Q-PR1 5-path diff: empty
- Dirty baseline: preserved
