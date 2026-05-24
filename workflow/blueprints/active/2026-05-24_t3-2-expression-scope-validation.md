# Task Blueprint: T3.2 Expression-Scope Occurrence Validation

- Status: implemented
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Class: S
- Related Modules:
  - `src/factgraph/application/protocol/rule_expr.py`
  - `src/factgraph/application/protocol/rule.py`
  - `tests/application/protocol/test_rule_expr.py`
- Related Docs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
- Audit Log:
  - [2026-05-24_t3-2-expression-scope-validation.audit.md](./2026-05-24_t3-2-expression-scope-validation.audit.md)

## 1. Problem

T3.1 shipped the base RuleExpr tree, `&` / `|` composition, bool guards, and join-free equality/hash. It intentionally preserved duplicate operands and did not validate expression-scope occurrence aliases.

T3.2 must add the expression-scope rules that Stage 3 synthesis assigned to this slice:

- alias uniqueness within one RuleExpr.
- repeated same Rule requires explicit aliases.
- default alias behavior when a Rule appears once.
- diagnostics for duplicate aliases and repeated unaliased Rules.

This must consume T1.4's shipped `Rule.as_(...)`, `RuleOccurrence`, `RulePortRef`, and alias regex rather than re-shipping those substrates.

Accepting `RuleOccurrence` as a RuleExpr operand is a prerequisite for the "repeated same Rule requires explicit aliases" must-include, not a scope expansion — it operationalizes the T1.4 substrate that D5 §4.3 explicitly cites.

Canonical drivers:

- D5 section 4.3: T3.2 owns expression-scope validation only; T1.4 already owns `.as_`, `RuleOccurrence`, `RulePortRef`, and alias regex validation.
- Synthesis section 3 T3.2: dependencies are T3.1 base RuleExpr tree and T1.4 occurrence substrate; four must-include validation items.
- Track plan T3.2 row at `9c857d0c`: expression-scope occurrence validation only, scope narrowed by T1.4 substrate.
- T3.1 closure §10: 3 minor type-precision follow-ups deferred to the next adjacent slice.

## 2. Goals

1. Accept `RuleOccurrence` as a RuleExpr operand.

2. Represent every Rule operand internally with an occurrence alias:
   - bare application `Rule` uses default alias `rule.id`.
   - `RuleOccurrence` uses its explicit `alias`.

3. Enforce alias uniqueness within the composed RuleExpr.

4. Enforce repeated same Rule requires explicit aliases:
   - a Rule appearing once may be bare.
   - a Rule appearing multiple times must appear through explicit `rule.as_(...)` occurrences for every occurrence.
   - `rule.as_("a") & rule.as_("b")` is valid.
   - `rule & rule` and `rule & rule.as_("b")` are invalid.

5. Emit stable diagnostics for duplicate aliases, repeated unaliased Rules, and invalid default aliases.

6. Inline T3.1 low-risk type-precision follow-ups:
   - add `-> _RuleExpr` return annotations to application `Rule.__and__` / `Rule.__or__`.
   - tighten `_RuleOperand.rule` from `object` to application `Rule`.

## 3. Non-goals

