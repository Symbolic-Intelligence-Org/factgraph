# Rule Condition Replace(Batch 5b of Round Story Completion Plan)

- Status: implemented
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

Step 0.A answered the first literal-only atom-kind set in §5.6.1:

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

Step 0.B answered the Path A output contract in §5.7:

- request/result DTO names and fields;
- whether the action extends `EvaluationOverlay.rule_actions` or uses a separate request-only DTO;
- runtime status enum and error codes;
- whether Batch 5a `RuleDisableResult` can be generalized or whether replace needs its own result DTO. **Note:** generalizing means modifying archived Batch 5a `protocol/rule_disable.py`,which would conflict with Batch 5a's drift-gate posture. Default expectation is a separate `RuleReplaceConditionResult` with the same dual-output shape(variant rows + original-frame ProofFrame),sharing structure but not type identity.
- whether multiple replace actions are accepted or MVP restricts to one action;
- two-entrypoint compatibility after adding another rule action type;
- drift gates for `fact_overlay_runtime.py`, `proofframe_runtime.py`, `rule_disable_runtime.py`,and `evaluate_native_where(...)`.

### 5.6 Step 0.A Outcome — Narrow Path A

**Decision:** Option A passes only as a narrow native `RuleLiteralReplaceAction`. The action replaces one existing `Const` leaf inside one existing top-level native where atom,then returns Batch 5a-style dual output:variant rows from a full native re-evaluation plus original-frame ProofFrame invalidation for the touched atom locator.

This is not a revival of v0.1.4 `param_override`. The other v0.1.4 lanes remain rejected:condition weights,ProbLog probability carriers,and PyReason bounds/thresholds are not where-execution literal leaves and are not part of this batch.

#### 5.6.1 First-Slice Literal Set

Step 0.A freezes the first atom-kind set to existing `Const` leaves in current native `where` IR:

| Atom family | Included literal paths | Example | Rationale |
|---|---|---|---|
| `pred` | `terms[index]` only when the current term is a constant and the replacement is also a constant | `("pred", "Person:region", ["$p", "us"])` -> `"eu"` at `terms[1]` | Preserves binder/filter role;predicate variables are not replaceable in 5b. |
| `eq` / `ne` | `lhs` or `rhs` only when that side is a current constant | `("eq", "$region", "us")` -> `"eu"` | Keeps atom kind and arity;variable-to-literal and literal-to-variable edits are rejected. |
| `gt` / `ge` / `lt` / `le` | constant side only | `("gt", "$age", 21)` -> `18` | Current evaluator already owns int/time coercion;invalid replacement values map through native eval error handling. |
| `in` | `values[index]` existing member only | `("in", "$region", ["us", "ca"])` member `"us"` -> `"eu"` | List length and membership shape remain unchanged;adding/removing values is not literal replace. |
| `addc` / `mulc` | constant operand `c` only | `("addc", "$score", "$base", 5)` -> `10` | Dedicated constant operand;generic arithmetic expression editing is deferred. |

Rejected from Path A first slice:

- variable-to-literal or literal-to-variable edits;
- atom kind,arity,term-list length,or `in` list-length changes;
- `add` / `sub` / `neg` generic literal operands;
- `not` internals;
- `ruleref` atoms or RuleRef child rules;
- condition weights,ProbLog probability carriers,and PyReason bounds/thresholds.

The target identity remains `rule_id + version + branch_index + atom_index + literal_path`. Step 0.B must freeze the concrete `literal_path` DTO spelling,but not reopen the semantic boundary above.

#### 5.6.2 Falsifiability Checklist Result

