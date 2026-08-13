# Q15 Decision: captured EvaluationQuery run v0

- Status: adopted
- Created: 2026-08-13
- Authority: the user's 2026-08-13 authorization for project-level continuous
  FactGraph delivery, bounded by the existing Query/F4 contracts.
- Depends on: Q5A/Q5B, Q6A/Q6B, Q8, Q9, Q12, Q13 and Q14.
- Downstream: [`FactGraph Query/Scenario program`](../../../blueprints/active/2026-08-13_factgraph-query-scenario-program.md)

## Decision

Add a separate `CapturedEvaluationQueryRunV0` outer artifact for a targeted,
native Query.  It composes — but does not alter — the existing F4
`EvaluationRunBundleV0`:

```text
targeted Query + optional contains_row expectations
  -> F4 bundle capture
  -> CapturedEvaluationQueryRunV0
     (bundle + wrapper pin + expectation inventory + outcomes)
```

The public fluent entrance is terminal:

```python
captured = fg.query(target).bind(...).select(...).expect_contains(...).capture()
captured.verify()
captured.explain(row_capture_digest=...)
```

The artifact is detached, codec-round-trippable and integrity-sealed, not
authenticated.  Its `verify()` reuses F4 isolated native verification; its
`explain(...)` reuses F4 detached evidence plus the readonly Policy projection.

## Preserved boundaries

- Do **not** change `EvaluationRunAnchorV0`, `EvaluationRunBundleV0`, the
  ordinary `EvaluateResult`, or the existing `eval.evaluate(..., capture=...)`
  rejection of expectation plus capture.
- The outer artifact owns the expectation inventory and outcomes.  It recomputes
  those outcomes from captured rows during decode/currentness checks.
- `not_satisfied` means only no matching row in this captured complete native
  enumeration.  It is not closed-world truth, source authority, a historical
  truth claim, a negative EvidenceGraph, or authorization.
- No Scenario plus expectation, generic expectation grammar, pagination,
  limits, non-native engine/config, premise-filter execution, Operator, Action,
  Agent or Meander API is added.

## Consequences

This closes the usability gap between F4's low-level detached components and a
normal Query/validation run without creating a second evaluator or widening
the historical replay claim.  It is a prerequisite for a later narrow Meander
L3 adapter, but is not such an adapter.

## Acceptance

- [x] The outer digest seals exact F4 bundle, targeted wrapper, ordered
  expectation inventory and recomputed outcomes.
- [x] Codec/decode rejects hybrid or stale inventory/outcome artifacts.
- [x] `verify()` and explicit-row `explain()` never read a live Store.
- [x] Zero-row/negative outcomes never manufacture an EvidenceGraph.
- [x] Existing F4 and ordinary expectation/capture rejection paths remain
  byte/behavior compatible.
