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
| 2026-05-24 | pre-impl | Step 4.6 grep clean | Pre-implementation grep found no shipped RuleExpr code surface, no application/legacy Rule operator or bool conflicts, no T1.4 bool-context test dependency, no `factgraph.sdk.all` / `factgraph.sdk.any` export, and existing SDK API docs/error rows for T3.1 docs alignment. No scope amendment required. |
| 2026-05-24 | baseline | G7 baseline recorded | Before implementation, direct `pytest tests/application/protocol/test_rule.py -v` and `python -m pytest ...` both exited with no output; subprocess capture showed pytest returncode `-11` (SIGSEGV). Fallback `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule -v` ran 23 tests OK. No code edits made. |
| 2026-05-24 | implementing | Import-cycle fallback | During implementation smoke tests, direct application `rule_expr.py` import from `factgraph.sdk.dsl.errors` triggered an application/SDK package cycle. Blueprint §5.2 now allows neutral internal SDK error base re-export support while preserving `issubclass(RuleExprError, factgraph.sdk.dsl.errors.SDKDSLError)`. |

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

### Step 4.6 Pre-Implementation Grep

| Check | Result |
|---|---|
| RuleExpr surface scan | `rg 'RuleExpr|RuleExprError|ExplicitBoolError|_AndGroup|_OrGroup|_RuleExpr' src/factgraph tests` only found forward-looking application docs mentions; no shipped code/test surface exists. |
| Rule truthiness scan | `rg 'if.*[Rr]ule\b|if.*rule:|if.*application_rule|bool\(.*[Rr]ule' src/factgraph tests` found no application Rule truthiness dependency; hits were docs, strings, or type checks. |
| Operator conflict scan | `rg '__and__|__or__|Rule\s*&\s*|Rule\s*\|\s*' src/factgraph/application src/factgraph/sdk/dsl/rule.py` found no shipped application or legacy SDK Rule operator conflicts. |
| SDK error catch/docs scan | Existing SDK docs list `DSLToApplicationRuleError`, `SDKDSLError`, and store/schema errors; T3.1 docs can follow that shape. Existing catches are store/shell specific and do not block `RuleExprError(SDKDSLError)`. |
| SDK `all` / `any` scan | `rg '\ball\b|\bany\b' src/factgraph/sdk/__init__.py` found no top-level `all` / `any` exports. |
| T1.4 bool baseline | `rg 'bool\(.*rule|if.*rule' tests/application/protocol/test_rule.py` found only the non-identifier rule-id test name, not a bool-context dependency. |

### G7 Baseline Record

| Check | Result |
|---|---|
| Branch and sacred state | Current branch `v0.2.0-t3-1-base-ruleexpr-bool-guards-2026-05-24`; `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`; dirty set remains the pre-existing 4 modified notebooks/docs plus 1 untracked directory. |
| RuleExpr surface | Step 4.6 grep already confirmed no shipped RuleExpr code/test surface before implementation. |
| Operator/bool baseline | Step 4.6 grep already confirmed no shipped application or legacy SDK Rule `__and__` / `__or__` / `__bool__` definitions and no T1.4 bool-context dependency. |
| Requested pytest baseline | `pytest tests/application/protocol/test_rule.py -v`, `PYTHONPATH=src pytest tests/application/protocol/test_rule.py -v`, and `PYTHONPATH=src python -m pytest tests/application/protocol/test_rule.py -v` exited with no stdout/stderr in this environment; escalated retry behaved the same. Subprocess capture returned `-11`, indicating pytest SIGSEGV rather than test failure. |
| Fallback baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule -v` ran 23 tests in 0.003s, OK. This is the pre-implementation T1.4 application Rule baseline for post-implementation comparison. |
