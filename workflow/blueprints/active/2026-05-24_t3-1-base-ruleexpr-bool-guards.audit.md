# Task Blueprint Audit: T3.1 Base RuleExpr And Bool Guards

- Blueprint: [2026-05-24_t3-1-base-ruleexpr-bool-guards.md](./2026-05-24_t3-1-base-ruleexpr-bool-guards.md)
- Status: scoped
- Created: 2026-05-24
- Last Updated: 2026-05-24

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | draft | Blueprint created | Initial T3.1 M-class scope recorded from Stage 1 audit, adopted D1/D4/D5 decisions, Stage 3 synthesis, and synced track plan. |
| 2026-05-24 | draft | P2 tightening | Step 4.2 review found the error hierarchy violated adopted D1 and the acceptance gates omitted RuleExpr immutability. Blueprint now locks `RuleExprError(SDKDSLError)` and adds an immutable RuleExpr acceptance check. |
| 2026-05-24 | scoped | Scope locked | Status advanced to scoped with P3 acceptance/implementation precision added: frozen DTO method-addition rationale, factory export acceptance, concrete G7 baseline command, required SDK API docs update, and operand coercion acceptance. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- Stage 2 adopted decisions:
  - D1 `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md`
  - D4 `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
  - D5 `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
- Track plan sync: `9c857d0c`

### G1-G7 Visible Mapping

| Gate | T3.1 mapping |
|---|---|
| G1 | Canonical source chain is parent C23-C27/C33-C35 via Stage 1 audit + adopted D1/D4/D5 + Stage 3 synthesis, not raw parent interpretation alone. |
| G2 | Blueprint §4 lists shipped source surfaces read in Stage 1; implementation must rerun G7 preconditions before code. |
| G3 | File:line citations are from Stage 1 audit and shipped source cited in §4. |
| G4 | Goals map to D1 public surface, D4 equality/hash, D5 bool timing, and synthesis T3.1 gates. |
| G5 | Non-goals explicitly defer joins, occurrence-scope validation, inspect, docs/examples, execution lowering, final Rule flip, and ADR lifecycle cleanup. |
| G6 | Reviewer should spot-check D1/D4/D5 traceability, negative-action gates, and T1.3/T1.4 substrate preservation. |
| G7 | §8 step 1 requires pre-implementation checks recorded in this audit log before code edits. |

### M-Class Trigger Analysis

T3.1 is M-class because it adds public SDK exports and changes application protocol Rule operator/bool behavior. It is not L-class by itself because the T3 L-class Stage 1 audit, Stage 2 decisions, and Stage 3 synthesis have already completed on the audit branch. T3.1 consumes those outputs as a per-slice blueprint.

### Reviewer Focus Areas

- Whether `RuleExprError(SDKDSLError)` is implemented without weakening the D1 requirement that callers can catch RuleExpr failures through existing SDK exception buckets.
- Whether public `RuleExpr` should be a facade or nominal base class; blueprint acceptance intentionally avoids over-locking internal inheritance.
- Whether duplicate operands should preserve multiplicity. Blueprint currently says yes because D4 says commutative, not idempotent.
- Whether `Rule.__bool__` should be added in application protocol `rule.py` or via mixin/helper. Blueprint chooses direct method for clarity.
- Whether docs updates are too small for T3.1 or should be deferred entirely to T3.6.

### Step 4.2 P2 Tightening

| Finding | Resolution |
|---|---|
| G-2: §5.2 chose `ValueError`, bypassing the existing SDK error hierarchy and violating adopted D1 section 4.1. | §5.2 now locks `RuleExprError(SDKDSLError)` and `ExplicitBoolError(RuleExprError)`, aligned with the shipped `DSLToApplicationRuleError(SDKDSLError)` precedent. |
| G-1: §7 acceptance mentioned immutability in prose but did not include an explicit RuleExpr immutability check. | §7 now requires `_RuleExpr` / `_AndGroup` / `_OrGroup` to be frozen dataclasses or equivalent immutable structures, with field assignment raising. |
