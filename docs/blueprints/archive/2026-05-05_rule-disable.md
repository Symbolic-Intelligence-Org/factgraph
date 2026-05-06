# Rule Disable(Batch 5a of Round Story Completion Plan)

- Status: implemented
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Parent: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.5a
- Scope: Batch 5a — application-first rule-side disable action over native rule bodies,with ProofFrame-compatible output
- Branch: `v0.1-rule-disable-2026-05-05`(off `7b307d1`)
- Related Modules:
  - `src/kernel/application/protocol/derivation_fact_overlay.py`(candidate:extend `EvaluationOverlay` with rule action container)
  - `src/kernel/application/protocol/proofframe.py`(consumer contract:existing 3-status ProofFrame output)
  - `src/kernel/application/rule_disable_runtime.py`(candidate new runtime;Step 0.B decides exact name/surface)
  - `src/kernel/core/rules/where_eval.py` / `src/kernel/core/store/_support_capture.py`(possible narrow core primitive if Step 0 proves application runtime cannot preserve locator stability without it)
  - **NOT** `src/kernel/sdk/` — no SDK replay substrate revival
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-05-05_proofframe-rechecker.md](../archive/2026-05-05_proofframe-rechecker.md)
  - [2026-05-05_evaluation-overlay.md](../archive/2026-05-05_evaluation-overlay.md)
  - `v0.1.1-evidence-tree-operational-overlay:docs/blueprints/archive/2026-05-02_v0.1.3-disable-condition.md`(historical reference via `git show`,not current truth)
- Audit Log:
  - [2026-05-05_rule-disable.audit.md](./2026-05-05_rule-disable.audit.md)

## 1. Problem

Batch 3 created `EvaluationOverlay` for fact-side `replace + remove`. Batch 4 created the narrow ProofFrame Rechecker that can explain which atoms in an existing frame remain valid under a fact overlay. Batch 5a starts rule-side operations with the smallest prior-art action:disabling one rule condition locator.

The reset removed the old v0.1.x SDK replay substrate. The old v0.1.3 experiment still matters as a design probe:it validated a native disabled-locator semantic where authoring payloads stay complete,locators stay stable,and evaluation/support capture skip disabled atoms by `b{branch}.a{atom}`. But that implementation lived under SDK replay and authoring module IR. Batch 5a must reintroduce the capability application-first,or abandon if the application DTO/runtime shape is not crisp.

The main design risk is a semantic split:

- **Variant evaluation semantics:** disabling a condition skips that condition,so the rule body is easier to satisfy.
- **ProofFrame semantics:** a frame whose old proof path contains the disabled locator should report that old atom/path as invalidated so Batch 4 narrative can say what changed.

Step 0 must prove those are two views of one crisp action,not two incompatible operations smuggled under one DTO.

## 2. Goals

- Freeze a rule-side disable action DTO that extends the Batch 3 overlay family without adding fact-side `add` or Batch 5b/5c operations.
- Implement native-only disabled-locator evaluation for rule bodies if Step 0 confirms the semantic and layer shape are crisp.
- Produce ProofFrame-compatible status output for the disabled locator path using the existing Batch 4 3-status vocabulary.
- Preserve locator stability:`b{branch}.a{atom}` positions do not shift when a condition is disabled.
- Preserve application-first boundaries:no SDK replay substrate,no persistent rule mutation,no service/agent surface.

## 3. Non-goals

- No rule condition replace(Batch 5b).
- No add condition / binding planner(Batch 5c).
- No fact-side `add`.
- No SDK `replay_with_patch(...)` revival or new SDK replay module.
- No persistent rule variant,registry mutation,or new rule version promotion.
- No cross-engine disable semantics;native only.
- No RuleRef-recursive disable semantics unless Step 0 explicitly proves a narrow first-slice handling. Default is reject/defer.
- No reintroduction of `superseded_by_full_eval` into ProofFrame.
- No status enum unification across application capabilities.
- No audit JSONL persistence(Batch 6).

