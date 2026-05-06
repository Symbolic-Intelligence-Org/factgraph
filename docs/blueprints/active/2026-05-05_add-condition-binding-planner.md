# Rule Add Condition + Binding Planner(Batch 5c of Round Story Completion Plan)

- Status: draft
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Branch: `v0.1-add-condition-binding-planner-2026-05-05`
- Scope: Batch 5c Step 0 — decide whether rule add-condition and binding planning are one crisp capability, split capabilities, or should be abandoned/suspended
- Related Modules:
  - `src/kernel/application/protocol/derivation_fact_overlay.py`
  - `src/kernel/application/protocol/rule_disable.py`
  - `src/kernel/application/protocol/rule_literal_replace.py`
  - `src/kernel/application/rule_disable_runtime.py`
  - `src/kernel/application/rule_literal_replace_runtime.py`
  - `src/kernel/core/rules/where_ast.py`
  - `src/kernel/core/rules/where_ast_validate.py`
  - `src/kernel/core/rules/where_eval.py`
- Related Docs:
  - [Round Story Completion Plan](./2026-05-05_round-story-completion-plan.md) §5.5c
  - [Batch 5a Rule Disable archive](../archive/2026-05-05_rule-disable.md)
  - [Batch 5b Rule Condition Replace archive](../archive/2026-05-05_rule-condition-replace.md)
  - [Rule replay redesign Direction G](../../references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md) §G
  - [Operational replay design open questions](../../references/working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md)
- Audit Log:
  - [2026-05-05_add-condition-binding-planner.audit.md](./2026-05-05_add-condition-binding-planner.audit.md)

## 1. Problem

Batch 5c is the last rule-side operation sub-batch and the first one with no v0.1.x implementation precedent. The master plan names it "Add Condition + Binding Planner", but that phrase may already hide the central risk:adding a condition to a rule body and planning how any new variables become bound may be two separate capabilities, not two views of one action.

Batch 5a and 5b both used a dual-output rule-action shape:

- variant rows from full native re-evaluation; and
- original-frame ProofFrame status for the old support artifact.

Batch 5c must test whether that shape still holds when a new atom is inserted into a branch. Add-condition can narrow or expand the candidate universe, introduce new variables, force atom ordering decisions, and shift source locators. A forced implementation could recreate the v0.1.4 false-merge failure in a more subtle form.

**Default posture:** conservative. Step 0 must make abandonment or split a first-class outcome. Path A only ships if the "new condition" action and the minimum binding-planner contract are proven to be one crisp, testable capability.

## 2. Goals

- Run a falsifiability-first Step 0 over the unified "add condition + binding planner" premise before any implementation.
- Decide whether Batch 5c uses:
  - Path A:narrow first-slice ship;
  - Path B:abandon/suspend with explicit decomposition; or
  - Path C:split into separate add-condition and binding-planner work.
- Preserve Batch 5a/5b dual-output discipline if any action ships:variant rows show full re-evaluation;ProofFrame explains the original frame only.
- Preserve locator stability for existing atoms;new inserted atoms must not renumber existing `b{branch}.a{atom}` handles.
- Freeze, or explicitly defer, the binding-planner contract:variables, shadowing, insertion position, and branch scope.
- Keep Batch 4 ProofFrame `rule_refs` symmetric hardening separate unless this blueprint explicitly scopes it later.

## 3. Non-goals

- No SDK replay substrate.
- No public SDK/service/agent surface.
- No persistent rule variant storage.
- No durable condition IDs or promoted rule versions.
- No RuleRef add-condition support unless Step 0 proves a narrow first slice;default is reject/defer.
- No `not` internals unless Step 0 proves a narrow first slice;default is reject/defer.
- No `superseded_by_full_eval` revival unless Step 0 records a parent-plan amendment;the default is still dual-output separation.
- No multi-action ordering across disable / literal replace / add-condition unless Step 0 explicitly scopes it.
- No variant `SupportArtifact` capture unless Step 0 proves it is necessary.
- No whole-rule AST editor or arbitrary atom insertion API.
- No condition weights,ProbLog probability carriers,or PyReason bounds.
- No hidden Batch 4 ProofFrame `rule_refs` fix inside this batch.

