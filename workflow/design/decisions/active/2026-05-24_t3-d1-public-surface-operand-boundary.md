# Q1 Decision: T3 Public Surface And Operand Boundary

- Status: proposed
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: design constraint; locks T3 RuleExpr public imports and operand acceptance during the T1.3 staged naming period.
- Inputs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md` Q1, D1, A1, A13, and T4/T5 naming seam.
  - `workflow/design/decisions/archive/2026-05-23_t1-3-sdk-rule-top-level-naming.md`
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` C23-C26, C28, and C35.
  - `src/factgraph/sdk/__init__.py:1-94` current staged SDK namespace.
- Outputs / Downstream:
  - T3 RuleExpr import/export blueprint.
  - T3 public docs examples.
  - T3-D5 slice split and bool-guard timing.
- Related:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md`
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`
- Depends on: T1.3 accepted naming decision.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

T1.3 adopted an A-staged naming decision: `factgraph.sdk.Rule` remains the legacy SDK DSL rule until the T5 legacy `.eval` / old-rule hard-cut. The new application rule is discoverable as `factgraph.sdk.ApplicationRule`, and the bridge is available as `factgraph.sdk.build_application_rule`.

The parent RuleExpr examples assume a final state where `Rule` means the application rule. T3 must ship before that final hard-cut without confusing legacy `Rule` with application `Rule`.

The Stage 1 audit Q1 surfaced four candidate directions: use `ApplicationRule` operands only, allow application protocol `Rule`, provide a RuleExpr namespace that rejects legacy SDK `Rule`, or defer examples until T5.

## 2. Scope

This decision locks:

- Where RuleExpr public names are exported during T3.
- Which Rule-like objects are valid operands for RuleExpr construction.
- How legacy SDK `Rule` is rejected.
- How docs name RuleExpr examples before T5.
- Whether T3 changes the T1.3 staged `factgraph.sdk.Rule` meaning.

## 3. Non-scope

This decision does not lock:

- Final T5 top-level `Rule` hard-cut behavior.
- Join constraint syntax.
- Inspect return shape.
- Structural equality/hash.
- RuleExpr execution lowering.
- Full field layout of internal `_RuleExpr` / `_AndGroup` / `_OrGroup`.

## 4. Decision

### 4.1 Export RuleExpr authoring surface from `factgraph.sdk`

T3 should expose public authoring names from `factgraph.sdk`:

- `RuleExpr`
- `RuleExprError`
- `ExplicitBoolError`

If factories are implemented in T3.1, `RuleExpr.all(...)` and `RuleExpr.any(...)` are class/static methods on `RuleExpr`, not separate top-level functions.

Internal implementation classes remain non-public:

- `_RuleExpr`
- `_AndGroup`
- `_OrGroup`

They may live in an implementation module, but they must not be exported from `factgraph.sdk`.

### 4.2 Valid operands are application protocol Rules and RuleExpr values

RuleExpr operators and factories accept:

- `factgraph.application.protocol.Rule`
- `factgraph.sdk.ApplicationRule` (same object)
- Existing RuleExpr values

Single application Rules are coerced into a single-rule RuleExpr where APIs accept RuleExpr, satisfying C35.

### 4.3 Legacy SDK `Rule` is rejected explicitly

`factgraph.sdk.Rule` remains the legacy SDK DSL rule during T1.3/T3. T3 RuleExpr construction MUST reject legacy SDK `Rule` operands with a clear error that tells the user to use `build_application_rule(...)` / `ApplicationRule` first.

Reason: accepting legacy SDK `Rule` would silently mix old `.eval` semantics and new RuleExpr semantics before the T5 hard-cut.

### 4.4 T3 does not change the T1.3 staged top-level `Rule`

T3 MUST NOT flip `factgraph.sdk.Rule` to the application Rule. That final flip remains tied to the T5 legacy `.eval` / old-rule hard-cut or a later superseding decision.

### 4.5 Documentation uses `ApplicationRule` and bridge examples before T5

T3 user-facing docs must present examples using:

```python
from factgraph.sdk import ApplicationRule, RuleExpr, build_application_rule
```

or examples where `build_application_rule(...)` produces the operand.

Docs must not imply that `from factgraph.sdk import Rule` is the new application Rule during the staged period.

## 5. Rejected Alternatives

### Option A: Accept legacy SDK `Rule` as a RuleExpr operand

- **Why rejected**: mixes old SDK rule shape with new RuleExpr semantics and undermines T1.3 A-staged naming clarity.

### Option B: Do not export RuleExpr from `factgraph.sdk`

- **Why rejected**: makes a major user-facing authoring feature hard to discover and pushes users toward internal modules.

### Option C: Flip `factgraph.sdk.Rule` in T3

- **Why rejected**: violates the T1.3 accepted decision and expands T3 into the T5 hard-cut migration.

### Option D: Defer all RuleExpr docs until T5

- **Why rejected**: T3 is a user-facing authoring feature; docs can be accurate with `ApplicationRule` and `build_application_rule` during the staged period.

## 6. Supporting Evidence

- T1.3 accepted decision keeps top-level `Rule` legacy and adds `ApplicationRule`.
- `src/factgraph/sdk/__init__.py:1-94` currently exports `Rule`, `LegacyRule`, `ApplicationRule`, and `build_application_rule`, but no RuleExpr names.
- Stage 1 audit D1 flags the parent example naming conflict.
- Parent C35 requires single Rule accepted where RuleExpr is accepted.
- Parent C26 says internal `_RuleExpr` / `_AndGroup` / `_OrGroup` are not public API.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- T3.1 public exports.
- T3 docs examples before T5.
- Legacy SDK Rule rejection tests.
- T3-D5 slice split and bool-guard timing.

### 7.2 Required follow-up actions

The T3.1 blueprint must:

- Export `RuleExpr`, `RuleExprError`, and `ExplicitBoolError` from `factgraph.sdk`.
- Keep `_RuleExpr`, `_AndGroup`, and `_OrGroup` internal.
- Accept application protocol Rule and RuleExpr operands.
- Reject legacy SDK `Rule` operands with an explicit error.
- Preserve `factgraph.sdk.Rule` legacy identity.
- Document staged examples using `ApplicationRule` / `build_application_rule`.

### 7.3 T5 boundary

This decision is compatible with the future T5 hard-cut. At T5, a superseding decision may flip `factgraph.sdk.Rule` and simplify docs. Until then, T3 must preserve T1.3's staged top-level namespace.

## 8. Acceptance Criteria

- [ ] `from factgraph.sdk import RuleExpr, RuleExprError, ExplicitBoolError` works.
- [ ] `_RuleExpr`, `_AndGroup`, and `_OrGroup` are not exported from `factgraph.sdk`.
- [ ] Application protocol Rule operands are accepted.
- [ ] Legacy SDK `Rule` operands are rejected with a clear error.
- [ ] `factgraph.sdk.Rule` remains legacy.
- [ ] Docs avoid final-state `Rule` examples before T5.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-24 | proposed | Decision drafted | Stage 1 audit Q1 required explicit public surface and operand boundary during the T1.3 staged naming period. |

