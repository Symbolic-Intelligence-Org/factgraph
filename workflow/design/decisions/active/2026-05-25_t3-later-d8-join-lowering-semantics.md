# D8 Decision: T3 Later Join Lowering Semantics

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks how RuleExpr `RuleJoinConstraint` values become executable constraints inside the private T3 later lowering plan.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md` Q5, F5, F6, F7, F8, F10, and §10 D8 mapping.
  - D6 `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`.
  - D7 `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`.
  - D2 `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`.
  - D4 `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §4.7 and §5.1-§5.4.
  - Shipped `src/factgraph/application/protocol/rule.py:35-39`, `src/factgraph/application/protocol/rule.py:145-185`, and `src/factgraph/application/protocol/rule.py:80-99`.
  - Shipped `src/factgraph/application/protocol/rule_expr.py:20-40`, `src/factgraph/application/protocol/rule_expr.py:105-115`, and `src/factgraph/application/protocol/rule_expr.py:217-236`.
  - Shipped `src/factgraph/application/protocol/rule_expr.py:283-330`.
  - Shipped `src/factgraph/core/rules/where_ast.py:46-52`, `src/factgraph/core/rules/where_ast.py:100-114`, and `src/factgraph/core/rules/where_ast.py:183-190`.
  - Shipped `src/factgraph/sdk/dsl/expr.py:444-456`.
  - Shipped `src/factgraph/adapters/pyreason/where_compile.py:113-137`.
- Outputs / Downstream:
  - D9 adapter support matrix.
  - D10 evaluation result / evidence boundary.
  - Stage 3 T3 later synthesis and per-slice blueprints.
- Related:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
- Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`
- Depends on: D6 and D7 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

T3.3 shipped explicit authoring-time joins:

```python
expr = (a & b).join(a.user.eq(b.user))
```

At authoring time, `RuleJoinConstraint` stores two `RulePortRef` endpoints and `op="eq"`. `_AndGroup.join(...)` validates constraint shape, same-occurrence rejection, direct AND reach, endpoint/operand match, and duplicate normalization.

D7 now gives D8 an execution-time input boundary:

- each branch has `body_atoms`;
- each branch has `pending_joins`;
- each occurrence has `RuleExprPortBinding` values;
- each port binding maps a declared port to an alias-local execution variable.

D8 decides how those `pending_joins` become executable constraints without weakening T3.3/T3.4 no-auto-join and no-OR-reach invariants.

## 2. Scope

This decision locks:

- the executable representation for explicit equality joins;
- how join endpoints resolve through D7 `RuleExprPortBinding`;
- type compatibility checks for entity-ref and value ports;
- join materialization order inside each D7 branch;
- duplicate normalized join handling;
- join provenance preserved for D10;
- D8's error bucket for join-lowering failures.

## 3. Non-scope

This decision does not lock:

- adapter support / rejection behavior for equality atoms; D9 owns it;
- whether D7 branches materialize to one branch-list plan or multiple compiled plans; D9 owns it;
- public result/evidence shape; D10 owns it;
- full T4 Head / closed-head semantics;
- authoring-time `.eq(...)` API changes;
- automatic same-name-port joins;
- new public error subclasses.

## 4. Decision

### 4.1 Explicit joins lower to explicit equality comparison atoms

D8 chooses explicit equality constraints.

For each `RuleJoinConstraint(left, right, op="eq")`, lowering emits a comparison equality over the alias-local execution variables for the two endpoints:

```python
CmpAtom(op="eq", lhs=left_binding.alias_local_execution_var, rhs=right_binding.alias_local_execution_var)
```

When materialized to raw WhereIR, the same constraint uses the existing comparison atom shape:

```python
("eq", left_term, right_term)
```

This matches the shipped comparison grammar:

- `where_ast.CmpAtom(op, lhs, rhs)` is the AST representation;
- raw WhereIR comparison atoms parse as `("eq", lhs, rhs)`;
- SDK DSL comparison lowering already emits `("eq", left, right)` for equality.

### 4.2 Variable unification is rejected for T3 later join lowering

D8 does not lower joins by mutating two alias-local execution variables into the same variable identity.

Rationale:

- D7 explicitly isolates occurrence variables before AND concatenation.
- Variable unification would erase which occurrence supplied which value.
- D10 would lose direct join provenance unless a parallel side channel was added.
- It increases the risk of accidental equality by private source variable name, the exact drift D7 prevents.

Explicit equality atoms preserve alias-local variable privacy while still giving the runtime an executable constraint.

### 4.3 Plan-level-only constraints are rejected

D8 does not leave joins as plan-level constraints that adapters must interpret independently.

Rationale:

- Existing native/Souffle/ProbLog paths already consume WhereIR-style atoms.
- Adapter-specific plan-level joins would duplicate equality semantics across engines.
- D9 should decide engine support for the shared equality atom shape, not invent per-adapter join semantics.

D8 may keep join provenance metadata alongside the materialized equality atom, but the executable body contains an equality constraint.

### 4.4 Join endpoint resolution uses D7 port bindings

Each join endpoint resolves by matching a `RulePortRef` to exactly one D7 `RuleExprPortBinding` in the branch:

```python
def resolve_endpoint(endpoint, branch, occurrence_map):
    binding = find_port_binding(
        occurrence_alias=endpoint.occurrence_alias,
        port_name=endpoint.port_name,
    )
    require binding.source_var == endpoint.var
    require binding.port_type == endpoint.port_type
    return binding.alias_local_execution_var