## 4. Current Context

Batch 5b final HEAD is `5213e76`. It shipped:

- `EvaluationOverlay.rule_actions` with `RuleDisableAction | RuleLiteralReplaceAction`;
- separate rule-action request/result DTOs for disable and literal replace;
- one-action MVP in each rule runtime;
- full native variant evaluation plus original-frame ProofFrame;
- lower-level primitives in `kernel.core.rules.where_eval` while preserving `evaluate_native_where(...)`;
- cross-runtime type guards so older rule runtimes reject unknown rule actions instead of silently processing them.

Current native where shape:

- AST parse/lower in `where_ast.py` supports `PredAtom`, `RuleRefAtom`, `CmpAtom`, `InAtom`, `BuiltinAtom`, and `NotAtom`.
- Dataflow validation in `where_ast_validate.py` binds predicate variables, lets `eq` bind one unbound variable if the other side is resolved, requires `in`/filter comparisons/builtins to reference already-bound variables, and treats RuleRef binding semantics as deferred.
- `not` bodies require at least one outer bound variable and do not bind new variables.
- `evaluate_where(...)` currently supports temporary disabling and literal replacement without changing `evaluate_native_where(...)`.

Historical Direction G says patch-time should not automatically reject new variables;the compiler/planner should decide binding viability. That is reference material, not current implementation truth. Step 0 must decide whether the current native dataflow validator is enough planner substrate for a narrow first slice or whether a new planner capability is required before shipping.

## 5. Step 0 Questions

### 5.1 Falsifiability Checklist

Step 0 must answer every item with source-grounded examples from `where_ast.py`, `where_ast_validate.py`, `where_eval.py`, and the Batch 5a/5b runtime contracts.

| # | Falsifier | If true,decision pressure |
|---|---|---|
| 1 | "Add condition" and "binding planner" require different DTOs, lifecycles, or error surfaces. | Path C split or Path B suspend. |
| 2 | A useful add-condition first slice requires introducing a new variable that is not already bound earlier in the branch. | Path C split toward a real binding planner, or Path B suspend. |
| 3 | Inserting an atom changes existing locator identity or requires renumbering downstream atoms. | Path B unless a stable inserted-locator scheme is proven. |
| 4 | The added atom cannot be represented by current native `where` AST and validator without changing `evaluate_native_where(...)` or RuleRef substrate. | Path B or parent-plan amendment;do not bypass drift gates. |
| 5 | Variant rows alone cannot represent universe shift and ProofFrame needs a new status such as `superseded_by_full_eval`. | Parent-plan amendment or Path B;default is no status revival. See §5.6 for explicit conflict resolution. |
| 6 | Cross-runtime ownership becomes ambiguous once a third rule action joins `EvaluationOverlay.rule_actions`. | Path B unless explicit type guards remain crisp. |
| 7 | `not` or RuleRef support is necessary for the first useful add-condition example. | Reject/defer those atoms or suspend 5c. |
| 8 | Adding a filter over already-bound variables is only sugar over literal replace / disable and has no distinct user-facing result contract. | Path B abandon;do not ship vanity API. |
| 9 | A single add condition can bind variables differently across OR branches, requiring branch-specific planner state outside the current `branch_index` model. | Path C split or narrower A with branch-local constraints. |
| 10 | Multi-action ordering(disable + replace + add) is required to make add-condition meaningful. | Defer multi-action or Path B;MVP must stay one-action unless Step 0 proves otherwise. |

### 5.2 Candidate Path A — Narrow Add-Filter Ship

Path A is valid only if Step 0 proves a narrow first slice that does **not** require a new general binding planner.

Conservative candidate:

- Add one top-level native atom to one existing branch.
- The added atom references only variables already bound earlier in that branch, or constants.
- Accepted atom families are limited to filter-like atoms whose dataflow does not bind new variables:
  - comparison filters:`ne`, `gt`, `ge`, `lt`, `le`;
  - `in` membership over an already-bound variable;
  - maybe `eq` only when both sides are already resolved and it does not bind.
