# Q4 Decision: T3 Structural Equality And Hash

- Status: adopted
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: design constraint; locks RuleExpr structural equality and same-process hashing before T3 RuleExpr value implementation.
- Inputs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md` Q4, A3, A10-A12, and hash/canonical friction.
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` C25, C33, C34, and lines 1298-1306.
- Outputs / Downstream:
  - T3 RuleExpr value implementation.
  - T3-D5 slice split and bool-guard timing.
  - T3 inspect canonicalization assumptions.
- Related:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md`
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`
- Depends on: T3-D2 adopted join constraint shape.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C25 requires AND/OR flattening. Parent C33 requires immutable RuleExpr values where `.join` and `.as_` return new values. Parent C34 requires semantically equivalent expressions such as `a & b` and `b & a` to compare equal and hash equal in the same process.

Parent lines 1298-1306 distinguish Python `__hash__` from canonical content digests: `__hash__` only needs same-process stability, while cross-process digests require separate canonical serialization.

T3-D2 adopted `RuleJoinConstraint(left, right, op="eq")` as the join DTO shape but explicitly deferred left/right symmetry and structural hash semantics to this decision.

## 2. Scope

This decision locks:

- Equality semantics for RuleExpr values.
- Same-process `__hash__` semantics.
- Canonicalization of commutative AND/OR groups.
- Whether occurrence aliases participate in equality.
- Whether join constraints are order-insensitive.
- How single-Rule coercion participates in equality.

## 3. Non-scope

This decision does not lock:

- Cross-process content digest format.
- Inspect render ordering.
- Adapter execution lowering.
- Full RuleExpr DTO/module placement.
- Whether self-joins are valid.
- Public operand import path.

## 4. Decision

### 4.1 RuleExpr values are immutable and structurally comparable

T3 RuleExpr values must be immutable. Equality compares normalized structural content rather than object identity.

`expr1 == expr2` returns true when the expressions have the same normalized tree, occurrence aliases, Rule template identities, and join constraints.

Equality with unsupported non-RuleExpr types follows Python convention by returning `NotImplemented`. Coercion from application Rule to RuleExpr happens at API boundaries where RuleExpr is expected, not inside `RuleExpr.__eq__`.

### 4.2 AND and OR groups are commutative and flattened for equality/hash

AND and OR groups normalize nested groups of the same kind before equality/hash.

Examples:

- `(a & b) == (b & a)`
- `(a & (b & c)) == ((c & a) & b)`
- `(a | b) == (b | a)`

AND and OR are not interchangeable:

- `(a & b) != (a | b)`

### 4.3 Occurrence aliases are part of identity

Occurrence aliases participate in RuleExpr equality/hash.

Reason: joins bind occurrences, not templates. Two expressions over the same Rule templates but different occurrence aliases are not guaranteed to have the same join graph or evidence labels.

### 4.4 Rule template identity participates by content digest and rule id

Rule occurrence identity in RuleExpr equality should include both:

- the underlying application Rule content digest
- the Rule id

Reason: content digest captures semantic rule content, while Rule id is user-facing identity used by default aliasing and diagnostics. Stage 3 may refine this if it finds a contradiction, but T3 must not use Python object identity alone.

### 4.5 Join constraints are set-like and equality joins are symmetric

The join constraint collection on an AND group is order-insensitive.

`a.user.eq(b.person)` and `b.person.eq(a.user)` are structurally equal join constraints because `op="eq"` is symmetric.

Duplicate equivalent join constraints normalize to one constraint for equality/hash purposes. The implementation may still preserve authoring order separately for diagnostics/rendering, but structural equality/hash use the normalized set.

### 4.6 Single Rule coercion normalizes to a one-occurrence RuleExpr

An application Rule coerced to RuleExpr equals the explicit one-occurrence RuleExpr for that Rule with the default alias.

This supports C35 while keeping equality predictable.

This equality applies between two RuleExpr values after coercion. It does not introduce direct cross-type equality such as `application_rule == rule_expr`, and it does not change T1.4 application Rule `__eq__` or `__hash__` semantics.

### 4.7 `__hash__` follows equality in-process only

`__hash__` must be consistent with `__eq__` in the same Python process.

T3 does not introduce a cross-process RuleExpr content digest. If a stable digest is needed later, it must be a separate explicit API and decision.

## 5. Rejected Alternatives

### Option A: Preserve authoring order in equality

- **Why rejected**: conflicts with parent C34, which explicitly treats `a & b` and `b & a` as equal.

### Option B: Ignore occurrence aliases in equality

- **Why rejected**: joins and evidence bind occurrences. Dropping aliases would conflate expressions that differ in diagnostics and join targets.

### Option C: Use Python object identity for Rule operands

- **Why rejected**: structurally equivalent rules built independently would compare unequal. T1.1 already provides content digest machinery.

### Option D: Make join constraints list-ordered for equality

- **Why rejected**: join order is authoring order, not semantics, for equality joins. Order can still be retained for render diagnostics outside structural equality.

### Option E: Add a cross-process digest in T3

- **Why rejected**: parent separates `__hash__` from stable digests. A digest API would add scope beyond RuleExpr authoring equality.

## 6. Supporting Evidence

- Parent C34 requires commutative equality/hash.
- Parent lines 1298-1306 distinguish `__hash__` from content digest.
- T3-D2 locks equality join DTO shape and defers left/right symmetry to this decision.
- T1.4 shipped alias defaults and occurrence DTOs, making alias identity load-bearing.
- Application Rule content digest already exists and is alias-independent.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- T3.1 RuleExpr base IR equality/hash tests.
- T3.3 join constraint normalization.
- T3.5 inspect canonical presentation choices.
- T3-D5 slice split and bool-guard timing.

### 7.2 Required follow-up actions

The T3 RuleExpr blueprint must:

- Normalize nested same-kind AND/OR groups.
- Normalize child ordering for equality/hash.
- Include occurrence aliases in equality/hash.
- Include Rule content digest and Rule id in occurrence identity.
- Treat join constraints as order-insensitive.
- Treat equality join endpoints as symmetric.
- Preserve any authoring order needed for render separately from structural equality/hash.
- Avoid adding a cross-process digest unless a later decision explicitly scopes it.

### 7.3 Interaction with inspect

Inspect rendering may choose a stable presentation order that differs from authoring order. That render order is not the equality/hash contract unless a later inspect decision says otherwise.

## 8. Acceptance Criteria

- [ ] `a & b == b & a` and hashes match.
- [ ] `a | b == b | a` and hashes match.
- [ ] Nested same-kind groups flatten for equality/hash.
- [ ] AND and OR expressions remain distinct.
- [ ] Different occurrence aliases compare unequal when aliases differ.
- [ ] Equivalent equality joins with reversed endpoints compare equal.
- [ ] Duplicate equivalent joins do not change equality/hash.
- [ ] Single application Rule coercion equals explicit one-rule RuleExpr with default alias.
- [ ] No cross-process digest API is introduced by T3 unless separately decided.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-24 | proposed | Decision drafted | Stage 1 audit Q4 and D2 amendment required structural equality/hash to absorb join symmetry and set-vs-list semantics. |
| 2026-05-24 | adopted | P2 amendment cleared, cross-decision dependencies sealed | D4 P2 framing sharpening landed in 4c845615; reviewer pass confirmed adoption prerequisites. |
