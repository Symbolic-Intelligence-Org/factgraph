# Q22 Decision: operator-sensitive Policy literal domains

- Status: adopted
- Created: 2026-08-20
- Last Updated: 2026-08-20
- Authority: adopted design constraint implemented by the 2026-08-20 Policy-literal equality-domain slice.
- Inputs:
  - [Policy literal equality-domain audit](../../../audit/active/2026-08-20_policy-literal-equality-domain-vs-shipped.md)
  - [Q19 Policy authoring SDK and literal comparison](2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md) §2.3
  - the user's 2026-08-20 domain-by-operator disposition
- Outputs / Downstream:
  - [implemented equality-domain blueprint](../../../blueprints/active/2026-08-20_policy-literal-equality-domains.md)
- Related:
  - [Q12 Policy comparison and field navigation](2026-08-13_q12-policy-comparison-field-navigation-v0-decision.md)
  - [Rules quickstart capability matrix](../../../../docs/quickstart/rules.md#policy-topology-capability-matrix)
- Branch: `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`
- Depends on: Q19's typed, canonical and sealed `PolicyLiteral` contract

> Q19 remains the historical int/time envelope. Q22 is the later
> operator-sensitive decision anticipated by Q19 §2.3 and is now implemented
> across protocol, SDK authoring, compiler admission, serialization views and
> the portable three-engine profile.

## 1. Scope

This decision separates equality portability from ordering portability for a
literal compared with a typed Policy endpoint. It locks the admissible domain
matrix and the minimum integrity obligations for a future additive change.

## 2. Non-scope

- No widening beyond the implemented domain/operator matrix below.
- No float64 equality or ordering semantics.
- No UUID or bytes literal decision.
- No relationship/multi-hop navigation, implicit coercion or literal-to-literal
  Policy comparison.
- No weakening of branch-total constraints, Policy lineage, replay or Explain
  seals.

## 3. Decision

### 3.1 Domain-by-operator matrix

| Literal domain | `eq` / `ne` | `gt` / `ge` / `lt` / `le` | Decision |
|---|---|---|---|
| `int` / `time` | admit | admit | Preserve shipped behavior. |
| `string` | admit | reject | Equality has portable identity semantics; ordering would require a collation contract. |
| `bool` | admit | reject | Equality is meaningful; Policy defines no bool ordering. |
| `entity_ref` | admit in a bounded, lower-priority implementation | reject | A specific-entity equality is valid, but needs an explicit canonical reference operand and endpoint path. |
| `float64` | reject | reject | Float values remain outside logical identity; changing that requires a separate engine-level decision. |

UUID and bytes remain rejected because this decision does not define their
canonical Policy-literal semantics.

### 3.2 Admission must be operator-sensitive

The SDK may not use one domain set for all comparison operators. Equality and
inequality admit the domains in §3.1; ordering remains limited to int/time.
Compiler admission must still require exact operand-domain agreement.

### 3.3 Entity references are not scalar by assertion

The implementation must define an explicit canonical entity-reference value
and endpoint-resolution route. It may not obtain support by labelling an
`EntityIdentityEndpoint` as an ordinary scalar field. Existing `same()` and
Query `bind()` remain the preferred forms when they express the intended
question.

### 3.4 Float exclusion is intentional

Float64 is not classified as unfinished authoring work. The project keeps
floating probability/materialization boundaries explicit and does not make
binary float equality part of Policy logical identity as a side effect of this
slice.

## 4. Supporting evidence

- `PolicyLiteral` in `application/protocol/policy.py` describes its current
  domain set in terms of shared ordering domains.
- `_PolicyScalarHandle._compare` in `sdk/policy_authoring.py` applies that set
  before distinguishing the operator.
- `_resolve_compare` in `application/policy_runtime.py` already checks exact
  domain agreement for every operator and applies `_ORDERING_DOMAINS` only to
  ordering.
- Native, Souffle and ProbLog Rule lowering already have distinct equality and
  ordering paths; the audit records the required Policy-path parity proof.

## 5. Consequences

The implementation adds canonical validation, preserves existing int/time
Policy identity construction, retains literals through replay/bundle/Product
V2 views, and proves real Native/Souffle/ProbLog equality parity. Float64,
UUID and bytes still require separate decisions.

## 6. Acceptance criteria

- [x] String and bool `eq` / `ne` literals have canonical protocol values and
      matching SDK authoring support.
- [x] Their ordering forms fail before engine execution with stable typed codes.
- [x] Entity-reference support uses an explicit reference
      operand/endpoint contract and does not weaken `same()` or `bind()`.
- [x] Existing int/time identity construction and digests are unchanged.
- [x] Float64, UUID and bytes remain rejected.
- [x] Native, Souffle and ProbLog Policy-path parity and replay/Explain tamper
      tests are green.

## 7. Decision record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-20 | adopted | Equality and ordering domains separated | User adopted string/bool equality, lower-priority entity-reference equality, and intentional float64 exclusion; implementation remains a later blueprint. |
| 2026-08-20 | implemented | Bounded Q22 slice verified | String/bool/entity-ref equality shipped; ordering remains int/time; float64/UUID/bytes remain rejected; real portable parity and codec/view coverage are green. |
