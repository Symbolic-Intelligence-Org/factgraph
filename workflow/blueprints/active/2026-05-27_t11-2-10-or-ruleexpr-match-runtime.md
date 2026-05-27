# Task Blueprint: T11.2.10 OR RuleExpr Match Runtime

- Status: scoped
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
7. **Docs**: update match docs and `CHANGELOG.md` to teach/record only the shipped OR behavior, not witnesses/query persistence/cross-entity tuple output.
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
- Deterministic ordering or de-duplication cannot be explained by the existing
  `evaluate_where(...)` final sort plus match's projected-ref de-duplication,
  or requires broad runtime redesign.
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

## 4.1 Final Scoped Decisions

| Decision | Scoped lock |
|---|---|
| Q1 Body IR shape | Use **uniform branch bodies** inside `_MatchPlan`: even single `Rule` and AND `RuleExpr` normalize to one branch, while OR `RuleExpr` has multiple branches. Build the public where IR as a one-level list for one branch and a two-level OR-of-AND list for multiple branches before calling `evaluate_where(...)`. This mirrors `_materialize_adapter_derivation_plan(...)` and preserves current AND behavior. |
| Q2 Constraint distribution | Append synthetic constraint atoms to **every effective branch**. This represents `constraint AND (branch1 OR branch2)` as `(branch1 AND constraint) OR (branch2 AND constraint)`, which is the shape `where_eval` already accepts. `_materialize_branch(...)` already emits head-port links per branch; match constraints are applied after those branch-local links. |
| Q3 OR connectivity | M21 becomes **per-effective-branch connectivity**. The current fallback that flattens every `OrExpr` branch into one graph is unsafe because one connected branch could mask a disconnected branch. Each branch must independently connect the projected entity port var and all constrained port vars. |
| Q4 Partial ports | Track partial ports from `_declared_port_state_for_rule_expr_plan(...)` in the match plan and reject constrained partial ports with `SDKStoreError` before matching: "match port '<name>' is only declared in some RuleExpr branches". Do not let partial ports fall through as generic unknown ports. |
| Q5 Cross-branch de-duplication | Preserve T11.2.9 projected-ref de-duplication: `evaluate_where(...)` may return multiple bindings across branches, then match uses `seen_refs: set[str]` to return each projected `idref_v1` once. |
| Q6 Limit semantics | `limit` applies **after** branch union and projected-ref de-duplication, never per branch. |
| Q7 Ordering | Public match order is deterministic because `evaluate_where(...)` sorts all bindings by sorted variable/value pairs before match projection. Match preserves that binding order while skipping duplicate projected refs. No semantic branch-priority ordering is promised. |
| Q8 Test matrix | Add pure OR, mixed AND+OR, duplicate entity across branches, per-branch disconnected reject, partial-port reject, constraint distribution across branches, limit-after-union, and empty/invalid OR construction coverage where the public builders allow it. |
| S1 Design section anchors | Actual anchors confirmed: §4.2 RuleExpr, §5.4 connectivity, §7 constraint composition, §12 deferred items, §13 commitments. |
| S2 Verification modules | Existing relevant modules: `tests/test_sdk_read_match_runtime.py`, `tests/test_db_attach_lifecycle.py`, `tests/application/protocol/test_rule_expr.py`, `tests/application/protocol/test_rule_expr_lowering.py`, `tests/application/protocol/test_rule_expr_lowering_adapter.py`, `tests/application/protocol/test_rule_expr_head_validation.py`, `tests/sdk/test_rule_expr_evaluate.py`. |
| S5 Fixture scope | Existing `Person` / `Account` match fixtures are sufficient for OR duplicate, constraint distribution, partial-port, and disconnected tests. Add helper rules in `tests/test_sdk_read_match_runtime.py`; no new schema module is required. |

## 5. Preliminary Implementation Hypothesis

The likely implementation path is to consume existing lowering branches and
existing `evaluate_where(...)` OR semantics:

1. Lower `RuleExpr` using current `_lower_rule_expr(...)` and port-state
   helpers.
2. Materialize every lowering branch into a branch body and store branch bodies
   uniformly in `_MatchPlan`.
3. Compose kwarg constraints onto every effective branch.
4. Validate connectivity independently for every effective branch.
5. Evaluate a one-level or two-level where IR through current `evaluate_where`.
6. Project and de-duplicate entity refs exactly as T11.2.9 does.

This is a hypothesis. If source inspection finds a simpler or safer way that
stays inside scope, use that and record the decision in Step 4.6.

## 6. Step 4.6 Inventory Plan

