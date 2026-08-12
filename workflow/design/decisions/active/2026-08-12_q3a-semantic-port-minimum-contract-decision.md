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
  - [`2026-08-12_factgraph-semantic-port-foundation-lite.md`](../../../blueprints/archive/2026-08-12_factgraph-semantic-port-foundation-lite.md)
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

The exact protocol values are:

```text
EntityIdentityEndpoint(entity_type: str)
FieldEndpoint(path: FieldPath)
```

`FieldPath` is the existing application protocol coordinate. Future SDK
classes and descriptors must lower to these values before entering this layer.

### 4.3 Resolve only what semantic binding needs

The resolver trusts an in-process `SchemaIndex` constructed by
`build_schema_index`. It checks:

- semantic keys exactly cover `Rule.ports`;
- each declared Var equals the corresponding Rule Var;
- one Var does not claim conflicting endpoints;
- an endpoint exists and agrees with the Rule port execution type;
- entity identity is witnessed only by a top-level direct
  `PredAtom(entity.exists_predicate_id, [var])`;
- a scalar field is witnessed only by a top-level direct
  `PredAtom(field.pred_id, [owner, var])`, with the port Var in value position;
- entity-reference fields and unknown endpoint kinds fail explicitly.

Negative subtrees and aggregate filters cannot act as a positive witness. The
predicate ids come from `SchemaIndex`; the resolver does not audit unrelated
predicates, inspect raw Schema IR, or reconstruct the index. Var matching uses
the shipped `Var` value semantics, not Python object identity.

### 4.4 Keep one conservative contract identity

Resolution returns an immutable contract containing exact Rule id/version and
content digest, the trusted `SchemaIndex` cached schema digest, and copied-then-
frozen authored ports using the Rule-owned Vars. The caller cannot supply the
derived digest.

One typed canonical digest payload contains a format/version tag, Rule
id/version/content digest, schema digest, and ports sorted by logical name. Each
port contributes the complete Var name/origin plus an endpoint `kind` and its
typed entity/field coordinates. The digest never hashes `repr` or an ambiguous
display path as the endpoint identity.

Any schema digest change invalidates the contract, including unrelated additive
changes. This conservative false invalidation is accepted until a real registry
or cache demonstrates the need for endpoint-local compatibility.

### 4.5 Limit the trust claim

The contract is an in-process resolved value, not an authorization credential.
A lightweight check detects subsequent Rule id/version/content/port drift.
Persisted, decoded, or external contracts are unsupported until a later
persistence boundary defines provenance and canonical re-verification.

### 4.6 Managed Rules are a closed subset

Every port of a managed Rule must resolve to an entity identity or supported
scalar field. A legacy Rule with an aggregate, computed, or intermediate public
port remains executable but cannot receive this managed contract. F1-lite does
not add `DerivedEndpoint`, partial coverage, or automatic endpoint inference.

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

- [x] Three-coordinate binding and exact coverage are enforced.
- [x] Endpoint/type/positive-position mismatches fail with typed errors.
- [x] Same endpoint does not merge Vars or create joins.
- [x] One stable whole-contract digest binds Rule, schema, and endpoints.
- [x] Contract ports are copied then frozen and input-map mutation cannot alter
      the contract or derived digest.
- [x] Shipped Rule behavior and digest bytes remain unchanged.
- [x] A focused existing evaluate-to-row-to-Explain path remains green.
- [x] Relative to `ca962dba`, added lines under
      `src/factgraph/application/**/*.py` (including export edits, excluding
      tests/docs, with deletions not offsetting additions) remain at or below
      450 unless this decision is explicitly amended.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | Minimum contract extracted | Full candidate retained as a defensive reference. |
| 2026-08-12 | adopted | User approved F1-lite | Authorized an isolated subtractive implementation before Policy work. |
| 2026-08-12 | adopted | Preflight amendments applied | PF-R1..R5 and PF-Rec1..Rec3 from independent preflight `1e6e16e7` narrowed executable semantics and the size denominator. |
| 2026-08-12 | adopted | Contract implemented | `490ab2bd` implements the minimum contract in 403 production added lines; two independent reviews returned CLEAR. |
