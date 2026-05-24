# Q2 Decision: T3 Join Constraint Construction

- Status: proposed
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: design constraint; locks RuleExpr join-constraint syntax and substrate preservation before T3 join implementation.
- Inputs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md` Q2, D4, A8, A9, and frictions.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` section 3.6 commitments 2, 4, and 7; section 4 C30-C31; section 5.9 C58.
  - T1.4 shipped substrate in `src/factgraph/application/protocol/rule.py:122-170` and `tests/application/protocol/test_rule.py:199-213`.
- Outputs / Downstream:
  - T3 join IR decision input.
  - T3.3 `.join(...)` and Every-Proof-Path Reach Rule blueprint.
  - T3 `.join_by_ports(...)` timing decision.
- Related:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`
- Depends on: none.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

The parent design uses examples like:

```python
a = rule_a.as_("a")
b = rule_b.as_("b")
(a & b).join(a.user == b.person)
```

Those examples imply a join-constraint object can be built from port references, and that the join binds occurrences rather than templates.

T1.4 has already shipped `RuleOccurrence` and `RulePortRef` as frozen value DTOs. `RuleOccurrence.__getattr__` and `.port(...)` return `RulePortRef` directly. T1.4 tests assert value equality for `RulePortRef` instances and use them as frozen/hashable objects. Overriding `RulePortRef.__eq__` to return a join constraint would therefore break shipped substrate expectations.

The Stage 1 audit sharpened Q2 with a substrate-preserving vs substrate-breaking axis. This decision locks the substrate-preserving path.

## 2. Scope

This decision locks:

- How T3 constructs explicit port-to-port join constraints.
- Whether T1.4 `RulePortRef` value equality remains intact.
- Whether parent `a.user == b.person` syntax is implemented exactly in the first RuleExpr join slice.
- The minimum join-constraint DTO shape that downstream validators can consume.
- Whether `.join_by_ports(...)` is coupled to `.join(...)` or deferred.

## 3. Non-scope

This decision does not lock:

- The full RuleExpr tree class layout.
- AND/OR flattening.
- Every-Proof-Path Reach Rule algorithm details beyond the constraint input shape.
- Self-join semantics for constraints such as `a.user.eq(a.user)`; the T3.3 Every-Proof-Path Reach Rule blueprint must decide whether these are rejected as vacuous, allowed, or normalized.
- `RuleJoinConstraint` structural equality/hash semantics, including left/right symmetry for `a.user.eq(b.person)` versus `b.person.eq(a.user)`; this belongs to T3-D4 structural equality and hash.
- RuleExpr inspect output.
- Adapter execution lowering.
- Final top-level `Rule` naming after T5.

## 4. Decision

### 4.1 Preserve T1.4 `RulePortRef` value equality

T3 MUST NOT override `RulePortRef.__eq__` to construct join constraints.

`RulePortRef` remains a frozen value DTO. Equality between two `RulePortRef` objects continues to mean value equality over occurrence alias, rule id, port name, Var, and port type. Hashability remains stable for set/dict usage.

### 4.2 Use an explicit substrate-preserving join-construction method

T3 will introduce an explicit method for join constraint construction:

```python
constraint = a.user.eq(b.person)
expr = (a & b).join(constraint)
```

The exact method name is locked as `.eq(...)` for T3 unless later review finds an existing local naming conflict. It is intentionally short because join constraints are authoring-surface syntax.

The method is added to `RulePortRef` and returns a join-constraint DTO rather than a bool. This preserves normal `RulePortRef.__eq__` behavior while giving users a dedicated DSL construction point.

### 4.3 JoinConstraint DTO shape

T3 should introduce a frozen DTO with a shape equivalent to:

```python
@dataclass(frozen=True)
class RuleJoinConstraint:
    left: RulePortRef
    right: RulePortRef
    op: Literal["eq"] = "eq"
