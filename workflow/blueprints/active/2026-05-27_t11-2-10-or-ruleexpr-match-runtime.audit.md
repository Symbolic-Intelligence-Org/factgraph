# Audit: T11.2.10 OR RuleExpr Match Runtime

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t11-2-10-or-ruleexpr-match-runtime.md`
- Stage: implemented
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `298f4581` | T11.2.10 blueprint pair drafted | Triggered by user handoff after T11.2.9 shipped AND-only match runtime and deferred OR RuleExpr support. |
| 2026-05-27 | scoped | `ece08453` | Step 4.6 OR match inventory recorded | Q1-Q8 answered; branch-body shape, constraint distribution, per-branch connectivity, partial-port rejection, dedup/limit/order, tests, and docs scope locked. |
| 2026-05-27 | implementation | `b7bd48f0` | OR match runtime core landed | SDK match now consumes uniform branch bodies, distributes constraints per branch, and validates connectivity per branch. |
| 2026-05-27 | implementation | `5b41f341` | OR match tests landed | OR runtime matrix added in `tests/test_sdk_read_match_runtime.py`. |
| 2026-05-27 | implementation | `dd88f1a0` | OR match docs/design updated | Match design, quickstart, SDK docs, and CHANGELOG now record OR support. |
| 2026-05-27 | implementation | `be759a1b` | IR variable convention comment added | One-line runtime comment records lowered where IR variable naming convention. |
| 2026-05-27 | closure | this commit | T11.2.10 implemented | Outcome, deviations, and verification recorded. |

## 2. Draft Source Scan

Read-only draft scan findings:

- `src/factgraph/sdk/match_runtime.py` still contains `_MATCH_OR_UNSUPPORTED`
  and rejects multi-branch lowerings in `_build_match_plan(...)`.
- `_MatchPlan` currently stores one `body_ir: list[Any]`, so OR support needs
  an explicit body-shape decision before implementation.
- `_apply_port_constraints(...)` currently appends synthetic atoms to a single
  flat body. OR support must decide how those constraints distribute across
  branches.
- `_validate_connectivity(...)` currently parses body IR and, if it sees
  `OrExpr`, flattens all branch atoms into one graph. Step 4.6 must decide
  whether that is safe for M21 or whether connectivity must be per branch.
- `where_eval.evaluate_where(...)` already supports OR-of-AND semantics and
  branch union/de-duplication at the core rule-evaluation layer.
- RuleExpr lowering exposes multi-branch structures and existing branch
  materialization helpers, but T11.2.9 only consumed the single-branch path.
- T11.2.9 docs and tests intentionally teach only AND `RuleExpr`; OR examples
  should be added only after runtime support lands.

## 3. Step 4.6 Inventory Results

Completed source-backed inventory:

| # | Item | Result |
|---|---|---|
| 1 | Current OR reject points | `_MATCH_OR_UNSUPPORTED` is defined at `src/factgraph/sdk/match_runtime.py:40`; `_build_match_plan(...)` raises it when `probe_plan.branches` or final `plan.branches` has length other than 1 (`match_runtime.py:126`, `:131`). |
| 2 | `_MatchPlan` shape and all call sites | `_MatchPlan` currently stores one `body_ir: list[Any]` (`match_runtime.py:53-57`). `_apply_port_constraints(...)`, `_validate_connectivity(...)`, and `evaluate_where(...)` consume this flat body. Scoped replacement: store uniform branch bodies and lower to one-level or two-level where IR at execution time. |
| 3 | `_build_match_plan(...)` lowering and partial-port behavior | Current RuleExpr path does two passes: probe declared ports, then build a projection head (`match_runtime.py:115-134`). `_declared_port_state_for_rule_expr_plan(...)` returns declared and partial port names (`rule_expr_lowering.py:457-481`); `_validate_head_declared_ports(...)` has the partial-port message text (`:545-569`). Match should track partial ports and reject constrained partial ports explicitly. |
| 4 | Constraint distribution | `_apply_port_constraints(...)` appends synthetic atoms to one flat body today (`match_runtime.py:171-189`). Since `where_eval._normalize_where(...)` accepts only one-level AND or two-level OR-of-AND (`where_eval.py:125-143`), constraints must be appended to each branch to represent outer AND over OR. |
| 5 | Connectivity under OR | `_validate_connectivity(...)` currently flattens `OrExpr` branch atoms into one graph (`match_runtime.py:241-277`). This is unsafe for M21 because a connected branch can hide a disconnected branch. Scoped invariant: per-effective-branch connectivity. |
| 6 | `where_eval` OR normalization / union / sort behavior | `evaluate_where(...)` normalizes bodies, evaluates each branch, de-duplicates full bindings with `seen`, then sorts by sorted variable/value pairs (`where_eval.py:50-97`). This supplies deterministic binding order; match still de-dups projected refs after evaluation. |
| 7 | RuleExpr lowering branch materialization and adapter precedent | `_materialize_adapter_derivation_plan(...)` materializes every branch and emits flat body for one branch or two-level OR body for multiple branches (`rule_expr_lowering.py:321-363`). `_lower_or(...)` expands OR children to multiple branches (`:682-693`). |
| 8 | Partial-port concrete example and expected error | If one OR branch declares `region` and another does not, `_declared_port_state_for_rule_expr_plan(...)` marks `region` partial. `fg.read.match(..., region=\"US\")` should raise `SDKStoreError` that the port is only declared in some RuleExpr branches before matching. |
| 9 | OR test matrix | Extend `tests/test_sdk_read_match_runtime.py` for pure OR, mixed AND+OR, branch duplicate dedup, per-branch disconnected reject, partial-port reject, distributed literal/Field constraints, limit-after-union, and empty/invalid OR construction. |
| 10 | Docs/design update set | Confirmed design anchors: `match-api-design.zh.md` §4.2, §5.4, §7, §12, and §13 M5/M21. User docs to update: quickstart rules-and-inferences, SDK rules docs, and CHANGELOG. |
| 11 | Verification module existence | Existing modules: `tests/test_sdk_read_match_runtime.py`, `tests/test_db_attach_lifecycle.py`, `tests/application/protocol/test_rule_expr.py`, `tests/application/protocol/test_rule_expr_lowering.py`, `tests/application/protocol/test_rule_expr_lowering_adapter.py`, `tests/application/protocol/test_rule_expr_head_validation.py`, `tests/sdk/test_rule_expr_evaluate.py`. |
| 12 | Fixture sufficiency | Existing `Person`/`Account` match fixture can express OR duplicate hits, branch-specific constraints, partial ports, and disconnected branches. Add helper rules in the current test module; no new schema fixture file needed. |
| 13 | Scope-stop findings | No core `where_eval`, `where_ast`, `rule_expr_lowering`, service, EvidenceGraph, release, or dirty-baseline file appears necessary. Stop and amend if implementation contradicts this. |
| 14 | Dirty baseline preservation | Dirty baseline remains unchanged: 4 tracked docs/notebooks plus untracked `rainbird-ai sdk code/`; sacred master hash remains locked. |

## 4. Open Questions Register

Step 4.6 must answer:

| ID | Question | Status |
|---|---|---|
| Q1 | Body IR shape: flat + branches, uniform branches, or `WhereExpr`? | Use uniform branch bodies in `_MatchPlan`; emit one-level IR for one branch and two-level OR-of-AND for multiple branches. |
| Q2 | Constraint distribution across OR branches. | Append constraints to every branch, representing outer AND distributed into OR branches. |
| Q3 | Connectivity semantics: per branch, global, or another invariant. | Per-effective-branch connectivity; global flattening is unsafe. |
| Q4 | Partial-port rejection path when constrained by kwargs. | Track partial ports and raise `SDKStoreError` for constrained partial port before matching. |
| Q5 | Cross-branch de-duplication. | Existing projected `seen_refs` de-dup remains correct after `evaluate_where` union. |
| Q6 | `limit` semantics under OR. | Apply after branch union and projected-ref de-duplication. |
| Q7 | Union ordering determinism. | Deterministic binding order comes from `evaluate_where` final sort; match preserves it while skipping duplicate projected refs. |
| Q8 | OR-specific corner cases to test. | Pure OR, mixed AND+OR, duplicate entity, per-branch connectivity, partial port, constraint distribution, limit-after-union, invalid/empty OR construction. |

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| OR support leaks into core engine changes | Scope escalates beyond M | Verify current `where_eval` / lowering artifacts are sufficient. |
| Connectivity is accidentally global | Silent cross-product branch may pass because another branch connects the vars | Decide M21 per-branch/global semantics explicitly. |
| Constraint atoms are applied only to one branch | Incorrect OR results | Lock distribution rule and test it. |
| Partial ports surface as confusing internal errors | Bad public API | Trace lowering error path and add test. |
| OR ordering is unstable | Flaky tests and user confusion | Trace `evaluate_where` final sorting and document contract. |

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Q1-Q8 answered.
- [x] Runtime implementation reviewed.
- [x] Tests reviewed.
- [x] Docs/design updates reviewed.
- [x] Closure notes filled.

## 7. Closure Notes

T11.2.10 shipped OR `RuleExpr` support for `fg.read.match(...)`:

- Runtime core stayed in `src/factgraph/sdk/match_runtime.py`; no core
  `where_eval`, `where_ast`, or RuleExpr lowering changes were required.
- `_MatchPlan` now stores uniform branch bodies and partial ports.
- Synthetic constraints are distributed to every effective branch.
- M21 connectivity is enforced per effective branch, preventing one connected
  OR branch from masking a disconnected branch.
- Partial-port kwargs raise explicit `SDKStoreError`.
- Cross-branch duplicate projected refs are de-duplicated by the existing
  `seen_refs` set; `limit` applies after union and de-dup.
- Tests cover pure OR, mixed AND+OR, duplicate entity across branches,
  per-branch connectivity rejection, partial port rejection, distributed
  constraints, limit-after-union, and empty OR construction.
- Docs/design now describe OR as shipped and continue to defer witness,
  Query adapter, method-level view, cross-entity tuple, and service/OpenAPI
  surfaces.
- Verification: 25 focused match/attach tests OK, 121 RuleExpr/match focused
  tests OK, touched-file ruff clean, and `git diff --check` clean.
- Deviation recorded: connectivity scanning now reads lowered where IR tuples
  directly. A comment was added to document the `"$..."` Var-name convention.
- Dirty baseline and sacred master were preserved.