## 4. Current Context

### 4.1 Parent-plan constraints

Round Story master plan §5.5a requires:

- `RuleDisable` action DTO frozen and归入 `EvaluationOverlay`;
- native overlay implementation;
- ProofFrame output explaining "disabled atom causes which frame invalidated";
- drift gates proving no SDK substrate.

Batch 5 total constraints apply:

- all new capability substrate starts in `kernel.application.protocol/` + `kernel.application/<runtime>.py`;
- no old SDK replay substrate revival;
- every rule action runtime must output ProofFrame status consumable by Batch 4 narrative;
- Step 0 must explicitly answer whether the action DTO is semantically crisp.

### 4.2 Current implementation substrate

- `EvaluationOverlay` currently has only `fact_actions: tuple[FactValueOverride | FactRemoveAction, ...]`.
- `ProofFrameStatus` is frozen to `still_valid | invalidated | unknown`;empty atom verdicts aggregate to `unknown`.
- `SupportArtifact` atom keys use `b{branch}.a{atom}:{kind-or-pred}` and preserve source atom positions.
- `RuleSpec.where` is tuple/list where IR evaluated by native `evaluate_where(...)` or by `ruleref_substrate.evaluate_native_where(...)` when RuleRef is present.
- No current code carries `disabled_locators`,and no current code under `src/kernel/sdk/` should be touched for this batch.

### 4.3 Historical v0.1.3 input(reference only)

`git show v0.1.1-evidence-tree-operational-overlay:docs/blueprints/archive/2026-05-02_v0.1.3-disable-condition.md` records a prior design:

- do not drop atoms because that shifts locator keys;
- do not add a truth/no-op atom because that expands the where language;
- use native runtime overlay:loops enumerate atoms and `continue` when locator is disabled;
- support capture also skips disabled locators,so disabled atoms do not emit support keys while later atom keys retain original numbers;
- RuleRef-bound replay remained rejected.

Batch 5a may adopt these conclusions only after reframing them as application-layer DTO/runtime decisions.

## 5. Step 0 Questions

### 5.1 Step 0.A Falsifiability Checklist

Step 0.A must answer each item with concrete code references and examples before any DTO is frozen:

- **Semantic crispness:** Is "disable condition locator" one operation?If variant evaluation(skip atom)and ProofFrame invalidation(old proof atom removed)cannot be explained as one action with two outputs,abandon or split.
- **Locator target crispness:** Does a target locator always mean `rule_id + version + branch_index + atom_index`?If branch/atom alone can collide across rules or versions,the DTO must include rule identity.
- **Where-shape coverage:** Can flat where and OR-branch where share the same locator semantics without shifting positions?
- **Variable binding safety:** What happens when disabling an atom removes the only binder for a later variable?Does native evaluation raise the existing validation error,return zero rows,or require a new error?If new error infrastructure is required,scope may be too broad.
- **Support capture alignment:** Can evaluation and support capture skip the same locator set while preserving support keys for later atoms?
- **ProofFrame integration:** Can a disabled locator be mapped to `ProofFrameAtomVerdict(verdict="invalidated", affected_action_indices=(i,))` without adding a new ProofFrame status or changing Batch 4 DTOs?
- **RuleRef boundary:** Does disable interact with RuleRef parent/child support?If recursive rule disable is needed for correctness,5a should reject RuleRef-bearing inputs and defer.
- **Layer boundary:** Can implementation start with application DTO/runtime while any core evaluator changes remain narrow primitives?If the only viable path is SDK replay substrate,abandon.

### 5.2 Candidate Action Shapes

Step 0.B should choose one active shape after Step 0.A:

#### Shape A — Extend `EvaluationOverlay` with `rule_actions`

```python
@dataclass(frozen=True)
class RuleDisableAction:
    rule_id: str
    version: str
    branch_index: int
    atom_index: int
    note: str | None = None

@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactOverlayAction, ...] = ()
    rule_actions: tuple[RuleDisableAction, ...] = ()
```