```

The initial T3 join surface only supports equality joins. Non-equality joins remain out of scope until a parent design explicitly requires them.

### 4.4 Parent `==` example is a final-state aspiration, not first-slice syntax

Parent examples using `a.user == b.person` are not implemented exactly in the first T3 join slice. This is an explicit substrate-preservation tradeoff.

Reason: exact `==` syntax would require changing `RulePortRef.__eq__`, which would break T1.4 value equality and hash semantics. The `.eq(...)` method preserves T1.4 while keeping the join constraint explicit and readable.

Future syntax sugar MAY add a separate wrapper layer that supports `==` without changing `RulePortRef` equality. Such a wrapper must be a new decision or a clearly scoped follow-up.

### 4.5 `.join_by_ports(...)` timing

`.join_by_ports(*explicit_names)` is deferred until after the base `.join(...)` constraint path lands.

Rationale:

- `.join_by_ports(...)` can compile into the same `RuleJoinConstraint` DTOs once occurrence and pairwise expansion rules are clear.
- It carries additional diagnostics for missing ports and more than two occurrences.
- Keeping it separate reduces T3.3 blast radius.

Stage 3 synthesis should represent `.join_by_ports(...)` as a separate sub-slice unless it is trivially implemented on top of the adopted `.join(...)` DTO.

## 5. Rejected Alternatives

### Option A: Override `RulePortRef.__eq__` to return join constraints

- **Why rejected**: substrate-breaking. It changes the meaning of `RulePortRef` equality shipped in T1.4 and invalidates current DTO equality/hash expectations.

### Option B: Return a join-proxy object from `RuleOccurrence.__getattr__`

- **Why rejected for first slice**: it preserves `RulePortRef` only if `.port(...)` returns the old DTO and `.__getattr__` returns a new wrapper, but that creates two subtly different access paths (`occ.user` vs `occ.port("user")`). This is possible later, but too confusing for the first join slice.

### Option C: Use a tuple form, e.g. `.join((a.user, b.person))`

- **Why rejected**: substrate-preserving but too weakly typed. It makes invalid tuple shapes easy and does not scale cleanly to future non-equality joins.

### Option D: Defer all join constraint construction

- **Why rejected**: C30/C31 are central T3 commitments. Deferring them would leave RuleExpr as only boolean grouping and would not exercise the T1.4 port substrate.

## 6. Supporting Evidence

- Stage 1 audit Q2 marks `a.user.eq(b.person)` and wrapper paths as substrate-preserving, and `__eq__` override / test migration paths as substrate-breaking.
- `RuleOccurrence` and `RulePortRef` are shipped at `src/factgraph/application/protocol/rule.py:139-170`.
- T1.4 tests assert `RulePortRef` value equality at `tests/application/protocol/test_rule.py:199-213`.
- Parent design commitment 7 says joins bind occurrences rather than templates.
- Parent C30/C31 require explicit joins and AND-spine reachability, but do not require the first implementation to use Python `==` if doing so would break shipped substrate.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- T3 join IR DTO design.
- T3 `.join(...)` API.
- Every-Proof-Path Reach Rule validation inputs.
- Stage 3 slice split for `.join_by_ports(...)`.

### 7.2 Required follow-up actions

The T3 join blueprint must:

- Add `RulePortRef.eq(other: RulePortRef) -> RuleJoinConstraint`.
- Reject joins whose operands are not `RulePortRef`.
- Preserve `RulePortRef.__eq__` value equality.
- Test that `a.user == b.person` still returns bool/value equality semantics rather than a join constraint.
- Test the documented join authoring path: `(a & b).join(a.user.eq(b.person))`.
- Keep `.join_by_ports(...)` out of the first join slice unless Stage 3 explicitly re-scopes it.

### 7.3 User-facing docs

Docs must explain that `.eq(...)` is the T3 join-constraint constructor. If parent-final `==` syntax is desired later, it requires a future wrapper/syntax decision.

### 7.4 Compatibility boundary

This decision intentionally prefers preserving shipped T1.4 substrate over exact parent example syntax. That deviation must be cited in the first T3 join blueprint's G5 section.

## 8. Acceptance Criteria

- [ ] `RulePortRef.__eq__` remains value equality.
- [ ] `RulePortRef.eq(...)` returns an immutable join constraint DTO.
- [ ] `.join(...)` accepts only join constraint DTOs from the explicit constructor path.
- [ ] T1.4 `RulePortRef` equality/hash tests continue to pass.
- [ ] Docs show `.eq(...)`, not `==`, for initial T3 join syntax.
- [ ] `.join_by_ports(...)` is either explicitly out of scope or implemented only after Stage 3 re-scopes it.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-24 | proposed | Decision drafted | Stage 1 audit review requested substrate-preserving vs substrate-breaking axis be made load-bearing before T3 join blueprinting. |
