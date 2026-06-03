# Project Memory: Eval-row bindings port-map Slice ζ implemented

- Date: 2026-06-03
- Final branch: `v0.2.0-impl-eval-row-bindings-port-map-2026-06-03`
- Final HEAD: `19f3724d`
- Fork base: `0719ace6` (Slice γ archive HEAD)
- Parent design: `workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md` §3.6 + §6 Slice ζ

## Summary

Slice ζ changed in-process `EvaluateRow.bindings` from the legacy `{pred_id, terms[]}` candidate payload to a direct `{port_name: term}` map.

The slice preserved compatibility where the legacy envelope is still the public or engine-facing contract:

- service JSON wire `"bindings"` still emits `{pred_id, terms[]}`
- ProbLog row evidence graph still receives candidate payloads shaped as `{pred_id, terms[]}`
- PyReason/core candidate provenance and service candidate-evidence-tree paths continue to consume original candidate payloads directly

## Commit chain

```text
6397e241  Step 4.1 blueprint draft
c3c89be7  Step 4.2 review + tightening
9d0e1186  Step 4.3 preflight artifact
b88c215f  Step 4.4 preflight amendment
0755fe91  Step 4.6 scope freeze
8625a7f9  Step 4.6.5 pre-impl grep
dad98c12  Step 4.7 implementation
d7f13531  Step 4.8 closure
46c95de9  Step 4.3 preflight cherry-pick onto impl branch
19f3724d  Step 4.9 archive
```

## Implementation notes

- `_candidate_set_to_evaluate_row(..., head=...)` now receives explicit head context.
- `_bindings_from_candidate(candidate, *, head)` maps candidate terms to `head.ports`.
- `row_id_for`, `claim_digest_for`, and `_row_digest_for(...)` use `evaluate_row_id_v2`, `evaluate_claim_v2`, and `evaluate_row_digest_v2`.
- `evaluate_evidence_ref_v1` remains unchanged.
- `_legacy_candidate_payload_for_row_result(row, result)` reconstructs `{pred_id, terms[]}` for compatibility paths.
- `_binding_value_for_head_port(...)` unwraps typed term dicts for row close / closed-head construction.

## Verification

- Full tests: `2454 passed / 32 skipped / 1044 subtests passed`
- Q-PR1 5-path diff vs `4c472b50`: empty
- Sacred master: `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged
- Dirty baseline preserved

## Deviation

PyReason field-style candidates can include more payload terms than application head ports. Slice ζ maps the first `len(head.ports)` terms into in-process row bindings and preserves the legacy candidate envelope only for compatibility paths.