Pros:matches parent-plan "归入 `EvaluationOverlay`";keeps one overlay container for Batch 3/4/5 consumers. Risk:modifies an already-shipped DTO,so default values and backward compatibility must be exact.

#### Shape B — Separate `RuleEvaluationOverlay`

```python
@dataclass(frozen=True)
class RuleEvaluationOverlay:
    rule_actions: tuple[RuleDisableAction, ...]
```

Pros:minimal blast radius on Batch 3 fact overlay. Risk:parent-plan deviation because Batch 5 explicitly says inherit `EvaluationOverlay` container;also forces future bridge logic between fact and rule overlays.

#### Shape C — Runtime-only disabled locator tuple

```python
def evaluate_rule_with_disabled_locators(..., disabled_locators: tuple[str, ...]) -> ...
```

Pros:smallest implementation. Risk:violates parent-plan DTO exit criterion and loses rule identity/action provenance needed by ProofFrame narrative. This is a deviation/suspend path,not a normal choice.

### 5.3 Candidate Runtime Surfaces

**Active Step 0.B candidate:Surface A only,unless Step 0.A finds a structural blocker.**

- **Surface A(active):** `check_rule_disable_action(request, *, store, registry) -> RuleDisableResult`,where result includes variant evaluation rows plus ProofFrame-compatible atom verdicts/status for the original frame.
- **Surface B(closed before Step 0.B):** a pure transformer that applies disabled-locator overlay to a `RuleSpec.where`,plus ProofFrame handled by a separate runtime. Rejected because parent-plan §5.5a requires rule action runtime to output ProofFrame status; splitting them creates a second mini-coordinator and likely sibling capability coupling later.
- **Surface C(closed before Step 0.B):** extend existing `recheck_proof_frame(...)` to understand `RuleDisableAction`. Rejected because Batch 4 ProofFrame is intentionally native + fact-overlay only; making it understand rule actions violates Q1 Sibling discipline and backfills Batch 5 concerns into a closed Batch 4 runtime.

Step 0.B should confirm Surface A and freeze its exact DTO/result shape. If Surface A is not viable after Step 0.A, Batch 5a should suspend or abandon rather than silently selecting Surface B/C as ordinary alternatives.

### 5.4 ProofFrame Output Contract

Step 0.B must freeze:

- whether disabled locator maps to `invalidated` even if the variant rule still returns the same binding through the relaxed body;
- whether non-target atoms remain `still_valid`;
- what happens when the support artifact does not contain the disabled locator;
- whether multiple rule actions can be represented now or Batch 5a restricts to exactly one disable action.
- whether `RuleDisableResult` surfaces **variant rows that emerge under the relaxed rule**. Disable can enable new bindings(universe shift),but Batch 4 ProofFrame is single-frame and must not reintroduce `superseded_by_full_eval`. If Batch 5a returns variant rows,the result must keep full-eval output separate from ProofFrame on the original frame. If not,document that callers must run the variant check separately to discover newly-emerged bindings.

### 5.5 Compatibility And Drift Gates

Step 0.B must define tests that prove:

- old fact-only `EvaluationOverlay(fact_actions=...)` construction still works;
- no `src/kernel/sdk` changes;
- no service/agent changes;
- no RuleRef recursive behavior sneaks in;
- no `superseded_by_full_eval` or new ProofFrame status appears;
- disabled locators preserve later atom keys.

### 5.6 Step 0.A Outcome(filled by spike)

**Decision:NARROW SHIP.** `RuleDisableAction` is semantically crisp if Batch 5a keeps the two outputs separate:

- **Variant evaluation output:** run native rule evaluation under a temporary disabled-locator overlay,so the disabled atom is skipped and the rule body may produce fewer,same,or more rows.
- **ProofFrame output:** explain the original proof frame by marking the disabled locator's atom as `invalidated` when that locator appears in the passed-in `SupportArtifact`;non-target atoms remain `still_valid`. This is not a full proof-tree diff and does not search for newly-emerged frames.

