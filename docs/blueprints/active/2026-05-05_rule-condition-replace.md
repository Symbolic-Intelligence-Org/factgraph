# Rule Condition Replace(Batch 5b of Round Story Completion Plan)

- Status: draft
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Branch: `v0.1-rule-replace-step0-2026-05-05`
- Scope: Batch 5b Step 0 — decide whether rule condition replace ships,literal-only narrows,splits,or is abandoned
- Related Modules:
  - `src/kernel/application/protocol/derivation_fact_overlay.py`
  - `src/kernel/application/protocol/rule_disable.py`
  - `src/kernel/application/rule_disable_runtime.py`
  - `src/kernel/core/rules/where_eval.py`
- Related Docs:
  - [Round Story Completion Plan](./2026-05-05_round-story-completion-plan.md) §5.5b
  - [Batch 5a Rule Disable archive](../archive/2026-05-05_rule-disable.md)
  - [Rule replay redesign lessons](../../references/working/rule-replay-line-redesign-input/60_lessons-learned.md) §3.5 / §4.1
  - [v0.1.4 Param Override negative result](../../references/working/rule-replay-line-redesign-input/50_archived-blueprints/2026-05-02_v0.1.4-param-override.md)
- Audit Log:
  - [2026-05-05_rule-condition-replace.audit.md](./2026-05-05_rule-condition-replace.audit.md)

## 1. Problem

Batch 5a reintroduced one rule-side operation application-first:temporarily disable one native rule-body locator and return variant rows plus original-frame ProofFrame. The next master-plan slot is Batch 5b,Rule Condition Replace. This is the highest-risk sub-batch because the old v0.1.4 `param_override` probe was abandoned after Step 0 discovered four unrelated semantic families under one name.

Batch 5b must not repeat that failure by shipping a generalized "override" action. Its first job is a source-backed Step 0 decision:

- **Option A — literal-only ship:** one crisp action replaces one literal leaf inside one native rule-body atom.
- **Option B — abandon:** no single crisp DTO exists;record decomposition and move to Batch 5c.
- **Option C — split:** replace decomposes into multiple independent capability DTOs,with implementation deferred to separate blueprints.

**Default lean per master plan §5.5b:Path B(abandon).** Path A only ships if Step 0 proves all §5.2 constraints. Path C only applies if Step 0 finds genuinely separate capabilities,and implementation must be deferred to child blueprints.

## 2. Goals

- Run a falsifiability-first Step 0 that explicitly chooses A/B/C before any implementation.
- Reuse Batch 5a's application-first lane only if a condition-replace DTO is semantically crisp.
- Preserve Batch 5a's dual-output separation if Option A ships:variant rows are full native evaluation output;ProofFrame explains the original frame only.
- Preserve locator stability:`b{branch}.a{atom}` continues to identify source atoms,not post-edit positions.
- Record abandonment as a valid close-out if the literal-only action is just replace sugar or if the DTO family decomposes.

## 3. Non-goals

- No generalized `param_override`.
- No `condition_weights` override.
- No ProbLog probability carrier override.
- No PyReason bound / threshold override.
- No SDK replay substrate or `SDKStore.evaluate(..., overrides=...)`.
- No persistent rule variant storage or promotion to a new rule version.
- No general AST editor,add-condition operation,or atom-kind change.
- No RuleRef-recursive replace unless Step 0 proves a narrow first slice;default is reject/defer.
- No Fact Overlay / ProofFrame protocol expansion unless Step 0 records a parent-plan deviation.
- No variant `SupportArtifact` capture unless Step 0 makes it necessary for the selected path.

## 4. Current Context

Batch 5a final HEAD is `7969dab`. It shipped:

- `EvaluationOverlay(fact_actions=(), rule_actions=())` with `RuleDisableAction` as the only current `RuleOverlayAction`;
- `check_rule_disable_action(...)` as the only runtime that interprets rule actions;
- old Fact Overlay and ProofFrame entrypoints reject non-empty `rule_actions`;
- lower-level `evaluate_where(..., disabled_locators=...)` while keeping `evaluate_native_where(...)` unchanged;
- no variant support capture and no SDK surface.

