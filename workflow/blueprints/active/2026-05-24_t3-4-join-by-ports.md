# Task Blueprint: T3.4 Join By Ports

- Status: implemented
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Class: S
- Related Modules:
  - `src/factgraph/application/protocol/rule_expr.py`
  - `tests/application/protocol/test_rule_expr.py`
- Related Docs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
  - `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
  - `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
  - `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`
- Audit Log:
  - [2026-05-24_t3-4-join-by-ports.audit.md](./2026-05-24_t3-4-join-by-ports.audit.md)

## 1. Problem

T3.3 shipped explicit `RuleJoinConstraint` values, `RulePortRef.eq(...)`, `_AndGroup.join(...)`, direct-AND-spine reach validation, and symmetric/dedup canonical join equality.

T3.4 now adds the convenience authoring method from C58: `.join_by_ports(*explicit_names)`. It must be explicit-name-only, deterministic, and a thin expansion over T3.3 `.join(...)`, without creating new join DTOs, new exports, or additional substrate methods.

Canonical drivers:

- D2 section 4.5 defers `.join_by_ports(...)` until after base `.join(...)`, and states it can compile into the same `RuleJoinConstraint` DTOs once occurrence and pairwise expansion rules are clear.
- D5 section 4.5 assigns C58 `.join_by_ports(*explicit_names)` to T3.4 and requires missing, fewer-than-two, ambiguous expansion, and explicit-name-only behavior.
- Stage 3 synthesis section 3 T3.4 depends on T3.3 join mechanics.
- Track plan T3.4 row at `9c857d0c` scopes `.join_by_ports(*names)` as explicit-name expansion plus diagnostics.
- T3.3 archived at `1100ea78` with `.join(...)`, `RuleJoinConstraint`, reach validation, and 0-deviation preemptive scoping discipline.

This slice is S-class because it adds one method to an existing internal `_AndGroup` RuleExpr surface, introduces no new public DTO/export, reuses T3.3 `RuleJoinConstraint` and `.join(...)`, and has no new execution or inspect semantics.

S-to-M triggers:

- introducing a new public DTO/export or new error subclass.
- adding `Rule.join_by_ports(...)` or `RuleOccurrence.join_by_ports(...)`.
- changing D2's pairwise-expansion direction for more-than-two occurrences.
- moving beyond pure expansion into inspect, docs/examples, or execution lowering.

## 2. Goals

1. Add `_AndGroup.join_by_ports(*explicit_names: str) -> _AndGroup`.

2. Expand each explicit port name into pairwise `RuleJoinConstraint` values over all direct reachable `_RuleOperand` children that expose that port name, then call the T3.3 `.join(...)` path.

3. Report missing-port diagnostics when a requested port name is present on zero direct reachable occurrences.

4. Report fewer-than-two diagnostics when a requested port name is present on exactly one direct reachable occurrence.

5. Lock more-than-two occurrence behavior: a requested port name present on three or more direct reachable occurrences expands pairwise into `C(n, 2)` constraints. This is the T3.4 resolution of D5's "ambiguous expansion" concern: no ambiguity error is raised; deterministic pairwise expansion is the chosen behavior inherited from D2 §4.5.

6. Preserve T3.3 AND-only semantics:
   - `_AndGroup.join_by_ports(...)` is the only meaningful method.
   - `_OrGroup.join_by_ports(...)` raises `RuleExprError` with the same distribute-into-AND-branches guidance as `_OrGroup.join(...)`.
   - application `Rule` and `RuleOccurrence` do not gain `.join_by_ports(...)`.

## 3. Non-goals

