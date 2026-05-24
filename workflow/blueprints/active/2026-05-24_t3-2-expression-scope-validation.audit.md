# Task Blueprint Audit: T3.2 Expression-Scope Occurrence Validation

- Blueprint: [2026-05-24_t3-2-expression-scope-validation.md](./2026-05-24_t3-2-expression-scope-validation.md)
- Status: scoped
- Created: 2026-05-24
- Last Updated: 2026-05-24

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | draft | Blueprint created | Initial T3.2 S-class scope recorded from D5 §4.3, Stage 3 synthesis §3 T3.2, synced track plan T3.2 row, T1.4 substrate, and archived T3.1 implementation. |
| 2026-05-24 | scoped | Scope locked + P3 amendments | T-2 Goal #1 prerequisite rationale recorded; T-3 D4 §4.3 alias identity operationalization acknowledged in §5.6. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- D5: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.3
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` §3 T3.2
- Track plan: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:180-196` synced at `9c857d0c`
- T1.4 archive: `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- T3.1 archive: `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`

### G1-G7 Visible Mapping

| Gate | T3.2 mapping |
|---|---|
| G1 | Canonical source chain is D5 §4.3 + synthesis §3 T3.2 + track plan T3.2 row, with T1.4/T3.1 archives as shipped substrate. |
| G2 | Blueprint §4 cites current shipped `rule.py` / `rule_expr.py` line ranges and distinguishes already-shipped substrate from T3.2 expression-scope validation. |
| G3 | File:line citations are current at draft time: T1.4 substrate in `rule.py:122-191`; T3.1 RuleExpr in `rule_expr.py:9-129`; synthesis §3 T3.2 at lines 122-135; track plan T3.2 at line 191. |
| G4 | Goals map 1:1 to the four D5/synthesis must-include items plus explicit handling of T3.1 P3 follow-ups. |
| G5 | Non-goals defer joins, join_by_ports, inspect, docs/examples, execution lowering, T1.4 substrate changes, T1.3 naming changes, and T2.3 aggregate changes. |
| G6 | Reviewer should spot-check RuleOccurrence operand acceptance, repeated-rule alias rule, duplicate alias diagnostics, default alias invalid-id behavior, and T3.1 negative-action gates. |
| G7 | §8 step 1 requires pre-implementation checks recorded in this audit log before code edits. |

### Class Trigger Analysis

T3.2 is S-class.

Reasons:

- No new public SDK exports.
- No new public error subclass.
- No new public DTO.
- No cross-engine semantics.
- No adapter changes.
- Scope is validation and diagnostics over the existing T1.4 and T3.1 substrates.

S-to-M triggers:

- introducing a public `RuleExprAliasError` or other new SDK error subclass.
- changing T1.4 `RuleOccurrence` / `RulePortRef` public fields.
- changing T3.1 public `RuleExpr` export shape.
- adding join or inspect behavior.
- adding user-facing docs/examples beyond a minimal note.

### Reviewer Focus Areas

- Whether repeated same Rule detection should use `(rule.id, rule.content_digest)` identity as D4/T3.1 does.
- Whether diagnostics should aggregate multiple expression-scope failures or fail fast. Blueprint chooses deterministic aggregate diagnostics for duplicate alias + repeated bare Rule issues.
- Whether bare Rule with non-identifier id should fail as `RuleExprError` with `.as_(...)` guidance. Blueprint chooses yes, matching T1.4 edge-case contract.
- Whether preserving duplicate operand multiplicity conflicts with validation. Blueprint keeps multiplicity internally but rejects invalid returned expressions.
- Whether deferring the duck-typed legacy SDK Rule detector is acceptable. Blueprint treats it as a deliberate cycle-avoidance choice.
- Whether the T3.1 `test_duplicate_operands_preserve_multiplicity` update is correctly treated as a deliberate cross-slice contract supersedence (not a regression) — blueprint §6 invariant + §7 acceptance #15 + §8 step 4 sub-step explicitly track this.

### Cross-Slice Contract Preservation

| Prior slice | Expected preservation |
|---|---|
| T1.1 Rule DTO | Application Rule fields, content digest, equality/hash, and port validation unchanged. |
| T1.2 DSL bridge | `build_application_rule(...)` still returns application `Rule`; no bridge behavior change. |
| T1.3 SDK naming | `factgraph.sdk.Rule` remains legacy; `ApplicationRule` remains application Rule; top-level RuleExpr exports from T3.1 unchanged. |
| T1.4 alias/port substrate | `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, and port APIs unchanged; T3.2 only consumes them. |
| T2.3 aggregate track | Aggregate AST/eval/adapter paths untouched. |
| T3.1 base RuleExpr | 23 acceptance gates and 5 negative-action gates preserved; T3.2 adds validation over the same tree. |
