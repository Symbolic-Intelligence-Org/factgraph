# Task Blueprint: T3.1 Base RuleExpr And Bool Guards

- Status: implemented
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Class: M
- Related Modules:
  - `src/factgraph/application/protocol/rule.py`
  - `src/factgraph/application/protocol/__init__.py`
  - `src/factgraph/_sdk_errors.py`
  - `src/factgraph/sdk/__init__.py`
  - `src/factgraph/sdk/errors.py`
  - `src/factgraph/sdk/dsl/errors.py`
  - `src/factgraph/sdk/dsl/rule.py`
  - `tests/application/protocol/`
  - `tests/sdk/`
- Related Docs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
- Audit Log:
  - [2026-05-24_t3-1-base-ruleexpr-bool-guards.audit.md](./2026-05-24_t3-1-base-ruleexpr-bool-guards.audit.md)

## 1. Problem

T3 RuleExpr is the first L-class track after T1 and T2.3 closure. Stage 1 audit, Stage 2 decisions, and Stage 3 synthesis are complete for the T3 track. T3.1 is the first implementing slice from that chain.

T3.1 must introduce the base RuleExpr authoring value and bool-guard behavior without pulling in joins, occurrence-scope validation, inspect, docs, or execution lowering. It must also preserve the staged T1.3 SDK namespace and T1.4 application Rule equality/hash substrate.

Canonical drivers:

- D1 sections 4.1-4.4: export `RuleExpr`, `RuleExprError`, `ExplicitBoolError`; accept application Rule / RuleExpr operands; reject legacy SDK `Rule`; do not flip `factgraph.sdk.Rule`.
- D4 sections 4.1-4.7: immutable structural RuleExpr values; AND/OR commutative flattening; same-process equality/hash; no cross-type `application_rule == rule_expr` equality.
- D5 section 4.2: T3.1 owns base RuleExpr value and bool guards.
- Synthesis section 3 T3.1: 11 must-include items plus 2 negative-action gates.
- Track plan T3.1 row: synchronized to the post-Q synthesis at `9c857d0c`.

## 2. Goals

1. Add the base public RuleExpr authoring surface:
   - `factgraph.sdk.RuleExpr`
   - `factgraph.sdk.RuleExprError`
   - `factgraph.sdk.ExplicitBoolError`

2. Add internal non-exported RuleExpr implementation types:
   - `_RuleExpr`
   - `_AndGroup`
   - `_OrGroup`

3. Implement base authoring operators and factories:
   - application `Rule & Rule`
   - application `Rule | Rule`
   - RuleExpr mixed with application Rule / RuleExpr
   - `RuleExpr.all(...)`
   - `RuleExpr.any(...)`

4. Implement AND/OR flattening and immutable RuleExpr values.

5. Implement join-free structural equality/hash:
   - AND and OR groups are commutative.
   - nested same-kind groups flatten.
   - AND and OR remain distinct.
   - occurrence aliases and Rule template identity participate as D4 requires.

6. Implement operand boundary from D1:
   - application protocol `Rule` and `factgraph.sdk.ApplicationRule` are valid operands.
   - legacy SDK `Rule` is rejected with a clear `RuleExprError`.
   - `factgraph.sdk.Rule` remains legacy.

7. Implement bool guards:
   - `RuleExpr.__bool__` raises `ExplicitBoolError`.
   - application protocol `Rule.__bool__` raises `ExplicitBoolError`.

8. Preserve two negative-action gates:
   - Do not change legacy SDK `Rule.__bool__`.
   - Do not introduce direct `application_rule == rule_expr` cross-type equality or change T1.4 application Rule `__eq__` / `__hash__`.

## 3. Non-goals

- No `.join(...)` or `RuleJoinConstraint`; T3.3 owns joins.
- No `.join_by_ports(...)`; T3.4 owns it.
- No expression-scope alias uniqueness or repeated-rule validation; T3.2 owns it.
- No `fg.rules.inspect(rule_expr)` or `RuleExprInspect`; T3.5 owns it.
- No T3.6 docs/examples beyond minimal API surface references needed by touched module docs.
- No RuleExpr execution lowering or adapter integration.
- No `factgraph.sdk.Rule` final flip; T5 owns the legacy hard-cut.
- No exact parent `a.user == b.person` join syntax; D2 selected `.eq(...)` for the join slice.
- No stable cross-process RuleExpr content digest; D4 keeps T3.1 at same-process `__hash__`.
- No ADR lifecycle/template cleanup; synthesis section 4 records this as governance follow-up, not a T3.1 blocker.