- The action inserts the atom at a stable synthetic position that does not renumber existing atom locators.
- Variant rows come from full native re-evaluation over the temporary inserted atom.
- Original-frame ProofFrame marks the rule chain as `invalidated` if the added condition filters out the old binding;otherwise `still_valid` or `unknown` according to existing Batch 4/5 proof-frame limits.

Path A must reject:

- any added atom that binds a new variable;
- `pred` atoms with new variables unless Step 0 proves current validator already covers a no-new-planner slice;
- `eq` used as binder;
- `add`, `sub`, `neg`, `addc`, `mulc` if they bind a new output variable;
- `not` internals;
- `ruleref` atoms;
- multi-action combinations.

### 5.3 Candidate Path B — Abandon / Suspend

Path B is valid if add-condition cannot be made crisp without building a separate binding planner first, or if the only safe first slice is too small to justify a public rule action.

If Path B is selected:

- status becomes `abandoned` or `suspended`;
- no code ships;
- the audit records which falsifiers failed;
- Batch 6 entry criteria must be revisited because the master plan names Batch 5c as a predecessor.

### 5.4 Candidate Path C — Split

Path C is valid if Step 0 finds two useful but separate capabilities:

- `RuleAddConditionAction` for branch-local insertion of already-bound filter atoms; and
- `BindingPlanner` or `RuleBindingPlanRequest` for proposing/legalizing new-variable atoms.

Path C must not implement both inside this blueprint. It should record the split,then either:

- fall back to Path A if narrowing to add-filter-only is sufficient; or
- open separate child blueprint(s) and amend the parent plan before implementation.

Path C itself means split. It is not a license to implement add-filter and binding-planner work together inside this blueprint.

### 5.5 Output Contract Questions

If Step 0 selects any shipping path, Step 0.B must freeze:

- request/result DTO names and fields;
- action DTO shape and whether it extends `EvaluationOverlay.rule_actions`;
- one-action MVP vs multi-action support;
- inserted locator identity(each option has hidden cost):
  - stable synthetic locator such as `b{branch}.new{index}`(ProofFrame must mark "atom not in original artifact");
  - explicit insertion position between existing atoms(exposes atom position as caller contract); or
  - action-index-based proof identity only(tight coupling to future multi-action support);
- whether the runtime captures variant `SupportArtifact` or returns only `variant_rows`;
- how original-frame ProofFrame reflects an added atom that did not exist in the original artifact;
- exact error codes for unsupported atom families,unbound variables,locator conflicts,RuleRef/not rejection,native evaluation errors,and action-type mismatch;
- cross-runtime guards for Rule Disable and Rule Literal Replace after a third rule action joins the union;
- lower-level primitive name and module location,with `evaluate_native_where(...)` unchanged.

### 5.6 Parent-Plan Conflict Check

The master plan says ProofFrame should output "`new condition adds -> previous frames superseded_by_full_eval`". Since Batch 4 explicitly collapsed `superseded_by_full_eval`, Step 0 must not treat that line as automatic current truth.

Step 0 must choose one:

- keep Batch 4/5a/5b dual-output discipline:variant rows show universe shift,ProofFrame remains 3-status over the old frame;
- amend the parent plan and ProofFrame protocol before any implementation; or
- abandon/suspend Batch 5c because the parent-plan exit criterion is incompatible with frozen Batch 4 protocol.

Default expectation:do **not** revive `superseded_by_full_eval`.

### 5.7 Step 0.A Outcome — Narrow Path A With Binding Planner Deferred

**Decision:** Path A passes only as a narrow native `RuleAddConditionAction` first slice:insert one new top-level filter atom into one existing branch,where the new atom references only variables already bound earlier in that branch plus constants. A real new-variable binding planner does **not** ship in Batch 5c.

This is a scoped reduction of the master-plan phrase "Add Condition + Binding Planner". The full phrase is a false-merge risk:adding an already-bound filter atom is an execution-time rule action,while planning new-variable introductions is a separate design surface with different inputs,outputs,and failure modes. Batch 5c can still ship a useful add-filter action because the planner contract collapses to a deterministic preflight:the inserted atom must not bind any new variables.

