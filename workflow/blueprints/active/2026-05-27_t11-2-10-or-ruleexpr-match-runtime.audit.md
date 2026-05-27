# Audit: T11.2.10 OR RuleExpr Match Runtime

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t11-2-10-or-ruleexpr-match-runtime.md`
- Stage: draft
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T11.2.10 blueprint pair drafted | Triggered by user handoff after T11.2.9 shipped AND-only match runtime and deferred OR RuleExpr support. |

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

Pending. Required inventory items:

| # | Item | Result |
|---|---|---|
| 1 | Current OR reject points | Pending. |
| 2 | `_MatchPlan` shape and all call sites | Pending. |
| 3 | `_build_match_plan(...)` two-pass lowering and partial-port behavior | Pending. |
| 4 | `_apply_port_constraints(...)` distribution options | Pending. |
| 5 | `_validate_connectivity(...)` OR flattening correctness | Pending. |
| 6 | `where_eval` OR normalization / union / sort behavior | Pending. |
| 7 | RuleExpr lowering branch materialization and adapter precedent | Pending. |
| 8 | Partial-port concrete example and expected error | Pending. |
| 9 | OR test matrix | Pending. |
| 10 | Docs/design update set | Pending. |
| 11 | Scope-stop findings | Pending. |
| 12 | Dirty baseline preservation | Pending. |

## 4. Open Questions Register

Step 4.6 must answer:

| ID | Question | Status |
|---|---|---|
| Q1 | Body IR shape: flat + branches, uniform branches, or `WhereExpr`? | Pending. |
| Q2 | Constraint distribution across OR branches. | Pending. |
| Q3 | Connectivity semantics: per branch, global, or another invariant. | Pending. |
| Q4 | Partial-port rejection path when constrained by kwargs. | Pending. |
| Q5 | Cross-branch de-duplication. | Pending. |
| Q6 | `limit` semantics under OR. | Pending. |
| Q7 | Union ordering determinism. | Pending. |
| Q8 | OR-specific corner cases to test. | Pending. |

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| OR support leaks into core engine changes | Scope escalates beyond M | Verify current `where_eval` / lowering artifacts are sufficient. |
| Connectivity is accidentally global | Silent cross-product branch may pass because another branch connects the vars | Decide M21 per-branch/global semantics explicitly. |
| Constraint atoms are applied only to one branch | Incorrect OR results | Lock distribution rule and test it. |
| Partial ports surface as confusing internal errors | Bad public API | Trace lowering error path and add test. |
| OR ordering is unstable | Flaky tests and user confusion | Trace `evaluate_where` final sorting and document contract. |

## 6. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Q1-Q8 answered.
- [ ] Runtime implementation reviewed.
- [ ] Tests reviewed.
- [ ] Docs/design updates reviewed.
- [ ] Closure notes filled.

## 7. Closure Notes

Pending implementation.