This makes "variant evaluation skip" and "old proof atom invalidation" two views of one action:the action disables a rule body atom identified by rule identity + stable locator. It does **not** merge two unrelated operations.

#### 5.6.1 Falsifiability checklist results

| # | Item | Verdict | Reason |
|---|---|---|---|
| 1 | Semantic crispness | **Holds with separated outputs** | The same locator action has two deterministic projections:skip the atom for variant evaluation;invalidate the same locator in the old frame if present. The trap would be using ProofFrame to report universe shift. Step 0.A rejects that:variant rows are full-eval output;ProofFrame is original-frame explanation only. |
| 2 | Locator target crispness | **Holds if rule identity is explicit** | `b{branch}.a{atom}` alone is not globally meaningful. The action target must carry `rule_id`, `version`, `branch_index`, and `atom_index`;a display/helper locator string can be derived but must not be the only identity. |
| 3 | Where-shape coverage | **Holds** | Current `where_eval._normalize_where(...)` treats flat bodies as branch `0` and OR bodies as explicit branch lists. Current evaluator/support code already uses `enumerate`,so a skip primitive can preserve source atom numbers instead of pre-filtering. |
| 4 | Variable binding safety | **Holds,with existing error/row behavior surfaced** | Disabling a binder can enable constant-driven rows(e.g. `eq($x, "alice")`)or can leave selected variables unbound. Existing native evaluation either yields rows according to the remaining body or raises existing `WhereValidationError` / `RuleCompileError` paths such as `select var is unbound`. Batch 5a should map these into its result errors;it does not need a new ProofFrame status. |
| 5 | Support capture alignment | **Viable,but not the source of truth for Step 0.A** | If Batch 5a captures variant support,`build_support_artifact_for_binding(...)` / `find_winning_branch_index(...)` / `derive_rule_ref_edges_for_binding(...)` must receive the same disabled locator set and skip with `enumerate(...); continue`. For the narrow result,ProofFrame can be computed from the original `SupportArtifact` directly,so support-capture threading is not required to prove the action crisp. Step 0.B decides whether variant support capture ships now. |
| 6 | ProofFrame integration | **Holds without Batch 4 DTO changes** | `ProofFrameRecheckResult` already supports `invalidated | still_valid | unknown` and `affected_action_indices`. A rule-disable runtime can build a result directly from original `SupportArtifact` atom keys:matching `bX.aY:*` → `invalidated` with the action index;non-matching atoms → `still_valid`. No `superseded_by_full_eval` or `recheck_proof_frame(...)` extension is needed. |
| 7 | RuleRef boundary | **Reject/defer** | A ruleref call site spans parent `NonFactStep` + `RuleRefEdge` + child support digest. Disabling parent or child atoms needs recursive traversal and sidecar lookup,which is outside 5a. Narrow Batch 5a should reject RuleRef-bearing inputs and rule bodies containing `ruleref` atoms. |
| 8 | Layer boundary | **Holds with narrow core primitives** | The public surface can start in `kernel.application.protocol` + `kernel.application/rule_disable_runtime.py`. Any evaluator change should be a small native primitive for disabled locators,not SDK replay substrate. If implementation pressure pushes toward `src/kernel/sdk/replay.py`,that is a scope failure. |

#### 5.6.2 ProofFrame contract answers

| Question | Step 0.A answer |
|---|---|
| Disabled locator maps to `invalidated` even if variant rows still include the binding? | **Yes.** ProofFrame explains the old path. If the old frame used the disabled locator,the old path is invalidated even when relaxed evaluation still returns the same binding through remaining atoms. |
| Non-target atoms remain `still_valid`? | **Yes**,for the original-frame explanation. Unknown is reserved for unsupported/rejected inputs,not for ordinary non-target atoms. |
| Support artifact does not contain the disabled locator? | The ProofFrame result is `still_valid` if the artifact is otherwise supported and no target atom key matches the disabled locator. This means the action did not invalidate this particular frame. |
| Multiple rule actions now? | Semantically possible,but Step 0.B should decide whether Batch 5a supports `tuple[RuleDisableAction, ...]` immediately or restricts the runtime request to one action for MVP. The DTO container may still be future-compatible. |
| Universe shift / newly-emerged bindings? | **Surface variant rows separately.** Disable can relax a rule and create new rows. Those rows are full native evaluation output,not ProofFrame output. Do not revive `superseded_by_full_eval`;callers compare original/variant rows outside ProofFrame. |