#### 5.7.1 First-Slice Atom Set

Path A freezes the first slice to one inserted atom in the current native where IR:

| Atom family | Included shape | Example | Reason |
|---|---|---|---|
| `ne` / `gt` / `ge` / `lt` / `le` | both variable operands already bound earlier,or variable + constant with the variable already bound | add `("lt", "$age", 65)` after `Person:age($p, $age)` | Pure filter;`where_ast_validate.py` already requires these vars to be bound. |
| `in` | first arg is already-bound variable;values are non-empty constants | add `("in", "$region", ["us", "ca"])` after `$region` is bound | Pure membership filter;does not bind. |
| `eq` | both sides already resolved;not used to bind an unbound variable | add `("eq", "$region", "us")` after `$region` is bound | Filter equality only;the existing validator can detect binder use when one side is unbound. |

Rejected from the first slice:

- `pred` atoms,because they can bind new variables and require predicate arity/type planning;
- `eq` used as binder;
- `add`, `sub`, `neg`, `addc`, `mulc`,because their output position binds a variable under current dataflow rules;
- `not` internals;
- `ruleref` atoms and RuleRef-bearing artifacts;
- inserted atoms that introduce any variable not bound earlier in the selected branch;
- cross-branch insertion or branch-template insertion;
- multi-action ordering with disable / literal replace.

#### 5.7.2 Falsifiability Checklist Result

| # | Verdict | Source-grounded reason |
|---|---|---|
| 1 | **Pass only after scope reduction** | Full "add condition + binding planner" is not one capability. The narrow add-filter action has a crisp DTO;new-variable planning is deferred as a separate future capability. |
| 2 | **Pass by rejection** | Current useful examples can be filters over already-bound vars(`lt`, `in`, resolved `eq`). Any example that needs a new variable triggers binding-planner deferral. |
| 3 | **Pass with inserted-locator freeze deferred to Step 0.B** | Existing locators stay stable if the inserted atom gets a synthetic/action-based identity instead of renumbering downstream `b{branch}.a{atom}` keys. Step 0.B must choose the concrete identity. |
| 4 | **Pass** | Included atom families are represented by current `where_ast.py` and validated by current `where_ast_validate.py`;runtime can extend lower-level `evaluate_where(...)` without changing `evaluate_native_where(...)`. |
| 5 | **Pass with parent-plan line rejected** | Universe shift is represented by `variant_rows`;original-frame ProofFrame remains the Batch 4 three-status result. `superseded_by_full_eval` stays collapsed unless the parent plan is amended later. |
| 6 | **Pass with cross-runtime guard requirement** | Batch 5a/5b already established explicit owner runtimes. Adding a third rule action requires Rule Disable and Rule Literal Replace to reject non-owned rule actions before field access. |
| 7 | **Pass by rejection** | `not` and RuleRef are not needed for the first filter examples and remain unsupported/deferred. |
| 8 | **Pass** | Adding `("lt", "$age", 65)` is not equivalent to disabling or literal-replacing an existing atom;it creates a new conjunct and a new variant-row universe while preserving old atoms. |
| 9 | **Pass by branch-local restriction** | The action targets one existing branch. It does not define branch templates or cross-branch variable planning. |
| 10 | **Pass by MVP restriction** | Single-action runtime remains sufficient for the first slice. Multi-action ordering stays deferred. |

#### 5.7.3 Parent-Plan Conflict Resolution

Step 0.A chooses the first §5.6 option:keep Batch 4/5a/5b dual-output discipline. Batch 5c does not revive `superseded_by_full_eval`.

- `variant_rows` show whether the inserted filter changes the result universe.
- original-frame ProofFrame explains only the old support artifact.
- if the old binding fails the new filter,ProofFrame can mark the inserted synthetic/action atom as `invalidated` or otherwise report frame-level invalidation according to the Step 0.B identity choice.
- if Step 0.B cannot define an honest ProofFrame mapping for an atom absent from the old artifact,it must fall back to Path B or reduce output to variant rows plus warning before scope freeze.

