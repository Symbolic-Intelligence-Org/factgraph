# Task Blueprint: T3.3 Joins And Reach Rule

- Status: scoped
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Class: M
- Related Modules:
  - `src/factgraph/application/protocol/rule.py`
  - `src/factgraph/application/protocol/rule_expr.py`
  - `src/factgraph/application/protocol/__init__.py`
  - `src/factgraph/sdk/__init__.py`
  - `tests/application/protocol/test_rule_expr.py`
- Related Docs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
  - `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
  - `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
- Audit Log:
  - [2026-05-24_t3-3-joins-and-reach-rule.audit.md](./2026-05-24_t3-3-joins-and-reach-rule.audit.md)

## 1. Problem

T3.1 shipped immutable RuleExpr values, `&` / `|`, flattening, bool guards, and join-free equality/hash. T3.2 added expression-scope occurrence validation, explicit-alias handling, deterministic diagnostics, and alias-aware canonical operands.

T3.3 must now turn T1.4 port references into explicit join constraints and attach those constraints to AND groups without allowing joins to reach into OR branches or single Rule values.

Canonical drivers:

- D2 sections 4.2-4.5: preserve `RulePortRef.__eq__`, add explicit `RulePortRef.eq(...)`, use a frozen `RuleJoinConstraint(left, right, op="eq")`, and keep `.join_by_ports(...)` out of the first join slice.
- D4 section 4.5: join constraints are set-like for equality/hash; equality joins are symmetric; duplicate equivalent constraints normalize to one semantic constraint.
- D5 section 4.4: T3.3 owns `.join(...)`, Every-Proof-Path Reach Rule validation, self-join semantics, and structural handling of join constraints.
- Stage 3 synthesis section 3 T3.3: dependencies are D2, D4, and the T3.1/T3.2 RuleExpr tree.
- Track plan T3.3 row at `9c857d0c`: `.join(...)` over AND groups plus `RulePortRef.eq(...)`, Every-Proof-Path Reach Rule, self-join semantics, join symmetry, and duplicate normalization.

This slice is M-class because it adds a new public DTO (`RuleJoinConstraint`), a new public SDK export, an additive method on the T1.4 `RulePortRef` DTO, a new `.join(...)` authoring method, and a non-trivial reachability validator that consumes multiple adopted decisions.

## 2. Goals

1. Add immutable `RuleJoinConstraint(left: RulePortRef, right: RulePortRef, op: Literal["eq"] = "eq")`.

2. Add `RulePortRef.eq(other: RulePortRef) -> RuleJoinConstraint` as the substrate-preserving join constructor from D2.

3. Add `_AndGroup.join(*constraints: RuleJoinConstraint) -> _AndGroup`, returning a new immutable AND group.

4. Enforce AND-only join attachment:
   - `_AndGroup.join(...)` is the only join method.
   - `_OrGroup.join(...)` is not available and should raise `RuleExprError` through an explicit method for better diagnostics.
   - single application `Rule` and `RuleOccurrence` do not gain `.join(...)`.

5. Enforce the Every-Proof-Path Reach Rule at construction time:
   - a join endpoint may reference only a direct `_RuleOperand` child of the joined `_AndGroup`.
   - endpoints inside `_OrGroup` children are not reachable from the outer `.join(...)`.
   - invalid reach raises `RuleExprError`.

6. Lock self-join semantics for T3.3: reject same-occurrence joins as vacuous/unsupported.
   - `a.user.eq(a.user)` raises.
   - `a.user.eq(a.region)` also raises because T3.3 joins connect occurrences; intra-rule filters belong in `Rule.where`, not RuleExpr joins.

7. Normalize join constraints for equality/hash:
   - `a.user.eq(b.person)` and `b.person.eq(a.user)` are structurally equal.
   - duplicate equivalent constraints dedupe for `_AndGroup` canonical equality/hash.

## 3. Non-goals

