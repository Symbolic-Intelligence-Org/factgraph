# Q12 Decision: Policy direct comparison and field navigation v0

- Status: adopted
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: the user's 2026-08-13 request to implement Policy direct comparison
  and field navigation on an isolated branch.
- Depends on: Q4A, Q4B, Q5A–Q6B, Q8–Q11.
- Branch: `codex/v0.3.0-f5c-policy-field-navigation-2026-08-13`

## 1. Problem

Q4B deliberately left Policy comparison and field navigation out of the first
Policy compiler.  The unified Query path is now able to target a direct Policy,
but an author still cannot state the natural constraint:

```python
worker1.person.age > worker2.person.age
```

The missing capability must not silently become a Query path, a string DSL, or
a compiler-generated Rule.  It must remain an authored Policy constraint with
total lowering lineage and evidence ownership.

## 2. Decision

### 2.1 Canonical authored values

The public Policy AST gains only these structured values:

```python
PolicyFieldNavigation(
    base=SemanticPortAddress("worker1", "person"),
    field=FieldPath("Person", "age"),
)

PolicyCompare(
    "gt",
    left=..., right=...,
)
```

An operand is either a direct `SemanticPortAddress` or one
`PolicyFieldNavigation`.  Dotted strings are not a canonical input form.
`PolicyCompare` is a direct `PolicyAll` child; a branch-local comparison is
therefore written inside the `PolicyAll` that owns its operands.

`eq` and `ne` canonicalize symmetric operand order.  `gt`, `ge`, `lt`, and
`le` retain operand order.

### 2.2 Strict semantic envelope

At compile time every operand must resolve against the exact
`SemanticAddressSpace` and `SchemaIndex`:

- direct addresses must be `single` scalar Field endpoints;
- navigation starts only at an EntityIdentity endpoint and reaches a field of
  that same entity type;
- navigated fields must be known `single` scalar schema fields;
- both operands must have the same scalar domain;
- `eq`/`ne` support matching scalar domains only;
- native ordering operators support only `int` and `time`, matching the
  shipped native evaluator rather than promising unsupported float coercion;
- literal operands, identity comparison, entity-ref fields, multi-value fields,
  relationship traversal, multi-hop navigation and Query-supplied navigation
  are rejected.

Every comparison is branch-total.  All referenced occurrence aliases must be
present in every DNF branch of the owning `PolicyAll`; otherwise compilation
fails with `PARTIAL_BRANCH_CONSTRAINT` before lowering or execution.

### 2.3 Lowering and integrity

For each applicable branch, the compiler creates immutable Policy-owned
conditions in this order:

```text
authored Rule body atoms
→ Policy field lookups (one per navigated operand)
→ Policy compare atom
→ existing Query value bindings
→ existing Unify atoms
→ projection-head links
```

The internal variables used by field lookups are compiler-private and must not
be addressable through Query bind/select.  Conditions, their branch placement,
their generated atoms and their authored compare node are sealed into the
compiled Policy and map bidirectionally through lineage.

### 2.4 Explain and captured evidence

Field lookup and compare atoms are first-class `EvidencePolicyCondition`
values, not Rule-body atoms or metadata.  A Policy explanation presents one
authored compare leaf with its `left_field`, `right_field` (when applicable)
and `compare` evidence.  Missing/incorrect mappings fail closed.

Detached bundle evidence uses the same partitioning and does not mistake a
Policy-owned condition for a query bind, join or projection-head atom.  This
slice covers positive-row live Explain and detached captured evidence.  A zero
row is still `not_asserted`, not a negative proof or a why-not explanation.

### 2.5 Persisted compatibility

Existing `PolicyStructureNodeV0` and `PolicyLoweredRef` fields remain
unchanged.  Compare structure and condition lineage use new DTO types.  This
preserves the canonical shape and seals of existing EvaluationRun anchors and
bundles instead of relying on default values that would alter `asdict`-based
historical seals.

## 3. Non-goals

- Query-level field navigation in `bind` or `select`.
- Field authorization, principal grants, Package/registry persistence or an
  Agent-facing policy contract.
- Literals, aggregates, Not, relation traversal, external Operators or a
  generic expression DSL.
- Scenario-specific Explain/replay, negative proof, complete-result claims or
  non-native engine support.

## 4. Consequences

- `fg.query(policy, address_space=...)` remains the public entry.  The builder
  supplies the trusted SchemaIndex while resolving a direct Policy target;
  existing legacy Policies and Rule lifts remain schema-index optional.
- A Policy author can now express a common relational business condition while
  the Agent still only chooses a Policy and direct public ports.
- FactGraph does not claim that a schema-valid field is caller-authorized.
  Visibility/authority remains a future Meander contract.

## 5. Acceptance criteria

- [x] Canonical DTOs reject unsupported operand/path/type/cardinality shapes.
- [x] Valid two-occurrence navigation and direct scalar comparison compile and
  execute through the existing native Query evaluator.
- [x] Partial Any branches reject before lowering; local branch forms compile.
- [x] Compiler conditions, lineage and digest are deterministic and tamper
  resistant at the existing integrity boundary.
- [x] Live Explain and detached bundle evidence show Policy-owned conditions
  without contaminating Rule evidence.
- [x] Existing Policy/Query/Run/bundle codecs retain their old paths and
  focused regressions remain green.

## 6. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | adopted | Scope frozen | The user requested the complete bounded capability; compiler, Explain and capture are one contract. |
| 2026-08-13 | adopted | Compatibility choice | New compare/condition DTOs preserve legacy V0 DTO fields and historic EvaluationRun seals. |
| 2026-08-13 | implemented | Q12 end-to-end contract closed | AST, compiler/lowering, native direct-Policy Query, live/detached evidence and compatibility regressions are complete. Query bind/select navigation and all stated non-goals remain deferred. |