#### 5.7.4 Step 0.B Carry-Overs

Step 0.B must freeze these before status can move to `scoped`:

- DTO names and fields,with a separate result DTO rather than generalizing Batch 5a/5b result DTOs.
- Add-atom payload encoding:raw native atom tuple vs structured `RuleAddedAtom` DTO.
- Exact allowed atom families and runtime preflight codes for unbound variables,unsupported atom kinds,RuleRef,`not`,and malformed atom shape.
- **Coupled decision(must be resolved together):**
  - inserted identity scheme:synthetic locator vs insertion-position contract vs action-index-only identity;
  - original-frame ProofFrame mapping for an inserted atom that was absent from the old artifact,derived from the chosen identity scheme.
- One-action MVP and cross-runtime action-type guards for Rule Disable and Rule Literal Replace.
- Whether `where_ast_validate.py` needs a narrow primitive for "does this atom bind variables outside the current bound set?" or whether the runtime can rely on existing validation internals;no SDK surface may expose this.
- Lower-level primitive location:default expectation per Batch 5a/5b precedent is `kernel.core.rules.where_eval.evaluate_where(..., added_conditions=frozenset())` plus private helper `_apply_added_conditions(...)` parallel to `_apply_disabled_locators(...)` and `_apply_literal_replacements(...)`;`evaluate_native_where(...)` remains unchanged.
- Whether Path A output includes warnings documenting that new-variable binding planner is deferred.
- Drift gates for SDK/service/agent,RuleRef substrate,ProofFrame protocol,`evaluate_native_where(...)`,and generic Fact Overlay / ProofFrame rule-action rejection.

### 5.8 Step 0.B Outcome — Synthetic Added-Atom ProofFrame Mapping

Step 0.B freezes Path A. The blueprint remains `draft` until review accepts this freeze;the next transition is a separate `draft → scoped` commit.

#### 5.8.1 Protocol Shape

Rule add condition extends the shared rule-action lane with one new action:

```python
RuleAddedAtomKind = Literal["eq", "ne", "gt", "ge", "lt", "le", "in"]

@dataclass(frozen=True)
class RuleAddedAtom:
    atom: tuple[Any, ...]

@dataclass(frozen=True)
class RuleAddConditionAction:
    rule_id: str
    version: str
    branch_index: int
    added_atom: RuleAddedAtom
    note: str | None = None

RuleOverlayAction = RuleDisableAction | RuleLiteralReplaceAction | RuleAddConditionAction
```

The action does not carry `atom_index`. It appends a new synthetic filter atom to the selected branch for variant evaluation while leaving existing atom positions and locators unchanged. Runtime preflight validates that the atom is one of the Step 0.A filter families and binds no new variables.

`RuleAddedAtom` stores the native atom tuple instead of a separate structured per-kind DTO. This keeps the first slice close to current `where` IR and avoids designing a larger AST editor. Protocol validation stays shallow(shape and tuple-ness);semantic validation belongs to the runtime/core helper because it needs branch-local bound-variable context.

#### 5.8.2 Request / Result Surface

Batch 5c ships a separate result type and does **not** generalize Batch 5a/5b result DTOs:

```python
RuleAddConditionStatus = Literal["completed", "unsupported", "invalid_request"]

@dataclass(frozen=True)
class RuleAddConditionRequest:
    rule_spec: RuleSpec
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class RuleAddConditionResult:
    status: RuleAddConditionStatus
    variant_rows: tuple[BindingItems, ...]
    proof_frame: ProofFrameRecheckResult | None
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()
```

The result invariant mirrors Rule Disable and Rule Literal Replace:

- `completed` requires `proof_frame is not None` and no errors;
- `unsupported` / `invalid_request` require empty `variant_rows`, `proof_frame is None`, and at least one error;
- `warnings` are allowed but not required on completed results.

Batch 5c does not add a success warning for "binding planner deferred". That boundary is encoded in protocol/runtime errors for rejected atoms and in module docs. Always-on warnings would make the happy path noisy without adding machine-checkable information.