Step 4.6 inventory is complete and locked these source-backed results:

| # | Item | Result |
|---|---|---|
| 1 | Current OR reject points | `_MATCH_OR_UNSUPPORTED` at `match_runtime.py:40` plus branch-count raises at `:126` and `:131`. Removing these requires changing `_MatchPlan` and branch materialization, not core engine code. |
| 2 | `_MatchPlan` shape and call sites | `_MatchPlan` currently stores `body_ir: list[Any]` at `match_runtime.py:53-57`; `_apply_port_constraints(...)`, `_validate_connectivity(...)`, and `evaluate_where(...)` consume that flat body. Scoped replacement is uniform branch bodies plus a helper that lowers one branch to one-level IR and multiple branches to OR-of-AND IR. |
| 3 | `_build_match_plan(...)` lowering and partial ports | Current RuleExpr path probes with `Rule.projection("__fg_match_probe")`, rejects multiple branches, then builds a head from declared ports (`match_runtime.py:115-134`). `_declared_port_state_for_rule_expr_plan(...)` returns declared and partial ports (`rule_expr_lowering.py:457-481`), and `_validate_head_declared_ports(...)` reports "only declared in some RuleExpr branches" (`:545-569`). T11.2.10 should preserve partial-port names in `_MatchPlan` for clearer SDK errors. |
| 4 | Constraint distribution | `_apply_port_constraints(...)` currently appends synthetic atoms to one flat body (`match_runtime.py:171-189`). `where_eval` accepts only one-level AND or two-level OR-of-AND (`where_eval.py:125-143`), so a logical outer AND must be distributed into each branch. `_materialize_branch(...)` already appends branch-local head-port links (`rule_expr_lowering.py:726-793`), so constraints can be appended after branch materialization. |
| 5 | Connectivity under OR | Current `_validate_connectivity(...)` flattens `OrExpr` branches (`match_runtime.py:241-277`), which is unsafe for OR. M21 must be per effective branch: every branch independently connects projected and constrained vars. |
| 6 | `where_eval` OR behavior | `evaluate_where(...)` normalizes OR-of-AND into `bodies`, evaluates every body, de-duplicates full bindings via `seen`, then sorts all bindings by sorted variable/value pairs (`where_eval.py:50-97`). Empty OR branches are rejected by `_normalize_where(...)` (`:125-143`). |
| 7 | RuleExpr branch materialization precedent | `_materialize_adapter_derivation_plan(...)` materializes every branch and emits one-level body for one branch or two-level body for multiple branches (`rule_expr_lowering.py:321-363`). `_lower_or(...)` expands OR children to branch tuples (`:682-693`). Match should mirror this representation and not alter lowering. |
| 8 | Partial-port concrete path | For `expr = rule_with_region | rule_without_region`, `_declared_port_state_for_rule_expr_plan(...)` marks `region` partial because at least one branch lacks it (`rule_expr_lowering.py:457-481`). If `region` appears in `port_constraints`, scoped behavior is a direct `SDKStoreError` for partial port before matching, not a generic unknown-port error. |
| 9 | OR test matrix | Extend `tests/test_sdk_read_match_runtime.py`: pure OR, mixed AND+OR, duplicate entity across branches, per-branch disconnected reject, partial-port reject, constraint distribution across every branch, limit-after-union, invalid empty OR builder behavior, and unchanged AND behavior. |
| 10 | Docs/design update set | Update `match-api-design.zh.md` §4.2/§5.4/§7/§12/§13, `docs/official/kernel/quickstart/rules-and-inferences.md`, `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`, and `CHANGELOG.md`. Keep witness/query/method-level view docs deferred. |
| 11 | Verification modules | Relevant modules exist: `tests/test_sdk_read_match_runtime.py`, `tests/test_db_attach_lifecycle.py`, `tests/application/protocol/test_rule_expr.py`, `tests/application/protocol/test_rule_expr_lowering.py`, `tests/application/protocol/test_rule_expr_lowering_adapter.py`, `tests/application/protocol/test_rule_expr_head_validation.py`, and `tests/sdk/test_rule_expr_evaluate.py`. |
| 12 | Scope-stop findings | No core engine/lowering/service/EvidenceGraph/release change is required by inventory. If implementation contradicts this, stop and amend. |
| 13 | Dirty baseline and sacred master | Dirty baseline remains the known 4 tracked docs/notebooks plus untracked `rainbird-ai sdk code/`; sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`. |

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

- [x] Step 4.6 inventory answers Q1-Q8 with source-backed rationale.
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
