# Q8 Decision: Unified EvaluationQuery target v1

- Status: adopted
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: design constraint for the F5-Core unified Query target slice only.
- Inputs:
  - 2026-08-13 user authorization to execute the FactGraph F5-Core implementation autonomously on a new isolated branch
  - [`2026-08-12_q4b-managed-policy-v0-decision.md`](./2026-08-12_q4b-managed-policy-v0-decision.md)
  - [`2026-08-12_q5a-evaluation-query-projection-v0-decision.md`](./2026-08-12_q5a-evaluation-query-projection-v0-decision.md)
  - [`2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md`](./2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md)
  - [`2026-08-13_q7-scenario-field-substitution-v0-decision.md`](./2026-08-13_q7-scenario-field-substitution-v0-decision.md)
- Outputs / Downstream:
  - [`2026-08-13_factgraph-f5-core-unified-query.md`](../../../blueprints/active/2026-08-13_factgraph-f5-core-unified-query.md)
- Branch: `codex/v0.3.0-f5-core-unified-query-2026-08-13`
- Base: `fd8a2494`
- Depends on: Q4B / Q5A / Q5B / Q6A / Q6B / Q7

## 1. Problem

FactGraph can already execute a compiled, Policy-owned `EvaluationQuery`, but
the caller must separately construct a `SemanticAddressSpace`, compile a
Policy, build an `EvaluationQuery`, then invoke `fg.eval.evaluate(...)`.
That makes a semantically resolved Rule appear unlike a Policy at the point
where a caller asks a question, even though both are intended reusable Query
targets.

The design direction is not to erase their difference: a Rule is a reusable
component and a Policy is a business-condition composition. The common layer
is the *runtime query target*: both must reach the same exact compiled Policy,
typed direct-port bind/select compiler, native evaluator, Run anchor, and
Policy-aware evidence projection.

## 2. Scope

This decision admits a native, in-process convenience surface:

```python
compiled = (
    fg.query(resolved_rule_or_policy, address_space=...)
      .bind(SemanticPortAddress(...), value)
      .select("alias", SemanticPortAddress(...))
      .compile()
)
result = fg.eval.evaluate(compiled, engine="native")
```

`ResolvedRuleBundle` is lifted deterministically to the one-occurrence Policy
`__factgraph_rule_lift__:<rule-id>` using alias `target`. A `Policy` remains
direct but must be accompanied by its exact `SemanticAddressSpace`. The
builder delegates to the existing `EvaluationQuery` compiler and does not
create a second evaluator or result model.

## 3. Non-scope

- Bare Rules without a resolved semantic-port contract; string IDs, registries,
  Packages, policy discovery, wire codecs, HTTP/MCP, Meander and Agent APIs.
- `expect`, query completeness, limits, pagination, empty-select `exists`, or
  interpreting zero rows as false.
- Compare/navigation/negation expansion of Policy grammar; source authority,
  premise filtering, multi-premise Scenario algebra, Policy overlays.
- Scenario EvidenceGraph, Scenario Run anchors/bundles/replay, external
  Operators, non-native engines/config, Actions or Decide.
- Renaming or reinterpreting the older SDK `Query` / application
  `QueryRuntimeRequest` surfaces.

## 4. Decision

### 4.1 Target normalization is typed and local

`fg.query(...)` accepts only a `ResolvedRuleBundle`, a managed `Policy` plus
`address_space=`, or a previously resolved internal target value. It rejects
a bare application Rule because port names alone do not prove their Ontology
endpoint, type, or schema binding. It rejects a Policy without the exact
address space for the same reason.

Rule lift is deterministic and sealed by the existing compiled-Policy digest:
one alias `target`, one matching Rule pin, the original Rule id/version, and
the reserved normalized Policy id. A direct Policy retains its own id/version.
No ambient catalog or policy lookup is introduced.

### 4.2 One compiler/evaluator/result path

The builder accumulates structured `SemanticPortAddress` binds and ordered
selections, then produces a small wrapper around the existing
`CompiledEvaluationQueryV0`. Its underlying compiled artifact remains the
sole lowering and execution authority. `fg.eval.evaluate(...)` unwraps it and
uses the current native path; `EvaluateResult`, rows, live Explain, optional
ordinary bundle capture, detached verification, and Policy projection remain
their existing contracts.

For a Rule lift, the Run anchor must faithfully expose
`original_target_kind="rule"` / `normalization_kind="rule_lift_v0"`; a direct
Policy exposes the existing direct-Policy form. This uses the already-defined
`EvaluationRunTargetV0` variants rather than inferring identity from generated
aliases.

### 4.3 Scenario is a request option, not evidence reuse

The new builder may forward the already-adopted
`ScenarioFieldSubstitutionV0` to exactly the existing Query execution path.
That preserves its narrow replacement-only semantics. A Scenario result must
continue to reject `capture`, live `close()`, live Explain, Run anchors and
bundles; those existing evidence forms represent ledger witnesses and cannot
truthfully represent a hypothetical source.

## 5. Rejected Alternatives

### Expose a bare Rule as a Query target

Rejected because it has no semantic-port contract and would make `bind` /
`select` names ambiguous or schema-untyped.

### Make Rule and Policy the same authored object

Rejected because it collapses reusable logical components into business
composition. They meet only at the resolved Query-target layer.

### Add `expect` or `exists` while adding the builder

Rejected because the present zero-row summary is explicitly
`not_asserted`/`unknown` completeness. An API that says passed/failed would
claim stronger search and completeness semantics than FactGraph has captured.

### Reuse ordinary F4 evidence/replay for Scenario

Rejected because F4 receipts and sources identify asserted ledger facts.
Attaching them to a synthetic Scenario witness would produce false provenance.

## 6. Supporting Evidence

- Q4B limits managed Policy v0 to typed occurrences, `All`/`Any`/`Unify`, and
  direct semantic ports; it excludes navigation and broad grammar.
- Q5A/Q5B establish the exact compiled `EvaluationQuery` → native
  `EvaluateResult` path and deliberately exclude `expect`/completeness.
- `EvaluationRunTargetV0` already defines validated `rule_lift_v0` and
  `policy_direct_v0` target identities.
- Q7 and `EvaluateResult` forbid Scenario anchor/bundle/support reuse.

## 7. Consequences

- The first public unified Query surface is ergonomic but remains explicitly
  in-process/native and typed.
- Rule lift exercises the existing Policy structure/lineage and F4 evidence
  machinery without changing their semantics.
- A later Query-contract decision must separately define modes, expectation,
  completeness and field navigation before they become public methods.
- Scenario provenance/replay and Meander L3 remain separate slices.

## 8. Acceptance Criteria

- [ ] A resolved Rule and a Policy both compile through `fg.query(...)` into
  the existing `CompiledEvaluationQueryV0` execution substrate.
- [ ] Rule-lift anchor identity is exact and direct-Policy identity is unchanged.
- [ ] Typed bind/select, branch-total validation, ordinary capture/evidence and
  current live Explain behavior remain intact.
- [ ] The builder can forward only the existing narrow Scenario request, whose
  no-anchor/no-bundle/no-ledger-evidence boundary remains intact.
- [ ] Bare Rules, missing Policy address spaces, string lookup, dotted paths,
  modes/expect and non-native/config expansion are not silently accepted.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-13 | adopted | User authorized autonomous F5-Core implementation | Scope is narrowed to resolved target normalization and the already shipped Query evaluator; it does not adopt the broader candidate Query/Scenario design. |
