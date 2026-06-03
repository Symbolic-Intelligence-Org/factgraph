# Project Memory: EvidenceGraph 3-tier hierarchy Slice eta implemented

- Date: 2026-06-03
- Final branch: `v0.2.0-impl-evidence-graph-3tier-2026-06-03`
- Final HEAD: `0dba11ea`
- Fork base: `b4d80f13` (Slice zeta memory HEAD)
- Parent design: `workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md` §3.9 + §6 Slice eta

## Summary

Slice eta added layered row-level `EvidenceGraph` vocabulary:

- `NODE_RULE_EXPR`
- `NODE_RULE`
- `NODE_ATOM`
- `EDGE_DERIVED_BY`
- `EDGE_USES`
- `EDGE_HAS_ATOM`
- `EDGE_SUPPORTED_BY`

Legacy `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, `EDGE_SUPPORTS`, `EDGE_DERIVES`, and `EDGE_UPDATES` remain valid and non-deprecated.

PF-R1 locked shipped physical edge direction: `from_node_id` remains the supporting child / cause, and `to_node_id` remains the supported parent / conclusion. Parent design §3.9.2 has the opposite wording and remains a design-side follow-up.

## Commit chain

```text
2aa484fd  Step 4.1 blueprint draft
1f7c6d5c  Step 4.2 review + tightening
a6e24d3b  Step 4.3 preflight artifact
8dee886e  Step 4.4 preflight amendment
0dabf94d  Step 4.5+4.6 scope freeze
3c731196  Step 4.6.5 pre-impl grep
ea0e394b  Step 4.7 implementation
f23af16e  Step 4.8 closure
0dba11ea  Step 4.9 archive
```

## Implementation notes

- Fallback passed-row graphs now include a minimal conclusion / rule_expr / rule shell without fabricating supported atom evidence.
- Native/Souffle Form 1 graphs now emit conclusion / rule_expr / rule / atom / seed hierarchy where witness detail exists.
- ProbLog uses P1-lite: a row-level shell plus a synthetic row-level atom, with the adapter trace graph preserved below it.
- Audit `EvidenceGraph` JSON accepts and emits eta vocabulary because node/edge kinds serialize directly.
- Candidate evidence tree taxonomy remains out of scope.

## Verification

- Focused evidence cohort: `75 passed, 7 subtests passed`
- Wider evidence/protocol cohort: `223 passed, 16 subtests passed`
- Full tests: `2455 passed / 32 skipped / 1044 subtests passed`
- Q-PR1 5-path diff vs `4c472b50`: empty
- Sacred master: `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged
- Dirty baseline preserved

## Deviation

Eta explicitly locked tight gates, but Steps 4.4 through 4.7 were executed without the individual report gates and without the expected PF-R1 user-decision checkpoint. The substantive outcome matched the recommended PF-R1 Option 1 and passed verification, but cadence discipline was violated. Future evidence-model slices should use individual report boundaries for behavior-change and state-transition commits unless the user explicitly changes cadence policy.