- No `.join_by_ports(...)`; T3.4 owns it.
- No `fg.rules.inspect(rule_expr)` or `RuleExprInspect`; T3.5 owns inspect.
- No user-facing RuleExpr docs/examples beyond minimal API surface entries; T3.6 owns docs and examples.
- No RuleExpr execution lowering or adapter integration.
- No non-equality joins; `op` remains `Literal["eq"]`.
- No parent-final `a.user == b.person` syntax; D2 rejects changing `RulePortRef.__eq__`.
- No changes to T1.4 `Rule.as_`, `RuleOccurrence`, alias regex validation, or port APIs.
- No changes to T1.3 staged SDK naming; `factgraph.sdk.Rule` remains legacy.
- No changes to T2.3 aggregate substrate or adapters.
- No direct `application_rule == rule_expr` cross-type equality.
- No replacement of the T3.1 duck-typed `_is_legacy_sdk_rule` check.

## 4. Current Context

### 4.1 T1.4 port substrate

- `RulePortRef` is defined in `src/factgraph/application/protocol/rule.py`.
- `RuleOccurrence.port(...)` and `RuleOccurrence.__getattr__(...)` return `RulePortRef`.
- T1.4 tests assert `RulePortRef` value equality and hashability.

T3.3 must add `RulePortRef.eq(...)` without changing `RulePortRef.__eq__` value equality or field layout.

### 4.2 T3.1/T3.2 RuleExpr substrate

- `RuleExpr`, `RuleExprError`, `ExplicitBoolError`, `_RuleExpr`, `_RuleOperand`, `_AndGroup`, `_OrGroup`, `_combine(...)`, `_rule_identity(...)`, and `_canonical_children(...)` live in `src/factgraph/application/protocol/rule_expr.py`.
- T3.2 `_RuleOperand` carries `rule`, `alias`, and `explicit_alias`.
- T3.2 `_validate_expression_scope(...)` runs before composed expressions return to callers.

T3.3 should extend the same module rather than introduce a separate join module.

### 4.3 Parent reach rule

The parent design defines Every-Proof-Path Reach Rule as direct AND-spine reachability:

- after flattening the outer AND group, direct Rule nodes are reachable.
- OR group internals are not reachable from the outer join.
- path-dependent joins must be distributed explicitly by the user into each OR branch.

T3.3 implements that mechanical rule rather than a general graph search through OR alternatives.

## 5. Proposed Shape

### 5.1 Module placement

Extend:

- `src/factgraph/application/protocol/rule.py`
- `src/factgraph/application/protocol/rule_expr.py`
- `src/factgraph/application/protocol/__init__.py`
- `src/factgraph/sdk/__init__.py`

Add tests in:

- `tests/application/protocol/test_rule_expr.py`

Minimal API surface docs:

- `src/factgraph/sdk/docs/04_api_surface.en.md`

Do not add tutorial docs or examples in T3.3; T3.6 owns those.

### 5.2 RulePortRef additive method

Add `RulePortRef.eq(...)` to the T1.4 frozen DTO:

```python
def eq(self, other: RulePortRef) -> RuleJoinConstraint:
    ...
```

This is an additive method-only change. `@dataclass(frozen=True)` constrains field assignment, not class method definitions. `RulePortRef` fields, `__eq__`, `__hash__`, `RuleOccurrence.port(...)`, and alias/port semantics remain unchanged.

This scope is explicitly listed now to avoid repeating the T3.2 T-1 drift, where a necessary operator method was discovered during implementation and bundled into feat instead of pre-feat blueprint scope.

### 5.3 RuleJoinConstraint DTO

Add a frozen public DTO in `rule_expr.py`:

```python
@dataclass(frozen=True)
class RuleJoinConstraint:
    left: RulePortRef
    right: RulePortRef
    op: Literal["eq"] = "eq"
```

Validation:

- `left` and `right` must be `RulePortRef`.
- `op` must be `"eq"`.
- same-occurrence constraints are rejected as vacuous/unsupported:
  - same `occurrence_alias` and same `rule_id` is invalid even if port names differ.