## 4. Current Context

### 4.1 Shipped substrate

- Application protocol `Rule` is a frozen dataclass with `id`, `version`, `desc`, `where`, and `ports`; T1.4 added `Rule.as_(...)` at `src/factgraph/application/protocol/rule.py:122-124`.
- `RuleOccurrence` and `RulePortRef` are shipped at `src/factgraph/application/protocol/rule.py:127-170`.
- `factgraph.application.protocol.__init__` exports `Rule`, `RuleOccurrence`, `RulePortRef`, and `RuleValidationError` at `src/factgraph/application/protocol/__init__.py:74`.
- T1.3 keeps `factgraph.sdk.Rule` as the legacy SDK DSL Rule and exposes `ApplicationRule` / `build_application_rule` at `src/factgraph/sdk/__init__.py:1-94`.
- Legacy SDK `Rule` lives in `src/factgraph/sdk/dsl/rule.py:53-118`; it must remain untouched for bool behavior.
- No RuleExpr code exists. Stage 1 audit N5 found no `RuleExpr`, `ExplicitBoolError`, `_AndGroup`, `_OrGroup`, or `join_by_ports` code surface.

### 4.2 Prior workflow inputs

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- Stage 2 adopted decisions:
  - D1 public surface and operand boundary
  - D4 structural equality/hash
  - D5 slice split and bool guard timing
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
- Track plan sync: `9c857d0c`

### 4.3 Current failure mode

Application Rule instances currently do not support `&` / `|` as RuleExpr operators and are truthy in boolean contexts. Legacy SDK Rule instances are also truthy. T3.1 must add bool guards only to application Rule and RuleExpr, not legacy SDK Rule.

## 5. Proposed Shape

### 5.1 Module placement

Add a new module:

- `src/factgraph/application/protocol/rule_expr.py`

This module owns:

- `RuleExprError`
- `ExplicitBoolError`
- `RuleExpr`
- internal `_RuleExpr`
- internal `_AndGroup`
- internal `_OrGroup`

Rationale:

- RuleExpr composes application protocol `Rule` objects, not legacy SDK rules.
- D1 requires SDK top-level exports, but implementation belongs with application protocol DTOs.
- Internal implementation names can stay out of SDK public `__all__`.

Update exports:

- `src/factgraph/application/protocol/__init__.py` exports public `RuleExpr`, `RuleExprError`, `ExplicitBoolError`.
- `src/factgraph/sdk/__init__.py` re-exports the same public names.
- `src/factgraph/sdk/dsl/__init__.py` remains unchanged unless a minimal import cycle forces otherwise.

### 5.2 Error hierarchy

`RuleExprError` and `ExplicitBoolError` must follow existing SDK error hierarchy conventions per D1 section 4.1.

Implementation lock:

- `RuleExprError` subclasses `SDKDSLError`.
- `ExplicitBoolError` subclasses `RuleExprError`.

Rationale:

- D1 section 4.1 requires RuleExpr failures to remain catchable through the existing SDK exception buckets.
- `DSLToApplicationRuleError(SDKDSLError)` is the nearest shipped precedent for SDK-facing DSL/application bridge failures.
- More specific SDK-store exceptions are not appropriate because T3.1 is not store/evaluation behavior.
- The implementation may keep the classes in `rule_expr.py`, but the inheritance must stay in the SDK DSL error hierarchy.
- Impl-time import-cycle fallback: direct `rule_expr.py -> factgraph.sdk.dsl.errors` imports execute `factgraph.sdk.__init__` and can cycle back through `factgraph.application`. To preserve class identity without the cycle, T3.1 may introduce a neutral internal `factgraph._sdk_errors` module and have `factgraph.sdk.errors` / `factgraph.sdk.dsl.errors` re-export those same classes. `RuleExprError` may import `SDKDSLError` from the neutral module as long as `issubclass(RuleExprError, factgraph.sdk.dsl.errors.SDKDSLError)` remains true.

### 5.3 Operand coercion