```

The implementation must not resolve joins by raw variable name alone. It must use the occurrence alias and port binding produced by D7.

If no binding exists, multiple bindings exist, or a binding does not match the endpoint's source var / port type, lowering raises `RuleExprError`.

T3.3 `_validate_endpoint_matches_operand(...)`, T1.4 `Rule.ports` uniqueness, and T3.2 alias uniqueness enforce these invariants at authoring time for normal inputs. D8 keeps this defensive check so malformed D7 plan construction fails before adapter selection.

### 4.5 Port type compatibility is checked at lowering

D8 adds a semantic compatibility check between the two join endpoints:

```python
require left_endpoint.port_type == right_endpoint.port_type
```

Consequences:

- entity-ref ports only join other entity-ref ports with the same inferred entity type;
- value ports join other value ports;
- entity-ref to value joins fail;
- value-to-value joins are allowed because T1.4 `PortType` does not carry a value subtype.

This keeps authoring `.eq(...)` permissive enough to remain a lightweight constraint constructor, while making execution lowering reject semantically incompatible joins before adapter selection.

If a future T1.4 substrate extension adds a value subtype field to `PortType`, this equality check naturally extends to value-subtype compatibility. Any different value-port matching rule must explicitly supersede this D8 decision.

### 4.6 Join equality atoms are appended after branch body atoms

Within a D7 branch, D8 appends materialized join equality atoms after the alias-scoped body atoms:

```python
materialized_body = [
    *branch.body_atoms,
    *materialized_join_eq_atoms,
]
```

Rationale:

- application `Rule` validation requires each declared port variable to appear in the rule body;
- after D7 alias-scoping, branch body atoms establish those execution variables;
- appending join equality atoms keeps ordering deterministic and avoids making join atoms responsible for binding port variables before their source bodies appear.

This ordering does not make same-name ports auto-join. Only `pending_joins` produce appended equality atoms.

The first bullet refers to shipped T1.4 Rule/port validation: declared port variables must appear in the source rule body before D7 can create a `RuleExprPortBinding`.

### 4.7 Join materialization order follows canonical join order

D8 materializes joins in the same canonical order used by shipped T3.3 join normalization:

```text
canonical join key = (op, sorted endpoint A, sorted endpoint B)
```

For each branch:

- duplicate joins are represented once;
- materialized equality atom order is stable across semantically equal expressions;
- join provenance records the canonical join key.

If an implementation receives duplicate pending joins because of a malformed internal plan, it must normalize them before materialization and may record a debug-only duplicate count. It must not emit duplicate executable equality atoms.

### 4.8 Join provenance is preserved internally

D8 must preserve enough internal metadata for D10 to reason about support/evidence later.

Minimum join materialization metadata:

```python
@dataclass(frozen=True)
class RuleExprJoinMaterialization:
    branch_id: str
    join_key: tuple[object, ...]
    left_occurrence_alias: str
    left_port_name: str
    right_occurrence_alias: str
    right_port_name: str
    materialized_atom_index: int
