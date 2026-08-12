# Task Blueprint: FactGraph semantic-port foundation lite

- Status: implemented
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
- Persisted/untrusted contract verification, codec, registry, service wire,
  replay, or schema-evolution compatibility.
- SDK `endpoint=Person` sugar.
- Policy, Query, Plan, Evaluate/Explain integration, Meander, or UI.
- Relationship endpoints, entity-reference field targets, derived/intermediate
  endpoints, automatic inference, and partial managed-port coverage.

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

The two endpoint DTOs are `EntityIdentityEndpoint(entity_type)` and
`FieldEndpoint(FieldPath)`. Identity requires a top-level unary exists witness;
scalar fields require a top-level binary field witness with the declared Var in
value position. Predicate ids come from existing `SchemaIndex` lookups.

The contract copies and freezes its port map. Its caller-inaccessible digest is
computed from a typed versioned payload containing the exact Rule identity and
content digest, cached schema digest, sorted logical names, complete Var
name/origin, and typed endpoint kind/coordinates.

## 6. Boundaries And Invariants

- Keys exactly equal `Rule.ports`; Vars equal the corresponding Rule Vars.
- Endpoint/type lookup uses existing `SchemaIndex` APIs.
- Only a top-level positive exact-arity predicate can witness a binding.
- Two distinct Vars targeting one endpoint stay distinct and do not auto-join.
- Entity-reference fields and unknown endpoint types fail closed.
- All managed ports must use a supported endpoint; unsupported intermediate or
  computed public ports reject the complete contract rather than become partial.
- The contract is trusted in-process only; the SchemaIndex digest is a cached
  pin, not a snapshot or proof of revalidated mutable state.
- New production implementation target: 350–420 lines; 450 is a hard review
  boundary requiring an explicit decision amendment. The denominator is added
  lines relative to `ca962dba` under `src/factgraph/application/**/*.py`,
  including exports; deletions do not offset additions and tests/docs do not count.

## 7. Acceptance

- [x] Happy path covers entity identity and scalar field bindings.
- [x] Coverage, Var, endpoint, type, and witness failures are tested.
- [x] Same-endpoint/different-Var behavior is tested.
- [x] Same-Var/conflicting-endpoint behavior is rejected using Var value equality.
- [x] Contract digest is order-stable and changes with Rule/schema/endpoint.
- [x] Contract copy/freeze survives mutation of the input mapping.
- [x] Lightweight Rule drift detection is tested.
- [x] Same-endpoint resolution leaves Rule body/digest and both Vars unchanged.
- [x] Legacy Rule digest, focused RuleExpr/evaluate compatibility, and an
      existing evaluate→row→`row.explain()` regression pass.
- [x] Production addition stays within the Q3A budget.
- [x] Application module docs state current behavior and deferred boundaries.

## 8. Implementation Plan

1. Add minimal protocol values and whole-contract digest.
2. Add trusted in-process resolver, one-map builder, and Rule-staleness check.
3. Add the minimum acceptance matrix and legacy compatibility regression.
4. Update application Rule/module docs and exports.
5. Run focused tests, the existing RuleStructure evaluate/row/explain path,
   Ruff, mypy, and the existing full suite; independently review semantic
   correctness and line-budget compliance.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/application/docs/README.md`

## 10. Outcome / Deviations

- Final implementation: `490ab2bd` adds two small production modules, two
  export edits, one focused test file, and current-truth application docs.
- Production denominator: 403 added Python lines (178 protocol + 195 runtime +
  18 protocol exports + 12 application exports), under the 450 cap. The full
  defensive reference remains unchanged at `9487b930`.
- Verification: focused semantic/RuleExpr/lowering/Explain chain is 91 passed
  plus 8 subtests; Ruff passed; targeted mypy passed for both new source files.
  Full `tests/` is 2,897 passed / 32 skipped / 1 failure. The sole failure is
  the pre-existing `service.static_ui` import of absent
  `render_evidence_graph_html`, independently reproduced by the full candidate.
- Two independent final reviews returned CLEAR with zero P0/P1. No Policy,
  Query, SDK sugar, persistence, schema reconstruction, or untrusted verifier
  was introduced.
- Deviation: the preflight remained an independent commit (`1e6e16e7`) rather
  than being merged into the implementation lineage; all findings and actions
  are durably summarized in the paired audit.
- Archive intent: move this blueprint and audit pair together after closure.
