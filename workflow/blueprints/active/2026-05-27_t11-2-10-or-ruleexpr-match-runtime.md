# Task Blueprint: T11.2.10 OR RuleExpr Match Runtime

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M (OR RuleExpr support for the existing match runtime)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t11-2-10-or-ruleexpr-match-runtime.audit.md`
- Trigger: T11.2.9 shipped the first read-side match runtime tranche with `Rule` and AND-only `RuleExpr`; `RuleExpr` OR support remained the explicit follow-up needed to fully satisfy M5.

## 0. Scope Locks

### In scope

Implement OR `RuleExpr` support for the already-shipped read-side match runtime:

```python
fg.read.match(EntityCls, rule_expr_with_or, *, limit=None, **port_constraints)
    -> tuple[EntityCls snapshot, ...]
```

Required work areas:

1. **Runtime body shape**: update `src/factgraph/sdk/match_runtime.py` so match can evaluate multi-branch OR `RuleExpr` output from existing lowering.
2. **Constraint distribution**: compose literal and own-class `Field` constraints across OR branches without mutating `Rule` / `RuleExpr`.
3. **Connectivity safety**: upgrade M21 wording and runtime validation for OR semantics.
4. **Partial ports**: preserve RuleExpr lowering's partial-port rejection behavior and add user-facing tests.
5. **Union semantics**: lock and test branch union, cross-branch de-duplication, `limit`, and deterministic ordering.
6. **Tests**: extend `tests/test_sdk_read_match_runtime.py` for OR-specific behavior and regress AND behavior.
7. **Docs**: update match docs to teach only the shipped OR behavior, not witnesses/query persistence/cross-entity tuple output.
8. **Design note**: update `workflow/design/design-points/active/match-api-design.zh.md` so M5 moves from "OR follow-up target" to shipped OR support and M21 states the OR connectivity invariant.

### Out of scope

- Any change to `src/factgraph/core/rules/where_eval.py`, `where_ast.py`, or `application/protocol/rule_expr_lowering.py`.
- Service / OpenAPI endpoints.
- EvidenceGraph, witness assertion output, `.as_assertions()`, `.witnesses()`, or `.to_view()`.
- Cross-entity tuple output such as `match((User, Order), expr)`.
- Legacy `Query` adapter or `fg.queries.*` persistence.
- Method-level `view=` support.
- Snapshot-at-tx matching (`at=` / `as_of`).
- Notebook namespace cleanup and remaining dirty baseline files.
- Release machinery changes.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

- OR support requires changing core `where_eval`, `where_ast`, or RuleExpr lowering rather than consuming their existing output.
- OR support requires a public wrapper DTO or return shape change.
- M21 cannot be made precise for OR without changing the T11.2.7 match design.
- Partial ports cannot be rejected through current lowering/projection paths.
- Deterministic ordering or de-duplication cannot be preserved without broad runtime redesign.
- Implementation touches service/OpenAPI/EvidenceGraph/release machinery or unrelated dirty baseline files.

## 1. Problem

T11.2.9 intentionally rejected OR `RuleExpr`:

```text
fg.read.match(...) currently supports Rule and AND RuleExpr only
```

That kept the first runtime tranche small, but it left M5 only partially
implemented. The lower layers already have OR-aware concepts:

- `where_ast.py` has `AndExpr` / `OrExpr` plus AST <-> IR conversion;
- `where_eval.py` can evaluate OR-of-AND bodies with union and de-duplication;
- `rule_expr_lowering.py` can produce multiple lowering branches.

T11.2.10 should decide how SDK match consumes those existing artifacts without
moving the core engine boundary.

## 2. Inputs

| Source | Role |
|---|---|
| `src/factgraph/sdk/match_runtime.py` | Current T11.2.9 runtime, OR reject points, match plan, constraints, connectivity, de-duplication. |
| `src/factgraph/core/rules/where_ast.py` | Existing `AndExpr` / `OrExpr` and AST/IR conversion. |
| `src/factgraph/core/rules/where_eval.py` | Existing OR-of-AND normalization, branch union, de-dup, and final ordering behavior. |
| `src/factgraph/application/protocol/rule_expr_lowering.py` | RuleExpr lowering branches, port state, partial-port rejection, branch materialization, adapter multi-branch precedent. |
| `workflow/design/design-points/active/match-api-design.zh.md` | Canonical M1-M21 design commitments; §5.4 connectivity invariant; M5 OR follow-up note. |
| `workflow/blueprints/archive/2026-05-27_t11-2-9-match-runtime-implementation.md` and audit | Prior implementation blueprint, scoped inventory, acceptance matrix, and OR-deferred outcome. |
| `tests/test_sdk_read_match_runtime.py` | Current match runtime matrix to extend. |
| `tests/test_db_attach_lifecycle.py` | Attach-view scoped match coverage to preserve. |

## 3. Design Questions To Resolve In Step 4.6

Step 4.6 must answer these questions from source inspection and small runtime
experiments if needed. Draft does not pre-decide them.

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Body IR shape | Choose `_MatchPlan.body_ir + branches`, uniform `branches: list[list[atom]]`, or `WhereExpr` internal representation. Explain why it preserves single-Rule and AND behavior. |
| Q2 | Constraint distribution | Decide whether synthetic constraint atoms are appended to every branch, represented as an outer AND, or handled another way. Cite `_materialize_branch` head-port-link behavior. |
| Q3 | OR connectivity semantics | Decide whether M21 is per-branch, global, or another invariant. Judge current flattening fallback in `_validate_connectivity` and update design wording. |
| Q4 | Partial port rejection path | Trace what happens when a user constrains a port declared only in some RuleExpr branches; lock expected error path and tests. |
| Q5 | Cross-branch de-duplication | Confirm whether `seen_refs: set[str]` naturally dedups one EntitySnapshot matched by multiple branches. |
| Q6 | Limit semantics | Lock whether `limit=N` applies after union + de-duplication or per branch. |
| Q7 | Union ordering determinism | Trace whether final order comes from `evaluate_where` sorting or match runtime. Document the contract. |
| Q8 | OR-specific test matrix | Lock tests for pure OR, mixed AND+OR, cross-branch duplicate entity, per-branch connectivity rejection, partial port rejection, constraint distribution, limit after union, and empty/null branch behavior. |

## 4. Existing Commitments To Preserve

T11.2.10 must preserve T11.2.7/T11.2.9 commitments unless it first amends the
design and blueprint:

| ID | Runtime requirement |
|---|---|
| M1-M4 | Public shape remains `fg.read.match(EntityCls, template, **kwargs)` and exactly one matching entity-ref projection port. |
| M5 | `RuleExpr` support expands from AND-only to include OR without accepting bare list/tuple. |
| M6-M8 | Legacy `Query` stays deferred; `Rule.head` stays irrelevant; match remains pattern matching, not inference. |
| M9-M11 | Return shape remains `tuple[EntityCls snapshot, ...]`, no wrapper DTO or chain methods. |
| M12-M15 | Literal / own-class Field kwargs still compose synthetic constraints without mutating Rule data. |
| M16 | Attach-time view scope only; method-level `view=` remains rejected. |
| M17-M20 | No witness output, no cross-entity tuple output, no `fg.eval.run` deletion, no assertion facade coupling. |
| M21 | Connectivity safety remains mandatory and must become precise for OR. |

## 5. Preliminary Implementation Hypothesis

The likely implementation path is to consume existing lowering branches and
existing `evaluate_where(...)` OR semantics:

1. Lower `RuleExpr` using current `_lower_rule_expr(...)` and port-state
   helpers.
2. Materialize every lowering branch into a branch body.
3. Compose kwarg constraints onto the effective branch bodies according to the
   Step 4.6 Q2 decision.
4. Validate connectivity according to the Step 4.6 Q3 decision.
5. Evaluate a one-level or two-level where IR through current `evaluate_where`.
6. Project and de-duplicate entity refs exactly as T11.2.9 does.

This is a hypothesis. If source inspection finds a simpler or safer way that
stays inside scope, use that and record the decision in Step 4.6.

## 6. Step 4.6 Inventory Plan

Step 4.6 must complete a source-backed inventory before implementation:

1. Current OR reject points in `match_runtime.py`: constant, branch count
   checks, and affected tests/docs.
2. `_MatchPlan` shape and call sites.
3. Current `_build_match_plan(...)` two-pass lowering and partial-port behavior.
4. `_apply_port_constraints(...)` shape and how synthetic atoms should distribute.
5. `_validate_connectivity(...)` current `OrExpr` flattening fallback and why it is or is not correct.
6. `where_eval._normalize_where(...)`, branch union, final sorting, and de-dup behavior.
7. `rule_expr_lowering` branch materialization and `_materialize_adapter_derivation_plan(...)` multi-branch precedent.
8. Partial-port rejection path with a concrete RuleExpr example.
9. Existing T11.2.9 tests to preserve and OR test additions.
10. Docs files needing OR examples and docs files that must remain silent.
11. Design doc sections to update: §4.2, §5.4, §7, §12, §13 M5/M21.
12. Stop-amend check: verify no core engine/service/EvidenceGraph/release file is required.
13. Dirty baseline and sacred master preservation.

## 7. Implementation Split Proposal

Likely split after Step 4.6:

1. **Runtime core**: match plan branch representation, constraint distribution,
   OR evaluation, de-dup/limit/order behavior.
2. **Tests**: OR matrix in `tests/test_sdk_read_match_runtime.py`, plus attach
   regression if needed.
3. **Docs/design**: match design updates, quickstart/SDK docs OR example,
   `CHANGELOG.md` OR support note.
4. **Verification/closure**: focused suites, broader relevant suites, ruff,
   `git diff --check`, outcome, archive.

## 8. Acceptance

- [ ] Step 4.6 inventory answers Q1-Q8 with source-backed rationale.
- [ ] OR RuleExpr runtime support lands without core engine/lowering changes.
- [ ] Single Rule and AND RuleExpr match behavior remains unchanged.
- [ ] OR with literal constraints works.
- [ ] OR with own-class Field constraints works or is explicitly rejected with a scoped rationale.
- [ ] Cross-branch duplicate entity refs return one snapshot.
- [ ] `limit` behavior under OR is tested and documented.
- [ ] Union ordering is deterministic and documented.
- [ ] Partial-port constraints reject with a clear error and test.
- [ ] M21 connectivity behavior under OR is tested and reflected in `match-api-design.zh.md`.
- [ ] Method-level `view=` remains rejected; attach-view scope still works.
- [ ] Docs teach only shipped OR match behavior, not witness/query/method-level view features.
- [ ] Focused tests and relevant suites pass.
- [ ] `ruff` and `git diff --check` pass.
- [ ] Dirty baseline and sacred master are preserved.

## 9. Verification Commands

Draft expected commands, to be finalized after Step 4.6:

```bash
PYTHONPATH=src python -m unittest tests.test_sdk_read_match_runtime
PYTHONPATH=src python -m unittest tests.test_db_attach_lifecycle
PYTHONPATH=src python -m unittest tests.application.protocol.test_rule_expr tests.application.protocol.test_rule_expr_lowering tests.sdk.test_rule_expr_evaluate tests.test_sdk_read_match_runtime
python -m ruff check src/factgraph/sdk/match_runtime.py src/factgraph/sdk/store.py tests/test_sdk_read_match_runtime.py tests/test_db_attach_lifecycle.py
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

Pending implementation.
