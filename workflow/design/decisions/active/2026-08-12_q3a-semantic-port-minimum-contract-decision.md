# Q3A Decision: Semantic-port minimum contract

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint; locks the minimum semantic-port contract before the integration-line F1-lite implementation.
- Inputs:
  - 2026-08-12 user approval to replace the over-expanded F1 candidate with an isolated F1-lite implementation
  - Full defensive candidate `codex/v0.3.0-f1-semantic-ports-2026-08-12@9487b930`
  - [`2026-08-11_meander-factgraph-post-probe-session.md`](../../../memory/session_handoffs/2026-08-11_meander-factgraph-post-probe-session.md)
- Outputs / Downstream:
  - [`2026-08-12_factgraph-semantic-port-foundation-lite.md`](../../../blueprints/active/2026-08-12_factgraph-semantic-port-foundation-lite.md)
- Related:
  - Branch-local full-candidate decision `8a72f235:workflow/design/decisions/active/2026-08-12_q3-semantic-port-contract-storage-decision.md`
- Branch: `codex/v0.3.0-f1-lite-semantic-ports-2026-08-12`
- Depends on: none

> The earlier Q3 exists only on the retained full-candidate branch and is not
> part of this branch's lineage. Q3A is the integration-line decision; this is
> not an ADR-state supersession of a decision absent from this lineage.

## 1. Inputs

The full F1 candidate proved that a Rule port can be bound explicitly to an
Ontology endpoint without changing shipped `Rule.ports`. It also grew to 1,333
lines across its two production modules by locally defending mutable Schema IR,
all nested Rule AST shapes, endpoint-local compatibility, persisted contracts,
and untrusted rehydration before any Policy or Query consumer exists.

The useful invariant is smaller: a managed port needs a public name, its exact
internal Rule `Var`, and a canonical Ontology endpoint. F1-lite establishes only
that invariant and the minimum identity needed by the next Policy experiment.

## 2. Scope

This decision locks the in-process semantic-port DTO, resolver, one-map Rule
builder, one whole-contract digest, and a lightweight Rule-staleness check.

## 3. Non-scope

- Policy, Query, Plan, Package, Evaluate, Explain, Meander, persistence, registry,
  service wire, codec, replay, and schema-evolution compatibility.
- SDK sugar such as `endpoint=Person` or `endpoint=Person.age`; a future SDK
  adapter may lower those values immediately to application coordinates.
- Endpoint-local digests, external-contract verification, Schema IR rebuilding,
  raw-schema closure audits, and whole-AST predicate validation.
- Relationship endpoints and entity-reference field targets.

## 4. Decision

### 4.1 Preserve the shipped Rule contract

`Rule.ports` remains `Mapping[str, Var]`; its digest, RuleExpr, lowering,
evaluation, Explain, match, SDK bridge, and service representation do not
change. A legacy Rule remains executable without semantic metadata.

### 4.2 Use an explicit three-coordinate binding

Each authored entry is:

```text
mapping key (logical port name)
+ SemanticRulePort.var (exact Rule Var)
+ SemanticRulePort.endpoint (Ontology coordinate)
```

Supported endpoints are the complete identity bundle of an entity and one
concrete scalar field. `Person.identity` and `Person.employee_id` remain
different meanings. Two distinct Vars may target the same endpoint and remain
distinct; no equality or join is inferred.

### 4.3 Resolve only what semantic binding needs

The resolver trusts an in-process `SchemaIndex` constructed by
`build_schema_index`. It checks:

- semantic keys exactly cover `Rule.ports`;
- each declared Var equals the corresponding Rule Var;
- one Var does not claim conflicting endpoints;
- an endpoint exists and agrees with the Rule port execution type;
- the exact Var has a top-level positive predicate witness in the endpoint's
  schema-defined position and arity;
- entity-reference fields and unknown endpoint kinds fail explicitly.

Negative subtrees and aggregate filters cannot act as a positive witness. The
resolver does not audit unrelated predicates or reconstruct Schema IR.

### 4.4 Keep one conservative contract identity

Resolution returns an immutable contract containing exact Rule id/version and
content digest, the whole schema digest, and frozen authored ports using the
Rule-owned Vars. One derived digest covers that complete payload.

Any schema digest change invalidates the contract, including unrelated additive
changes. This conservative false invalidation is accepted until a real registry
or cache demonstrates the need for endpoint-local compatibility.

### 4.5 Limit the trust claim

The contract is an in-process resolved value, not an authorization credential.
A lightweight check detects subsequent Rule id/version/content/port drift.
Persisted, decoded, or external contracts are unsupported until a later
persistence boundary defines provenance and canonical re-verification.

## 5. Rejected Alternatives

### Option A: Merge the full defensive candidate

- **Why rejected**: it assigns Schema, compiler, persistence, and replay duties
  to the first semantic-port slice before a downstream consumer validates them.

### Option B: Put SDK Entity classes in the protocol

- **Why rejected**: SDK classes and descriptors are process-local authoring
  objects. The application contract needs stable symbolic coordinates.

### Option C: Omit the exact internal Var

- **Why rejected**: an endpoint alone does not identify which Rule value the
  public port exposes.

## 6. Supporting Evidence

- `src/factgraph/application/protocol/rule.py`: shipped Var-valued Rule ports and
  shallow immutable Rule digest contract.
- `src/factgraph/application/schema_runtime.py`: canonical runtime entity and
  field lookup from `SchemaIndex`.
- Full candidate `176d6b9d`: reference implementation and threat inventory;
  intentionally not an integration ancestor.

## 7. Consequences

- Policy work can consume a real semantic binding without importing the full
  candidate's future infrastructure.
- SDK `endpoint=Person` remains a small follow-up adapter, not a core type.
- Persistence or remote transport must add a new trust-boundary decision rather
  than silently treating this in-process contract as authenticated.

## 8. Acceptance Criteria

- [ ] Three-coordinate binding and exact coverage are enforced.
- [ ] Endpoint/type/positive-position mismatches fail with typed errors.
- [ ] Same endpoint does not merge Vars or create joins.
- [ ] One stable whole-contract digest binds Rule, schema, and endpoints.
- [ ] Shipped Rule behavior and digest bytes remain unchanged.
- [ ] Production implementation remains within 450 new lines unless this
      decision is explicitly amended.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | Minimum contract extracted | Full candidate retained as a defensive reference. |
| 2026-08-12 | adopted | User approved F1-lite | Authorized an isolated subtractive implementation before Policy work. |