- endpoint symmetry is handled in a private canonical helper; `RulePortRef.__eq__` remains value equality.

Validation location:

- Basic shape validation (`left` / `right` types, `op == "eq"`) lives in `RuleJoinConstraint.__post_init__` for defense-in-depth against direct `RuleJoinConstraint(...)` construction, matching the T1.4 substrate pattern.
- Same-occurrence rejection lives in `.eq(...)` factory and `_AndGroup.join(...)` reach validator because same-occurrence rejection is a join authoring concern, not a DTO shape concern.
- Endpoint-vs-operand match validation (alias / rule_id / port_name / var / port_type) lives in `_AndGroup.join(...)` reach validator because it requires the AND group's current operand context.

Export:

- `factgraph.application.protocol.RuleJoinConstraint`
- `factgraph.sdk.RuleJoinConstraint`
- `rule_expr.__all__`
- `application/protocol/__init__.__all__`
- `sdk.__all__`

No new error subclass is introduced. Join violations use `RuleExprError(SDKDSLError)` from T3.1.

### 5.4 AND group join storage

Extend `_AndGroup` from:

```python
@dataclass(frozen=True, eq=False)
class _AndGroup(_RuleExpr):
    children: tuple[_RuleExpr, ...]
```

to:

```python
@dataclass(frozen=True, eq=False)
class _AndGroup(_RuleExpr):
    children: tuple[_RuleExpr, ...]
    joins: tuple[RuleJoinConstraint, ...] = ()
```

`_AndGroup.join(*constraints)` returns a new `_AndGroup` with existing and new constraints normalized/deduped.

When `_combine("and", ...)` flattens nested `_AndGroup` values, it must preserve and merge their `joins` into the new group. This keeps `(a & b).join(c) & d` immutable while preserving the previously attached join constraint.

Zero-constraint `.join()` is rejected by `_AndGroup.join(*constraints)` to avoid accidental no-op calls that could mask missing constraints. Users wanting to compose without joins should use `&` / `|` directly without `.join()`.

### 5.5 AND-only enforcement

Only `_AndGroup` exposes meaningful `.join(...)`.

Add an explicit `_OrGroup.join(...)` method that raises `RuleExprError` with guidance that joins must be distributed into AND branches. This produces a predictable error for `(a | b).join(...)`.

Do not add `.join(...)` to application `Rule` or `RuleOccurrence`. `rule.join(...)` and `rule.as_("a").join(...)` should remain normal Python attribute errors. Parent semantics say single-rule self constraints belong in `Rule.where`.

### 5.6 Reach rule algorithm

T3.3 uses direct AND-spine reachability.

Pseudocode:

```python
def _reachable_operands(group: _AndGroup) -> dict[tuple[str, str], _RuleOperand]:
    reachable = {}
    for child in group.children:
        if isinstance(child, _RuleOperand):
            reachable[(child.alias, child.rule.id)] = child
        # _OrGroup children are deliberately not traversed.
    return reachable

def _validate_join_reach(group: _AndGroup, constraints: tuple[RuleJoinConstraint, ...]) -> None:
    reachable = _reachable_operands(group)
    for constraint in constraints:
        for endpoint in (constraint.left, constraint.right):
            key = (endpoint.occurrence_alias, endpoint.rule_id)
            operand = reachable.get(key)
            if operand is None:
                raise RuleExprError(...)
            _validate_endpoint_matches_operand(endpoint, operand)
```

Endpoint validation:

- occurrence alias + rule id must match a direct `_RuleOperand`.
- `port_name` must exist on the operand's Rule.
- `var` must match the Rule's declared port Var for that `port_name`.
- `port_type` must match the Rule's inferred port type.

Complexity:

- Let `n` be direct AND children and `m` be total join constraints on the AND group.
- Reach validation is `O(n + m)` for alias/rule lookup plus endpoint field checks.
- Normalization sorting is `O(m log m)`.

Corner cases:

- `(a & b).join(a.user.eq(b.user))` is valid.
- `(a & (b | c)).join(a.user.eq(b.user))` is invalid because `b` is inside an OR child.
- `((a & b).join(a.user.eq(b.user)) | c)` remains valid because join is attached inside the AND branch.
- `((a & b) | c).join(...)` is invalid because outer expression is OR.

### 5.7 Join normalization

Add private helpers:

```python
def _canonical_join_constraint(constraint: RuleJoinConstraint) -> tuple[object, ...]: ...
def _normalize_join_constraints(constraints: Iterable[RuleJoinConstraint]) -> tuple[RuleJoinConstraint, ...]: ...
```

For equality joins, endpoint order is symmetric:

- canonicalize each endpoint as `(occurrence_alias, rule_id, port_name, var, port_type)`.
- sort the two endpoint canonical values.
- canonical join key is `("eq", endpoint_a, endpoint_b)`.

Deduplication:

- duplicate equivalent constraints normalize to one constraint.
- implementation may preserve the first authored object for storage, but `_AndGroup._canonical()` must use canonical normalized join keys.

### 5.8 Canonical equality/hash update

Update `_AndGroup._canonical()` to include normalized joins:

```python
return ("and", _canonical_children(self.children), _canonical_joins(self.joins))
```

Consequences:

- `a.user.eq(b.user)` and `b.user.eq(a.user)` are equal for RuleExpr structural equality/hash.
- duplicate joins do not affect equality/hash.
- AND child order remains commutative from T3.1.
- occurrence aliases remain identity-bearing from T3.2.

### 5.9 Validation ordering

Validation order for `_AndGroup.join(...)`:

1. Coerce and validate each `RuleJoinConstraint` shape.
2. Reject same-occurrence constraints.
3. Merge with existing joins and normalize duplicates.
4. Validate reachability against the current AND group's direct operand children.
5. Return a new frozen `_AndGroup`.

`_combine("and", ...)` should continue to run T3.2 expression-scope validation after flattening and before returning. If `_combine` merges child AND-group joins, it should run join reach validation on the resulting flattened group before returning.

Keep expression-scope validation and join reach validation as separate helpers. T3.2 owns alias/repeated-rule validation; T3.3 owns join endpoint/reach validation.

### 5.10 Diagnostics

Use `RuleExprError` for all join construction violations.

Messages should identify:

- invalid constraint operand type.
- `.join(...)` on OR groups.
- same-occurrence self join.
- endpoint alias/rule id not reachable from the direct AND spine.
- endpoint port mismatch for manually constructed `RuleJoinConstraint`.

Diagnostics do not need to aggregate every join issue in T3.3. Reach validation may fail fast because the invalid constraint is usually local and directly actionable.

## 6. Invariants

- T1.4 `Rule.as_`, `RuleOccurrence`, alias regex validation, and port APIs remain unchanged.
- T1.4 `RulePortRef` fields, value equality, and hashability remain unchanged; `RulePortRef.eq(...)` is additive.
- T1.3 staged SDK naming remains unchanged; `factgraph.sdk.Rule` remains legacy.
- T2.3 aggregate substrate and adapters remain untouched.
- T3.1 public exports, bool guards, and negative-action gates remain intact.
- T3.2 expression-scope validation remains intact and continues to run before RuleExpr values return.
- T3.2 `_validate_expression_scope(...)` and T3.3 join validation remain separate helpers.
- No direct `application_rule == rule_expr` cross-type equality is introduced.
- No legacy SDK Rule truthiness behavior changes.
- No `.join_by_ports(...)`, inspect, docs/examples, or execution lowering enters this slice.

## 7. Acceptance