- No T3.5 inspect work.
- No T3.6 docs/examples beyond optional minimal API surface mention if needed by implementation.
- No RuleExpr execution lowering or adapter integration.
- No new public DTO, SDK export, or error subclass.
- No changes to T1.4 `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex validation, port APIs, or `RulePortRef.eq(...)`.
- No changes to T1.3 staged SDK naming; `factgraph.sdk.Rule` remains legacy.
- No changes to T2.3 aggregate substrate or adapters.
- No changes to T3.1/T3.2/T3.3 negative-action gates.
- No direct `application_rule == rule_expr` cross-type equality.
- No replacement of the T3.1 duck-typed `_is_legacy_sdk_rule` check.

## 4. Current Context

### 4.1 T3.3 join substrate

T3.3 currently provides:

- `RuleJoinConstraint(left, right, op="eq")`.
- `RulePortRef.eq(other)` for explicit constraint construction.
- `_AndGroup.join(*constraints)` for AND-only join attachment.
- `_OrGroup.join(...)` diagnostic.
- `_reachable_operands(group)` for direct AND-spine operand lookup.
- `_validate_join_reach(...)` and `_validate_endpoint_matches_operand(...)`.
- `_normalize_join_constraints(...)` and `_canonical_join_constraint(...)`.

T3.4 should reuse those helpers and avoid creating parallel reach or canonicalization logic.

### 4.2 Direct reachable port inventory

For each explicit port name, T3.4 needs the direct reachable `_RuleOperand` children of the `_AndGroup` and each operand's `Rule.ports` mapping.

OR-branch internals remain unreachable by design. `(a & (b | c)).join_by_ports("user")` should evaluate only direct children `a` and the OR child; it should not look through `b | c`.

## 5. Proposed Shape

### 5.1 Module placement

Extend only:

- `src/factgraph/application/protocol/rule_expr.py`
- `tests/application/protocol/test_rule_expr.py`

Do not edit `src/factgraph/application/protocol/rule.py`, `src/factgraph/application/protocol/__init__.py`, or `src/factgraph/sdk/__init__.py`.

No new docs are required unless implementation exposes a minimal API-surface row adjustment. T3.6 owns user-facing examples and precedence/parentheses documentation.

### 5.2 Method shape

Add to `_AndGroup`:

```python
def join_by_ports(self, *explicit_names: str) -> _AndGroup:
    constraints = _expand_join_by_ports(self, explicit_names)
    return self.join(*constraints)
```

Zero names are rejected with `RuleExprError`, mirroring T3.3 zero-constraint `.join()` rejection.

Port names must be non-empty strings. Non-string or empty names raise `RuleExprError`.

### 5.3 Expansion algorithm

T3.4 expands explicit port names into T3.3 constraints.

Pseudocode:

```python
from itertools import combinations

def _expand_join_by_ports(group: _AndGroup, names: tuple[str, ...]) -> tuple[RuleJoinConstraint, ...]:
    direct = tuple(_reachable_operands(group).values())
    issues = []
    constraints = []
    for name in names:
        refs = []
        for operand in direct:
            if name in operand.rule.ports:
                refs.append(operand.rule.as_(operand.alias).port(name))
        if len(refs) == 0:
            issues.append(f"port {name!r} is not present on any direct AND occurrence")
        elif len(refs) == 1:
            issues.append(f"port {name!r} is present on fewer than two direct AND occurrences")
        else:
            constraints.extend(left.eq(right) for left, right in combinations(refs, 2))
    if issues:
        raise RuleExprError("RuleExpr.join_by_ports validation failed: " + "; ".join(sorted(issues)))
    return tuple(constraints)
