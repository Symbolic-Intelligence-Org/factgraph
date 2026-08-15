# Q16 Decision: query-scoped EffectiveSnapshot v1

- Status: adopted
- Created: 2026-08-13
- Authority: the user's 2026-08-13 authorization for project-level continuous
  FactGraph delivery, bounded by the existing Query/F4 and Q7/Q11 contracts.
- Inputs:
  - Q7/Q11 replacement-only Scenario implementation and its current protocol
    tests.
  - P2 read-only contract and adversarial reviews recorded in the paired
    program audit.
- Outputs / Downstream:
  - [FactGraph Query/Scenario program](../../../blueprints/archive/2026-08-13_factgraph-query-scenario-program.md)
- Depends on: Q7, Q11, Q13 and Q14.

## 1. Scope

Add a parallel, pre-evaluation identity for the relation that a currently
admissible replacement-only Scenario will evaluate.  The identity is called
`QueryEffectiveSnapshotV1` because it identifies the exact effective relation
for one Query; it is not a global ledger snapshot, a historical snapshot, or a
truth/authority assertion.

## 2. Decision

### 2.1 Query-dependency scope

The resolver recomputes the dependency predicates from the trusted materialized
Query body.  It copies exactly that relation, including explicit empty
relations. It separately captures only the active-identity memberships required
by the submitted Scenario, then uses the private full projected view to copy
that exact relation and establish existing-entity visibility.
`base_view_digest` remains a live-view TOCTOU guard; it does not expand the
snapshot's relation scope.

### 2.2 Parallel v1 identity

`QueryEffectiveSnapshotV1` seals:

- Query, Policy, address-space, schema and base-view pins;
- canonical dependency predicate ids;
- baseline and effective relation digests;
- canonical, existing-visible scalar replacement operations; and
- the narrow normalization profile that minted the synthetic witness.

It does **not** seal a result diff.  A private resolver result carries the
immutable baseline/effective relation alongside that public identity; execution
must continue to verify the live view after resolution and between evaluations.

### 2.3 Compatibility adapter

The existing Q7 single and Q11 set resolvers become adapters over the v1
normalizer.  They retain their existing public DTOs, `scenario_digest`
formulae, relation-digest domain, synthetic witness prefixes, `origin_kind`,
`EvaluateResult.scenario` type, `ScenarioRunV0` wire and result behavior.
In particular, Q7/Q11 still include `result_diff` in their legacy
`scenario_digest`; they cannot be retroactively redefined as pre-evaluation
identities.

## 3. Non-scope

- No generic premise/claim DSL, source admission, authority, closure or
  absence semantics.
- No insert/delete/mask, relationship, new-entity, Policy/rule overlay, or
  field-navigation premise l-value.
- No Scenario plus expectation/capture combination, cross-engine profile,
  external Operator, Action, Meander or Agent surface.
- No public durable codec or historical replay claim for the new identity.

## 4. Consequences

This creates one stable pre-evaluation seam from which a future explicit
Scenario plan can grow without binding its identity to observed rows.  It does
not authorize that future plan or broaden today's replacement-only semantics.

## 5. Acceptance Criteria

- [x] Snapshot identity has no result-diff dependency and validates its
  dependency relation, operation inventory and relation pins fail-closed.
- [x] Q7/Q11 public values and ScenarioRun behavior retain their old identity
  and witness profiles.
- [x] Same-value, permutation, missing/multi/non-dependency and live-view
  mutation cases retain their bounded failure semantics.
- [x] Application docs state the precise non-global, non-historical boundary.

## 6. Decision Record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | adopted | P2 boundary frozen | Continuous-delivery authorization permits this conservative internal foundation without a separate user pause. |
| 2026-08-13 | implemented | P2 accepted | The sealed identity is pre-evaluation only; Q7/Q11 remain compatibility outputs. Final verification passed 588 application/SDK tests plus 172 subtests, targeted static checks and independent adversarial review. |