#### 5.6.3 Active Step 0.B carry-overs

- Shape A is the default active path:extend `EvaluationOverlay` with a backward-compatible `rule_actions` lane. Step 0.B must freeze exact defaults and constructor compatibility tests.
- Surface A remains the only active runtime surface:`check_rule_disable_action(request, *, store, registry) -> RuleDisableResult`. Step 0.B must freeze request/result fields.
- Step 0.B must choose whether variant support capture ships in Batch 5a. If it does not ship,document that Batch 5a returns variant rows + original-frame ProofFrame only.
- Step 0.B must freeze error representation for unsupported RuleRef and native evaluation errors.
- Step 0.B must decide multi-action MVP scope:the DTO container can be `tuple[RuleDisableAction, ...]` for forward compatibility,but the runtime may restrict to one action for Batch 5a. If restricted,document the constraint and error behavior.
- Step 0.B must freeze the two-entry-point contract:`check_rule_disable_action(...)` owns rule actions;Batch 4 `recheck_proof_frame(...)` and existing Fact Overlay runtime remain fact-only and must not silently become rule-action runtimes.

### 5.7 Step 0.B Outcome(filled by spike)

**Decision:NARROW SHIP with Shape A and Surface A.** Batch 5a extends the shared `EvaluationOverlay` container with a rule-action lane,but the only runtime that interprets rule actions is the new Rule Disable runtime. Existing Fact Overlay Check and ProofFrame entrypoints stay fact-only and must reject non-empty `rule_actions` instead of silently ignoring them.

#### 5.7.1 Action and overlay DTO shape

Shape A is selected:

```python
@dataclass(frozen=True)
class RuleDisableAction:
    rule_id: str
    version: str
    branch_index: int
    atom_index: int
    note: str | None = None

RuleOverlayAction: TypeAlias = RuleDisableAction

@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactOverlayAction, ...] = ()
    rule_actions: tuple[RuleOverlayAction, ...] = ()
```

Frozen constraints:

- `rule_id` and `version` are non-empty strings.
- `branch_index` and `atom_index` are non-negative integers.
- `note` is `str | None`.
- `EvaluationOverlay` keeps `fact_actions` as its first field,so legacy positional construction `EvaluationOverlay((fact_action,))` still binds to fact actions.
- Keyword construction `EvaluationOverlay(fact_actions=(...))` remains valid.
- `EvaluationOverlay()` is newly valid and means no actions in either lane.
- Shape B is rejected as a parent-plan deviation;Shape C is rejected because it drops action provenance and ProofFrame narrative indexing.

#### 5.7.2 Runtime surface and request/result DTOs

Surface A is selected:

```python
RuleDisableStatus: TypeAlias = Literal["completed", "unsupported", "invalid_request"]

@dataclass(frozen=True)
class RuleDisableRequest:
    rule_spec: RuleSpec
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class RuleDisableResult:
    status: RuleDisableStatus
    variant_rows: tuple[BindingItems, ...]
    proof_frame: ProofFrameRecheckResult | None
    errors: tuple[ErrorDTO, ...]
    warnings: tuple[WarningDTO, ...]
```

Runtime entrypoint:

```python
def check_rule_disable_action(
    request: RuleDisableRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> RuleDisableResult: ...
```

Field semantics:

- `rule_spec` is the concrete native `kernel.core.rules.rule_ir.RuleSpec` being evaluated under disable overlay.
- `support_artifact` is the original native frame whose atom keys are explained. It is not a variant support artifact.
- `support_artifact` is interpreted in the context of `rule_spec`. Batch 4 `SupportArtifact` does not carry `rule_id/version`,so Batch 5a can validate native shape and RuleRef absence but cannot mechanically prove artifact provenance. Passing a frame from a different rule is a caller contract violation; adding rule provenance to `SupportArtifact` is deferred.
- `overlay` may contain rule actions only for this runtime. `fact_actions` in this request are rejected as `invalid_request`.
- `variant_rows` are normalized `BindingItems` rows from full native evaluation under the disabled locator. They are the only Batch 5a surface for universe shift/newly-emerged bindings.
- `proof_frame` is an original-frame `ProofFrameRecheckResult` assembled directly by Rule Disable runtime. It is `None` for `unsupported` and `invalid_request`.
- `errors` are required for `unsupported` and `invalid_request`;`warnings` may remain empty for MVP.

#### 5.7.3 Variant support capture

Batch 5a does **not** ship variant `SupportArtifact` capture. It returns `variant_rows + original-frame ProofFrame` only.

Rejected reason:variant support capture would require threading disabled-locator sets through `evaluate_native_where(...)`, `build_support_artifact_for_binding(...)`, `find_winning_branch_index(...)`, and `derive_rule_ref_edges_for_binding(...)`. That is viable future work,but it is not needed to satisfy the parent-plan proof-frame requirement and would expand the 1-2 session 5a slice. The only core primitive needed in 5a is native evaluation with disabled locators while preserving source atom indexes.

Future trigger:Batch 5b/5c or a UI consumer needs explanations for **variant** rows,not just old-frame invalidation.

#### 5.7.4 Error and unsupported representation

Batch 5a freezes these result mappings:

| Condition | Status | Code |
|---|---|---|
| `support_artifact.kind != "native_binding_v1"` | `unsupported` | `RULE_DISABLE_SUPPORT_UNSUPPORTED` |
| `support_artifact.rule_ref_edges` non-empty | `unsupported` | `RULE_DISABLE_RULE_REF_UNSUPPORTED` |
| `rule_spec.where` contains any `ruleref` atom | `unsupported` | `RULE_DISABLE_RULE_REF_UNSUPPORTED` |
| `support_artifact.root_result_kind != "row"` | `unsupported` | `RULE_DISABLE_SUPPORT_UNSUPPORTED` |
| `overlay.fact_actions` non-empty in `RuleDisableRequest` | `invalid_request` | `RULE_DISABLE_FACT_ACTIONS_UNSUPPORTED` |
| `len(overlay.rule_actions) != 1` | `invalid_request` | `RULE_DISABLE_ACTION_COUNT` |
| action `rule_id/version` does not match `request.rule_spec` | `invalid_request` | `RULE_DISABLE_RULE_MISMATCH` |
| action branch/atom index does not point at an atom in `rule_spec.where` | `invalid_request` | `RULE_DISABLE_TARGET_NOT_FOUND` |
| disabled atom itself is `ruleref` | `unsupported` | `RULE_DISABLE_RULE_REF_UNSUPPORTED` |
| native variant evaluation raises `WhereValidationError` or `RuleCompileError` | `invalid_request` | `RULE_DISABLE_NATIVE_EVAL_ERROR` |

No mapping introduces a ProofFrame status beyond `still_valid | invalidated | unknown`. `superseded_by_full_eval` remains rejected.

#### 5.7.5 Multi-action MVP scope

The DTO container is tuple-shaped for forward compatibility,but Batch 5a runtime accepts **exactly one** `RuleDisableAction`.

Rejected reason for multi-action MVP:multiple disabled locators are semantically possible,but they complicate variant-evaluation ordering,ProofFrame affected-index narratives,and partial error reporting. They are not required for the first Rule Disable slice. A future batch can lift the `RULE_DISABLE_ACTION_COUNT` preflight without changing the container shape.

#### 5.7.6 Two-entry-point compatibility contract

