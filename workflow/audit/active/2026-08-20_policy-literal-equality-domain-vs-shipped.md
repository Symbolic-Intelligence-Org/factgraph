# Audit: Policy literal equality domains versus shipped runtime

- Status: complete
- Created: 2026-08-20
- Last Updated: 2026-08-20
- Authority: working triage document; informs but does not lock implementation. Implementation decisions follow only after audit-row review.
- Inputs:
  - [Q19 Policy authoring SDK and literal comparison](../../design/decisions/active/2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md) §2.2–§2.5
  - the user's 2026-08-20 operator-sensitive literal-domain disposition
  - shipped protocol, SDK authoring, compiler and engine comparison paths listed in §1
- Outputs / Downstream:
  - [Q22 Policy literal equality-domain decision](../../design/decisions/active/2026-08-20_q22-policy-literal-equality-domain-decision.md)
  - [implemented equality-domain blueprint](../../blueprints/active/2026-08-20_policy-literal-equality-domains.md)
- Related:
  - [Policy authoring SDK versus shipped runtime](../archive/2026-08-14_factgraph-policy-authoring-sdk-vs-shipped.md)
  - [Rules quickstart](../../../docs/quickstart/rules.md#policy-topology-capability-matrix)
- Source intent: separate equality portability from ordering portability without widening float semantics or misreporting current shipped support.
- Branch: `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`

## 1. Scope

Primary Policy surface:

| Layer | File | Relevant contract |
|---|---|---|
| Durable protocol | `src/factgraph/application/protocol/policy.py` | `PolicyLiteral`, `PolicyCompare`, canonical node identity and V2-only topology markers |
| SDK authoring | `src/factgraph/sdk/policy_authoring.py` | `_PolicyScalarHandle._compare` literal construction and rejection |
| Compiler | `src/factgraph/application/policy_runtime.py` | `_resolve_compare`, `_resolve_compare_operand` and `CmpAtom` lowering |
| Native equality | `src/factgraph/core/rules/where_eval.py` | `_eval_eq_atom` / `_eval_ne_atom` use value equality; ordering alone uses numeric coercion |
| Souffle lowering | `src/factgraph/adapters/souffle/where_compile.py` | ordinary `eq` / `ne` use symbol equality; ordering uses int/time conversion and guards |
| ProbLog lowering | `src/factgraph/adapters/problog/problog_export.py` | ordinary `eq` / `ne` lower to term equality/inequality |

Out of scope: implementing codecs, changing historical Policy digests, enabling
float logical identity, defining UUID/bytes literals, relationship navigation,
or changing Rule-body comparison semantics.

## 2. Shipped topology terminal table

| Form | Shipped state | Audit note |
|---|---|---|
| Nested `all` / `any` | covered | `any` is an authored logical alternative inside one Policy, not relational `UNION` or probabilistic choice. |
| `same(port, port)` | covered only inside one owning `all` subtree | Cross-arm partial constraints fail with `PARTIAL_BRANCH_CONSTRAINT`. |
| Scalar port vs scalar port | equality covered for matching scalar domains; ordering only int/time | The compiler applies `_ORDERING_DOMAINS` only to `gt/ge/lt/le`; string-port equality is therefore structurally admitted. |
| Scalar port vs literal | int/time only | The SDK rejects other domains with `POLICY_LITERAL_DOMAIN_UNSUPPORTED` before the operator is considered. |
| One-hop navigation | two distinct surfaces | Policy-owned navigation may be a compare operand; Query-owned navigation is select-only. |
| `WeightedChoice` / Product Function | V2-only | WeightedChoice is ProbLog-point-only; Function is one Rule source/no chaining/output-not-bindable; the first slices cannot coexist. |

## 3. Triage table

5-state classification follows CADENCE Stage 1.

| ID | Intent | State | Evidence / disposition |
|---|---|---|---|
| A-01 | Keep Policy topology distinct from Rule-body logic and Query projection | **(a) shipped covers** | Policy owns structural nodes and compare lineage; unsupported literal predicates can already be authored in a Rule body without changing Policy. |
| I-01 | Ordering remains portable only for canonical int/time values | **(a) shipped covers** | `_resolve_compare` and all engine ordering paths reject non-int/time domains. |
| D-01 | String/bool equality literals should not be rejected merely because their domains lack portable ordering | **(c) shape conflict** | `PolicyLiteral` and the SDK gate use one int/time domain set for every operator, although compiler and engines already distinguish equality from ordering. |
| D-02 | Entity-reference equality literal should be admissible as a bounded, lower-priority capability | **(d) genuinely new** | Current comparison operands require single scalar fields or Function values; an entity-reference codec and endpoint-resolution contract do not yet exist on this path. |
| D-03 | Prove string constant equality in Native, Souffle and ProbLog through the Policy path | **(b) small gap** | Rule-body engine support exists, but no dedicated Policy-literal parity fixture can exist until the authoring/protocol envelope is widened. |
| N-01 | Keep float64 equality outside logical identity | **(e) deferred-aligned** | The current protocol rejects float literals, ordering rejects float, and Product probability semantics use explicit decimal/float-boundary records instead. |
| N-02 | UUID and bytes remain outside this decision | **(e) deferred-aligned** | Q22 does not supply semantics or codecs for them. |

## 4. Root cause

`PolicyLiteral` states that its initial public envelope mirrors the three
engines' shared **ordering** domains, but the same type-level envelope is used
for `eq` and `ne`. `_PolicyScalarHandle._compare` then rejects a non-int/time
literal before dispatch can distinguish equality from ordering. The compiler
already has the correct operator-sensitive shape: domain equality is checked
for every comparison, while `_ORDERING_DOMAINS` is consulted only for
`gt/ge/lt/le`.

Consequently these three routes are asymmetric even though they eventually use
the same `CmpAtom` family:

1. string scalar port `eq` string scalar port is admitted;
2. a string equality constant authored in a Rule body is admitted;
3. string scalar port `eq` string `PolicyLiteral` is rejected at authoring.

For string/bool equality this is an unfinished authoring envelope, not an
engine semantic boundary. Entity-reference equality is different: it also
needs a new typed operand/endpoint contract. Float64 remains an intentional
semantic exclusion.

## 5. Operator-sensitive disposition

| Domain | `eq` / `ne` | Ordering | Classification |
|---|---|---|---|
| `int` / `time` | keep admitted | keep admitted | shipped |
| `string` | admit | keep rejected | unfinished authoring envelope |
| `bool` | admit | reject | unfinished authoring envelope |
| `entity_ref` | admit in a bounded lower-priority slice | reject | genuinely new endpoint/codec work |
| `float64` | keep rejected | keep rejected | intentional logical-identity boundary |

## 6. Required implementation shape

A consuming blueprint must:

1. widen `PolicyLiteral` additively with domain-directed canonical value
   validation, preserving every existing int/time digest;
2. make SDK admission operator-sensitive: equality accepts the approved
   domains while ordering remains int/time-only;
3. retain compiler-side exact domain matching and define the entity-reference
   endpoint/codec path explicitly rather than pretending it is scalar;
4. update every structure, lineage, replay and Explain codec that serializes a
   literal;
5. add real Native/Souffle/ProbLog Policy-path parity fixtures for string and
   bool equality, plus negative ordering and float cases.

## 7. Method notes

The 2026-08-14 archived audit and blueprint remain historical rationale and
were not rewritten. This follow-up records a new shipped-vs-intended delta.
Engine files were inspected only for their complete equality/ordering semantic
units; a future implementation preflight must re-read the full affected files
and execute the real three-engine fixtures.

## 8. Audit completeness checklist

- [x] All in-scope rows triaged
- [x] Equality and ordering boundaries separated
- [x] Entity-reference and float64 classifications kept distinct
- [x] Current manual state separated from future disposition
- [x] Implementation touchpoints and parity obligation recorded

## 9. Implementation closure

The audit remains a historical Stage 1 snapshot: §2–§6 describe the boundary
before repair. The consuming blueprint has now closed D-01, D-02 and D-03:

- `PolicyLiteral` canonically admits string, bool and entity-ref values;
- SDK and compiler gates distinguish equality from ordering;
- entity references use an explicit identity endpoint and trusted-schema
  canonicalization rather than scalar relabelling;
- replay/bundle/Product V2 views retain the new tagged literals; and
- real Native/Souffle/ProbLog `eq` and `ne` Policy-path parity is green.

N-01 and N-02 remain intentionally closed: float64, UUID and bytes are not
Policy equality literals.