| # | Verdict | Source-backed reason |
|---|---|---|
| 1 | Pass with hard exclusions | `where_ast.py` distinguishes `Const` leaves from rule metadata;condition weights and adapter parameters are not native `where` atoms. The v0.1.4 negative lanes remain out of scope. |
| 2 | Pass only after narrowing | Predicate constants,comparison constants,`in` members,and `addc/mulc` constants use different validation details,but all can be expressed as existing `Const` leaf replacement plus full native re-evaluation. Generic arithmetic operands and `not` internals are rejected. |
| 3 | Pass with variable edits rejected | `where_ast_validate.py` dataflow shows predicates and `eq` can bind variables. Path A therefore allows only current `Const -> Const`;it never changes `Var` leaves and does not need a binding planner. |
| 4 | Pass with structural edits rejected | Current native atoms are fixed tuple/list shapes. Path A does not change atom tag,arity,term count,or list length. |
| 5 | Pass | Batch 5a already proves original-frame atom locator invalidation can use existing `ProofFrameRecheckResult` and `affected_action_indices`. No new ProofFrame status is needed and `superseded_by_full_eval` stays rejected. |
| 6 | Pass with lower-level primitive only | Batch 5a precedent forbids `evaluate_native_where(...)` signature drift. Path A can transform a temporary `where` body and call lower-level `evaluate_where(...)`;SDK replay substrate remains out of scope. |
| 7 | Pass by rejection | RuleRef-bound replace is not required for the first slice. `ruleref` atoms and RuleRef-bearing artifacts are unsupported/deferred. |
| 8 | Pass | This is not a vanity wrapper over a shipped whole-atom replace capability:there is no current whole-atom replace runtime,and the user-facing contract is narrower leaf identity plus variant rows and original-frame ProofFrame. If Step 0.B cannot preserve that distinct contract,it must fall back to Path B. |

#### 5.6.3 Step 0.B Carry-Overs

Step 0.B must freeze these before status can move to `scoped`:

- DTO names and fields,with a separate result DTO rather than generalizing Batch 5a `RuleDisableResult`.
- Exact `literal_path` encoding for `pred`,comparison,`in`,and `addc/mulc` constants.
- Rule action container shape in `EvaluationOverlay.rule_actions`,including whether runtime MVP allows one replace action only.
- Error codes for unsupported atom families,non-Const target leaves,invalid replacement values,target-not-found,and native evaluation errors.
- Two-entrypoint compatibility:Fact Overlay and ProofFrame must continue explicit rule-action rejection;Rule Disable must reject replace actions rather than silently treating them as disable.
- Path A primitive function name and module location. Default expectation per Batch 5a precedent:extend `kernel.core.rules.where_eval.evaluate_where(...)` with an optional literal-replacement kwarg and implement a private helper parallel to `_apply_disabled_locators(...)`;do not modify `evaluate_native_where(...)` per falsifier #6.
- Drift gates,especially `evaluate_native_where(...)` signature stability and no SDK/service/agent diffs.

### 5.7 Step 0.B Outcome — DTO / Runtime Freeze

Step 0.B freezes the Path A implementation shape. The blueprint remains `draft` until review accepts this freeze;the next transition is a separate `draft → scoped` commit.

#### 5.7.1 Protocol Shape

Rule literal replace extends the shared overlay lane with one new rule action:

```python
RuleLiteralPathKind = Literal[
    "pred_term",
    "lhs",
    "rhs",
    "in_value",
    "const_operand",
]

@dataclass(frozen=True)
class RuleLiteralPath:
    kind: RuleLiteralPathKind
    index: int | None = None

@dataclass(frozen=True)
class RuleLiteralReplaceAction:
    rule_id: str
    version: str
    branch_index: int
    atom_index: int
    literal_path: RuleLiteralPath
    old_literal: Any
    new_literal: Any
    note: str | None = None

RuleOverlayAction = RuleDisableAction | RuleLiteralReplaceAction
```

Path semantics:

- `pred_term`:requires `index`;targets `("pred", pred_id, terms)[2][index]`.
- `lhs` / `rhs`:requires `index is None`;targets side `1` / `2` of `eq`, `ne`, `gt`, `ge`, `lt`, or `le`.
- `in_value`:requires `index`;targets `("in", var, values)[2][index]`.
- `const_operand`:requires `index is None`;targets arg `3` of `addc` / `mulc`.

The DTO carries `old_literal` as a stale-target guard,mirroring `FactValueOverride.old_fact_tuple` and preventing accidental replacement after the caller's source view has drifted. `old_literal` and `new_literal` must be current native constants,not variables;structural shape is validated by the runtime against the target atom.

#### 5.7.2 Request / Result Surface

Batch 5b ships a separate result type and does **not** generalize Batch 5a `RuleDisableResult`:

```python
RuleLiteralReplaceStatus = Literal["completed", "unsupported", "invalid_request"]

@dataclass(frozen=True)
class RuleLiteralReplaceRequest:
    rule_spec: RuleSpec
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class RuleLiteralReplaceResult:
    status: RuleLiteralReplaceStatus
    variant_rows: tuple[BindingItems, ...]
    proof_frame: ProofFrameRecheckResult | None
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()
```

Runtime entrypoint:

```python
def check_rule_literal_replace_action(
    request: RuleLiteralReplaceRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> RuleLiteralReplaceResult: ...
```

