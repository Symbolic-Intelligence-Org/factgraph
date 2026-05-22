# Task Blueprint Audit: Rule Add Condition + Binding Planner(Batch 5c)

- Blueprint: [2026-05-05_add-condition-binding-planner.md](./2026-05-05_add-condition-binding-planner.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 5c Step 0 framing drafted on `v0.1-add-condition-binding-planner-2026-05-05` off Batch 5b final `5213e76`. The draft intentionally treats "add condition + binding planner" as a falsifiable premise rather than a pre-scoped implementation path. |
| 2026-05-06 | scoped | Scope frozen | Status moved from `draft` to `scoped` after Step 0.A and Step 0.B review. Implementation may proceed only within §5.7/§5.8:narrow add-filter action,synthetic added-atom ProofFrame verdict,one-action MVP,no new-variable planner,no ProofFrame protocol change,no `evaluate_native_where(...)` change. |
| 2026-05-06 | implemented | Implementation shipped and archived | Added `RuleAddConditionAction`,separate request/result DTOs,one-action native runtime,`atom_binds_new_variables(...)`,`evaluate_where(..., added_conditions=...)`,synthetic added-atom ProofFrame verdict,focused tests/docs,and archive inventory update. Verification:192 focused tests OK,full kernel 1265 OK / 1 skipped,ruff clean,`git diff --check` clean. |
| 2026-05-06 | implemented | Post-archive hardening | Strict review found a P2 contract gap shared with Batch 5a/5b:the local RuleRef body scan only saw top-level branch atoms,so `not(ruleref(...))` reached native evaluation and returned `RULE_ADD_CONDITION_NATIVE_EVAL_ERROR` instead of the frozen `RULE_ADD_CONDITION_RULE_REF_UNSUPPORTED`. The scan is now recursive for compound atoms currently represented by `not` bodies,and all three rule-action runtimes have focused regressions. No protocol,ProofFrame,RuleRef substrate,SDK,service,or agent surface changed. |

## Decision Notes

### 2026-05-06 — Initial Draft Framing

- **Default conservative posture:** Batch 5c has no v0.1.x prior art,so the draft makes abandonment/suspension and split outcomes first-class. Path A is only a narrow first-slice candidate.
- **False-merge risk is higher than v0.1.4:** v0.1.4 merged four parameter lanes under one DTO. Batch 5c may merge two lifecycle-different concerns:add-condition execution and binding-planner design. The draft's first falsifier tests that directly.
- **Parent-plan ProofFrame conflict surfaced early:** master plan §5.5c mentions `superseded_by_full_eval`,but Batch 4 collapsed that status. The draft requires Step 0 to resolve this explicitly instead of reviving the status by implication.
- **Current substrate grounding:** `where_ast_validate.py` already has dataflow rules for bound variables,`eq` binding,and `not` correlation. The draft asks Step 0 to decide whether this is enough for a narrow no-new-variable add-filter slice or whether a new binding planner is required.
- **Deferred hardening kept separate:** the Batch 4 ProofFrame `rule_refs` symmetric gap is named as out-of-scope unless explicitly scoped,so Batch 5c cannot hide unrelated hardening inside its implementation.

### 2026-05-06 — Pre-commit Review Pass 1

Review accepted the falsifiability-first framing and requested three P3 polish edits before draft commit:Path C was sharpened so it only means split into child blueprint(s),not an alternate spelling of Path A;falsifier #5 now cross-references the parent-plan ProofFrame conflict in §5.6;and inserted-locator identity options now list their hidden trade-offs so Step 0.B cannot treat them as equivalent.

### 2026-05-06 — Step 0.A Spike Completed

Step 0.A selected Path A only as a **narrow add-filter first slice**. The full master-plan phrase "Add Condition + Binding Planner" was treated as a false-merge risk and reduced:Batch 5c may add one top-level native filter atom that references only variables already bound earlier in the branch;any new-variable introduction,`pred` atom binder,`eq` binder,arithmetic binder,`not`,RuleRef,or multi-action ordering is deferred/rejected. The binding-planner contract for this slice is a deterministic preflight("does not bind new variables"),not a shipped planner capability. Step 0.A also rejected `superseded_by_full_eval` revival and kept the Batch 4/5a/5b dual-output discipline:variant rows carry universe shift;ProofFrame explains the old frame only.

### 2026-05-06 — Step 0.A Pre-commit Review

Review accepted the Step 0.A reduction and requested three P3 carry-over refinements before commit:inserted identity and ProofFrame mapping are now a single coupled Step 0.B decision;Step 0.B must decide whether a narrow `where_ast_validate.py` binding-effect primitive is needed;and the lower-level primitive default now mirrors Batch 5a/5b explicitly(`evaluate_where(..., added_conditions=frozenset())` + private `_apply_added_conditions(...)`,with `evaluate_native_where(...)` unchanged).

### 2026-05-06 — Step 0.B Spike Completed

Step 0.B froze Path A rather than falling back to Path B. The coupled identity/ProofFrame problem has an honest mapping:the runtime appends one synthetic `ProofFrameAtomVerdict` with atom key `b{branch}.add{action_index}:{atom_kind}`. Existing artifact atom verdicts remain `still_valid`;the synthetic verdict is `invalidated` iff the original `binding_items` disappears from `variant_rows`,otherwise `still_valid`. This avoids renumbering old locators,does not modify the Batch 4 ProofFrame protocol,and preserves the 3-status aggregate invariant. Step 0.B also froze a separate `RuleAddConditionRequest / Result`,raw native tuple `RuleAddedAtom`,one-action MVP,narrow `where_ast_validate.py` binding-effect helper,`evaluate_where(..., added_conditions=frozenset())`,and cross-runtime non-owned action guards for Rule Disable and Rule Literal Replace.

### 2026-05-06 — Step 0.B Pre-commit Review

Review accepted the synthetic-verdict mapping and requested three P3 clarifications before commit:§5.8.3 now explains why existing `not` steps can be `still_valid` under filter-only add-condition even though Batch 4 fact-overlays strictly deferred `not`;§5.8.4 marks the three-way primitive ordering as forward-compatible only,not a current multi-action semantics claim;and §5.8.7 notes Batch 5a/5b runtimes already reject non-owned action types through existing `isinstance` guards,so tests should verify behavior without requiring runtime edits.

### 2026-05-06 — Scoped For Implementation

The scoped implementation lane is intentionally narrow:ship `RuleAddConditionAction` for one added native filter atom over already-bound variables;append one synthetic added-atom ProofFrame verdict;return variant rows from full native evaluation;add no public binding-planner surface;and preserve existing ProofFrame protocol,RuleRef substrate,SDK/service/agent surfaces,and `evaluate_native_where(...)`.

### 2026-05-06 — Implementation Close-out

Implementation followed the scoped shape. The novel synthetic-verdict mapping shipped without changing `ProofFrameAtomVerdict` or `ProofFrameStatus`;`b{branch}.add{action}:{kind}` keys are produced only by `check_rule_add_condition_action(...)`. Existing Rule Disable and Rule Literal Replace runtimes were not edited;new tests verify their existing type guards reject `RuleAddConditionAction`. The core evaluator gained only the lower-level `WhereAddedCondition` / `added_conditions` primitive,with no `evaluate_native_where(...)` signature drift and no RuleRef substrate,SDK,service,or agent drift.