Current native where atoms include predicate atoms,comparison/filter atoms(`eq`, `ne`, `in`, `gt`, `ge`, `lt`, `le`),arithmetic atoms(`add`, `sub`, `neg`, `addc`, `mulc`),and `not`. RuleRef support is outside plain `evaluate_where(...)` and must go through the RuleRef substrate.

The v0.1.4 negative result is binding context,not implementation authority. It found four separate lanes:

1. literal / term changes,which are constrained atom replacement;
2. `condition_weights`,which affect certainty/explain materialization rather than where execution;
3. ProbLog probability carriers,adapter-local;
4. PyReason bounds / thresholds,adapter-local.

Batch 5b starts from this negative result and must show whether the first lane alone is useful and crisp enough to ship.

## 5. Step 0 Questions

### 5.1 Falsifiability Checklist

Step 0 must answer each item with concrete examples from current `RuleSpec.where`,native evaluator behavior,and Batch 5a output contracts.

| # | Falsifier | If true,decision pressure |
|---|---|---|
| 1 | Literal replacement cannot be defined without also covering weights,ProbLog probabilities,or PyReason bounds. | Option B abandon or Option C split. |
| 2 | The "literal-only" action still has multiple unrelated substrates:predicate term constants,comparison thresholds,`in` list members,and arithmetic constants require incompatible validation/result rules. | Option C split or narrower A with rejected subfamilies. |
| 3 | A replacement can change binder/filter roles(e.g. variable to literal or literal to variable),requiring a binding planner rather than a literal leaf edit. | Option B abandon or defer to Batch 5c binding planner. |
| 4 | Atom-kind,arity,or term-list length must change to cover useful examples. | Not literal-only;Option B/C. |
| 5 | ProofFrame cannot explain the old frame with existing `ProofFrameRecheckResult` and `affected_action_indices` without adding a new status. | Option B or parent-plan deviation;do not revive `superseded_by_full_eval`. |
| 6 | Variant evaluation requires changing `evaluate_native_where(...)` / RuleRef substrate signatures or SDK replay substrate. | Scope failure;Option B unless a narrow lower-level primitive is proven. |
| 7 | RuleRef-bound replace is required for correctness of the first slice. | Reject/defer RuleRef or abandon 5b. |
| 8 | The action is merely syntactic sugar over replacing a whole atom and has no distinct user-facing result contract. | Option B abandon;do not ship vanity API. |

### 5.2 Candidate Path A — Literal-Only Ship

Path A is valid only if Step 0 proves all of the following:

- Target identity is `rule_id + version + branch_index + atom_index + literal_path`.
- `literal_path` points to one existing literal leaf,not a variable,not an atom kind,not an arity/list-length edit.
- Replacement keeps the containing atom kind and structural shape unchanged.
- Native variant evaluation can run by applying a temporary transformed `where` body,then calling existing evaluator paths.
- Original-frame ProofFrame marks the matching source atom locator as `invalidated` when the artifact contains it;non-target atoms remain `still_valid`.
- Universe shift is surfaced as `variant_rows`,not as a ProofFrame status.

Open Step 0 question:which atom kinds are in the first literal-only set?

- Conservative candidate:comparison/filter literals only(`eq`, `ne`, `in`, `gt`, `ge`, `lt`, `le`)and arithmetic constants in `addc` / `mulc`.
- Riskier candidate:also predicate term constants. Replacing a constant in `Person.tag($p, "vip")` with `"premium"` can be a leaf swap,but replacing a predicate variable with a literal changes binder/filter role and triggers falsifier #3. Step 0 must judge predicate-term constants case by case.
- Likely reject in A:`not` internals,RuleRef atoms,variable-to-literal or literal-to-variable edits,atom-kind changes,arity changes.

### 5.3 Candidate Path B — Abandon

Path B is not failure. It is the default-lean path if Step 0 finds that "replace condition" is still a false abstraction or that useful literal edits are already adequately covered by whole-atom replacement concepts without a new application capability.

If Path B is selected:

- status becomes `abandoned`;
- archive blueprint/audit immediately with explicit decomposition;
- no code changes;
- Batch 5c entry criteria are still met because master plan allows non-cascading abandonment.

### 5.4 Candidate Path C — Split

Path C is valid if Step 0 finds more than one useful but separate capability:

- `RuleLiteralReplaceAction` for native where literal leaves;
- `ConditionWeightOverrideAction` for certainty/explain materialization;
- adapter-local parameter actions for ProbLog / PyReason.

Path C should not implement all three inside this blueprint. It should record the split,then open separate child blueprints or abandon 5b implementation work until the parent plan is amended.

### 5.5 Output Contract Questions

If Path A ships,Step 0.B must freeze:

- request/result DTO names and fields;
- whether the action extends `EvaluationOverlay.rule_actions` or uses a separate request-only DTO;
- runtime status enum and error codes;
- whether Batch 5a `RuleDisableResult` can be generalized or whether replace needs its own result DTO. **Note:** generalizing means modifying archived Batch 5a `protocol/rule_disable.py`,which would conflict with Batch 5a's drift-gate posture. Default expectation is a separate `RuleReplaceConditionResult` with the same dual-output shape(variant rows + original-frame ProofFrame),sharing structure but not type identity.
- whether multiple replace actions are accepted or MVP restricts to one action;
- two-entrypoint compatibility after adding another rule action type;
- drift gates for `fact_overlay_runtime.py`, `proofframe_runtime.py`, `rule_disable_runtime.py`,and `evaluate_native_where(...)`.

## 6. Boundaries And Invariants

- Application-first:protocol + runtime start under `kernel.application/`.
- Q1 Sibling discipline:Rule Condition Replace must not import sibling capability runtimes.
- No ledger writes,no store sidecar writes,no support cache mutation.
- Existing Rule Disable behavior remains unchanged.
- Existing Fact Overlay and ProofFrame rule-action rejection behavior remains explicit;no silent ignore.
- Existing ProofFrame status set remains `still_valid | invalidated | unknown`.
- `evaluate_native_where(...)` signature remains stable. Per Batch 5a precedent(`062ba88` mid-implementation correction),signature drift is rejected by frontier drift gates as a hard block,not advisory. Path A primitives must extend `where_eval.evaluate_where(...)` or add a new lower-level primitive,not modify `evaluate_native_where(...)`. Step 0 cannot relax this via "deviation" without a parent-plan amendment.
- Batch 4 deferred symmetric ProofFrame `rule_refs` hardening is tracked separately and must not be hidden inside 5b unless explicitly scoped.

## 7. Acceptance

**Step 0 acceptance:**

- [ ] Step 0 records a concrete A/B/C decision with rejected reasons.
- [ ] Step 0 answers all eight falsifiers in §5.1 with source-backed examples.
- [ ] If Path A is selected,Step 0 freezes the first atom-kind set and literal-path constraints.
- [ ] If Path B is selected,abandonment audit records why no single crisp DTO exists.
- [ ] If Path C is selected,the split is recorded without implementing a three-capability merge in this blueprint.

**Implementation acceptance(Path A only;blocked until scoped):**

- [ ] Protocol DTOs are frozen and tested.
- [ ] Native variant rows stay separate from original-frame ProofFrame.
- [ ] RuleRef-bearing inputs are rejected/deferred.
- [ ] Existing Rule Disable / Fact Overlay / ProofFrame behavior is unchanged except explicitly scoped compatibility guards.
- [ ] No SDK/service/agent diffs.
- [ ] No `superseded_by_full_eval` revival.
- [ ] Module docs under `src/kernel/application/docs/` are updated if implementation ships.
- [ ] Focused tests,full kernel unittest,ruff,and `git diff --check` pass.

## 8. Implementation Plan

1. Step 0.A:source-grounded falsifiability pass over §5.1,including at least one current where example for each candidate atom family.
2. Step 0.B:commit one of A/B/C and record rejected alternatives.
3. If A:freeze DTO/runtime shape and move `draft → scoped`;only then implement.
4. If B:mark `abandoned`,fill Outcome/Deviations,archive blueprint/audit,and move to Batch 5c.
5. If C:record split,update parent-plan audit if needed,and open child blueprint(s) rather than implementing a merged capability here.

## 9. Docs To Update

Path A only:

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/blueprints/archive/README.md` after archive

Path B/C:

- `docs/blueprints/archive/README.md` after archive

## 10. Outcome / Deviations

To be filled after Step 0:

- Final landed result:
- A/B/C decision:
- Rejected alternatives:
- Deviations from draft:
- Verification / archive note:
