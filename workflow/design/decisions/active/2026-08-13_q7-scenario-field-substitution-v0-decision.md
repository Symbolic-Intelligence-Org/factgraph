# Q7 Decision: minimal Scenario field substitution v0

- Status: adopted
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: narrow implementation constraint for F5A; it does not adopt the broader Scenario/What-if design.
- Inputs:
  - 2026-08-13 user direction to complete the currently implementable F5 work without further step-by-step authorization
  - [Q6A EvaluationRun boundary](./2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md)
  - [Q6B bundle-capture boundary](./2026-08-12_q6b-evaluation-run-bundle-capture-decision.md) §2.3
  - `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` §7.2–§8.1, §12.1 (candidate reference only)
- Outputs / Downstream:
  - [`2026-08-13_factgraph-f5-scenario-field-substitution.md`](../../../blueprints/active/2026-08-13_factgraph-f5-scenario-field-substitution.md)
- Branch: `codex/v0.3.0-f5-scenario-v0-2026-08-13`
- Depends on: Q5A/Q5B and Q6A/Q6B

## 1. Problem

The intended product model makes a Scenario an optional resolution stage before
the ordinary Query evaluator.  The existing FactOverlay helpers are useful
implementation substrate, but their assertion-id-oriented before/after API is
not a public semantic Scenario contract.  F4 bundles are captured evaluator
inputs, not a complete historical database snapshot, and cannot silently
answer Scenario missing/add or historical-value semantics.

## 2. Scope

This decision locks exactly one experimental FactGraph capability:

```python
fg.eval.evaluate(
    compiled_query,
    scenario=ScenarioFieldSubstitutionV0(
        entity=EntityRef("Person", {"employee_id": "alice"}),
        field=FieldPath("Person", "age"),
        value=22,
        premise_id="review-age-hypothesis",
    ),
)
```

It is a single, direct, visible-field substitution for one already-known
entity.  It is deliberately named `ScenarioFieldSubstitutionV0`, rather than
a general `ScenarioPlan` or `SET_EFFECTIVE_VALUE` API.

## 3. Decision

### 3.1 Input and resolution

- The only target is a trusted `CompiledEvaluationQueryV0`; there is no bare
  Policy/rule string lookup or ambient catalog resolution.
- The premise contains one `EntityRef`, one direct `FieldPath`, one scalar
  value and one opaque `premise_id`.  A supplied encoded entity reference is
  ignored and rebuilt from the trusted schema identity.
- The field must be schema-defined, owned by that entity type, extensional,
  non-identity, scalar and `single` cardinality.  The entity identity bundle
  and exactly one visible projected field fact must exist.  Missing,
  ambiguous, invisible or malformed targets fail closed; v0 never chooses a
  value or adds one.
- The target predicate must occur in the exact materialized Query dependency
  relation.  Policy-relative navigation such as `pair.person1.age` remains
  deferred.

### 3.2 Execution and result

- Resolution pins the current Query view, derives a dependency-complete
  run-local relation, and makes an immutable copied relation whose target row
  carries a deterministic synthetic Scenario-hypothesis identity.  The
  original ledger and its assertions are never written or reclassified.
- Baseline and substituted relations run through the same materialized native
  Query evaluator.  No second public evaluator, Scenario engine or mutable
  Store view is introduced.
- The returned `EvaluateResult` carries typed `scenario` resolution/result
  diff metadata.  Its effective fingerprint commits a Scenario effective-view
  digest; it does not claim that digest is a ledger snapshot.
- Same-value substitution is legal: it reports
  `semantic_value_changed=false` and `effective_source_changed=true`.
- Scenario rows deliberately have no live `close()` or `explain()` path, no
  F4 Run anchor and no run-bundle capture.  Present F4 evidence refers to
  ledger assertions; using it to prove a hypothetical value would be false
  provenance.

### 3.3 Strict v0 execution profile

Only native, `config=None`, empty premise-filter Query evaluation is admitted.
The current base view is checked before and after resolution and each internal
evaluation; a concurrent Store change rejects the entire request.

## 4. Non-scope

- Missing-value insertion, add/delete/mask, multiple premises, multi-value or
  relationship fields, ephemeral entities, temporal/as-of/versioned or
  historical-fact semantics, negation/closure, Policy overlays and rule
  changes. An ordinary scalar field with value domain `time` remains
  admissible; that is not temporal history or temporal truth semantics.
- SourceRecord/admission/authority semantics, Agent or Meander wire formats,
  UI, Package/catalog lookup, Operator/Action, cross-engine execution.
- Scenario-aware EvidenceGraph, closed head, bundle capture, replay or durable
  Scenario persistence.

## 5. Rejected alternatives

### Reuse `FactOverlay` as the public contract

Rejected: it requires caller-supplied assertion identity and old tuple, has a
separate before/after capability shape, and would make a low-level storage
operation the public premise language.

### Treat an F4 bundle as the Scenario base snapshot

Rejected: Q6B §2.3 explicitly limits it to the captured post-projection
evaluator relation; it cannot restore prior single-cardinality state after a
future Scenario deletion or decide missing/add semantics.

### Expose normal live Explain or capture for hypothetical rows

Rejected: both would currently use/describe ledger-backed provenance as if it
supported the substituted value.

## 6. Acceptance criteria

- [x] Direct existing-field substitution is schema-checked, deterministic and
  uses the normal materialized Query evaluator for both baseline/effective
  relations.
- [x] All unsupported target/profile shapes fail before native execution.
- [x] Ledger contents remain byte-for-byte/read-only unchanged; Scenario
  support is not persisted to the support sidecar or candidate index.
- [x] Same/different values, missing/ambiguous targets, type mismatch,
  irrelevant predicates and concurrent-view changes have focused tests.
- [x] Scenario `close()`, `explain()` and `capture=` are explicitly rejected;
  ordinary Query/F4 behavior stays unchanged.

## 7. Decision record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-13 | proposed | Existing evaluator/overlay/bundle seams audited | The audit found one safe injection point and rejected FactOverlay/bundle promotion. |
| 2026-08-13 | adopted | User authorized autonomous completion of F5 | Adoption is limited to this replacement-only F5A contract, not to general Scenario semantics. |
| 2026-08-13 | implemented | F5A acceptance completed and independently re-reviewed | The final implementation retains the narrow replacement-only boundary; it does not authorize a general Scenario/What-if contract. |
