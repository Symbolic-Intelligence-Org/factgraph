# Task Blueprint Audit: T3.3 Joins And Reach Rule

- Blueprint: [2026-05-24_t3-3-joins-and-reach-rule.md](./2026-05-24_t3-3-joins-and-reach-rule.md)
- Status: implemented
- Created: 2026-05-24
- Last Updated: 2026-05-24

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | draft | Blueprint created | Initial T3.3 M-class scope recorded from D2 §4.2-§4.5, D4 §4.5, D5 §4.4, Stage 3 synthesis §3 T3.3, synced track plan T3.3 row, and archived T1.4/T3.1/T3.2 substrates. |
| 2026-05-24 | scoped | Scope locked + P3 precision amendments | T3.3-F1 flatten-merge acceptance added; T3.3-F2 RuleJoinConstraint validation location explicit; T3.3-F3 zero-arg `.join()` rejection rationale added. |
| 2026-05-24 | pre-impl | Step 4.6 grep clean | `RulePortRef.eq`, `_AndGroup` / `_OrGroup`, `_combine`, `RuleJoinConstraint`, `.join(...)`, SDK export names, and T3.2 validation helper scans matched expected shipped scope. No blueprint scope amendment required. |
| 2026-05-24 | baseline | G7 baseline recorded | Branch/sacred/dirty state verified; Step 4.6 grep remains clean; `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 45 tests OK. |
| 2026-05-24 | implemented | Step 4.7 clean; 0 deviation | Feat `0b80fe9b` passed Step 4.7 with 0 P0/P1/P2/P3. 64 cross-slice tests OK, ruff clean. First T3 feat with 0 deviation thanks to preemptive `RulePortRef.eq()` lock (§5.2), 3-layer validation (§5.3), and Reach Rule specification (§5.6). Lesson: future T3 slices should preempt prior-slice mid-impl drifts in scoped blueprints. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- D2 join constraint construction: `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md` §4.2-§4.5
- D4 structural equality/hash: `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md` §4.5
- D5 slice split: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.4
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` §3 T3.3
- Track plan: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:180-196` synced at `9c857d0c`
- Parent design: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.6 and C30-C31
- T1.4 archive: `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- T3.1 archive: `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
- T3.2 archive: `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`

### G1-G7 Visible Mapping

| Gate | T3.3 mapping |
|---|---|
| G1 | Canonical source chain is D2 + D4 + D5 + synthesis §3 T3.3 + track plan T3.3 row, with T1.4/T3.1/T3.2 archives as shipped substrate. |
| G2 | Blueprint §4 cites current shipped `rule.py` / `rule_expr.py` substrate and separates shipped occurrence validation from new join validation. |
| G3 | File/source citations are current at draft time: D2/D4/D5 active decision docs, synthesis §3 T3.3, track plan T3.3 row, and shipped T3.2 code in `rule_expr.py` / `rule.py`. |
| G4 | Goals map to D2 `.eq(...)` + `RuleJoinConstraint`, D5 `.join(...)` and reach validation, and D4 symmetry/dedup normalization. |
| G5 | Non-goals defer `.join_by_ports`, inspect, docs/examples, execution lowering, parent-final `==`, and T1.3/T2.3/T3.1/T3.2 substrate changes. |
| G6 | Reviewer should spot-check `RulePortRef.eq(...)` substrate acknowledgment, self-join decision, reach-rule algorithm, join symmetry/dedup, AND-only enforcement, and T3.2 negative-action preservation. |
| G7 | §8 step 1 requires baseline checks recorded in this audit log before implementation. |

### Class Trigger Analysis

T3.3 is M-class.

M-class triggers:

- New public DTO and export: `RuleJoinConstraint`.
- Additive public method on shipped T1.4 DTO: `RulePortRef.eq(...)`.
- New authoring method on internal RuleExpr surface: `_AndGroup.join(...)`.
- Consumption of three adopted decisions: D2, D4, and D5.
- Every-Proof-Path Reach Rule algorithm with non-trivial validation and diagnostics.
- Cross-slice interaction with T3.1/T3.2 canonical equality/hash and occurrence validation.

Why not L-class:

- No adapter execution lowering.
- No inspect surface.
- No T5 legacy hard-cut.
- No new multi-stage audit/decision cycle is needed because Stage 1-3 T3 work already adopted the governing decisions.

S-to-M triggers are already active; additional L trigger would be introducing execution semantics, changing D2/D4/D5 decisions, or pulling inspect/docs into this slice.

### Reviewer Focus Areas

- Whether `RulePortRef.eq(...)` is explicitly scoped as an additive method on a frozen T1.4 DTO, avoiding the T3.2 T-1 pattern drift.
- Whether self-join rejection is the right T3.3 choice versus allowing or normalizing same-occurrence constraints.
- Whether Every-Proof-Path Reach Rule uses the parent mechanical direct-AND-spine rule rather than traversing OR groups.
- Whether `_combine("and", ...)` preserving joins from flattened child AND groups is necessary and correctly scoped.
- Whether join symmetry and duplicate normalization match D4 §4.5 without changing `RulePortRef.__eq__`.
- Whether `_AndGroup.join(...)` and `_OrGroup.join(...)` diagnostics preserve parent AND-only semantics.
- Whether T3.2 `_validate_expression_scope(...)` remains separate from T3.3 join reach validation.
- Whether the new `RuleJoinConstraint` SDK export is reflected in minimal API docs without leaking into T3.6 tutorial scope.

### Cross-Slice Contract Preservation

| Prior slice | Expected preservation |
|---|---|
| T1.1 Rule DTO | Application Rule fields, content digest, equality/hash, and port validation unchanged. |
| T1.2 DSL bridge | `build_application_rule(...)` still returns application `Rule`; no bridge behavior change. |
| T1.3 SDK naming | `factgraph.sdk.Rule` remains legacy; `ApplicationRule` remains application Rule; T3.1/T3.2 exports unchanged. |
| T1.4 alias/port substrate | `RulePortRef.eq(...)` is additive; `Rule.as_`, `RuleOccurrence`, `RulePortRef` fields, alias regex, `RulePortRef.__eq__`, and port APIs remain unchanged. |
| T2.3 aggregate track | Aggregate AST/eval/adapter paths untouched. |
| T3.1 base RuleExpr | Bool guards, join-free equality/hash, public exports, and negative-action gates preserved. |
| T3.2 expression-scope validation | Alias uniqueness, repeated-rule explicit alias validation, diagnostics, and alias-aware canonical operands preserved; T3.3 adds join validation as a separate pass. |

### Step 4.2 Draft Review Checklist

- [ ] M-class declaration justified by public DTO/export, additive `RulePortRef.eq(...)`, D2/D4/D5 consumption, and reach-rule algorithm.
- [ ] D2/D4/D5/synthesis/track-plan cite chain is complete and uses real current paths.
- [ ] Seven goals are visible and acceptance items map back to them.
- [ ] Self-join semantics are locked before implementation.
- [ ] Every-Proof-Path Reach Rule has pseudocode, complexity, and corner cases.
- [ ] `RulePortRef.eq(...)` additive T1.4 DTO method is explicitly scoped in §5.2.
- [ ] Join normalization covers endpoint symmetry and duplicate dedupe.
- [ ] `.join(...)` AND-only enforcement includes `_OrGroup.join(...)` diagnostics and no single Rule `.join(...)`.
- [ ] Cross-slice preservation table includes T1.4, T3.1, and T3.2 negative-action gates.

### Step 4.6 Pre-Implementation Grep

| Check | Result |
|---|---|
| `RulePortRef.eq` naming conflict | `rg '\.eq\b' src/factgraph/application/ tests/application/` and `rg 'RulePortRef\.eq' src/factgraph/ tests/` returned no shipped hits; `.eq(...)` is a new T3.3 method and does not collide with T1.4. |
| `_AndGroup` / `_OrGroup` construction and access | `rg '_AndGroup\(|_OrGroup\(' src/factgraph/ tests/` found only class definitions and `_combine` construction in `rule_expr.py`; `rg '_AndGroup\.|_OrGroup\.' src/factgraph/ tests/` returned no hits. |
| `_combine(...)` callers | `rg '_combine\(' src/factgraph/ tests/` found only Rule / RuleOccurrence operators and RuleExpr operators/factories plus the `_combine` definition. |
| `RuleJoinConstraint` naming conflict | `rg 'RuleJoinConstraint' src/factgraph/ tests/ workflow/` found workflow/design and blueprint mentions only; no shipped code or tests define the symbol. |
| `.join(...)` RuleExpr naming conflict | `rg '\.join\(' src/factgraph/application/ src/factgraph/sdk/dsl/ src/factgraph/sdk/__init__.py` found only string/list join usage in current application code; no RuleExpr `.join(...)` surface exists. |
| SDK / application export name conflict | `rg '"RuleJoinConstraint"' src/factgraph/sdk/__init__.py src/factgraph/application/protocol/__init__.py` returned no hits; the export name is new. |
| T3.2 validation helper callers | `rg '_validate_expression_scope\|_iter_rule_operands' src/factgraph/ tests/` found only internal T3.2 `rule_expr.py` definition/call sites. |

### G7 Baseline Record

| Check | Result |
|---|---|
| Branch and sacred state | Branch `v0.2.0-t3-3-joins-and-reach-rule-2026-05-24` at `52eec99e`; sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`; dirty set remains 4 modified files + 1 untracked directory. |
| RuleExpr / T1.4 substrate | Step 4.6 grep already confirmed `RulePortRef.eq`, `_AndGroup` / `_OrGroup`, `_combine`, `RuleJoinConstraint`, `.join(...)`, and export-name scope are clean. |
| Operator / `.eq` / `RuleJoinConstraint` baseline | Step 4.6 grep confirmed `.eq(...)` and `RuleJoinConstraint` are new T3.3 surfaces with no shipped implementation conflict. |
| Requested pytest baseline | Pytest remains out of the T3.3 baseline path because T3.1 recorded the current environment SIGSEGV issue; the spawned tooling investigation remains out of scope for T3.3. |
| Fallback unittest baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 45 tests in 0.008s and passed OK. |
