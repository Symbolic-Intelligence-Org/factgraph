# Q11 Decision: Scenario field substitution set v0

- Status: adopted
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: narrow implementation constraint for F5B2; extends Q7 only with
  an atomic set of direct substitutions, not a general Scenario or What-if
  algebra.
- Inputs:
  - User instruction to complete F5B1, M0, and F5B2 in sequence (2026-08-13)
  - [`2026-08-13_q7-scenario-field-substitution-v0-decision.md`](./2026-08-13_q7-scenario-field-substitution-v0-decision.md)
  - [`2026-08-13_q9-query-contains-expectation-v0-decision.md`](./2026-08-13_q9-query-contains-expectation-v0-decision.md)
  - F5A shipped protocol/runtime and F5B1 rejection contract
- Outputs / Downstream:
  - [`2026-08-13_factgraph-f5b2-scenario-substitution-set.md`](../../../blueprints/active/2026-08-13_factgraph-f5b2-scenario-substitution-set.md)
- Branch: `codex/v0.3.0-f5b2-scenario-substitution-set-2026-08-13`
- Depends on: Q7, Q9

> ADR 4-state lifecycle: `proposed` → `adopted` (current binding constraint)
> → `superseded` or `withdrawn`.  This decision does not reopen Q7.

## 1. Problem

Q7 safely replaces one already-visible scalar field, but a real bounded
counterfactual often changes more than one independent visible field.  Calling
Q7 repeatedly would produce unrelated baselines and permit order-dependent
partial application.  The next smallest useful capability is one atomic set
over a single captured dependency relation.

## 2. Scope

Lock `ScenarioFieldSubstitutionSetV0(substitutions=(...))` as an optional
`scenario=` input for the existing trusted compiled Query path.  Each member
uses the exact Q7 direct field replacement contract; the set is resolved
atomically before either native evaluator call.

## 3. Non-scope

- General ScenarioPlan, add/delete/mask, absence/negation, relationship or
  multi-valued fields, new entities, historical/as-of behavior, rule or Policy
  overlay, source authority, and Agent/Meander wire formats.
- Combining Q9 expectation with any Scenario, including this set.
- F4 anchor/bundle, live `close()`/`explain()`, replay, persistence, external
  operators, non-native engines, config or premise filters.

## 4. Decision

### 4.1 Set admission and canonical identity

- A set is an immutable tuple of at least two Q7
  `ScenarioFieldSubstitutionV0` inputs. The old single-substitution object
  remains supported unchanged.
- Every `premise_id` must be unique.  Every schema-canonical `(entity_ref,
  predicate)` target must be unique, even if its requested replacement value
  is equal.  A duplicate rejects the *whole* request before evaluation.
- Input order is not semantic: resolution canonicalizes operations by a stable
  trusted target key.  The set scenario digest commits the canonical operation
  set, base view and baseline/effective relation digests.  It is integrity
  metadata, not authentication.

### 4.2 Atomic resolution and execution

- Project the dependency-complete baseline relation exactly once, resolve all
  members against it, then make one immutable effective relation containing all
  replacements.  No ledger, support or candidate state changes.
- Any invalid member (unsupported field, type mismatch, inactive/missing or
  ambiguous target, non-dependency predicate, duplicate) aborts before the
  evaluator.  A baseline view change aborts before effective evaluation.
- The same materialized native evaluator runs exactly twice: once against the
  one baseline relation and once against the complete effective relation.
- Result metadata preserves per-operation baseline/effective values and exposes
  one set-level result diff.  It never claims historical truth or general
  premise provenance.

### 4.3 Compatibility boundary

`EvaluateResult.scenario` accepts either Q7's `ScenarioResolutionV0` or the
new set resolution.  Their validation is parallel rather than mutating the
old Q7 digest formulas.  Both keep the existing no-anchor/no-bundle/no-live
ledger-evidence behavior.  F5B1's Scenario-plus-expectation rejection remains
strictly unchanged.

## 5. Rejected Alternatives

### Repeated single substitutions

- **Why rejected**: each call has a different baseline and cannot represent a
  single atomic hypothetical state.

### General premise collection

- **Why rejected**: it would implicitly decide add/delete/absence, conflicts,
  source authority and rule overlay semantics that remain unmodeled.

### Mutate Q7 resolution and digest in place

- **Why rejected**: it would silently change an implemented v0 contract and
  weaken independent old-result validation.

## 6. Supporting Evidence

- Q7 §3.1–3.3 and §4 define the existing safe direct-replacement boundary.
- Q9 §3 explicitly rejects Scenario-plus-expectation until a joint artifact
  contract exists.
- F5A resolver `src/factgraph/application/evaluation_scenario_runtime.py`
  projects the relation and invokes the private evaluator twice; F5B2 reuses
  that seam without a new evaluator.
- `src/factgraph/sdk/store.py` already rejects Scenario capture, non-native
  config and premise-filter profiles at the compiled Query entry point.

## 7. Consequences

### 7.1 Downstream unblocking

The product can express a bounded multi-field counterfactual through the same
Query evaluator without pretending that all What-if forms are now solved.

### 7.2 Required follow-up actions

F5B2 must test atomic admission, permutation invariance, duplicates, type and
dependency rejection, evaluator cardinality, no-side-effect behavior and Q7/
Q9 regression boundaries.  Any broader overlay or explanation remains a new
decision.

## 8. Acceptance Criteria

- [ ] Multiple valid substitutions execute as one atomic baseline/effective
  pair and expose canonical set-level metadata.
- [ ] Invalid or duplicate members fail before evaluator entry and cannot leave
  a partial effective relation.
- [ ] Q7 inputs/results remain byte-contract compatible; F5B1 expectations,
  F4 artifacts and Scenario evidence limits remain rejected/unchanged.
- [ ] Focused protocol, runtime, SDK and cross-slice regression tests pass.

## 9. Decision Record

| Date | Stage | Event | Notes |
| --- | --- | --- |
| 2026-08-13 | adopted | User-authorized F5B2 implementation consumes Q11 | Atomic direct-field set selected instead of general What-if algebra. |