`EvaluationOverlay` becomes a mixed container,but runtime ownership remains explicit:

- `check_rule_disable_action(...)` owns `rule_actions`.
- `check_fact_overlay_binding(...)` remains fact-only. If passed an `EvaluationOverlay` with non-empty `rule_actions`,it returns `invalid_request` with `RULE_ACTIONS_NOT_SUPPORTED`.
- `recheck_proof_frame(...)` remains fact-overlay-only. If passed an `EvaluationOverlay` with non-empty `rule_actions`,it returns frame-level `unknown` with no atom verdicts rather than interpreting or silently ignoring rule actions.
- `render_proof_frame_narrative(...)` does not gain rule-action-specific wording in Batch 5a. Rule Disable result narrative is deferred unless a caller explicitly renders the returned `ProofFrameRecheckResult`.

The Fact Overlay vs ProofFrame response asymmetry is intentional. Fact Overlay has `invalid_request` in its status enum;ProofFrame's Batch 4 enum is frozen to `still_valid | invalidated | unknown`. Returning frame-level `unknown` is the nearest honest signal inside that frozen ProofFrame contract and matches its existing non-native/rule-ref behavior. Adding `invalid_request` to ProofFrame is rejected as Batch 4 protocol drift.

This is the minimum compatibility guard needed after extending `EvaluationOverlay`. It intentionally amends the earlier drift gate:Batch 5a may touch `fact_overlay_runtime.py` and `proofframe_runtime.py` only to add these rule-action rejection guards;it must not add rule-action semantics to either runtime.

## 6. Boundaries And Invariants

- Application DTO/runtime first;SDK stays untouched.
- Disable action is temporary evaluation overlay,not persistent rule mutation.
- Native only.
- Rule identity is explicit;locators are not globally meaningful without rule identity.
- Locator stability is mandatory:do not pre-filter where branches before assigning support keys.
- Existing fact overlay behavior remains backward-compatible.
- Existing ProofFrame DTOs remain unchanged unless Step 0 explicitly records a parent-plan amendment;default is no ProofFrame DTO change.
- Core changes,if any, must be small evaluator/support-capture primitives that do not expose a new public SDK surface.

## 7. Acceptance

**Step 0 acceptance:**
- [x] Step 0.A records the falsifiability checklist with concrete examples(see §5.6.1).
- [x] Step 0.B freezes one action DTO shape and rejected reasons for alternatives(see §5.7.1).
- [x] Step 0.B freezes one runtime surface and ProofFrame output contract(see §5.7.2-§5.7.6).
- [x] No parent-plan deviation selected;Shape A and Surface A follow parent-plan §5.5a.

**Implementation acceptance(to refine after Step 0):**
- [x] `RuleDisableAction` protocol DTO is frozen and tested.
- [x] `EvaluationOverlay` compatibility tests prove fact-only callers still work.
- [x] If Shape A is selected,`EvaluationOverlay(fact_actions=(...))` remains backward-compatible for both positional and keyword construction.
- [x] If Shape A is selected,`EvaluationOverlay()` empty construction is explicitly allowed and tested.
- [x] `RuleDisableRequest` rejects mixed fact+rule overlays;Batch 5a accepts exactly one `RuleDisableAction`.
- [x] `RuleDisableRequest` documents and tests the native row-frame support-artifact contract;rule provenance remains caller-owned because `SupportArtifact` has no `rule_id/version`.
- [x] Existing Fact Overlay and ProofFrame entrypoints reject non-empty `rule_actions` per §5.7.6 rather than silently ignoring them.
- [x] `RuleDisableResult.variant_rows` surfaces newly-emerged bindings as normalized `BindingItems`;ProofFrame remains original-frame only.
- [x] Batch 5a does not ship variant `SupportArtifact` capture.
- [x] Native disable runtime skips disabled locators without shifting later `b{branch}.a{atom}` keys.
- [x] Variable binding failure behavior is documented and tested.
- [x] RuleRef-bearing inputs are rejected/deferred unless Step 0 scopes them in.
- [x] Runtime returns ProofFrame-compatible status/verdicts for disabled atom invalidation.
- [x] `git diff --stat -- src/kernel/application/protocol/proofframe.py` is empty(no Batch 4 protocol DTO drift).
- [x] `git diff --stat -- src/kernel/application/proofframe_runtime.py` contains only the §5.7.6 rule-action rejection guard,no rule-action semantics.
- [x] `src/kernel/application/protocol/derivation_fact_overlay.py` changes are limited to the §5.7.1 backward-compatible `EvaluationOverlay` extension and `RuleDisableAction` / `RuleOverlayAction` protocol additions.
- [x] `src/kernel/application/fact_overlay_runtime.py` changes are limited to consuming `EvaluationOverlay.fact_actions` unchanged plus the §5.7.6 non-empty `rule_actions` rejection guard returning `invalid_request` with `RULE_ACTIONS_NOT_SUPPORTED`;no rule-action semantics.
- [x] No SDK/service/agent diffs.
- [x] No `superseded_by_full_eval` status is introduced.
- [x] Module docs under `src/kernel/application/docs/` are updated.
- [x] Focused tests,full kernel unittest,ruff,and `git diff --check` pass.

