# Task Blueprint: FactGraph semantic-port foundation lite

- Status: draft
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for the F1-lite integration branch.
- Inputs:
  - [`2026-08-12_q3a-semantic-port-minimum-contract-decision.md`](../../design/decisions/active/2026-08-12_q3a-semantic-port-minimum-contract-decision.md)
  - Full defensive reference `codex/v0.3.0-f1-semantic-ports-2026-08-12@9487b930`
- Outputs / Downstream:
  - Application semantic-port implementation, focused tests, and module docs
- Related:
  - [`2026-08-12_factgraph-semantic-port-foundation-lite.audit.md`](./2026-08-12_factgraph-semantic-port-foundation-lite.audit.md)
- Related Modules:
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/`
- Related Docs:
  - `src/factgraph/application/docs/rule.md`
- Audit Log:
  - [`2026-08-12_factgraph-semantic-port-foundation-lite.audit.md`](./2026-08-12_factgraph-semantic-port-foundation-lite.audit.md)
- Branch: `codex/v0.3.0-f1-lite-semantic-ports-2026-08-12`
- Base: `ca962dba`

## 1. Problem

Rule ports need explicit Ontology meaning before Policy can address them. The
first candidate proved the shape but combined it with future trust-boundary and
schema-integrity machinery. This slice implements only the minimum semantic
binding needed to test the next product layer.

## 2. Goals

- Add entity-identity and scalar-field endpoint DTOs.
- Bind each logical port to its exact Rule Var and endpoint.
- Resolve complete bindings through the existing trusted `SchemaIndex`.
- Return an ordinary Rule plus a frozen, whole-schema-pinned contract.
- Preserve legacy Rule/RuleExpr/evaluate/Explain behavior.

## 3. Non-goals

- Schema deep-copy/rebuild or raw Schema IR revalidation.
- Recursive validation of unrelated Rule AST predicates.
- Endpoint-local compatibility digests.
- Persisted/untrusted contract verification, codec, registry, or service wire.
- SDK `endpoint=Person` sugar.
- Policy, Query, Plan, Evaluate/Explain integration, Meander, or UI.

## 4. Current Context

- `Rule.ports` is `Mapping[str, Var]` and remains unchanged.
- `SchemaIndex` already owns entity, field, cardinality, type, and schema digest
  lookup for trusted in-process runtime use.
- The full candidate remains untouched at `9487b930` as threat inventory, not
  as an implementation ancestor or correctness oracle.

## 5. Proposed Shape

```text
SemanticRulePort(var, endpoint)
             + mapping key
                    |
                    v
resolve_rule_contract(rule, ports, schema_index)
                    |
                    v
ResolvedRuleContract(rule digest + schema digest + frozen ports + one digest)
```

`build_resolved_rule(...)` accepts the complete semantic map once and returns a
bundle containing the unchanged application `Rule` and its resolved contract.

## 6. Boundaries And Invariants

- Keys exactly equal `Rule.ports`; Vars equal the corresponding Rule Vars.
- Endpoint/type lookup uses existing `SchemaIndex` APIs.
- Only a top-level positive exact-arity predicate can witness a binding.
- Two distinct Vars targeting one endpoint stay distinct and do not auto-join.
- Entity-reference fields and unknown endpoint types fail closed.
- The contract is trusted in-process only; no provenance claim is made.
- New production implementation target: 350–420 lines; 450 is a hard review
  boundary requiring an explicit decision amendment.

## 7. Acceptance

- [ ] Happy path covers entity identity and scalar field bindings.
- [ ] Coverage, Var, endpoint, type, and witness failures are tested.
- [ ] Same-endpoint/different-Var behavior is tested.
- [ ] Contract digest is order-stable and changes with Rule/schema/endpoint.
- [ ] Lightweight Rule drift detection is tested.
- [ ] Legacy Rule digest and focused RuleExpr/evaluate compatibility pass.
- [ ] Production addition stays within the Q3A budget.
- [ ] Application module docs state current behavior and deferred boundaries.

## 8. Implementation Plan

1. Add minimal protocol values and whole-contract digest.
2. Add trusted in-process resolver, one-map builder, and Rule-staleness check.
3. Add the minimum acceptance matrix and legacy compatibility regression.
4. Update application Rule/module docs and exports.
5. Run focused tests, Ruff, mypy, and the existing full suite; independently
   review semantic correctness and line-budget compliance.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/application/docs/README.md`

## 10. Outcome / Deviations

To be completed after implementation.
