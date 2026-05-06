# Rule Condition Replace — Audit Log

- Blueprint: [2026-05-05_rule-condition-replace.md](./2026-05-05_rule-condition-replace.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.5b

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 5b branch `v0.1-rule-replace-step0-2026-05-05` cut off `7969dab`(Batch 5a Rule Disable final + post-archive hardening). Draft is intentionally Step-0-first and records the parent-plan A/B/C decision gate:literal-only ship,abandon,or split. No implementation is authorized until Step 0 chooses one path and,for Path A only,status moves to `scoped`. |
| 2026-05-06 | draft | Pre-commit review pass 1 | Four P3 framing polish items landed before draft commit:§1 now states the master-plan default lean is Path B abandonment;§5.2 explains why predicate term constants are riskier than comparison/filter literals;§5.5 warns that generalizing Batch 5a `RuleDisableResult` would conflict with archived drift-gate posture and sets a separate result DTO as default expectation;§6 strengthens the `evaluate_native_where(...)` boundary using the Batch 5a frontier-drift correction as hard precedent. |
| 2026-05-06 | draft | Step 0.A spike completed | Option A passes only as a narrow native `RuleLiteralReplaceAction`:replace one existing `Const` leaf in one top-level native where atom and return dual output(variant rows + original-frame ProofFrame). The spike rejects generalized `param_override`,variable edits,structural atom edits,`not` internals,RuleRef replace,condition weights,ProbLog carriers,and PyReason bounds. Step 0.B remains required before scope freeze. |
| 2026-05-06 | draft | Pre-commit review pass on Step 0.A | Review accepted Step 0.A and requested one P3 carry-over:Step 0.B must freeze the Path A primitive function name and module location. The blueprint now sets the default expectation to extend lower-level `where_eval.evaluate_where(...)` with a private helper parallel to Batch 5a `_apply_disabled_locators(...)`,while keeping `evaluate_native_where(...)` unchanged. |
| 2026-05-06 | draft | Step 0.B spike completed | Path A shape frozen: `RuleLiteralReplaceAction` joins `EvaluationOverlay.rule_actions`;`RuleLiteralPath` encodes five Const-leaf path kinds;runtime surface is separate `RuleLiteralReplaceRequest/Result` and `check_rule_literal_replace_action(...)`;core primitive is `WhereLiteralReplacement` plus `evaluate_where(..., literal_replacements=...)`;MVP accepts exactly one replace action;Rule Disable gets a narrow non-disable-action rejection guard;Fact Overlay and ProofFrame keep generic rule-action rejection. Blueprint remains draft until review accepts this freeze. |
| 2026-05-06 | draft | Pre-commit review pass on Step 0.B | Review accepted Step 0.B and requested two P3 polish items:dedicate `RULE_LITERAL_REPLACE_NEW_LITERAL_INVALID` to variable/non-native replacement values,and explain why future overlap with disabled locators applies literal replacement before disable. Both were added before commit. |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 5b starts after Batch 5a closed at `7969dab`. Entry criteria are met:Rule Disable exists application-first,`EvaluationOverlay.rule_actions` exists,Fact Overlay / ProofFrame reject rule actions rather than silently ignoring them,and the lower-level disabled-locator primitive exists without `evaluate_native_where(...)` signature drift.

The active parent plan explicitly marks Batch 5b as a Step 0 decision batch,not an implementation-first batch. It requires one of three outputs:

- Option A — literal-only ship;
- Option B — abandon;
- Option C — split into separate capability DTOs.

The default posture is conservative:if the DTO is not crisp,choose Option B rather than recreating a generalized `param_override`.

### 2026-05-06 — v0.1.4 Negative Result Applied

The old v0.1.4 `param_override` blueprint is used as negative evidence. It found four distinct semantic lanes:

- literal / term changes;
- condition weight changes;
- ProbLog probability carriers;
- PyReason bounds / thresholds.

Batch 5b therefore only asks whether the first lane can be made useful and crisp as **literal-only rule condition replace**. The other three lanes are non-goals unless Step 0 selects Option C and records an explicit split.

### 2026-05-06 — Draft Framing

The draft is deliberately falsifiability-first. It does not present Path A as the default implementation. It requires Step 0 to prove target identity, literal-path semantics, atom-kind scope, variable-binding safety, ProofFrame compatibility, RuleRef boundary, and layer boundary before any code changes.

If Step 0 selects Path B,that is a valid close-out and should be archived as abandoned. If Step 0 selects Path C,the split should become separate blueprints rather than a merged implementation inside this batch.

### 2026-05-06 — Pre-commit Review Pass 1

Review accepted the draft framing as structurally sound and requested wording tighteners only. The changes make conservative defaults visible earlier, clarify predicate-term risk, protect Batch 5a result DTOs from accidental generalization, and restate `evaluate_native_where(...)` signature stability as a hard frontier-gate boundary rather than a soft preference.

### 2026-05-06 — Step 0.A Decision

Step 0.A selected **Option A, narrow literal-only ship**, not Path B abandonment and not Path C split. This is justified only because the selected first slice is materially narrower than v0.1.4 `param_override`:the action targets an existing AST `Const` leaf and preserves atom kind,arity,list length,and variable/dataflow role.

The selected first-slice atom families are:

- predicate term constants where the current term is already `Const`;
- comparison/filter constants in `eq`, `ne`, `gt`, `ge`, `lt`, and `le`;
- existing `in` list members by index;
- `addc` / `mulc` constant operand `c`.

The spike explicitly rejects variable-to-literal and literal-to-variable edits because current native dataflow can turn predicates and `eq` into binders. It also rejects generic arithmetic operands in `add` / `sub` / `neg`, `not` internals,RuleRef atoms,atom-kind changes,arity changes,and list-length changes. Those are not part of Path A and must not be quietly added during implementation.

The v0.1.4 negative result remains binding. Condition weights,ProbLog probability carriers,and PyReason bounds/thresholds are separate semantic lanes. They are not included in Batch 5b, and Path C would require child blueprints rather than a merged implementation here.

Step 0.B carry-overs are still open:DTO names/fields,exact `literal_path` encoding,result DTO shape,error codes,single-vs-multi action MVP,two-entrypoint compatibility,and drift gates. Until those are frozen,the blueprint remains `draft` and implementation is not authorized.

### 2026-05-06 — Pre-commit Review Pass on Step 0.A

Review accepted the Step 0.A falsification result and found no blocker. The only requested polish was to make the primitive landing zone explicit before Step 0.B:Path A should follow the Batch 5a pattern by extending the lower-level native `where_eval.evaluate_where(...)` path and adding a private helper parallel to `_apply_disabled_locators(...)`. The frontier-protected `evaluate_native_where(...)` signature remains a hard no-change boundary.

### 2026-05-06 — Step 0.B Decision

Step 0.B froze the implementation shape for the narrow Path A selected by Step 0.A.

Protocol decisions:

- Add `RuleLiteralPath(kind,index)` and `RuleLiteralReplaceAction(rule_id,version,branch_index,atom_index,literal_path,old_literal,new_literal,note=None)` to the shared overlay protocol.
- Extend `RuleOverlayAction` to `RuleDisableAction | RuleLiteralReplaceAction`.
- Keep `RuleDisableResult` untouched and add a separate `RuleLiteralReplaceRequest / RuleLiteralReplaceResult` surface with local status values `completed | unsupported | invalid_request`.

Runtime decisions:

- Add `check_rule_literal_replace_action(...)` as the only runtime that interprets `RuleLiteralReplaceAction`.
- Runtime MVP accepts exactly one replace action;multi-action support remains deferred behind the tuple container.
- Fact actions in the request overlay are invalid for Rule Literal Replace.
- RuleRef-bearing support artifacts or rule bodies are unsupported,matching Batch 5a's narrow rule action posture.

Core primitive decisions:

- Extend lower-level `kernel.core.rules.where_eval.evaluate_where(...)` with `literal_replacements`.
- Add a core `WhereLiteralReplacement` dataclass and private `_apply_literal_replacements(...)` helper parallel to Batch 5a `_apply_disabled_locators(...)`.
- Keep `evaluate_native_where(...)` unchanged;signature drift remains a hard block.

Cross-runtime compatibility decisions:

- `check_rule_disable_action(...)` must type-check the single rule action and return `RULE_DISABLE_ACTION_TYPE_UNSUPPORTED` for `RuleLiteralReplaceAction`,instead of reading disable-specific fields first.
- `check_fact_overlay_binding(...)` keeps generic `RULE_ACTIONS_NOT_SUPPORTED` behavior for any rule action.
- `recheck_proof_frame(...)` keeps frame-level `unknown` for any rule action and does not inspect `RuleLiteralReplaceAction`.

Rejected alternatives:

- Do not generalize Batch 5a `RuleDisableResult`;that would create archived DTO drift.
- Do not let Rule Disable silently process or crash on non-disable rule actions.
- Do not add action-specific semantics to Fact Overlay or ProofFrame.
- Do not expand RuleRef,`not` internals,condition weights,ProbLog carriers,PyReason bounds,or `superseded_by_full_eval`.

The blueprint remains `draft` for review. If this freeze is accepted,the next commit should move `Status: draft → scoped` before implementation begins.

### 2026-05-06 — Pre-commit Review Pass on Step 0.B

Review accepted the Step 0.B freeze and found no blocker. Two clarity fixes landed before commit:

- `new_literal` validation now has a dedicated `RULE_LITERAL_REPLACE_NEW_LITERAL_INVALID` code so variable-form or unsupported native-literal values do not collapse into path/stale-target errors.
- The future ordering rule for combined `literal_replacements` and `disabled_locators` now explains why replacements apply before disables:overlap still resolves to disable-wins,while non-overlap is order-independent.
