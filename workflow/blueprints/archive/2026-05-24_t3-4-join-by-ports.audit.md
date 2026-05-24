# Task Blueprint Audit: T3.4 Join By Ports

- Blueprint: [2026-05-24_t3-4-join-by-ports.md](./2026-05-24_t3-4-join-by-ports.md)
- Status: implemented
- Created: 2026-05-24
- Last Updated: 2026-05-24

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | draft | Blueprint created | Initial T3.4 S-class scope recorded from D2 §4.5, D5 §4.5, Stage 3 synthesis §3 T3.4, synced track plan T3.4 row, and archived T3.3 join substrate. |
| 2026-05-24 | scoped | Scope locked + P3 precision amendments | T3.4-F1 "requested names" typo fixed; T3.4-F2 §5.7 step 1 wording clarified; T3.4-F3 §5.3 pseudocode standardized with `itertools.combinations`. |
| 2026-05-24 | pre-impl | Step 4.6 grep clean | `join_by_ports`, `itertools.combinations`, `_reachable_operands`, T3.3 join substrate usage, `_OrGroup` direct access, and SDK `__all__` scans matched expected shipped scope. No blueprint scope amendment required. |
| 2026-05-24 | baseline | G7 baseline recorded | Branch/sacred/dirty state verified; Step 4.6 grep remains clean; `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 55 tests OK. |
| 2026-05-24 | implemented | Step 4.7 clean; 0 deviation (second consecutive) | Feat `8f248212` passed Step 4.7 with 0 P0/P1/P2/P3. 72 cross-slice tests OK, ruff clean. Second consecutive T3 feat with 0 deviation. Preemptive scope locking pattern (6 explicit "no" + 1 explicit "yes" in §5.5), diagnostics aggregation stable-order pattern (§5.4), and 5-step validation ordering (§5.7) carried T3.3 discipline forward to T3.4. Bonus test `test_join_by_ports_preserves_export_scope` actively verifies SDK export scope preemptive lock. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- D2 join constraint construction: `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md` §4.5
- D5 slice split: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.5
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` §3 T3.4
- Track plan: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:180-196` synced at `9c857d0c`
- Parent design: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §5.9 / C58
- T1.4 archive: `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- T3.1 archive: `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
- T3.2 archive: `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
- T3.3 archive: `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`

### G1-G7 Visible Mapping

| Gate | T3.4 mapping |
|---|---|
| G1 | Canonical source chain is D2 §4.5 + D5 §4.5 + synthesis §3 T3.4 + track plan T3.4 row, with T3.3 archive as shipped substrate. |
| G2 | Blueprint §4 cites current shipped `rule_expr.py` substrate and identifies T3.3 helpers that T3.4 should reuse. |
| G3 | File/source citations are current at draft time: D2/D5 active decision docs, synthesis §3 T3.4, track plan T3.4 row, and shipped T3.3 `rule_expr.py`. |
| G4 | Goals map to C58 / D2 `.join_by_ports(...)` deferral, D5 T3.4 diagnostics, and T3.3 `.join(...)` mechanics. |
| G5 | Non-goals defer inspect, docs/examples, execution lowering, T1.4 substrate changes, new exports, and new error subclasses. |
| G6 | Reviewer should spot-check pairwise expansion, missing/fewer-than-two diagnostics, more-than-two behavior, `_OrGroup.join_by_ports(...)` diagnostics, and preemptive scope locks. |
| G7 | §8 step 1 requires baseline checks recorded in this audit log before implementation. |

### Class Trigger Analysis

T3.4 is S-class.

S-class reasons:

- No new public DTO or SDK export.
- No new error subclass.
- No new substrate method on `Rule`, `RuleOccurrence`, or `RulePortRef`.
- Pure expansion over T3.3 `RuleJoinConstraint` and `_AndGroup.join(...)`.
- Diagnostics are local to authoring validation and reuse `RuleExprError`.
- No execution, inspect, or adapter semantics.

S-to-M triggers:

- adding public surface beyond `_AndGroup.join_by_ports(...)`.
- adding `Rule.join_by_ports(...)` or `RuleOccurrence.join_by_ports(...)`.
- replacing D2's pairwise expansion with a new ambiguity policy.
- adding a new error subclass or helper module with broader ownership.
- pulling T3.5 inspect, T3.6 docs, or execution lowering into this slice.

### Preemptive Scope Check

T3.4 applies the T3.3 0-deviation lesson before implementation:

- `Rule.join_by_ports(...)`: explicitly not added.
- `RuleOccurrence.join_by_ports(...)`: explicitly not added.
- `RulePortRef` changes: none.
- New helper module: none; use `rule_expr.py`.
- New error subclass: none; reuse `RuleExprError`.
- `_OrGroup.join_by_ports(...)`: explicitly added as a diagnostic method, matching `_OrGroup.join(...)`.

### Reviewer Focus Areas

- Whether more-than-two occurrences are correctly locked as deterministic pairwise expansion rather than an ambiguity error.
- Whether missing and fewer-than-two diagnostics aggregate in stable order.
- Whether duplicate requested names are rejected rather than silently deduped.
- Whether `_AndGroup.join_by_ports(...)` delegates to T3.3 `.join(...)` instead of duplicating join validation/canonicalization.
- Whether `_OrGroup.join_by_ports(...)` diagnostics match T3.3 AND-only guidance.
- Whether no `Rule` / `RuleOccurrence` / `RulePortRef` methods or new SDK exports sneak into scope.
- Whether T3.3 21 acceptance gates and 9 negative-action gates remain preserved.

### Cross-Slice Contract Preservation

| Prior slice | Expected preservation |
|---|---|
| T1.1 Rule DTO | Application Rule fields, content digest, equality/hash, and port validation unchanged. |
| T1.2 DSL bridge | `build_application_rule(...)` still returns application `Rule`; no bridge behavior change. |
| T1.3 SDK naming | `factgraph.sdk.Rule` remains legacy; no top-level export changes. |
| T1.4 alias/port substrate | `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, `RulePortRef.eq(...)`, `RulePortRef.__eq__`, and port APIs remain unchanged. |
| T2.3 aggregate track | Aggregate AST/eval/adapter paths untouched. |
| T3.1 base RuleExpr | Bool guards, public exports, join-free composition, and negative-action gates preserved. |
| T3.2 expression-scope validation | Alias uniqueness, repeated-rule explicit alias validation, and alias-aware canonical operands preserved. |
| T3.3 joins + reach rule | `.join(...)`, `RuleJoinConstraint`, reach validation, symmetry/dedupe, flatten-merge behavior, and all negative-action gates preserved. |

### Step 4.2 Draft Review Checklist

- [ ] S-class declaration is justified by pure expansion over T3.3 and no new public DTO/export.
- [ ] D2 §4.5 / D5 §4.5 / synthesis / track-plan cite chain is complete.
- [ ] Goals cover `_AndGroup.join_by_ports(...)`, pairwise expansion, missing diagnostics, fewer-than-two diagnostics, and more-than-two pairwise behavior.
- [ ] Preemptive scope check explicitly rejects `Rule.join_by_ports(...)`, `RuleOccurrence.join_by_ports(...)`, new helper module, new error subclass, and new exports.
- [ ] `_OrGroup.join_by_ports(...)` diagnostic method is intentionally scoped.
- [ ] Acceptance gates map one-to-one to goals and cross-slice preservation.
- [ ] T3.3 helpers are reused rather than duplicated.

### Step 4.6 Pre-Implementation Grep

| Check | Result |
|---|---|
| `join_by_ports` naming conflict | `rg 'join_by_ports' src/factgraph/ tests/ workflow/` found workflow/design, memory, and blueprint mentions only. `rg 'join_by_ports' src/factgraph/ tests/` returned no shipped code/test hits; the method name is new. |
| `itertools.combinations` import pattern | `rg 'from itertools import\|itertools\.combinations' src/factgraph/` found only existing `from itertools import count` in `src/factgraph/sdk/dsl/expr.py`; adding `combinations` in `rule_expr.py` is local and non-conflicting. |
| T3.3 `_reachable_operands` callers | `rg '_reachable_operands' src/factgraph/ tests/` found only the T3.3 internal call and definition in `src/factgraph/application/protocol/rule_expr.py`; T3.4 will be the first additional internal caller. |
| T3.3 join substrate usage | `rg 'RuleJoinConstraint\(|RulePortRef\.eq|_AndGroup\.join' src/factgraph/ tests/` found current T3.3 implementation and tests only. No external caller bypasses the intended join path. |
| `_OrGroup` direct access | `rg '_OrGroup\.' src/factgraph/ tests/` returned no hits; adding `_OrGroup.join_by_ports(...)` as a diagnostic method has no existing direct-access collision. |
| SDK `__all__` export scope | `grep -A 80 '__all__' src/factgraph/sdk/__init__.py \| head -90` shows existing T3.3 `RuleJoinConstraint`, `RuleExpr`, `RuleExprError`, and `ExplicitBoolError` exports; T3.4 adds no new SDK export. |

### G7 Baseline Record

| Check | Result |
|---|---|
| Branch and sacred state | Branch `v0.2.0-t3-4-join-by-ports-2026-05-24` at `4035d360`; sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`; dirty set remains 4 modified files + 1 untracked directory. |
| T3.3 join substrate | Step 4.6 grep already confirmed T3.3 `RuleJoinConstraint`, `RulePortRef.eq(...)`, `_AndGroup.join(...)`, `_reachable_operands(...)`, and `_OrGroup` direct-access scope are clean. |
| `join_by_ports` baseline | Step 4.6 grep confirmed `join_by_ports` is absent from shipped `src/factgraph/` and `tests/`; T3.4 adds the first implementation. |
| Requested pytest baseline | Pytest remains out of the T3.4 baseline path because T3.1 recorded the current environment SIGSEGV issue; the spawned tooling investigation remains out of scope for T3.4. |
| Fallback unittest baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 55 tests in 0.009s and passed OK. |