## 8. Implementation Plan(Draft)

1. Step 0.A:source-grounded falsifiability pass over locator semantics,variable binding,support capture,ProofFrame output,and RuleRef boundary.
2. Step 0.B:freeze DTO shape,runtime surface,ProofFrame output contract,and drift gates.
3. Move `Status: draft → scoped` only after Step 0.B is reviewed.
4. Protocol implementation:extend/add DTOs according to Step 0.B;add protocol tests.
5. Runtime implementation:native disable overlay and ProofFrame-compatible result;add focused runtime tests.
6. Drift gates:no SDK/service/agent;no FactOverlay/ProofFrame status expansion;RuleRef boundary tests.
7. Docs update:application overview docs.
8. Close-out:fill Outcome/Deviations,archive blueprint/audit,update archive inventory.

## 9. Docs To Update

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/blueprints/archive/README.md` after archive

No SDK docs update unless Step 0 explicitly scopes an SDK wrapper,which is currently a non-goal.

## 10. Outcome / Deviations

- 最终落地结果:Batch 5a ships application-first Rule Disable. `EvaluationOverlay` now has a backward-compatible `rule_actions` lane with `RuleDisableAction`;`RuleDisableRequest` / `RuleDisableResult` live in `protocol/rule_disable.py`;`check_rule_disable_action(...)` evaluates one native `RuleSpec` under exactly one disabled locator and returns `variant_rows` plus an original-frame `ProofFrameRecheckResult`. Fact Overlay and ProofFrame old entrypoints reject non-empty `rule_actions` rather than silently ignoring them.
- 与 blueprint 不同的地方:the scoped plan allowed a narrow core primitive. Implementation first tried threading `disabled_locators` through `evaluate_native_where(...)`,but full-kernel frontier drift gates correctly rejected that public signature change. The final implementation keeps `evaluate_native_where(...)` unchanged and adds the lower-level `evaluate_where(..., disabled_locators=...)` primitive;Rule Disable calls it directly after rejecting RuleRef-bearing inputs.
- 为什么会有这些调整:Rule Disable does not need RuleRef substrate in Batch 5a,so changing the native RuleRef-aware entrypoint was unnecessary scope drift. The lower-level primitive preserves the required native skip semantics without affecting frontier parity gates or existing `evaluate_native_where(...)` consumers.
- 归档说明:Archive with paired audit after implementation verification. Verification snapshot:focused Rule Disable / Fact Overlay / ProofFrame / disabled-locator tests 159 OK;full kernel `python -m unittest discover -s src/kernel/tests -p "test_*.py"` 1193 OK / 1 skipped;`python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` clean;`git diff --check` clean;`git diff --stat -- src/kernel/sdk src/factpy_kernel/service src/factpy_kernel/agent` empty.