`registry` remains a side-channel kwarg for signature symmetry, but Batch 5b rejects RuleRef-bearing inputs before registry use. Variant rows and original-frame ProofFrame remain separate. No variant `SupportArtifact` capture ships in Batch 5b.

#### 5.7.3 Runtime Scope And Core Primitive

Runtime MVP accepts exactly one `RuleLiteralReplaceAction` and rejects all fact actions in the request overlay. Multiple replace actions are intentionally deferred;the tuple container remains future-compatible.

The native primitive lands in `kernel.core.rules.where_eval`:

```python
@dataclass(frozen=True)
class WhereLiteralReplacement:
    branch_index: int
    atom_index: int
    literal_path: tuple[str, int | None]
    old_literal: Any
    new_literal: Any

def evaluate_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    disabled_locators: frozenset[tuple[int, int]] = frozenset(),
    literal_replacements: frozenset[WhereLiteralReplacement] = frozenset(),
) -> list[dict[str, Any]]: ...
```

Implementation uses a private `_apply_literal_replacements(...)` helper parallel to Batch 5a `_apply_disabled_locators(...)`. The helper validates locator bounds,path compatibility,current target is a supported native literal(`bool`, `int`, or non-variable `str`),`old_literal` matches,`new_literal` is also a supported native literal,and the replacement preserves structural shape. `evaluate_native_where(...)` remains unchanged;this is a hard drift gate.

If both `literal_replacements` and `disabled_locators` are ever supplied by a future caller,the implementation applies literal replacements before disabled locators. This order is chosen for deterministic debugging:overlap cases still become disable-wins because the atom is removed after replacement,and non-overlap cases are order-independent. Batch 5b runtime supplies only `literal_replacements`.

#### 5.7.4 Error / Unsupported Contract

`RuleLiteralReplaceResult` uses the same local status shape as Rule Disable: `completed | unsupported | invalid_request`. It does not import or unify Rule Disable's status alias.

| Condition | Status | Code |
|---|---|---|
| non-native or non-row support artifact | `unsupported` | `RULE_LITERAL_REPLACE_SUPPORT_UNSUPPORTED` |
| support artifact has `rule_refs` or `rule_ref_edges` | `unsupported` | `RULE_LITERAL_REPLACE_RULE_REF_UNSUPPORTED` |
| `rule_spec.where` contains `ruleref` atom | `unsupported` | `RULE_LITERAL_REPLACE_RULE_REF_UNSUPPORTED` |
| overlay contains fact actions | `invalid_request` | `RULE_LITERAL_REPLACE_FACT_ACTIONS_UNSUPPORTED` |
| zero or multiple rule actions | `invalid_request` | `RULE_LITERAL_REPLACE_ACTION_COUNT` |
| single rule action is not `RuleLiteralReplaceAction` | `invalid_request` | `RULE_LITERAL_REPLACE_ACTION_TYPE_UNSUPPORTED` |
| action rule identity mismatches request rule | `invalid_request` | `RULE_LITERAL_REPLACE_RULE_MISMATCH` |
| target locator does not exist | `invalid_request` | `RULE_LITERAL_REPLACE_TARGET_NOT_FOUND` |
| target atom kind unsupported by §5.6.1 | `invalid_request` | `RULE_LITERAL_REPLACE_ATOM_UNSUPPORTED` |
| literal path incompatible with target atom | `invalid_request` | `RULE_LITERAL_REPLACE_PATH_INVALID` |
| target leaf is not a constant or `old_literal` mismatches current leaf | `invalid_request` | `RULE_LITERAL_REPLACE_STALE_LITERAL` |
| `new_literal` is not a supported native literal or is a variable form | `invalid_request` | `RULE_LITERAL_REPLACE_NEW_LITERAL_INVALID` |
| native variant evaluation raises evaluator/runtime validation error | `invalid_request` | `RULE_LITERAL_REPLACE_NATIVE_EVAL_ERROR` |

Invalid replacement values are primarily caught by native evaluation and returned as `RULE_LITERAL_REPLACE_NATIVE_EVAL_ERROR`. The application runtime may preflight obvious structural violations, but it must not duplicate all evaluator type semantics.

#### 5.7.5 Cross-Runtime Compatibility

Adding `RuleLiteralReplaceAction` to `EvaluationOverlay.rule_actions` changes the union accepted by the shared overlay DTO. Runtime ownership remains explicit:

- `check_rule_literal_replace_action(...)` owns `RuleLiteralReplaceAction` semantics.
- `check_rule_disable_action(...)` owns `RuleDisableAction` semantics and must return `invalid_request` with `RULE_DISABLE_ACTION_TYPE_UNSUPPORTED` for a single non-disable rule action. It must not try to read `.rule_id` from an unknown action before type-checking.
- `check_fact_overlay_binding(...)` continues to reject any non-empty `rule_actions` with `RULE_ACTIONS_NOT_SUPPORTED`;no action-specific semantics are added.
- `recheck_proof_frame(...)` continues to return frame-level `unknown` for any non-empty `rule_actions`;the ProofFrame protocol is not expanded.

This mirrors Batch 5a's two-entrypoint discipline and prevents silent ignore of new rule actions.

#### 5.7.6 Drift Gates / Acceptance Additions

Implementation acceptance adds these gates:

- `git diff --stat -- src/kernel/core/rules/ruleref_substrate.py src/kernel/application/protocol/proofframe.py` is empty.
- `def evaluate_native_where` signature is unchanged.
- `src/kernel/sdk`, `src/factpy_kernel/service`, and `src/factpy_kernel/agent` diffs are empty.
- `src/kernel/application/rule_disable_runtime.py` changes are limited to the narrow non-disable rule-action rejection guard.
- `src/kernel/application/fact_overlay_runtime.py` and `src/kernel/application/proofframe_runtime.py` keep generic rule-action rejection behavior and do not import or inspect `RuleLiteralReplaceAction`.
- no `superseded_by_full_eval`, `param_override`, `condition_weights`, ProbLog probability carrier, or PyReason bound surface appears in Batch 5b code.

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

- [x] Step 0 records a concrete A/B/C decision with rejected reasons(see §5.6).
- [x] Step 0 answers all eight falsifiers in §5.1 with source-backed examples(see §5.6.2).
- [x] If Path A is selected,Step 0 freezes the first atom-kind set and literal-path constraints(see §5.6.1).
- [x] Step 0.B freezes Path A protocol/runtime/core primitive/error/drift-gate shape(see §5.7).
- [x] Path B was not selected;abandonment is not applicable(see §5.6).
- [x] Path C was not selected;split follow-up is not applicable(see §5.6).

**Implementation acceptance(Path A only;blocked until scoped):**

- [x] Protocol DTOs are frozen and tested.
- [x] Native variant rows stay separate from original-frame ProofFrame.
- [x] RuleRef-bearing inputs are rejected/deferred.
- [x] Existing Rule Disable / Fact Overlay / ProofFrame behavior is unchanged except explicitly scoped compatibility guards.
- [x] No SDK/service/agent diffs.
- [x] No `superseded_by_full_eval` revival.
- [x] `evaluate_native_where(...)` signature and RuleRef substrate are unchanged.
- [x] Rule Disable rejects non-disable rule actions with a narrow guard;Fact Overlay and ProofFrame keep generic rule-action rejection.
- [x] Module docs under `src/kernel/application/docs/` are updated if implementation ships.
- [x] Focused tests,full kernel unittest,ruff,and `git diff --check` pass.

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

- Final landed result:Batch 5b shipped narrow native Rule Literal Replace. `RuleLiteralReplaceAction` joins `EvaluationOverlay.rule_actions`;`RuleLiteralReplaceRequest / RuleLiteralReplaceResult` provide a separate runtime surface;`check_rule_literal_replace_action(...)` evaluates one temporary Const-to-Const literal replacement and returns variant rows plus the original-frame ProofFrame.
- A/B/C decision:Step 0 selected Path A only. Path B abandonment and Path C split were rejected because the selected first slice is a single Const-leaf replacement family,not a generalized v0.1.4 `param_override` revival.
- Rejected alternatives:variable edits,atom shape changes,`not` internals,RuleRef replacement,condition weights,ProbLog carriers,PyReason bounds,generalized result DTO reuse,variant SupportArtifact capture,and multi-action runtime support remain out of scope.
- Deviations from draft:none after Step 0.B. Implementation followed the scoped shape:separate result DTO,one-action MVP,lower-level `evaluate_where(..., literal_replacements=...)`,unchanged `evaluate_native_where(...)`,generic Fact Overlay / ProofFrame rule-action rejection,and narrow Rule Disable action-type rejection.
- Verification / archive note:194 focused tests passed;full kernel unittest passed with 1228 OK / 1 skipped;`python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` passed;`git diff --check` passed;drift checks show no SDK/service/agent,RuleRef substrate,or ProofFrame protocol changes. Blueprint and audit archived after implementation.