- No `.join(...)` or `RuleJoinConstraint`; T3.3 owns joins.
- No `.join_by_ports(...)`; T3.4 owns it.
- No `fg.rules.inspect(rule_expr)` or `RuleExprInspect`; T3.5 owns inspect.
- No user-facing T3 docs/examples; T3.6 owns docs and examples.
- No RuleExpr execution lowering or adapter integration.
- No changes to T1.4 `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex validation, or port APIs.
- No changes to T1.3 staged SDK naming; `factgraph.sdk.Rule` remains legacy.
- No changes to T2.3 aggregate substrate or adapters.
- No direct `application_rule == rule_expr` cross-type equality.
- No replacement of the T3.1 duck-typed `_is_legacy_sdk_rule` check unless G7 or implementation proves a cycle-safe nominal check is available. The current duck-typed check is deliberately retained to avoid an application/SDK import cycle.

## 4. Current Context

### 4.1 T1.4 substrate already shipped

- Application `Rule.as_(alias: str | None = None)` exists at `src/factgraph/application/protocol/rule.py:122-124`.
- `RuleOccurrence` exists at `src/factgraph/application/protocol/rule.py:154-181`.
- `RulePortRef` exists at `src/factgraph/application/protocol/rule.py:142-151`.
- Alias validation uses `_validate_occurrence_alias(...)` at `src/factgraph/application/protocol/rule.py:186-191`.

T3.2 must call or reuse this substrate. It must not duplicate alias regex logic in `rule_expr.py`.

### 4.2 T3.1 base RuleExpr tree already shipped

- Public `RuleExpr`, `RuleExprError`, `ExplicitBoolError` exist at `src/factgraph/application/protocol/rule_expr.py:9-41`.
- Internal frozen `_RuleExpr`, `_RuleOperand`, `_AndGroup`, `_OrGroup` exist at `src/factgraph/application/protocol/rule_expr.py:47-82`.
- `_coerce_rule_expr_operand(...)` accepts application `Rule` and `_RuleExpr` at `src/factgraph/application/protocol/rule_expr.py:85-97`.
- `_combine(...)` flattens same-kind groups and preserves duplicate operands at `src/factgraph/application/protocol/rule_expr.py:100-116`.
- T3.1 tests verify duplicate multiplicity is preserved and `application_rule == rule_expr` cross-type equality is not introduced.

### 4.3 Current failure mode

Current T3.1 behavior allows expression shapes that T3.2 must reject:

- `rule & rule` currently builds an `_AndGroup` with two bare `_RuleOperand` children.
- `rule & rule.as_("b")` is not accepted yet because `RuleOccurrence` is not a RuleExpr operand; after T3.2 it should be accepted syntactically but rejected semantically because the repeated Rule includes a bare occurrence.
- `rule.as_("a") & other_rule.as_("a")` is not accepted yet; after T3.2 it should be rejected for duplicate alias.

## 5. Proposed Shape

### 5.1 Module placement

Extend the existing T3.1 module:

- `src/factgraph/application/protocol/rule_expr.py`

No new public SDK exports are required. T3.2 reuses `RuleExprError` for diagnostics.

Rationale:

- D5 defines T3.2 as validation over the existing RuleExpr tree.
- Introducing a public `RuleExprAliasError` would fire an M-class public-surface trigger without current need.
- `RuleExprError(SDKDSLError)` is already the correct public bucket from T3.1 / D1.

### 5.2 Internal operand shape

Change `_RuleOperand` from:

```python
@dataclass(frozen=True, eq=False)
class _RuleOperand(_RuleExpr):
    rule: object
```

to:

```python
@dataclass(frozen=True, eq=False)
class _RuleOperand(_RuleExpr):
    rule: Rule
    alias: str
    explicit_alias: bool