Define a private coercion helper in `rule_expr.py`:

```python
def _coerce_rule_expr_operand(value: object) -> _RuleExpr: ...
```

It accepts:

- application protocol `Rule`
- `RuleExpr` / internal `_RuleExpr`

It rejects:

- legacy SDK `Rule`
- arbitrary objects

Legacy SDK Rule rejection can avoid importing the legacy class directly by checking for the application protocol `Rule` type positively and then producing a clear error for unsupported operands. Tests must cover a real legacy SDK Rule instance.

### 5.4 Public wrapper vs internal types

`RuleExpr` is the public factory/namespace class. Internal values are `_RuleExpr` subclasses or instances.

Implementation may choose either:

- public `RuleExpr` as a lightweight facade with classmethods returning internal `_RuleExpr` values; or
- public `RuleExpr` as a nominal base class for the internal value classes.

Acceptance tests must lock the public surface, not the exact internal inheritance, unless implementation requires it:

- public imports work from `factgraph.sdk`.
- internal `_RuleExpr`, `_AndGroup`, `_OrGroup` are not exported from `factgraph.sdk`.
- operators return a RuleExpr value that supports equality/hash and bool guard.

### 5.5 Operators and factories

Add operator methods to application protocol `Rule`:

- `Rule.__and__(self, other)`
- `Rule.__or__(self, other)`
- `Rule.__bool__(self)`

Adding these methods to the T1.4 frozen application Rule DTO is an additive method change only: `frozen=True` constrains field assignment, not class method definitions.

Add reflected/mixed operators to RuleExpr values:

- `RuleExpr & Rule`
- `Rule & RuleExpr`
- `RuleExpr & RuleExpr`
- same for `|`

Add factories:

- `RuleExpr.all(*operands)`
- `RuleExpr.any(*operands)`

Factories should reject empty input in T3.1. Empty unit semantics are not in parent T3 commitments and would require a separate decision.

### 5.6 Flattening and canonical equality/hash

For join-free T3.1 expressions:

- same-kind nested AND groups flatten.
- same-kind nested OR groups flatten.
- AND/OR child order is normalized for equality/hash.
- AND and OR remain distinct.
- duplicate children are not collapsed unless D4 or a later decision explicitly says set semantics for duplicate rules; T3.1 should preserve multiplicity for repeated-rule detection in T3.2.

This last point is important: D4 says commutative equality, not idempotent set semantics. T3.1 should normalize order, not erase repeated operands.

### 5.7 Rule identity in equality/hash

Per D4 section 4.4, Rule occurrence identity includes:

- application Rule content digest
- application Rule id

T3.1 can represent a single Rule operand as an internal occurrence with default alias `rule.id`, but must not run T3.2 expression-scope repeated-rule validation yet.

### 5.8 Bool guard behavior

Add:

```python
def Rule.__bool__(self) -> NoReturn:
    raise ExplicitBoolError(...)
```

Add:

```python
def RuleExpr.__bool__(self) -> NoReturn:
    raise ExplicitBoolError(...)
```

Error message should mention using `&` / `|` rather than Python `and` / `or`.

Do not add or change `__bool__` on legacy SDK `Rule` in `src/factgraph/sdk/dsl/rule.py`.

### 5.9 Size class rationale

T3.1 is M-class:

- public SDK exports are added.
- application protocol `Rule` gets new operators and `__bool__`.
- error classes and RuleExpr value semantics become public authoring surface.
- Stage 1-3 L-class audit/decision/synthesis already completed for the T3 track, so this per-slice blueprint does not rerun L-class Stage 1-3.

S→M trigger is public API impact and cross-module surface (`application.protocol` + `factgraph.sdk` + tests/docs).

## 6. Boundaries And Invariants