#### 5.8.3 Added-Atom Identity And ProofFrame Mapping

Step 0.B chooses the synthetic-locator option.

Inserted atom identity:

```text
b{branch_index}.add{action_index}:{atom_kind}
```

Examples:

- action `#0`,branch `0`,added atom `("lt", "$age", 65)` -> `b0.add0:lt`
- action `#0`,branch `2`,added atom `("in", "$region", ["us"])` -> `b2.add0:in`

This does not renumber old atoms and does not claim the added atom existed in the old support artifact. It is a rule-action synthetic atom key,produced only by the Rule Add Condition runtime's `ProofFrameRecheckResult`.

ProofFrame mapping:

- existing `artifact.pred_witnesses` and `artifact.non_fact_steps` are emitted as `still_valid`. This is honest under Batch 5c's filter-only scope because the added condition cannot introduce new facts;it only filters existing bindings,so existing fact witnesses and `not` absence checks are preserved. Batch 4's strict `not` deferral applied because fact-replacing overlays could introduce new positive matches;Batch 5c's narrower add-filter scope avoids that risk. Batch 5c constructs its own `ProofFrameRecheckResult` and does not delegate to `recheck_proof_frame(...)`;
- one synthetic `ProofFrameAtomVerdict` is appended for the added atom;
- if the old frame's `binding_items` appears in `variant_rows`,the synthetic verdict is `still_valid`;
- if the old frame's `binding_items` does not appear in `variant_rows`,the synthetic verdict is `invalidated` with `affected_action_indices=(0,)`;
- frame status remains `aggregate_proof_frame_status(atom_verdicts)`.

This keeps the Batch 4 protocol intact: `atom_key` remains a string,`affected_action_indices` remains the action link,and no new ProofFrame status is introduced. The runtime is responsible for documenting that `b*.add*:*` keys are synthetic action atoms,not source artifact atom keys.

Rejected alternatives:

- **Insertion-position identity** was rejected because it exposes a caller-visible position contract and still cannot point to an old artifact atom.
- **Action-index-only identity** was rejected because it overloads `atom_key` with non-atom semantics and becomes brittle when multi-action support is introduced.
- **Frame-level `unknown` instead of synthetic verdict** was rejected because it throws away useful old-binding pass/fail information after a full variant evaluation has already run.

#### 5.8.4 Runtime Scope And Core Primitive

Runtime MVP accepts exactly one `RuleAddConditionAction` and rejects all fact actions. Multiple rule actions are deferred.

The native primitive lands in `kernel.core.rules.where_eval`:

```python
@dataclass(frozen=True)
class WhereAddedCondition:
    branch_index: int
    atom: tuple[Any, ...]

def evaluate_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    disabled_locators: frozenset[tuple[int, int]] = frozenset(),
    literal_replacements: frozenset[WhereLiteralReplacement] = frozenset(),
    added_conditions: frozenset[WhereAddedCondition] = frozenset(),
) -> list[dict[str, Any]]: ...
```

Implementation uses a private `_apply_added_conditions(...)` helper after literal replacements and before disabled locators:

```text
literal_replacements -> added_conditions -> disabled_locators
```

This order is deterministic and future-compatible:literal replacements edit existing atoms;added conditions append synthetic atoms without renumbering old locators;disabled locators remove old atoms after any edits. Batch 5c runtime supplies only `added_conditions`.

This three-way ordering is forward-compatible only. Batch 5c's MVP single-action runtime never combines literal replacements,added conditions,and disabled locators. Future multi-action work must re-validate combined-input semantics,including whether disable can target an appended atom or only original atom locators.

`evaluate_native_where(...)` remains unchanged.

#### 5.8.5 Binding-Effect Validation

Step 0.B scopes a narrow core validation helper in `where_ast_validate.py`:

```python
def atom_binds_new_variables(
    atom_ir: tuple[Any, ...],
    *,
    bound_vars: frozenset[str],
) -> bool: ...
```

The exact helper name may change during implementation,but the contract is fixed:

- parse and validate one candidate atom against current native AST/dataflow rules;
- return whether the atom would bind any variable outside `bound_vars`;
- raise `WhereASTValidationError` for malformed or unsupported atoms;
- expose no SDK/service/agent surface.

Runtime computes branch-local `bound_vars` from atoms before the insertion point. Since Batch 5c appends to the selected branch,the insertion point is the end of the branch. That means `bound_vars` are the variables bound by the original branch. If future work supports insertion between atoms,it must reopen this contract.

#### 5.8.6 Error / Unsupported Contract

`RuleAddConditionResult` uses the local status shape `completed | unsupported | invalid_request`.

| Condition | Status | Code |
|---|---|---|
| non-native or non-row support artifact | `unsupported` | `RULE_ADD_CONDITION_SUPPORT_UNSUPPORTED` |
| support artifact has `rule_refs` or `rule_ref_edges` | `unsupported` | `RULE_ADD_CONDITION_RULE_REF_UNSUPPORTED` |
| `rule_spec.where` contains `ruleref` atom | `unsupported` | `RULE_ADD_CONDITION_RULE_REF_UNSUPPORTED` |
| overlay contains fact actions | `invalid_request` | `RULE_ADD_CONDITION_FACT_ACTIONS_UNSUPPORTED` |
| zero or multiple rule actions | `invalid_request` | `RULE_ADD_CONDITION_ACTION_COUNT` |
| single rule action is not `RuleAddConditionAction` | `invalid_request` | `RULE_ADD_CONDITION_ACTION_TYPE_UNSUPPORTED` |
| action rule identity mismatches request rule | `invalid_request` | `RULE_ADD_CONDITION_RULE_MISMATCH` |
| target branch does not exist | `invalid_request` | `RULE_ADD_CONDITION_BRANCH_NOT_FOUND` |
| added atom shape is malformed | `invalid_request` | `RULE_ADD_CONDITION_ATOM_MALFORMED` |
| added atom kind unsupported by §5.7.1 | `invalid_request` | `RULE_ADD_CONDITION_ATOM_UNSUPPORTED` |
| added atom would bind a new variable | `invalid_request` | `RULE_ADD_CONDITION_BINDS_NEW_VARIABLE` |
| added atom is `not` or contains `not` internals | `invalid_request` | `RULE_ADD_CONDITION_NOT_UNSUPPORTED` |
| native variant evaluation raises evaluator/runtime validation error | `invalid_request` | `RULE_ADD_CONDITION_NATIVE_EVAL_ERROR` |

The runtime may preflight obvious malformed/unsupported cases before calling the core helper. Evaluator errors remain mapped to `RULE_ADD_CONDITION_NATIVE_EVAL_ERROR`.

#### 5.8.7 Cross-Runtime Compatibility

Adding `RuleAddConditionAction` to `EvaluationOverlay.rule_actions` changes the union accepted by the shared overlay DTO. Runtime ownership remains explicit:

- `check_rule_add_condition_action(...)` owns `RuleAddConditionAction` semantics.
- `check_rule_disable_action(...)` and `check_rule_literal_replace_action(...)` must reject non-owned rule actions before field access.
- `check_fact_overlay_binding(...)` continues to reject any non-empty `rule_actions` generically.
- `recheck_proof_frame(...)` continues to return frame-level `unknown` for any non-empty `rule_actions`;no add-condition-specific semantics are added there.

Implementation note:Batch 5a and 5b runtimes already type-check with `isinstance(action, RuleDisableAction)` and `isinstance(action, RuleLiteralReplaceAction)`,which automatically rejects `RuleAddConditionAction`. Batch 5c prefers no code changes in those runtimes;new tests should verify the existing guards reject the new action type.

#### 5.8.8 Drift Gates / Acceptance Additions

Implementation acceptance adds these gates:

- `git diff --stat -- src/kernel/core/rules/ruleref_substrate.py src/kernel/application/protocol/proofframe.py src/kernel/application/proofframe_runtime.py src/kernel/application/fact_overlay_runtime.py` is empty.
- `def evaluate_native_where` signature is unchanged.
- `src/kernel/sdk`, `src/factpy_kernel/service`,and `src/factpy_kernel/agent` diffs are empty.
- `src/kernel/application/rule_disable_runtime.py` and `src/kernel/application/rule_literal_replace_runtime.py` changes are limited to narrow non-owned rule-action rejection guards.
- no `superseded_by_full_eval`, generalized binding planner public surface,SDK replay substrate,or RuleRef add-condition support appears in Batch 5c code.

## 6. Boundaries And Invariants

- Application-first:all public task DTOs start in `kernel.application.protocol`;runtime starts in `kernel.application`.
- Q1 Sibling discipline:no rule runtime imports sibling rule runtimes for semantics.
- Existing Rule Disable and Rule Literal Replace behavior must remain unchanged except narrow action-type rejection guards.
- Fact Overlay and ProofFrame keep generic rule-action rejection unless Step 0.B explicitly scopes a guard-only amendment.
- No ledger writes,no store sidecar writes,no support cache mutation.
- `evaluate_native_where(...)` signature remains stable;Batch 5a/5b established this as a hard drift gate.
- RuleRef substrate remains unchanged.
- SDK/service/agent diffs remain empty.
- Batch 4 deferred ProofFrame `rule_refs` gap remains separately tracked.
- Existing atom locator identity must remain stable for old atoms.

## 7. Acceptance

**Step 0 acceptance:**

- [x] Step 0 records a concrete A/B/C decision with rejected reasons(see §5.7 and §5.8).
- [x] Step 0 answers every falsifier in §5.1 with source-grounded examples(see §5.7.2).
- [x] Step 0 explicitly decides whether "add condition" and "binding planner" are one capability or split capabilities(see §5.7).
- [x] Step 0 explicitly resolves the `superseded_by_full_eval` parent-plan conflict in §5.6(see §5.7.3).
- [x] If Path A ships,Step 0 freezes the atom family set,variable-binding boundary,and inserted-locator scheme(see §5.7.1 and §5.8.3).
- [x] Path B/C was not selected;closure/split is not applicable(see §5.7 and §5.8).

**Implementation acceptance(blocked until scoped):**

- [ ] Protocol DTOs are frozen and tested.
- [ ] Runtime returns variant rows plus original-frame ProofFrame or records a parent-plan deviation first.
- [ ] Added atoms do not renumber existing locators.
- [ ] New-variable atoms are rejected unless a binding-planner contract is explicitly shipped.
- [ ] RuleRef and `not` behavior matches Step 0.B.
- [ ] Existing Rule Disable / Rule Literal Replace / Fact Overlay / ProofFrame behavior is unchanged except explicitly scoped guards.
- [ ] No SDK/service/agent diffs.
- [ ] `evaluate_native_where(...)` signature and RuleRef substrate are unchanged.
- [ ] No `superseded_by_full_eval` revival unless explicitly amended.
- [ ] Module docs under `src/kernel/application/docs/` are updated if implementation ships.
- [ ] Focused tests,full kernel unittest,ruff,and `git diff --check` pass.

## 8. Implementation Plan

1. Step 0.A:source-grounded falsifiability pass over §5.1,including at least one current where example for add-filter,no-new-variable,new-variable,`not`,and RuleRef cases.
2. Step 0.B:commit one of A/B/C and record rejected alternatives.
3. If A:freeze DTO/runtime/core primitive/error/drift-gate shape and move `draft → scoped`;only then implement.
4. If B:mark `abandoned` or `suspended`,fill Outcome/Deviations,archive blueprint/audit,and revisit Batch 6 entry criteria.
5. If C:record split,update parent-plan audit if needed,and open child blueprint(s) rather than implementing a merged capability here.

## 9. Docs To Update

Path A only:

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/blueprints/archive/README.md` after archive

Path B/C:

- `docs/blueprints/archive/README.md` after archive

## 10. Outcome / Deviations

Task completion will fill:

- Final landed result:
- A/B/C decision:
- Rejected alternatives:
- Deviations from draft:
- Verification / archive note:
