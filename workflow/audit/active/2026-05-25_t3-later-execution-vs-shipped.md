# Stage 1 Audit: T3 Later RuleExpr Execution Lowering vs Shipped Runtime

Status: draft
Date: 2026-05-25
Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`
Base: `e4e4417f` (`docs(memory): record next-track selection T3 later tranche`)
Class prediction: L cluster (Stage 2 decisions + Stage 3 synthesis + per-slice M/S blueprints)
Owner split: Codex drafts; Claude reviews

## 1. Purpose

This audit starts the T3 later tranche selected in `workflow/memory/current.md`: RuleExpr execution lowering / adapter integration for composite expressions.

The audit is intentionally read-only. It answers:

- what T3.1-T3.6 actually shipped;
- where execution lowering is deliberately absent;
- which parent commitments are ready to consume;
- which decisions must be resolved before implementation blueprints.

## 2. Scope

In scope:

- accepting application `Rule` / RuleExpr authoring values at execution boundaries;
- lowering composite AND / OR RuleExpr trees plus explicit joins into executable runtime shape;
- deciding how that lowering maps to native, Souffle, ProbLog, and PyReason;
- deciding whether this tranche owns only lowering or also a public `fg.eval.evaluate(rule_expr, head=...)` entrypoint;
- deciding how much proof/evidence result integration is in this tranche versus T5.

Out of scope for this Stage 1 audit:

- implementation;
- blueprint scoping;
- T4 Head implementation;
- T5 EvaluateResult / WhyNot / hard-cut work;
- factgraph push;
- pytest SIGSEGV investigation;
- dirty-set cleanup.

## 3. Canonical Sources Read

| Source | Relevant lines | Audit use |
|---|---:|---|
| `workflow/memory/current.md` | 307-334 | Human-direct next-track selection, cross-flip assignment, source refs, hold gates. |
| `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` | 155-167 | D5 explicitly excludes execution lowering from T3.1-T3.6 and requires later decision/synthesis. |
| `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` | 203-208, 212-218 | Synthesis records later tranche dependencies and cadence reminders. |
| `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` | 180-198 | Track plan row for T3 later tranche and initial T3 slice ladder. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 397-409 | Parent §4 states RuleExpr is composition only and has no head/projection/claim. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 713-816 | Parent §5 head contract and `fg.eval.evaluate(expr, head=...)` examples. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 1670-1765 | Parent §8 engine capability and lowering matrix. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 1835-1867, 1873-1959 | Parent §10 atom grammar and ArithExpr/AggregateExpr restrictions. |
| `workflow/blueprints/archive/2026-05-24_t3-1-*` through `t3-6-*` | archive pairs | T3.1-T3.6 closure trail and negative-action gates. |

Line ranges are pinned to the Stage 1 audit branch state; the initial audit commit was `4ac498f0`.

## 4. Shipped Code Read

| File | Relevant lines | Shipped truth |
|---|---:|---|
| `src/factgraph/application/protocol/rule.py` | 43-170 | Application `Rule` is condition-only, frozen, port-bearing, bool-guarded, and exposes occurrence / port refs. |
| `src/factgraph/application/protocol/rule_expr.py` | 43-179 | RuleExpr factories/operators, bool guard, AND/OR nodes, flattening, alias validation, joins. |
| `src/factgraph/application/protocol/rule_expr.py` | 105-130, 239-283 | `_AndGroup.join(...)`, `_AndGroup.join_by_ports(...)`, AND-only diagnostics, reach validation. |
| `src/factgraph/application/protocol/rule_expr_inspect.py` | 155-240 | Inspect coercion, AST projection, occurrences, joins, ports, unjoined same-name hints. |
| `src/factgraph/application/protocol/rule_expr_inspect.py` | 200-228 | Inspect reads `Rule.atom_ids`, ports, and `value_type="unknown"` sentinel for value ports. |
| `src/factgraph/application/protocol/__init__.py` | 74-76, 199-204 | Application protocol exports RuleExpr and inspect DTOs. |
| `src/factgraph/sdk/__init__.py` | 28-38, 88-106 | SDK exports `ApplicationRule`, RuleExpr, join, inspect, and error surfaces. |
| `src/factgraph/sdk/store.py` | 406-434 | `fg.eval.evaluate(...)` namespace manager remains inference-oriented. |
| `src/factgraph/sdk/store.py` | 2088-2097 | `fg.rules.inspect(...)` has 3-way dispatch for application Rule, RuleExpr, and legacy dict outputs. |
| `src/factgraph/sdk/store.py` | 2197-2264 | `SDKStore.evaluate(...)` accepts legacy derivation objects/dicts or delegates args to core `Store.evaluate`; no RuleExpr branch. |
| `src/factgraph/application/protocol/derivation.py` | 34-43, 75-93 | Compiled derivation runtime shape is `body_ir + heads`, not RuleExpr. |
| `src/factgraph/application/derivation_runtime.py` | 69-119 | Application derivation runtime calls `evaluate_store(...)` with `body_ir`, head spec, and engine. |
| `src/factgraph/core/store/_evaluate.py` | 33-49, 79-144 | Core evaluation consumes `target_pred_id`, `head_vars`, and `where`; no RuleExpr object boundary. |
| `src/factgraph/adapters/souffle/where_compile.py` | 462-798, 856-922, 1194-1323, 1349-1365 | Souffle compiler consumes lowered WhereIR atoms and supports broad Form 1 grammar plus internal arithmetic atoms. |
| `src/factgraph/adapters/problog/problog_export.py` | 236-318, 416-419 | ProbLog compiler consumes lowered WhereIR atoms; supports pred/eq/ne/comparisons/in/not and aggregate filter constraints. |
| `src/factgraph/adapters/pyreason/where_compile.py` | 113-137 | PyReason compiler accepts pred atoms and rejects eq/not/ruleref/other kinds. |
| `src/factgraph/sdk/dsl/application_rule.py` | 53-82, 85-91 | SDK bridge builds application `Rule` from AND-only bodies; OR branches are rejected. |

## 5. Executive Findings

### F1. T3.1-T3.6 shipped an authoring and inspect surface, not execution.

Shipped `RuleExpr` has factories, operators, equality/hash, bool guards, joins, join-by-ports, reach validation, and inspect. It does not have a lowering or evaluation method. This matches D5: "RuleExpr execution lowering is not part of T3.1-T3.6" and must be later L/M work.

### F2. `fg.eval.evaluate(...)` has no RuleExpr dispatch.

`SDKStore.evaluate(...)` currently routes:

- legacy SDK derivation-like objects via `to_authoring_payload`;
- structured derivation dicts;
- remaining arguments directly to core `Store.evaluate(...)`.

There is no branch for application `Rule`, `_RuleExpr`, or `RuleExprInspect`. Core `evaluate_store(...)` consumes `derivation_id`, `target_pred_id`, `head_vars`, and `where`, so RuleExpr lowering needs an explicit bridge rather than an adapter-only patch.

### F3. The runtime shape already has possible lowering targets.

`CompiledDerivationPlan` stores `body_ir`, `heads`, optional `head_spec`, engine extension/options, and semantics profile. `evaluate_derivation_plans(...)` then calls `evaluate_store(...)` per head. This is one existing runtime shape that could be targeted, but it is not yet a decided contract for RuleExpr lowering.

This is a Stage 2 entry hypothesis, not a Stage 1 conclusion; D7 must compare it against transient derivation dicts, a new internal lowering plan, and adapter-specific lowering.

### F4. Parent head commitments are load-bearing and may require T4 or a T3-later sub-slice.

Parent §5 examples use `fg.eval.evaluate(expr, head=...)`. The parent commits to head being a `Rule`, identity checks when the head is already in the expression, and port-name alignment for inline heads. Those are T4 commitments in the track plan, while T3 later is execution lowering. This creates a dependency question: T3 later can either include a minimal head subset, block on T4, or produce internal lowering only.

### F5. Adapter semantics are not uniform enough for a single "just lower it" implementation.

Native, Souffle, and ProbLog all consume WhereIR-style bodies; PyReason is explicitly pred-only and rejects equality, negation, and other atom kinds. Parent §8 also records Form 1 portability constraints and PyReason Form 2 separation. T3 later must lock an engine support matrix and explicit rejection behavior before implementation.

T2.3 aggregate support is part of this matrix. RuleExpr lowering must preserve both RuleExpr alias/occurrence scoping and T2.3 aggregate-local variable isolation, empty-set guard semantics, and PyReason exclusion behavior.

### F6. Joins are structurally validated but not executable.

`RuleJoinConstraint` records two `RulePortRef` endpoints, and `_AndGroup.join(...)` enforces shape, distinct occurrence, reach, and duplicate normalization. Nothing lowers those constraints into WhereIR equality atoms, variable unification, or adapter-specific constraints. This is the central semantic gap for T3 later.

### F7. OR lowering needs an explicit representation decision.

Application `Rule` is AND-only; the SDK bridge rejects OR branches. Legacy `where` can represent OR-like branch lists in derivation paths. RuleExpr has nested AND/OR trees. T3 later must decide whether OR branches become:

- multiple `CompiledDerivationPlan`s;
- one plan with branch-list `body_ir`;
- distributed normal form;
- or an internal rule-expression lowering IR before producing WhereIR.

### F8. Proof/evidence integration is not just a byproduct of evaluation.

D5 says execution lowering must decide how composite RuleExprs map to proof/evaluation machinery. Core evaluation already produces support artifacts for WhereIR evaluation, but RuleExpr aliases, occurrence identities, joins, and OR choices are additional authoring-layer structure. T3 later should avoid silently discarding this structure if T5 needs it for EvaluateResult / WhyNot.

### F9. Public surface expansion is likely, so L-class is justified.

Possible public surfaces include `fg.eval.evaluate(rule_expr, head=...)`, error messages, docs, and maybe lower/inspect helpers. Even if implementation targets internal lowering first, this tranche crosses SDK dispatch, application protocol, core runtime, adapter support, and proof/evidence boundaries.

### F10. L-class means cluster, not one monolithic blueprint.

The current scope crosses public SDK dispatch, application protocol lowering, runtime plans, adapter behavior, and evidence/result boundaries. It should follow L-class cluster cadence: Stage 2 decisions, Stage 3 synthesis, then smaller scoped implementation blueprints.

## 6. Commitment Triage

| Commitment / seam | Current status | T3 later implication |
|---|---|---|
| RuleExpr composition (`&`, `|`, factories) | Shipped in T3.1 | Input substrate available. |
| Occurrence alias validation | Shipped in T3.2 | Lowering can rely on unique aliases. |
| Explicit joins and reach validation | Shipped in T3.3 | Need executable lowering for constraints. |
| `join_by_ports(...)` pairwise expansion | Shipped in T3.4 | Lowering only sees normalized joins. |
| RuleExpr inspect | Shipped in T3.5 | Useful for diagnostics/debug, not runtime lowering. |
| User docs | Shipped in T3.6 | Current docs intentionally stop at authoring/inspect. |
| `fg.eval.evaluate(rule_expr, head=...)` | Not shipped | Needs Stage 2 decision. |
| Head as Rule | Parent committed, not shipped in T4 yet | Dependency / ownership decision required. |
| Adapter execution lowering | Not shipped | Main tranche objective. |
| Evidence / proof shape for aliases/joins | Pending | Avoid accidental T5 commitments. |

## 7. Stage 2 Questions Recommended

### Q1. Public entrypoint and ownership

Should T3 later ship a public `fg.eval.evaluate(rule_expr_or_rule, *, head=...)` path, or only an internal lowering primitive consumed later by T4/T5?

Decision pressure:

- parent examples show public evaluate with `head=`;
- current `fg.eval.evaluate(...)` is inference-oriented;
- T4 owns full head / closed-head semantics;
- T5 owns EvaluateResult / WhyNot redesign.

### Q2. Head dependency boundary

If public evaluation ships now, what subset of parent §5 head semantics is in this tranche?

Candidate directions:

- require T4 first, which would pause this T3 later tranche pending T4 cycle completion and require Human re-engagement on next-track ordering;
- ship minimal head-as-application-Rule checks in T3 later;
- allow only existing expression occurrence heads initially;
- keep public path unsupported until T4.

### Q3. Lowering IR strategy

What is the canonical internal result of lowering RuleExpr?

Candidate directions:

- direct `CompiledDerivationPlan`;
- transient derivation dict payload;
- a new non-public `RuleExprLoweringPlan`;
- adapter-specific lowering without a shared plan.

Stage 2 entry hypothesis: a shared plan may be attractive because existing application runtime already consumes `CompiledDerivationPlan`. This is not binding; D7 must decide the canonical lowering target before coding.

### Q4. AND / OR tree lowering

How do nested AND/OR RuleExpr trees map to executable branches?

Required locks:

- AND concatenation over occurrence bodies;
- OR branch representation;
- nested OR under AND distribution or branch-list expansion;
- deterministic branch ids / occurrence identity preservation;
- empty branch impossibility.

### Q5. Join lowering semantics

How should `RuleJoinConstraint(left, right, op="eq")` lower?

Required locks:

- variable unification versus explicit `eq` atoms;
- entity-ref and value ports;
- same-name ports still do not auto-join;
- alias-local variable privacy;
- duplicate normalized joins;
- cross-OR reach remains forbidden.

### Q6. Engine support matrix

Which engines must work in the first execution-lowering slice?

Required locks:

- native support;
- Souffle support;
- ProbLog support;
- PyReason pred-only rejection or subset;
- behavior for non-pred atoms in PyReason;
- semantics profile interaction.

### Q7. Adapter grammar floor

Should T3 later require the full currently shipped T2.3 atom grammar through each adapter, or only lower RuleExpr structure over whatever each adapter already supports?

This matters because parent §8 records Form 1 portability goals, while shipped adapters have different support levels, especially PyReason.

Q7 is a sub-question of Q6. D9 must answer both jointly so the engine matrix and per-engine grammar floor do not diverge.

### Q7a. Aggregate-in-RuleExpr preservation

How should RuleExpr lowering preserve `AggregateAtom` / aggregate expression behavior already shipped by T2.3?

Required locks:

- aggregate-local variable isolation remains independent from RuleExpr alias-local variable privacy;
- empty-set guard semantics remain unchanged;
- adapter support follows the D9 engine matrix;
- PyReason aggregate behavior remains explicitly unsupported unless a later Form 2 decision changes it.

### Q8. Evidence / support / explanation boundary

Does T3 later preserve alias, occurrence, join, and OR-branch identity in support artifacts, or does it only return existing `CandidateSet` rows?

Decision pressure:

- D5 mentions proof/evaluation machinery;
- T5 EvaluateResult and WhyNot are still pending;
- support artifacts currently operate over WhereIR, not RuleExpr AST.

### Q9. Error hierarchy and diagnostics

Should lowering failures raise `RuleExprError`, `SDKStoreError`, `WhereValidationError`, or a new error?

Audit leaning: avoid new error subclasses unless Stage 2 finds public API pressure; preserve T3 discipline by reusing existing error buckets where possible.

### Q10. Slice split

Should this tranche be one L-class blueprint or a staged L-class cluster?

Possible split:

- T3L.1: internal lowering plan + native engine only;
- T3L.2: Souffle/ProbLog adapter parity;
- T3L.3: public `fg.eval.evaluate(...)` and docs;
- T3L.x: PyReason explicit unsupported/subset behavior.

## 8. Risk Register

| Risk | Severity | Reason |
|---|---|---|
| Bundling head semantics into execution lowering without T4 decision | High | Parent §5 is large and track-plan assigns Head to T4. |
| Lowering joins by variable-name coincidence | High | T1.4 ports are the boundary; internal Var names are private. |
| Silent PyReason partial behavior | High | PyReason rejects non-pred WhereIR today; silent downgrade would violate parent §8. |
| Dropping alias/occurrence identity in support artifacts | Medium | May block T5 evidence / WhyNot later. |
| Changing legacy SDK `Inference` evaluation behavior | Medium | Current `evaluate(...)` path is broad and already user-facing. |
| Adding new public DTOs too early | Medium | T5 EvaluateResult likely owns result surface. |
| Treating inspect DTOs as runtime IR | Medium | `RuleExprInspect` is authoring projection, not execution plan. |

## 9. Negative-Action Gates For Future Blueprints

- Do not change legacy SDK `Rule` truthiness or meaning.
- Do not change legacy SDK `Inference` evaluation semantics without a dedicated decision.
- Do not introduce cross-type `application_rule == rule_expr` equality.
- Do not auto-join same-name ports.
- Do not look through OR branches for join reach.
- Do not use `RuleExprInspect` as the execution IR.
- Do not alter `RulePortRef.__eq__` value equality.
- Do not add `RuleExpr` cross-process digest unless a separate cache/serialization decision requires it.
- Do not expand T5 EvaluateResult / WhyNot scope into this tranche without an explicit class upgrade.
- Do not treat PyReason as Form 1 compatible.

## 10. Recommended Next Step

Proceed to Stage 2 Q-resolution before any blueprint implementation.

Each decision doc should follow the T3 D1-D5 lifecycle: proposed, reviewed, adopted.

Recommended decision docs:

1. **D6: T3 later public entrypoint and head dependency** — decide whether public `fg.eval.evaluate(rule_expr, head=...)` is in this tranche and whether T4 blocks it.
2. **D7: RuleExpr lowering plan shape** — decide canonical internal lowering target and how AND/OR trees map to plans/branches.
3. **D8: Join lowering semantics** — decide port equality lowering, variable privacy, and alias/occurrence preservation.
4. **D9: Adapter support matrix** — decide native/Souffle/ProbLog/PyReason support and rejection behavior.
5. **D10: Evaluation result / evidence boundary** — decide what this tranche returns now and what remains T5.

Q-to-D disposition:

| Question | Disposition |
|---|---|
| Q1 public entrypoint | D6 |
| Q2 head dependency boundary | D6 |
| Q3 lowering IR strategy | D7 |
| Q4 AND / OR tree lowering | D7 |
| Q5 join lowering semantics | D8 |
| Q6 engine support matrix | D9 |
| Q7 adapter grammar floor | D9 |
| Q7a aggregate-in-RuleExpr preservation | D9 |
| Q8 evidence / support boundary | D10 |
| Q9 error hierarchy and diagnostics | Cross-cutting acceptance in D6-D9; D9 owns adapter rejection error policy. Create a standalone D11 only if review finds the cross-cut too diffuse. |
| Q10 slice split | Stage 3 synthesis, not a decision doc. |

After those decisions, run Stage 3 synthesis to split implementation slices and update the track plan before any scoped blueprint enters implementation.

Per-slice implementation should carry forward the validated T3 cadence discipline: preemptive scope locking, executable-quality §5/§6 specs, sibling module isolation where it reduces touch surface, Step 4.6 proactive grep with pre-feat A-fallback amendments when needed, and Step 4.7 review before closure/archive.

## 11. Audit Status

Draft complete for Step 4.2 review.

Open review asks:

- Confirm L-class cluster classification.
- Confirm Stage 2 decision count and names.
- Confirm whether T4 head dependency should be treated as blocker or partial in-tranche scope.
- Confirm whether native-only first slice is acceptable if adapters require a broader decision.