- D1 invariant: `factgraph.sdk.Rule` remains legacy.
- D1 invariant: `factgraph.sdk.ApplicationRule is factgraph.application.protocol.Rule`.
- D1 invariant: legacy SDK Rule operands are rejected.
- D4 invariant: RuleExpr equality with unsupported non-RuleExpr types returns `NotImplemented`.
- D4 invariant: coercion happens at RuleExpr API boundaries, not inside `RuleExpr.__eq__`.
- D4 invariant: T1.4 application Rule `__eq__` / `__hash__` semantics do not change.
- D5 invariant: legacy SDK `Rule.__bool__` does not change in T3.1.
- Synthesis invariant: execution lowering is out of scope.
- Synthesis invariant: direct `application_rule == rule_expr` cross-type equality is not introduced.
- T1.4 invariant: `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, and port APIs remain unchanged.
- T2.3 invariant: aggregate substrate/adapters remain untouched.

## 7. Acceptance

- [ ] `from factgraph.sdk import RuleExpr, RuleExprError, ExplicitBoolError` works.
- [ ] `factgraph.sdk` does not export `_RuleExpr`, `_AndGroup`, or `_OrGroup`.
- [ ] `factgraph.application.protocol` exports `RuleExpr`, `RuleExprError`, and `ExplicitBoolError`.
- [ ] Application protocol `Rule & Rule` and `Rule | Rule` produce RuleExpr values.
- [ ] `RuleExpr.all(rule_a, rule_b)` equals `rule_a & rule_b`.
- [ ] `RuleExpr.any(rule_a, rule_b)` equals `rule_a | rule_b`.
- [ ] `RuleExpr.all` and `RuleExpr.any` are classmethods or staticmethods on `RuleExpr`; no module-level `factgraph.sdk.all` or `factgraph.sdk.any` exists.
- [ ] Nested same-kind AND and OR groups flatten for equality/hash.
- [ ] AND/OR child order is commutative for equality/hash.
- [ ] AND and OR expressions remain unequal.
- [ ] Duplicate operands are preserved for equality/hash multiplicity.
- [ ] RuleExpr values are immutable: `_RuleExpr` / `_AndGroup` / `_OrGroup` are frozen dataclasses or equivalent immutable structures, and field assignment raises.
- [ ] `bool(rule_expr)` raises `ExplicitBoolError`.
- [ ] `bool(application_rule)` raises `ExplicitBoolError`.
- [ ] `bool(legacy_sdk_rule)` behavior is unchanged from pre-T3.1.
- [ ] `_coerce_rule_expr_operand` accepts application Rule and `_RuleExpr` values, and rejects legacy SDK Rule and arbitrary objects with `RuleExprError`.
- [ ] Legacy SDK `Rule` operands are rejected with `RuleExprError` and a message that points to `build_application_rule(...)` / `ApplicationRule`.
- [ ] `application_rule == rule_expr` does not return True and does not alter application Rule equality/hash.
- [ ] Direct equality with arbitrary objects follows Python convention and does not raise.
- [ ] Existing T1.4 tests for `Rule.as_`, `RuleOccurrence`, `RulePortRef`, and content digest still pass.
- [ ] Existing T1.3 top-level SDK alias tests still pass.
- [ ] T2.3a-d aggregate tests remain untouched and pass in the targeted cross-slice suite.
- [ ] Ruff passes on touched Python files.

## 8. Implementation Plan

1. Record G7 precondition in the audit log before code:
   - verify no RuleExpr symbols exist in shipped code.
   - verify `factgraph.sdk.Rule` is legacy and `ApplicationRule` is application Rule.
   - verify application Rule currently has no custom `__bool__`.
   - verify legacy SDK Rule currently has no custom `__bool__`.
   - run `pytest tests/application/protocol/test_rule.py -v` before changes and record the baseline pass count for post-implementation comparison.

2. Add `src/factgraph/application/protocol/rule_expr.py` with errors, public `RuleExpr`, internal value types, operand coercion, flattening, equality/hash, and bool guard. If needed to avoid application/SDK import cycles, add neutral SDK error re-export support as described in §5.2.

3. Add application `Rule` operator methods and `__bool__` in `src/factgraph/application/protocol/rule.py`.

4. Export public RuleExpr names from `src/factgraph/application/protocol/__init__.py`.

5. Export public RuleExpr names from `src/factgraph/sdk/__init__.py`; do not export internal types.

6. Add T3.1 tests:
   - public exports.
   - operator/factory equivalence.
   - flattening and commutative equality/hash.
   - bool guards.
   - legacy SDK Rule rejection.
   - negative-action gates.

7. Run targeted test gates:
   - new T3.1 tests.
   - T1.3 SDK naming tests.
   - T1.4 application Rule tests.
   - T2.3 aggregate targeted suites.

8. Run ruff on touched Python files.

9. Fill §10 Outcome and close/archive after review.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`:
  - Mention RuleExpr base surface only if needed to document `Rule.__bool__` and operator availability.
  - Do not document joins, inspect, or full examples; T3.6 owns user-facing docs/examples.