```

The implementation may construct `RulePortRef` values directly from `_RuleOperand.rule.ports` instead of calling `Rule.as_(alias).port(name)`, but it must preserve the same alias, rule id, `Var`, and `PortType` fields. Reusing `RuleOccurrence.port(...)` is preferred when it stays simple.

Complexity:

- Let `n` be direct reachable operands and `p` be requested port names.
- Inventory scan is `O(p * n)`.
- Pairwise expansion for a single name with `k` matches is `O(k^2)`.
- Final join normalization/reach validation is delegated to T3.3 `.join(...)`.

### 5.4 Diagnostics policy

Diagnostics aggregate per requested name using the stable-order pattern from T3.2.

Rules:

- Missing port: zero direct reachable occurrences expose the requested name.
- Fewer-than-two: exactly one direct reachable occurrence exposes the requested name.
- More-than-two: not an error; deterministic pairwise expansion creates all pair constraints.
- Duplicate requested names should be rejected as duplicate requested names rather than silently duplicating work.

If multiple requested names fail, raise one `RuleExprError` with `; `-joined issues sorted by requested name.

### 5.5 Preemptive scope lock

T3.4 applies the T3.3 zero-deviation lesson by explicitly locking likely drift points before implementation:

- Do not add `Rule.join_by_ports(...)`.
- Do not add `RuleOccurrence.join_by_ports(...)`.
- Do not edit T1.4 DTO fields or validation.
- Do not add a new helper module; keep the expansion in `rule_expr.py`.
- Do not add a new error subclass; reuse `RuleExprError(SDKDSLError)`.
- Add `_OrGroup.join_by_ports(...)` as a diagnostic method, matching T3.3 `_OrGroup.join(...)`.

This keeps `.join_by_ports(...)` expression-level and prevents a T3.2-style mid-impl method-discovery drift.

### 5.6 AND-only enforcement

Only `_AndGroup` performs expansion.

Add `_OrGroup.join_by_ports(...)` that raises `RuleExprError` with guidance to distribute the join-by-ports call into each AND branch.

Single application `Rule` and `RuleOccurrence` intentionally have no `.join_by_ports(...)`; callers must first compose an AND expression.

### 5.7 Validation ordering

`_AndGroup.join_by_ports(...)` should:

1. validate explicit name shapes (non-empty strings) and detect duplicate requested names.
2. gather direct reachable operands via T3.3 `_reachable_operands(...)`.
3. build diagnostics for missing/fewer-than-two names.
4. expand valid names pairwise into `RuleJoinConstraint` values via T3.3 `.eq(...)`.
5. call `self.join(*constraints)` so T3.3 shape validation, same-occurrence validation, normalization, dedupe, and reach validation remain canonical.

## 6. Invariants

- T3.4 is a pure expansion layer over T3.3 join mechanics.
- T3.3 `.join(...)`, `RuleJoinConstraint`, reach validation, symmetry, dedupe, and `_combine("and", ...)` join merge behavior remain unchanged.
- T1.4 `Rule`, `RuleOccurrence`, `RulePortRef`, alias regex, and port APIs remain unchanged.
- T1.3 staged naming remains unchanged; `factgraph.sdk.Rule` remains legacy.
- T2.3 aggregate substrate and adapters are untouched.
- T3.1 bool guards, public exports, join-free boolean composition, and cross-type equality negative-action gates remain unchanged.
- T3.2 alias uniqueness, repeated-rule explicit alias validation, deterministic diagnostics, and alias-aware canonical operands remain unchanged.
- T3.3 9 negative-action gates remain preserved.
- `.join_by_ports(...)` never silently joins same-name ports unless the caller explicitly names that port in the method call.

## 7. Acceptance

- [ ] `(a & b).join_by_ports("user")` equals `(a & b).join(a.user.eq(b.user))`.
- [ ] Pairwise expansion for three occurrences produces three normalized constraints and is equal/hash-equal to the equivalent explicit `.join(...)` expression.
- [ ] More-than-two occurrence expansion is deterministic and does not raise an ambiguity error.
- [ ] Missing requested port names raise `RuleExprError` with the missing name.
- [ ] Names present on exactly one direct reachable occurrence raise `RuleExprError` with fewer-than-two guidance.
- [ ] Multiple invalid requested names aggregate diagnostics in stable order.
- [ ] Duplicate requested names raise `RuleExprError`.
- [ ] Zero-name `.join_by_ports()` raises `RuleExprError`.
- [ ] Non-string or empty requested names raise `RuleExprError`.
- [ ] `(a | b).join_by_ports("user")` raises `RuleExprError` with AND-branch distribution guidance.
- [ ] `hasattr(rule, "join_by_ports")` and `hasattr(rule.as_("a"), "join_by_ports")` remain false.
- [ ] `(a & (b | c)).join_by_ports("user")` does not look through the OR branch; diagnostics reflect only direct AND-spine operands.
- [ ] T3.3 `.join(...)` tests continue to pass unchanged.
- [ ] T1.4 application protocol tests pass unchanged.
- [ ] T1.3 SDK naming tests pass unchanged.
- [ ] T2.3 aggregate tests pass unchanged.
- [ ] Ruff passes on touched files.

## 8. Implementation Plan

1. Record G7 baseline in the audit log before implementation:

   ```bash
   PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v
   ```

   Expected baseline after T3.3: 55 tests OK.

2. Add `_AndGroup.join_by_ports(...)`.

3. Add `_OrGroup.join_by_ports(...)` diagnostic method.

4. Add private helpers in `rule_expr.py`:
   - `_validate_join_by_port_names(...)`
   - `_expand_join_by_ports(...)`
   - optionally `_port_refs_for_name(...)`

5. Ensure expansion delegates to `self.join(*constraints)`.

6. Add tests in `tests/application/protocol/test_rule_expr.py` covering all acceptance gates.

7. Run targeted gates:

   ```bash
   PYTHONPATH=src python -m unittest \
     tests.application.protocol.test_rule \
     tests.application.protocol.test_rule_expr \
     tests.sdk.test_rule_naming \
     tests.application.protocol.test_rule_aggregate \
     -v
   ```

8. Run ruff on touched files:

   ```bash
   python -m ruff check \
     src/factgraph/application/protocol/rule_expr.py \
     tests/application/protocol/test_rule_expr.py
   ```

## 9. Docs

No tutorial or example docs are required in T3.4. T3.6 owns RuleExpr user-facing docs and examples, including `.eq(...)`, `.join(...)`, `.join_by_ports(...)`, bool guards, inspect examples, and precedence/parentheses guidance.

If API-surface docs already list RuleExpr methods at implementation time, add a minimal `.join_by_ports(...)` mention there; otherwise defer user-facing docs to T3.6.

## 10. Outcome / Deviations

### Final Landed Code

- `src/factgraph/application/protocol/rule_expr.py`: added `from itertools import combinations`, `_AndGroup.join_by_ports(*explicit_names) -> _AndGroup` as a thin delegate, `_OrGroup.join_by_ports(...)` as an AND-only diagnostic raise method, and private `_validate_join_by_port_names`, `_expand_join_by_ports`, and `_port_refs_for_name` helpers. The implementation follows the §5.7 five-step ordering: validate name shapes and duplicates, gather reachable operands, build stable diagnostics, expand pairwise constraints, then delegate to T3.3 `.join(...)`.
- `tests/application/protocol/test_rule_expr.py`: added 8 T3.4 tests in `RuleExprJoinByPortsTests`, covering explicit `.join(...)` equivalence, pairwise expansion for more than two occurrences, missing and fewer-than-two diagnostics, duplicate requested names, zero/empty/non-string names, AND-only enforcement, OR-branch reach exclusion, and the bonus `test_join_by_ports_preserves_export_scope` scope-boundary check.

### Test Gates

- G7 baseline `81285e98`: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 55 tests OK.
- Post-implementation core gate: the same command ran 63 tests OK (55 baseline + 8 T3.4 tests).
- Cross-slice gate: adding `tests.sdk.test_rule_naming` and `tests.application.protocol.test_rule_aggregate` ran 72 tests OK.
- Ruff: `python -m ruff check src/factgraph/application/protocol/rule_expr.py tests/application/protocol/test_rule_expr.py` passed clean.

### Deviations / Follow-Ups

T3.4 closed with **zero deviations** from blueprint scope. This is the **second consecutive T3 feat commit** to achieve 0 P0/P1/P2/P3 findings at Step 4.7 review.

The clean result is attributed to the same preemptive blueprint design pattern that worked for T3.3:

- **Preemptive scope locking in §5.5**: 6 explicit "no" locks and 1 explicit "yes" lock were listed before implementation: no `Rule.join_by_ports`, no `RuleOccurrence.join_by_ports`, no T1.4 DTO changes, no new helper module, no new error subclass, no new SDK export, and explicit addition of `_OrGroup.join_by_ports` as a raise diagnostic.
- **Algorithm specification in §5.3**: pseudocode with `itertools.combinations(refs, 2)` for pairwise expansion, plus complexity analysis. Implementation followed this shape directly.
- **Validation ordering in §5.7**: the five-step sequence (name shape + dedup, reachable operands, diagnostics, expand, delegate to T3.3 `.join()`) was implemented as scoped.
- **Diagnostics aggregation in §5.4**: the stable-order aggregation pattern from T3.2/T3.3 was preserved for missing and fewer-than-two port-name diagnostics.

**Bonus discipline**: `test_join_by_ports_preserves_export_scope` actively verifies preemptive lock #6 (no new SDK export). This asserts a scope boundary directly, rather than only testing functional behavior.

**Lesson for future T3 slices**: T3.3 and T3.4 both achieving 0 deviation through the same blueprint pattern demonstrates that preemptive scope locking, algorithm specification, validation-layer ordering, and diagnostics precision are repeatable, not slice-specific. T3.5 inspect and T3.6 docs blueprints should continue this approach.

No T3.4 follow-ups are deferred to T3.5 or later slices.

### Stage 1-3 Traceability

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`.
- Adopted D2 §4.5: `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`.
- Adopted D5 §4.5: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`.
- Stage 3 synthesis §3 T3.4: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`.
- Track plan sync: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` at `9c857d0c`.
- Substrate archives: T1.4 `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`, T3.1 `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`, T3.2 `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`, and T3.3 `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`.

### Archive Readiness

Yes. T3.4 implementation, tests, ruff, deviation review, and traceability records are complete. The blueprint pair is ready to move from `workflow/blueprints/active/` to `workflow/blueprints/archive/`.