```

Rules:

- bare application `Rule` -> `_RuleOperand(rule=rule, alias=rule.id, explicit_alias=False)`.
- `RuleOccurrence` -> `_RuleOperand(rule=occ.rule, alias=occ.alias, explicit_alias=True)`.
- `_RuleExpr` input remains accepted unchanged.

### 5.3 Default alias validation

Bare Rule operands inherit `alias = rule.id`. The inherited alias must pass T1.4 alias validation.

Implementation should call `rule.as_()` or `_validate_occurrence_alias(...)` rather than duplicating the regex. Preferred implementation:

```python
occ = rule.as_()
return _RuleOperand(rule=occ.rule, alias=occ.alias, explicit_alias=False)
```

If `rule.id` is not identifier-shaped, `_coerce_rule_expr_operand(rule)` should raise `RuleExprError` with guidance to call `rule.as_("custom_alias")`. This mirrors the T1.4 edge-case contract rather than silently accepting invalid aliases.

### 5.4 Expression-scope validation pass

Add a private validation helper:

```python
def _validate_expression_scope(expr: _RuleExpr) -> None: ...
```

`_combine(...)` should build and flatten the expression first, then validate the resulting expression before returning it.

The helper traverses all `_RuleOperand` leaves and checks:

1. Alias uniqueness across all operands in the expression.
2. Repeated same Rule identity requires every occurrence of that Rule to have `explicit_alias=True`.

Rule identity for repeated-rule detection follows T3.1/D4:

```python
(rule.id, rule.content_digest)
```

This preserves D4's identity contract and does not add cross-type equality.

### 5.5 Diagnostic policy

Diagnostics should be deterministic and aggregated into one `RuleExprError` where practical.

Preferred message shape:

```text
RuleExpr occurrence validation failed: duplicate alias 'u'; rule 'orders_total' appears multiple times without explicit aliases
```

Policy:

- collect duplicate aliases in stable sorted order.
- collect repeated Rule identities with any bare occurrence in stable `(rule.id, content_digest)` order.
- raise one `RuleExprError` with all collected issues joined by `; `.
- if alias validation fails while deriving a bare Rule default alias, wrap the underlying `RuleValidationError` in `RuleExprError` and include "use .as_(...)" guidance. This may fail before aggregate collection because the operand cannot be represented.

Rationale:

- T3.2's purpose is diagnostics. Aggregating duplicate alias and repeated-unaliased issues avoids fix-one-error-per-run churn.
- Default-alias invalidity is an operand construction error and can fail immediately.

### 5.6 Canonical equality/hash update

`_RuleOperand._canonical()` must include alias:

```python
return ("rule", _rule_identity(self.rule), self.alias)
```

T3.2 §5.6 implements D4 §4.3 "alias 参与 identity" for `_RuleOperand`. T3.1 had no alias concept so D4 §4.3 was vacuously true; T3.2 makes alias identity operational at the canonical tuple level.

Consequences:

- `rule & other` uses default aliases.
- `rule.as_("a") & other` is not equal to `rule.as_("b") & other`.
- repeated explicit aliases are still rejected before equality/hash is observed.
- no direct `application_rule == rule_expr` equality is introduced.

### 5.7 T3.1 P3 follow-up handling

Inline:

- add `-> _RuleExpr` return annotations to `Rule.__and__` and `Rule.__or__` in `src/factgraph/application/protocol/rule.py`.
- tighten `_RuleOperand.rule` typing to `Rule` as part of §5.2.

Defer:

- `_is_legacy_sdk_rule` stays duck-typed unless a cycle-safe nominal check appears during G7 or implementation. This is an explicit preservation choice, not an omitted cleanup.

## 6. Invariants

- T1.4 `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, and port APIs remain unchanged.
- T3.1 public exports and bool guards remain unchanged.
- T3.1 negative-action gates remain intact:
  - legacy SDK `Rule.__bool__` unchanged.
  - no direct `application_rule == rule_expr` cross-type equality.
  - T1.4 application Rule `__eq__` / `__hash__` unchanged.
- Duplicate operands are still physically representable internally, but invalid expression-scope combinations are rejected before returning to callers.
- T3.1 `test_duplicate_operands_preserve_multiplicity` will be updated to use explicit occurrence aliases. T3.2 enforces the uniqueness contract at the `_combine` API boundary, not at the canonical tuple level — internal `_RuleOperand` multiplicity preservation remains intact at the data-structure level.
- No T3.3 join semantics are introduced.
- No T3.5 inspect semantics are introduced.
- No T2.3 aggregate code changes.

## 7. Acceptance

- [ ] `rule & other_rule` succeeds when both Rules appear once and uses default aliases equal to each Rule id.
- [ ] `rule.as_("a") & other_rule.as_("b")` succeeds.
- [ ] `rule & rule` raises `RuleExprError` explaining repeated same Rule requires explicit aliases.
- [ ] `rule & rule.as_("b")` raises `RuleExprError` because the repeated Rule includes a bare occurrence.
- [ ] `rule.as_("a") & rule.as_("b")` succeeds and compares unequal to `rule.as_("c") & rule.as_("d")`.
- [ ] `rule.as_("same") & other_rule.as_("same")` raises `RuleExprError` explaining duplicate alias.
- [ ] A combined expression with both duplicate alias and repeated bare Rule emits one aggregated deterministic `RuleExprError` message containing both issues.
- [ ] Bare Rule with non-identifier `rule.id` raises `RuleExprError` with `.as_(...)` guidance when used as a RuleExpr operand.
- [ ] `RuleOccurrence` remains frozen/hashable and T1.4 tests continue to pass unchanged.
- [ ] `_RuleOperand.rule` is typed as application `Rule`; `Rule.__and__` and `Rule.__or__` have `-> _RuleExpr` annotations.
- [ ] `_is_legacy_sdk_rule` behavior remains covered by T3.1 legacy SDK Rule rejection tests.
- [ ] `RuleExpr.all(...)` and `RuleExpr.any(...)` apply the same expression-scope validation as `&` / `|`.
- [ ] Legacy SDK `Rule` remains rejected as a RuleExpr operand.
- [ ] `application_rule == rule_expr` remains false / non-cross-type; application Rule `__eq__` / `__hash__` unchanged.
- [ ] T3.1 core tests pass after `test_duplicate_operands_preserve_multiplicity` is updated to use explicit occurrence aliases (a deliberate cross-slice contract supersedence required by T3.2 Goal #4); T1.4 application protocol tests pass unchanged.
- [ ] T1.3 SDK naming tests pass.
- [ ] At least one T2.3 aggregate cross-slice suite passes, proving no aggregate regression.
- [ ] Ruff clean on touched Python files.

## 8. Implementation Plan

1. G7 precondition record before code edits:
   - verify branch / sacred / dirty set.
   - run `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v`.
   - grep shipped `_RuleOperand`, `_coerce_rule_expr_operand`, `_combine`, and T1.4 `RuleOccurrence` line ranges.
   - record in audit log before edits.

2. Extend `src/factgraph/application/protocol/rule_expr.py`:
   - import application `Rule` and `RuleOccurrence` in a cycle-safe way.
   - update `_RuleOperand` fields.
   - update `_coerce_rule_expr_operand(...)` to accept `RuleOccurrence`.
   - add default alias validation and error wrapping.
   - add `_validate_expression_scope(...)`.
   - update `_RuleOperand._canonical()`.

3. Add T3.1 type-precision follow-up in `src/factgraph/application/protocol/rule.py`:
   - annotate `Rule.__and__` and `Rule.__or__` as returning `_RuleExpr`.
   - use local import / `TYPE_CHECKING` as needed to avoid cycles.

4. Add focused tests to `tests/application/protocol/test_rule_expr.py`:
   - success cases.
   - duplicate alias.
   - repeated unaliased Rule.
   - mixed bare + explicit repeated Rule.
   - aggregated diagnostics.
   - non-identifier default alias guidance.
   - factory parity.
   - type-precision assertions.
   - update T3.1 `test_duplicate_operands_preserve_multiplicity` to use `rule.as_("a1")` / `rule.as_("a2")` for explicit-alias repeated occurrences; the multiplicity preservation assertion semantics are preserved but expressed through valid T3.2 expressions.

5. Run targeted tests:
   - `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v`
   - `PYTHONPATH=src python -m unittest tests.sdk.test_rule_naming -v`
   - one T2.3 aggregate suite, e.g. `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule_aggregate -v`

6. Run ruff on touched Python files.

7. Fill §10 Outcome after implementation and archive only after review pass.

## 9. Docs

No user-facing T3 docs/examples in this slice; T3.6 owns complete docs.

Optional minimal module docs are not required because T3.2 changes validation behavior in an existing T3.1 module and remains covered by tests. If implementation updates `application/docs/rule.md`, keep it to one sentence clarifying that expression-scope alias uniqueness is enforced by RuleExpr, not by `RuleOccurrence` itself.

## 10. Outcome / Deviations

### Final Landed Code

- `src/factgraph/application/protocol/rule_expr.py`: `_RuleOperand` now carries `alias` and `explicit_alias`; `_coerce_rule_expr_operand(...)` accepts `RuleOccurrence`, derives validated default aliases for bare application `Rule`, wraps invalid default aliases in `RuleExprError` with `.as_(...)` guidance, runs `_validate_expression_scope(...)`, aggregates deterministic duplicate-alias / repeated-bare-rule diagnostics, and includes alias in `_RuleOperand._canonical()`.
- `src/factgraph/application/protocol/rule.py`: `Rule.__and__` and `Rule.__or__` now carry `-> _RuleExpr` return annotations via `TYPE_CHECKING` + forward reference. `RuleOccurrence.__and__` and `RuleOccurrence.__or__` were added as a necessary discovered additive method change for explicit-alias infix expressions; see Deviations.
- `tests/application/protocol/test_rule_expr.py`: `test_duplicate_operands_preserve_multiplicity` now uses explicit occurrence aliases, and T3.2 coverage verifies `RuleOccurrence` operands, repeated-rule alias requirements, duplicate aliases, aggregate diagnostics, non-identifier default-alias guidance, factory parity, alias metadata, frozen fields, and type precision.

### Test Gates

- G7 baseline `62c04100`: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 38 tests OK.
- Post-implementation core gate: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 45 tests OK.
- Cross-slice gate: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate -v` ran 54 tests OK.
- Ruff: `python -m ruff check src/factgraph/application/protocol/rule_expr.py src/factgraph/application/protocol/rule.py tests/application/protocol/test_rule_expr.py` passed clean.

### Deviations / Follow-Ups

- **`RuleOccurrence.__and__` / `__or__` scope expansion**: T3.2 blueprint §5.5 listed `_RuleOperand` field additions and §3 non-goals stated no changes to T1.4 `RuleOccurrence` / port APIs. Implementation discovered that `rule.as_("a") & other_rule.as_("b")` requires `RuleOccurrence.__and__` because Python operator resolution cannot delegate to application `Rule.__and__` for a left-hand `RuleOccurrence`. Two methods (`__and__`, `__or__`) were added to `RuleOccurrence` in feat `2a16dd98` as a necessary additive change. This is method-only, preserves frozen dataclass field semantics, preserves all T1.4 alias regex / port API / `Rule.as_` / `RulePortRef` behavior, and is operationally required for explicit-alias infix expressions.

  **Pattern correction for future slices**: this scope expansion should have followed the (A-fallback) discipline established by T3.1 `8de03372` — a pre-feat doc-only blueprint scope amendment commit, then feat. It was bundled into feat for expedience, which is a process discipline drift. Future T3.x slices discovering necessary operator or dunder additions should pause for a pre-feat scope amendment commit before bundling the change into feat.

- **T3.1 P3 follow-ups landed inline as planned**: `Rule.__and__` / `Rule.__or__` gained `-> _RuleExpr` return annotations via `TYPE_CHECKING` + forward reference; `_RuleOperand.rule` typing tightened from `object` to application `Rule`. The duck-typed `_is_legacy_sdk_rule` detector remains in place per §5.7 and §3 non-goals because no cycle-safe nominal check appeared.
- **T3.1 `test_duplicate_operands_preserve_multiplicity` updated**: the test now uses `rule.as_("a1") & rule.as_("a2") & b` per §6 invariant and §7 acceptance #15 supersedence. Multiplicity preservation semantics remain covered through explicit aliases while invalid bare repeated-rule expressions are rejected at the `_combine` API boundary.

### Stage 1-3 Traceability

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`.
- Stage 2 governing decision: D5 §4.3 in `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`.
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` §3 T3.2.
- Track plan sync: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` synced at `9c857d0c`.
- Shipped substrate references: T1.4 archive `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md` and T3.1 archive `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`.

### Archive Readiness

Yes. The blueprint and audit log are implemented, Step 4.7 review found no functional blockers or required code fixes, and the only P2 was recorded above as a process-discipline deviation.