- [ ] `RulePortRef.__eq__` still returns value equality; `a.user == b.user` is bool/value equality, not a join constraint.
- [ ] `a.user.eq(b.person)` returns a frozen `RuleJoinConstraint(left=a.user, right=b.person, op="eq")`.
- [ ] `RuleJoinConstraint` is exported from `factgraph.application.protocol` and `factgraph.sdk`.
- [ ] Non-`RulePortRef` inputs to `.eq(...)` raise `RuleExprError`.
- [ ] Same-occurrence constraints such as `a.user.eq(a.user)` and `a.user.eq(a.region)` raise `RuleExprError`.
- [ ] `(a & b).join(a.user.eq(b.user))` returns a new `_AndGroup`; the original expression remains unchanged.
- [ ] `(a & b).join(a.user.eq(b.user)) == (b & a).join(b.user.eq(a.user))` and hashes match.
- [ ] Duplicate equivalent joins do not change equality/hash.
- [ ] `(a & b).join(a.user.eq(b.user)) & c` flattens children to `(a, b, c)`, preserves the join constraint, and re-validates reach against the new direct children. The result equals `(c & b & a).join(b.user.eq(a.user))` for canonical equality/hash.
- [ ] `_AndGroup.join(...)` rejects zero constraints.
- [ ] `_AndGroup.join(...)` rejects constraints whose endpoints are not direct AND-spine operands.
- [ ] `(a & (b | c)).join(a.user.eq(b.user))` raises `RuleExprError` because `b` is inside an OR child.
- [ ] `((a & b).join(a.user.eq(b.user)) | c)` remains valid.
- [ ] `(a | b).join(...)` raises `RuleExprError` with distribute-to-AND-branches guidance.
- [ ] `rule.join(...)` and `rule.as_("a").join(...)` remain unavailable; single-rule joins are not introduced.
- [ ] Manually constructed `RuleJoinConstraint` endpoints with mismatched alias/rule/port/var/port_type raise `RuleExprError`.
- [ ] T3.2 expression-scope validation still rejects duplicate aliases and repeated bare Rules.
- [ ] T1.4 application protocol tests pass.
- [ ] T1.3 SDK naming tests pass.
- [ ] T2.3 aggregate tests pass.
- [ ] T3.1/T3.2 RuleExpr tests pass after adding join tests.
- [ ] Ruff passes on touched Python files.

## 8. Implementation Plan

1. G7 baseline:
   - verify branch, sacred master, and dirty set.
   - run `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v`; expected baseline is 45 tests OK from T3.2.
   - record baseline in the audit log before code edits.

2. Add `RuleJoinConstraint` in `src/factgraph/application/protocol/rule_expr.py`.

3. Add `RulePortRef.eq(...)` in `src/factgraph/application/protocol/rule.py`, importing `RuleJoinConstraint` / `RuleExprError` lazily to avoid cycles.

4. Extend `_AndGroup` with `joins: tuple[RuleJoinConstraint, ...] = ()` and `.join(...)`.

5. Add `_OrGroup.join(...)` that raises `RuleExprError`; do not add join methods to `Rule` or `RuleOccurrence`.

6. Add join normalization and reach validation helpers in `rule_expr.py`.

7. Update `_combine("and", ...)` to preserve joins from flattened AND groups and validate merged join reach.

8. Export `RuleJoinConstraint` from application protocol and top-level SDK.

9. Add focused tests to `tests/application/protocol/test_rule_expr.py` covering all acceptance items.

10. Add minimal API surface docs for `RuleJoinConstraint` and `.eq(...)` syntax in `src/factgraph/sdk/docs/04_api_surface.en.md`. Do not add T3.6 tutorial/examples.

11. Run verification:
    - `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate -v`
    - `python -m ruff check src/factgraph/application/protocol/rule.py src/factgraph/application/protocol/rule_expr.py src/factgraph/application/protocol/__init__.py src/factgraph/sdk/__init__.py tests/application/protocol/test_rule_expr.py`

## 9. Docs To Update

- `src/factgraph/sdk/docs/04_api_surface.en.md`: add minimal `RuleJoinConstraint` API surface entry and mention `.eq(...)` as the initial join constraint constructor.
- No broad examples or user guide edits in T3.3. T3.6 owns final docs/examples after T3.5 inspect stabilizes.

## 10. Outcome / Deviations

To be filled during closure.