```

`materialized_atom_index` records the 0-based position of this equality atom within the branch's `materialized_body` after §4.6 appending. It is not the pending-join input index.

This metadata remains internal unless D10 decides to expose it. It is not part of the public result surface in D8.

### 4.9 OR reach remains forbidden

D8 does not attempt to repair or reinterpret joins across OR branches.

Shipped `_OrGroup.join(...)` rejects, and shipped `_AndGroup.join(...)` validates reach only through the direct AND spine. If D8 sees a pending join whose endpoint is not present in the current D7 branch, the lowering plan is malformed and must raise `RuleExprError`.

D8 must not look through an OR child to find an endpoint that was unreachable at authoring time.

### 4.10 `join_by_ports(...)` has no separate execution semantics

T3.4 `join_by_ports(...)` expands to ordinary `RuleJoinConstraint` values before D8.

D8 treats constraints produced by `.join_by_ports(...)` exactly the same as constraints produced by explicit `.join(a.user.eq(b.user))`.

There is no name-based execution path and no same-name-port auto-join path.

### 4.11 D8 error bucket

D8 does not introduce a new public error subclass.

Join-lowering failures use `RuleExprError` when they are about RuleExpr join semantics:

- missing endpoint port binding;
- endpoint binding source-var / port-type mismatch;
- incompatible endpoint port types;
- unsupported `RuleJoinConstraint.op`;
- pending join endpoint absent from the current branch;
- malformed duplicate or non-normalized internal join state that cannot be recovered.

Adapter rejection of equality atoms, including PyReason rejection, remains D9 scope.

This extends D6/D7's Q9 disposition for the D8 scope.

## 5. Rejected Alternatives

### Option A: Lower joins by variable unification

- **Why rejected**: unification destroys D7 alias-local variable isolation and makes join provenance harder to preserve for D10.

### Option B: Leave joins as plan-level constraints only

- **Why rejected**: plan-level-only joins would force each adapter to implement join semantics independently instead of consuming a shared WhereIR equality constraint.

### Option C: Auto-join same-name ports during lowering

- **Why rejected**: violates T3.4 and T3.6 user-facing docs. Same-name ports are discoverability hints only until authors call `.join(...)` or `.join_by_ports(...)`.

### Option D: Permit cross-OR endpoint resolution at lowering

- **Why rejected**: violates T3.3 reach validation and would make lowering semantics differ from authoring diagnostics.

### Option E: Reject all value-port joins until value subtypes exist

- **Why rejected**: T1.4 has no value subtype. Rejecting value-to-value joins would make common explicit equality joins impossible despite the existing WhereIR `eq` support.

### Option F: Add a new public join error subclass

- **Why rejected**: D6-D8 keep Q9 error policy within existing `SDKStoreError` / `RuleExprError` buckets unless Stage 2 discovers stronger public API pressure.

## 6. Supporting Evidence

- Shipped `RuleJoinConstraint` supports only `op="eq"`.
- Shipped `RulePortRef.eq(...)` constructs `RuleJoinConstraint` without changing `RulePortRef.__eq__` value equality.
- Shipped `_AndGroup.join(...)` normalizes joins and validates direct AND reach before D8.
- Shipped `_canonical_join_constraint(...)` sorts endpoints and normalizes duplicate joins deterministically.
- D4 and shipped `_canonical_join_constraint(...)` provide the canonical ordering basis for §4.7.
- Shipped `Rule.port_types` stores `PortType(kind="entity_ref" | "value", entity_type=...)`.
- Shipped `where_ast.CmpAtom` and raw WhereIR support equality comparison atoms.
- Shipped SDK DSL equality lowering emits raw WhereIR `("eq", left, right)`.
- Shipped PyReason adapter rejects `eq`, so D9 must decide public PyReason behavior for joined RuleExprs.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- D9: can decide per-engine support for equality atoms and joined RuleExprs.
- D10: can decide whether internal `RuleExprJoinMaterialization` metadata becomes public evidence, internal support metadata, or deferred.
- Stage 3 synthesis: can split implementation into D7 plan construction, D8 join materialization, D9 adapter behavior, and public dispatch.

### 7.2 Required D9 follow-up

D9 must decide:

- whether `engine="pyreason"` rejects any RuleExpr branch containing D8 equality atoms;
- whether native, Souffle, and ProbLog support the D8 equality atom shape unchanged;
- whether adapter grammar floors treat entity-ref joins and value joins differently;
- whether aggregate-containing branches plus D8 equality atoms are supported per engine.

### 7.3 Required D10 follow-up

D10 must decide:

- whether join materialization metadata is exposed, retained internally, or deferred;
- how support artifacts identify equality atoms that came from explicit RuleExpr joins versus atoms already present in a source Rule body;
- whether public results remain existing `CandidateSet` values.

## 8. Acceptance Criteria

- [ ] D9 cites D8 and decides equality atom support/rejection per engine.
- [ ] D10 cites D8 and decides whether join materialization metadata is exposed, internal, or deferred.
- [ ] Future implementation blueprints lower explicit joins to equality atoms, not variable unification.
- [ ] Future implementation blueprints resolve joins through D7 port bindings, not raw variable names.
- [ ] Future implementation blueprints reject incompatible endpoint port types with `RuleExprError`.
- [ ] Future implementation blueprints append join equality atoms after branch body atoms in canonical join order.
- [ ] Future implementation blueprints preserve same-name-port no-auto-join and no cross-OR reach.
- [ ] Future implementation blueprints treat `.join_by_ports(...)` output exactly like explicit `.join(...)` constraints.
- [ ] No new public error subclass is introduced by D8.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | D8 chooses explicit equality atom materialization for `RuleJoinConstraint(op="eq")`, rejects variable unification and plan-level-only joins, and preserves join provenance internally for D10. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 precision amendments | Clarified D8 endpoint invariant chain, `materialized_atom_index` semantics, PortType future evolution, Rule/port validation dependency, and D4 canonical-ordering citation. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | WC1-WC4 and N1 addressed; endpoint invariants, materialized atom index semantics, and D4 canonical ordering reviewed clean; D9 unblocked. |