- `src/factgraph/sdk/docs/04_api_surface.en.md`:
  - Add minimal API surface entries for `RuleExpr`, `RuleExprError`, `ExplicitBoolError`, including the §5.2 lock that `RuleExprError` subclasses `SDKDSLError`.
  - Do not add tutorial examples; T3.6 owns them.

No `sdk/docs/03_rules_and_inferences.en.md` tutorial update in T3.1 unless reviewer requires a minimal warning for bool guards. Full tutorial docs are T3.6.

## 10. Outcome / Deviations

### Final Landed Code

T3.1 landed in `e049c93e` after the G7 baseline commit `febe7028` and the import-cycle fallback scope amendment `8de03372`.

Landed files:

- `src/factgraph/application/protocol/rule_expr.py` — public `RuleExpr`, `RuleExprError`, `ExplicitBoolError`; internal frozen `_RuleExpr`, `_RuleOperand`, `_AndGroup`, `_OrGroup`; operand coercion; flattening; equality/hash; bool guard.
- `src/factgraph/application/protocol/rule.py` — additive `Rule.__and__`, `Rule.__or__`, and `Rule.__bool__` methods.
- `src/factgraph/application/protocol/__init__.py` — public RuleExpr exports.
- `src/factgraph/sdk/__init__.py` — SDK top-level RuleExpr re-exports; no module-level `all` / `any`.
- `src/factgraph/_sdk_errors.py`, `src/factgraph/sdk/errors.py`, `src/factgraph/sdk/dsl/errors.py` — neutral SDK error base re-export support preserving `SDKDSLError` class identity while avoiding application/SDK import cycles.
- `tests/application/protocol/test_rule_expr.py` — T3.1 acceptance tests.
- `src/factgraph/application/docs/rule.md` and `src/factgraph/sdk/docs/04_api_surface.en.md` — minimal API/docs updates.

### Test Gates

- G7 fallback baseline before code: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule -v` → 23 tests OK.
- Core post-implementation gate: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` → 38 tests OK.
- Cross-slice gate: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_rule_naming tests.test_sdk_error_hierarchy tests.sdk.dsl.test_application_rule tests.sdk.dsl.test_aggregate_ergonomic tests.core.rules.test_aggregate_substrate tests.core.rules.test_aggregate_eval tests.application.protocol.test_rule_aggregate -v` → 88 tests OK.
- Ruff: `python -m ruff check` on touched Python files → all checks passed.

### Deviations / Follow-Ups

- (A-fallback) Directly importing `factgraph.sdk.dsl.errors.SDKDSLError` from `application.protocol.rule_expr` triggered an application/SDK package cycle. T3.1 introduced `factgraph._sdk_errors` as a neutral internal source of SDK error classes, with `factgraph.sdk.errors` and `factgraph.sdk.dsl.errors` re-exporting the same class objects. This preserves `issubclass(RuleExprError, factgraph.sdk.dsl.errors.SDKDSLError)` and the D1 error-bucket requirement.
- Pytest remains an environment/tooling issue in this workspace: pytest exits with returncode `-11` and no output. T3.1 uses the recorded unittest fallback baseline; the pytest SIGSEGV investigation is out of T3.1 scope.
- Step 4.7 review found 0 P0/P1/P2 and 3 minor P3 type-precision follow-ups: add `-> _RuleExpr` return annotations on `Rule.__and__` / `Rule.__or__`, narrow `_RuleOperand.rule` from `object` to `Rule`, and optionally replace the duck-typed legacy SDK Rule detector if a cycle-safe nominal check becomes available. These do not block closure and are deferred to T3.2 or a cleanup slice.

### Stage 1-3 Traceability

T3.1 consumes the completed T3 audit-to-synthesis chain:

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- Adopted D1 / D4 / D5 decision docs in `workflow/design/decisions/active/`
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
- Track plan sync: `9c857d0c`

### Archive Readiness

Ready. Blueprint and audit log are `implemented`; active pair can be moved to `workflow/blueprints/archive/` with no content edits.
