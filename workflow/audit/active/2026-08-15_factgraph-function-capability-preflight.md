# Preflight: FactGraph first-class Function capability

- Status: complete
- Created: 2026-08-15
- Authority: implementation preflight for the Q21 scoped blueprint.
- Inputs:
  - [Q21 decision](../../design/decisions/active/2026-08-15_q21-function-capability-boundary-decision.md)
  - [Q21 blueprint](../../blueprints/active/2026-08-15_factgraph-function-capability.md)
- Branch: `codex/v0.3.0-impl-factgraph-product-interface-2026-08-14`

## Findings

| ID | Severity | Finding | Blueprint disposition |
| --- | --- | --- | --- |
| PF-1 | Required amendment before scoped | Existing `SemanticEndpoint` is schema-Rule-only, so a Function output cannot be safely selected through the current address space. | Product Function ports receive a distinct typed occurrence/address contract and controlled V2 lowering; Rule contracts are not widened as public semantics. |
| PF-2 | Required amendment before scoped | Existing Query target compilation happens before V2 planning; a sidecar-only Function marker could be stripped and evaluated incorrectly. | Function occurrence is intrinsic in the authored AST; legacy/V1 resolvers reject it, and only the private V2 bridge derives a compiler skeleton. |
| PF-3 | Required amendment before scoped | Native/ProbLog/Souffle UDF mechanisms are not equivalent and portable V1 rejects generic builtin/code atoms. | One pre-engine sealed relation is canonical; native UDF registration is not used. |
| PF-4 | Required amendment before scoped | V2 replay currently captures program/world but has no Function result relation. Reinvoking a callable during replay would be nondeterministic and unsafe. | Per-side Function materializations are included in the sealed program/run capture and replay consumes them only. |
| PF-5 | Required amendment before scoped | General multi-source dependency planning would require Policy subgraph slicing, cycle analysis and branch-sensitive scheduling. | First slice requires all inputs from one branch-total Rule occurrence; broader graph scheduling is a later additive slice. |
| PF-6 | Required amendment before scoped | Product Explain currently supports fact/compare/builtin/aggregate atom forms and must not pretend a pure computation is an external Source. | Add separate structured Function-call views; EvidenceGraph form only when genuine evidence capture exists. |

## Verified assumptions

- Existing Product asset metadata/binding seals can be reused for Function
  assets without changing Rule/Policy identities.
- Existing V2 isolated Store creation can accept a derived execution-only
  schema and internal facts without mutating the source SDKStore ledger.
- Existing portable adapters can consume an ordinary finite predicate once the
  derived schema and facts are materialized consistently.

## Self-check

PF-1 through PF-6 are represented in blueprint §§5–8. The user's explicit
instruction to proceed directly with implementation and testing authorizes the
scoped implementation phase for this bounded slice.
