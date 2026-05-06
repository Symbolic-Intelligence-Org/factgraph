# ProofFrame Rechecker(narrow)(Batch 4 of Round Story Completion Plan)

- Status: scoped
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Parent: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.4
- Scope: Batch 4 — narrow per-frame proof validity over native + fact-overlay; deterministic narrative formatting
- Branch: `v0.1-proofframe-2026-05-05`(off `319d879`)
- Related Modules:
  - `src/kernel/application/protocol/proofframe.py`(new — `ProofFrameRecheckRequest` / `ProofFrameRecheckResult` / `ProofFrameAtomVerdict` / `ProofFrameStatus` per §5.5.5 Decision 1)
  - `src/kernel/application/proofframe_runtime.py`(new — `recheck_proof_frame(...)` + `render_proof_frame_narrative(...)` per §5.5.5 Decisions 1 + 2)
  - `src/kernel/application/docs/`(overview update)
  - `src/kernel/tests/`(protocol + runtime + narrative tests)
  - **NOT** `src/kernel/application/capability_helpers.py` — Batch 4 ships no helpers per §5.5.5 Decision 3
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-05-05_evaluation-overlay.md](../archive/2026-05-05_evaluation-overlay.md)
- Audit Log:
  - [2026-05-05_proofframe-rechecker.audit.md](./2026-05-05_proofframe-rechecker.audit.md)

## 1. Problem

Batch 1-3 shipped the 5 canonical questions and the multi-action `EvaluationOverlay` container(`replace + remove`). But after applying an overlay, users only see `Fact Overlay Check`'s before / after pass-fail flip — they cannot see *which atoms in the original proof became invalid* and *which still hold*. That granularity is necessary for:

- Future Batch 5 rule ops(disable / replace / add condition):rule actions can flip a binding's pass-status by invalidating one atom path while another atom path stays valid;Diagnose only locates the failed atom, not the path-replacement;
- Future Batch 6 persistence:durable round events need per-frame validity to express "what did the overlay change";
- Future Batch 7 cross-run diff:per-frame validity is the unit of comparison.

Batch 4 must add this layer **narrowly**:native engine + fact-overlay only,no rule-action assumption,no cross-engine,no persistence. The risk is v0.1.4-style decomposition:`still_valid / invalidated / unknown / superseded_by_full_eval` look like one status enum but may carry incompatible semantics. Step 0 must prove they form one crisp set before any DTO is frozen.

## 2. Goals

- Freeze a `ProofFrame` recheck protocol shape over the action set Step 0.A confirms is crisp.
- Implement a deterministic native + fact-overlay rechecker that consumes existing `SupportArtifact` + `EvaluationOverlay` and produces per-frame validity per the Step 0.A status set.
- Ship a deterministic narrative renderer whose scope and inputs are decided by Step 0.B(may be the per-frame status only,or status + per-atom provenance — Step 0.B chooses).
- Preserve the cross-capability invariants:no Check / Diagnose / Fact Overlay / Why-not status enum changes;no SDK shell;no ledger writes;no live Store cache writes;no cross-engine attempt.

## 3. Non-goals

- No L4 per-frame proof tree diff(Batch 7).
- No L5 cross-run module aggregation(Batch 7).
- No L8 audit JSONL persistence or event reload(Batch 6).
- No cross-engine ProofFrame(L7 territory,non-target this plan).
- No rule-side overlay actions(Batch 5);Batch 4 must not assume `EvaluationOverlay` carries rule actions.
- No `kernel.sdk` shell or substrate.
- No status enum unification across Check / Diagnose / Fact Overlay / Why-not(reframe:伪需求,per Round Story Completion Plan).
- No new helper categories beyond what Step 0 confirms is needed. **Step 0.B Decision 3:** Batch 4 ships **no** application-layer helpers(`build_proof_frame_recheck_request(...)` rejected as zero-value;Request DTO is trivial to construct).
- **Step 0.B Decision 4:** No `not` step re-evaluation in narrow Batch 4. `not` steps emit `ProofFrameAtomVerdict(verdict="unknown", affected_action_indices=())` in Shape B output. Future batch may implement `not(pred(...))` re-eval,possibly bundled with substrate enhancement to replace `NonFactStep.details["atom_repr"]` with structured atom storage.
- No `SupportArtifact` whose `rule_ref_edges` is non-empty in narrow Batch 4. Rechecker returns frame-level `unsupported`-equivalent for such artifacts;recursive ruleref recheck deferred to follow-up batch.

## 4. Current Context

### 4.1 Inputs available

- **`SupportArtifact`** at `src/kernel/core/store/_support.py:96-127`:
  - `kind: str` — backend identifier(`"native_binding_v1"` for native-evaluator path)
  - `root_result_kind: SupportRootResultKind` — `"fact" | "entity" | "row"`
  - `binding_items: BindingItems` — sorted normalized variable→value pairs
  - `pred_witnesses: tuple[PredWitness, ...]` — per-predicate-atom witness asrt_ids;`PredWitness = (pred_atom_key, asrt_ids)`
  - `non_fact_steps: tuple[NonFactStep, ...]` — comparison / arithmetic / NOT-logic atoms
  - `rule_refs: tuple[str, ...]` + `rule_ref_edges: tuple[RuleRefEdge, ...]` — cross-rule deps
- **`EvaluationOverlay`**(Batch 3,`derivation_fact_overlay.py:141-150`):
  - `fact_actions: tuple[FactValueOverride | FactRemoveAction, ...]` only(no fact `add`,no rule actions yet)
- **A "frame" = one complete binding**(per native check flow analysis):`SupportArtifact` is built only for the winning primary binding;not for sub-trees,not for atom sets.

### 4.2 No existing recheck mechanism

The codebase has `evaluate_native_where(...)`,`build_support_artifact_for_binding(...)`,`derive_rule_ref_edges_for_binding(...)` — but **nothing** consumes a `SupportArtifact` and produces per-frame validity. Batch 4 builds genuinely new surface,not refactor.

### 4.3 Hard inherited constraints

- Application-first(per `project_application_first_runtime_authority.md`):DTO + pure runtime in `kernel.application/` first;no SDK substrate.
- Q1 Sibling discipline:do not import sibling capability runtimes / result types.
- No-write invariant:rechecker must not mutate ledger,Store cache,or SupportArtifact sidecar.
- Layer separation:rechecker is application,not evaluator;must not import `kernel.core.rules.frontier` or other evaluator-only modules unless via existing `kernel.core.store/view` projection helpers.

### 4.4 Entry-criteria check from Batch 3 outcome

Batch 3 narrowed `EvaluationOverlay` to `replace + remove`(no `add`). **Step 0.A must verify**:if the rechecker design assumes overlay can carry `add` or rule actions,that assumption fails entry criteria and the design must be revised before Step 0.B.

## 5. Step 0 Questions

### 5.1 Falsifiability Checklist

Step 0.A must attempt to falsify the "single ProofFrame Rechecker capability over 4 statuses" idea before any DTO is frozen. Record yes/no per item with reason:

- **Status set crispness:** Are `still_valid / invalidated / unknown / superseded_by_full_eval` four genuinely-distinct cases or two pairs of synonyms?In particular,what concrete recheck input produces `unknown` and what produces `superseded_by_full_eval`?If they overlap or one always dominates the other,the set is decomposed.
- **Frame granularity invariance:** Does "frame = one binding" hold across all overlay-action types Step 0 considers in scope?If a single overlay action affects multiple bindings(e.g.,a `remove` on a multi-card field that participated in N matched bindings),is the rechecker output one frame or N frames?
- **Future-action backward compatibility:** When Batch 5 ships rule actions(disable / replace condition / add condition),will the same status set + DTO carry their semantics,or does Batch 4 narrow design forbid extension?If forbid,is that explicit in DTO type or only in current implementation?
- **Validity vs narrative split:** Are per-frame validity computation and narrative rendering one capability(fall together or apart together)or two?If narrative requires data validity-computation does not naturally surface(e.g.,per-atom invalidation reasons,overlay-action attribution),they are likely two capabilities.
- **Native + fact-overlay-only sufficiency:** With current Batch 3 overlay actions and current native SupportArtifact,does the rechecker have any meaningful output beyond what `Fact Overlay Check` already gives?If recheck always agrees with Fact Overlay Check's after-status,Batch 4 has no new value at this scope.
- **No-write invariance:** Can the rechecker compute its output entirely from passed-in `SupportArtifact` + `EvaluationOverlay` + projected witness rows,without ledger writes,without Store cache writes,without SupportArtifact sidecar writes?If any path requires write,abandon or split.
- **Engine-kind handling:** What does the rechecker return when given a `SupportArtifact` whose `kind` is not `"native_binding_v1"` (e.g.,from souffle / problog / pyreason)?If the answer is anything other than a clean `unsupported`-equivalent rejection,the narrow scope is leaking.

Step 0.A must also produce a **per-atom recheck decomposition map**:

| Substrate element in `SupportArtifact` | Overlay leaves untouched | Overlay `replace` matches asrt_id | Overlay `remove` matches asrt_id |
|---|---|---|---|
| `pred_witnesses` entry whose asrt_ids include matched id | TBD | TBD | TBD |
| `pred_witnesses` entry whose asrt_ids do not include matched id | TBD | TBD | TBD |
| `non_fact_steps` entry(comparison / arithmetic / NOT,**indirectly** affected by changed bindings)| TBD | TBD | TBD |
| `non_fact_steps` entry that represents an in-body ruleref invocation(`step_key` form `b<i>.a<j>:ruleref`)| TBD | TBD | TBD |
| `rule_ref_edges` entry(metadata:`child_support_digest` / `unresolved_reason`,paired with the ruleref step above)| TBD | TBD | TBD |

**Substrate note:** A ruleref invocation lives in **two** substrate elements — a `NonFactStep` carrying the atom key,and a paired `RuleRefEdge` carrying child-support metadata. Step 0.A must explicitly decide whether the recheck rule reads the step,the edge,or both,and how to avoid double-counting or missed invalidation. **Do not** treat them as one atom.

If the map cannot be filled with a single crisp recheck rule per cell,the rechecker is decomposed and Step 0.A must choose:abandon,suspend,or narrow Batch 4 to a smaller crisp subset(e.g.,fact-only atoms,defer ruleref entries to a follow-up batch).

### 5.2 Status Set Decomposition

Step 0.A must answer for each candidate status:

- `still_valid`:concrete input that produces this — e.g.,no overlay action touches any asrt_id used by the frame.
- `invalidated`:concrete input — e.g.,a `remove` action removes an asrt_id that appears in `pred_witnesses`,leaving a pred atom with no witness.
- `unknown`:concrete input under **current substrate**(Batch 3 overlay = `replace + remove` only,acting on projected facts):overlay actions cannot directly touch `non_fact_steps` or `rule_ref_edges` — those substrate elements have no asrt_id that overlay actions target. `unknown` may therefore only fire indirectly when:(a) a ruleref's `RuleRefEdge.child_support_digest` is unresolved or its child support cannot be locally inspected;(b) `SupportArtifact.kind != "native_binding_v1"`(overlap with §5.1 item 7 — Step 0.A must reconcile). **Mark `unknown` as collapse-prone until Step 0.A produces a concrete current-substrate input that fires it but not `superseded_by_full_eval`.**
- `superseded_by_full_eval`:concrete input — does this differ from `unknown`?Possibilities:(a) the overlay enables new bindings that did not previously exist,which only full re-eval can find;(b) frame's primary-selection guarantee no longer holds.

If `unknown` and `superseded_by_full_eval` cannot be distinguished by an input that fires one but not the other under current Batch 3 substrate,collapse them and shrink the status set. Future Batch 5 rule actions may justify reintroducing the split,but **must not** be cited as Batch 4 justification.

### 5.3 Narrative Renderer Boundary

Step 0.B must decide:

- Is the renderer **status-only**(consumes only the per-frame status enum)or **status + provenance**(consumes per-atom invalidation attribution)?
- Is the renderer **single-frame**(one frame in,one text out)or **multi-frame**(green / red board over many frames)?
- What language scope:English-only,Chinese-only,both?
- Does it consume capability-specific identifiers(`pred_atom_key`,`asrt_id`)or pure status?

If renderer needs data validity-computation does not surface,Step 0.A may split renderer into Batch 4.5 / future or merge with Step 0.B contract.

### 5.4 Helper Migration / DTO Surface Question

Per Batch 3 helper-migration lesson,Step 0 must decide:

- Does Batch 4 ship a `recheck_proof_frame(support_artifact, overlay, *, store)` runtime entry only,or also application-layer helpers(e.g.,`build_proof_frame_recheck_request(...)`)?
- If helpers ship,must not introduce SDK shell surface(per Batch 2/3 invariant).
- Does Batch 4 add anything to existing protocol re-exports,or stay strictly module-local?

### 5.5 Step 0.A Outcome(filled by spike)

**Decision: NARROW SHIP.**

- **Action set:** `replace + remove`(matches Batch 3 outcome,no `add` / no rule actions)
- **Status set:** 3 statuses — `still_valid | invalidated | unknown`(`superseded_by_full_eval` **collapsed**;see §5.2 results below)
- **Substrate scope:** `pred_witnesses` + `non_fact_steps`. Concrete `NonFactStep.kind` tags(per `where_eval.py` enumeration):
  - **Binding-driven**(input from `pred_witnesses`):`eq`, `ne`, `in`, `gt`, `ge`, `lt`, `le`, `neg`, `add`, `sub`, `addc`, `mulc`, ...
  - **Absence-checking**:`not`(re-evaluation requires re-projecting view_facts under overlay;Step 0.B / impl decides whether to implement;deferral makes `unknown` reachable per §5.5.3)
  - **Unrecognized future kinds**:always `unknown`
- **Reject** `SupportArtifact` whose `rule_ref_edges` is non-empty in narrow Batch 4 — return an `unsupported`-equivalent result and defer ruleref recheck to a follow-up batch
- **Engine scope:** `SupportArtifact.kind == "native_binding_v1"` only;all other kinds return `unsupported`
- **Entry-criteria check from Batch 3:** confirmed — design assumes only `replace + remove` overlay actions;no `add` or rule-action assumption present anywhere in §5.5 / §6 / §7

#### 5.5.1 Falsifiability checklist results

| # | Item | Verdict | Reason(grounded in substrate)|
|---|---|---|---|
| 1 | Status set crispness | **Falsified for `superseded_by_full_eval`** | Detecting universe shift from `replace + remove` requires re-running `evaluate_native_where(...)`,which defeats the rechecker's narrow-scope purpose. Without re-eval,`superseded_by_full_eval` is either always-on(useless)or never-fires(unreachable). Collapse it. `still_valid / invalidated / unknown` remain distinguishable(see §5.5.3). |
| 2 | Frame granularity invariance | **Holds** | `SupportArtifact` is built per primary winning binding(`_support_capture.py:29`);overlay action's effect on other bindings is not this frame's concern. Frame = one binding stays invariant under `replace + remove`. |
| 3 | Future-action backward compatibility | **Compatible at narrow scope** | 3-status set carries Batch 5 rule `disable / replace condition / add condition` cleanly:all map to `invalidated` if the frame's rule chain depends on the changed rule;`still_valid` otherwise. Universe-shift concerns(rule add condition enabling new bindings)reintroduce `superseded_by_full_eval` need,but **that is Batch 5's design problem,not Batch 4 justification**. |
| 4 | Validity vs narrative split | **One capability** | To compute validity,the rechecker must identify which action invalidated which atom — narrative just formats this. Per-atom verdict data is a natural by-product. Step 0.B chooses Shape A vs B based on whether to expose this in DTO,but it is not a separate batch. |
| 5 | Native + fact-overlay sufficiency | **Marginally meaningful,kept** | Pure pass/fail(Fact Overlay Check)cannot distinguish "exact witness chain still holds" from "alternative witness chain exists". When `PredWitness.asrt_ids` has multiple elements(`_build_pred_witness` L185-194 collects all matching projection rows),removing one asrt_id may leave the atom satisfied via the others. ProofFrame surfaces this distinction;Fact Overlay Check does not. Strongest value still lives in Batch 5 rule ops,but narrow Batch 4 has non-trivial output. |
| 6 | No-write invariance | **Holds** | Inputs are read-only(`SupportArtifact` immutable;`EvaluationOverlay` immutable;`project_view_facts_with_witness(store.ledger, store.schema_ir)` does not mutate). Recheck logic is pure projection over these inputs. No `set_field` / `add_field` / `retract_by_asrt` / sidecar-write call paths required. |
| 7 | Engine-kind handling | **Reject non-native** | `SupportArtifact.kind != "native_binding_v1"` returns explicit `unsupported`-equivalent. Souffle's `"souffle_witness_v1"` is also witness-bearing(per `_WITNESS_BEARING_SUPPORT_KINDS`)but excluded by §7 narrow-scope rule(L7 territory,non-target this plan). |

#### 5.5.2 Per-substrate decomposition map(filled)

For each substrate element × overlay-action effect,the recheck rule is:

| Substrate element | Untouched | `replace` matches asrt_id | `remove` matches asrt_id |
|---|---|---|---|
| `pred_witnesses` entry whose `asrt_ids` include the matched id | atom `still_valid` | If new `fact_tuple` value at the bound-variable position equals the binding's value for that variable → atom `still_valid`(witness chain holds via the new value);else atom `invalidated`(this asrt_id no longer witnesses the grounded atom) | If `asrt_ids` had **other** matching elements not touched by overlay → atom `still_valid`(alternative witness still holds);if this was the only asrt_id → atom `invalidated` |
| `pred_witnesses` entry whose `asrt_ids` do not include the matched id | atom `still_valid` | atom `still_valid`(action's asrt_id is not part of this witness chain) | atom `still_valid`(same reason) |
| `non_fact_steps` of binding-driven kinds(`eq`, `ne`, `in`, `gt`, `ge`, `lt`, `le`, `neg`, `add`, `sub`, `addc`, `mulc`, ...) | step `still_valid` | **Never fires `unknown` in narrow Batch 4.** Frame's `binding_items` is fixed by original eval;`replace + remove` cannot mutate it mid-frame. Either(a) a referenced `pred_witnesses` atom is `invalidated` upstream → frame `invalidated` regardless of step,or(b) all referenced atoms still witness via alternative asrt_ids → step input unchanged → step `still_valid`. | Same as `replace` column |
| `non_fact_steps` of `not` kind(absence-checking) | step `unknown` (per Step 0.B Decision 4:strict deferral — rechecker emits `unknown` for **every** `not` step regardless of overlay action;follow-up batch may bundle `not` re-eval with substrate enhancement) | step `unknown` (deterministic per Decision 4) | step `unknown` (deterministic per Decision 4) |
| `non_fact_steps` of unrecognized future kind(rechecker has no kind-specific re-eval logic) | step `still_valid`(no input changed,result preserved) | step `unknown`(rechecker cannot decide without re-evaluating the unknown kind) | step `unknown`(same) |
| `rule_ref_edges` entry(plus its paired `non_fact_steps` ruleref step) | **Out of scope:** any `SupportArtifact` with non-empty `rule_ref_edges` returns frame-level `unsupported`;narrow Batch 4 does not traverse `child_support_digest` recursively | same(out of scope) | same(out of scope) |

**Substrate note already in §5.1 honored:** the dual-element ruleref(NonFactStep + RuleRefEdge sharing `step_key == ruleref_atom_key`)is not double-counted because narrow Batch 4 simply rejects any artifact carrying ruleref. A follow-up batch may implement recursive ruleref recheck;this batch defers the design.

**Frame-level aggregation rule:** frame status is the worst per-element verdict in this priority order:`invalidated > unknown > still_valid`. Any single `invalidated` element → frame `invalidated`;else any `unknown` → frame `unknown`;else `still_valid`.

#### 5.5.3 Status set decomposition results

| Status | Concrete current-substrate input that fires it | Kept? |
|---|---|---|
| `still_valid` | Overlay actions touch zero asrt_ids that appear in any `pred_witnesses.asrt_ids`,and all `non_fact_steps` are either untouched or recognizable-kind passes after re-eval. Example:overlay `replace` on `Person.name`(not used by frame's pred atoms). | ✅ kept |
| `invalidated` | Overlay's `remove` removes the only asrt_id of a `pred_witnesses` entry,or `replace` changes the bound-variable value such that the witness no longer matches the grounded atom. Example:frame binding `$age=25` from `Person.age($p, $age)` with witness asrt_id `a2`;overlay `remove a2` → atom unsupported → frame `invalidated`. | ✅ kept |
| `unknown` | **Deterministic** for any frame whose `SupportArtifact.non_fact_steps` contains at least one entry with `kind == "not"`(per Step 0.B Decision 4 strict deferral). Concrete:frame has `not(BlockedAtTime($p, "now"))` step;rechecker emits `ProofFrameAtomVerdict(verdict="unknown", affected_action_indices=())` for that step regardless of what `overlay.fact_actions` contains. Aggregated to frame status:if no other element is `invalidated`,frame status is `unknown`. **Comparison/arithmetic/membership kinds never fire `unknown`** under narrow Batch 4(per §5.5.2 binding-driven row):frame `binding_items` is fixed,`replace + remove` cannot mutate it mid-frame,so their inputs are either preserved or pre-empted by upstream `invalidated`. | ✅ kept(deterministic for any artifact containing `not` steps;follow-up batch may implement `not` re-evaluation alongside substrate enhancement,which would let `not`-bearing frames produce `still_valid` or `invalidated`. In Batch 4 narrow scope,3-status set has all 3 statuses reachable.) |
| `superseded_by_full_eval` | No current-substrate input fires this without running full re-eval. Detecting "universe shift"(new bindings emerge / primary selection changes)requires `evaluate_native_where(...)`,which is exactly what Fact Overlay Check does. Within narrow Batch 4 scope,this status is either always-on or unreachable. | ❌ **collapsed** — Future Batch 5 rule actions(esp. `add condition` enabling new derivations)may justify reintroducing this status,but per `§5.2` directive that is Batch 5's design problem,not Batch 4 justification. |

#### 5.5.4 Step 0.B carry-overs(decided in next sub-step,not now)

Step 0.A produces these inputs for Step 0.B; Step 0.B will choose:

- **DTO shape choice from §6:** Shape A(status only)vs Shape B(status + per-atom verdicts)— validity/narrative are one capability(§5.5.1 item 4),so the question is whether per-atom verdicts belong in the protocol DTO or stay in the runtime. **Shape C(multi-frame)is rejected before Step 0.B**:Batch 4 caller has one primary frame from Check;multi-frame is premature. **Shape D(no DTO)remains in §6 as the parent-plan deviation path only;not selectable as a normal candidate.**
- **Narrative renderer scope from §5.3:** Step 0.B input — narrative renderer is single-frame,deterministic;language scope and per-atom-key consumption are open questions tied to Shape A vs B choice.
- **Helper migration scope from §5.4:** Step 0.B input — runtime-only vs add `build_proof_frame_recheck_request(...)` helper,strictly inside `kernel.application.capability_helpers`.

### 5.5.5 Step 0.B Outcome(filled by spike)

Four decisions before scope freeze. Each decision records rejected reason for unchosen alternatives.

#### Decision 1 — Shape B selected(Shape A rejected)

**Selected: Shape B**(per-frame result with per-atom verdicts;same `ProofFrameRecheckRequest` as Shape A per master plan §5.4 mandatory DTO).

**Rationale:** §5.5.1 item 5 confirmed ProofFrame's value over Fact Overlay Check is distinguishing "exact witness chain still holds" from "alternative witness chain exists" — that information is per-atom. §5.5.1 item 4 confirmed validity computation must already identify which action invalidated which atom internally. Shape A would hide this data and force any narrative consumer to re-run the analysis(violating §5.5.1 item 4 "one capability" finding). Shape B exposes the natural by-product;Shape A's "minimal" claim is paid for by duplicated work downstream.

**Shape A rejection reason:** narrative renderer would have to compute per-atom attribution itself,duplicating the rechecker's work. The "minimal API surface" framing is misleading because the data must exist somewhere — Shape A pushes it from protocol into renderer. Capability boundary becomes blurred.

**Refinements to the §6 Shape B sketch under Step 0.B:**

- **Shared status enum:** drop the separate `AtomVerdict` literal alias;reuse `ProofFrameStatus` for both frame status and atom verdict so coupling drift is impossible at the type level. Both use `Literal["still_valid", "invalidated", "unknown"]` per §5.5.3.
- **Multi-action attribution:** replace `affected_action_index: int | None` with `affected_action_indices: tuple[int, ...]`. A multi-witness `pred_witnesses` entry can have several `asrt_ids` each touched by different overlay actions;a single `int | None` cannot represent this. Empty tuple = untouched.
- **Aggregation invariant:** `result.status` must equal the priority-aggregation of `result.atom_verdicts` per §5.5.2 frame-level rule(`invalidated > unknown > still_valid`). Enforced by runtime invariant test.

**Final selected DTO shape:**

```python
@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

ProofFrameStatus: TypeAlias = Literal["still_valid", "invalidated", "unknown"]

@dataclass(frozen=True)
class ProofFrameAtomVerdict:
    atom_key: str  # pred_atom_key or non_fact_step_key from SupportArtifact
    verdict: ProofFrameStatus  # shared enum with frame status
    affected_action_indices: tuple[int, ...]  # indices into overlay.fact_actions; () if untouched

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus  # MUST equal aggregate(atom_verdicts) per §5.5.2 priority rule
    binding_items: BindingItems  # echo of input artifact's binding for caller convenience
    atom_verdicts: tuple[ProofFrameAtomVerdict, ...]
```

#### Decision 2 — Narrative renderer scope

**Selected scope:**
- **Single-frame.** Frame = one binding(per Step 0.A);multi-frame is premature(matches Shape C closure rationale).
- **English-only,deterministic.** Localization is a Batch 8 public-surface concern,not Batch 4. Same input bytes-equal same output.
- **Consumes `atom_key` and `affected_action_indices`,not `asrt_id`.** `pred_atom_key` and `non_fact_step_key`(`b<i>.a<j>:<kind>`)are useful for debugging;`asrt_id` is internal-opaque and should not leak to narrative text.
- **Function signature:**

```python
def render_proof_frame_narrative(
    result: ProofFrameRecheckResult,
    *,
    overlay: EvaluationOverlay,
) -> str: ...
```

- **Output format:** header line(`Frame status: <status>`)+ ordered per-atom lines for any verdict ≠ `still_valid`,each citing `atom_key` + `verdict` + `affected_action_indices` + brief action-kind hint(e.g.,`atom b0.a1:Person.age: invalidated by overlay action[0] (replace)`). For `not` steps with `verdict="unknown"`(see Decision 4)the hint is `recheck deferred to follow-up batch; use Fact Overlay Check for binding-level pass/fail`.
- **Determinism:** atom verdicts are already sorted in `SupportArtifact.pred_witnesses` / `non_fact_steps`(per `_support.py` ordering rules);renderer output preserves this order.

**Rejected alternatives:**
- Status-only renderer:would not use Shape B's per-atom data,wasting the chosen shape's value.
- Multi-frame renderer:premature batching;callers concatenate single-frame outputs as needed.
- Bilingual / localized output:Batch 8 concern,not Batch 4.

#### Decision 3 — No helpers in Batch 4

**Selected: runtime entry only.** No `build_proof_frame_recheck_request(...)` or other application-layer helpers.

**Rationale:** `ProofFrameRecheckRequest` has 2 fields(`support_artifact` from Check,`overlay` from caller). Both are caller-provided primitives. No store projection,no `asrt_id` lookup,no schema reasoning — none of the mechanical setup that justified Batch 2 helpers like `build_fact_value_override` or `build_fact_remove_action`. A helper here would add zero value and expand application surface unnecessarily(violating "narrow public API" principle from `feedback_narrow_public_api.md`).

**Future trigger:** if a real ergonomic need emerges(e.g.,constructing requests from non-Check sources,or from a Why-not result with multiple frames),helpers can be added in a follow-up batch — possibly the same one that lifts the Shape C multi-frame restriction.

#### Decision 4 — Defer `not` re-evaluation(`unknown` for `not` steps)

**Selected: defer.** Any `NonFactStep` whose `kind == "not"` produces `ProofFrameAtomVerdict(verdict="unknown", affected_action_indices=())` regardless of overlay actions.

**Rationale — three structural problems with implementing now:**

1. **Atom representation is `repr()` string.** `NonFactStep.details["atom_repr"]` is `repr(atom)` per `_build_non_fact_step` L207-211. To re-evaluate `not(<inner_atom>)`,the rechecker would need to parse this back. `ast.literal_eval` works only when atoms are pure literal tuples,which is fragile against future kinds carrying non-literal payloads. The substrate-clean fix is to store structured atoms in `details`,but that is a substrate change outside narrow Batch 4.
2. **Sibling import violation.** Re-evaluating `not(<pred>)` requires applying overlay actions to projected witness rows — exactly what `_apply_fact_overlay_projection` in `kernel.application.fact_overlay_runtime` does. Importing it from ProofFrame violates Q1 Sibling discipline(per `project_fact_overlay_operation_shipped.md`). Inline-duplicating the ~30 lines violates DRY and creates two parallel projection-apply paths to keep in sync.
3. **Test coverage burden.** Honest `not` re-evaluation needs tests for each `not(<sub_kind>)` combination(`not(pred(...))`,`not(eq(...))`,`not(in(...))`,nested `not(not(...))`),plus negative cases(non-matching `replace`,`remove` of negated witness,etc.). That alone exceeds narrow Batch 4 budget.

**Cost of deferral:** `unknown` becomes a frequent verdict for any rule body containing `not` clauses. Callers needing binding-level pass/fail can use Fact Overlay Check;ProofFrame is honest about its narrow-scope limit.

**Future path:** a follow-up batch(e.g.,Batch 4.5 or bundled with Batch 5)can implement `not` re-evaluation alongside the substrate enhancement that replaces `details["atom_repr"]` with a structured atom field. That batch can also choose whether to refactor `_apply_fact_overlay_projection` into a shared `kernel.application._helpers` module(consumed by both Fact Overlay Check and ProofFrame),or to keep the projection logic per capability.

**Documented in §3 Non-goals + §8 Acceptance(`not` step verdict test).**

## 6. Candidate Shapes(Draft)

**Active Step 0.B candidates after Step 0.A: Shape A and Shape B only.** §5.5.4 closed Shape C and Shape D before Step 0.B:

- **Shape C(multi-frame): rejected pre-Step 0.B** as premature — Batch 4 callers from Check have one primary frame;multi-frame is an extension unjustified by narrow Batch 4 entry criteria.
- **Shape D(pure function, no DTO): retained for traceability only** as the parent-plan deviation path. Selecting Shape D requires the §6.D suspend / amendment / explicit deviation audit per master plan §5.4 exit criteria;**not a normal Step 0.B alternative**.

Step 0.B chooses between Shape A and Shape B and records the rejected reason for the unchosen one. C and D remain in §6 below for traceability only.

**Common runtime contract(applies to every Request/Result shape below):** the rechecker entrypoint takes `*, store: Store, registry: RuleRegistry | None = None` as keyword-only side-channel arguments(matching the existing `check_fact_overlay_binding` / `check_derivation_binding` pattern). Request DTOs carry only caller intent;`Store` and `registry` are not part of any DTO.

### Shape A — Per-frame request / result with status enum(REJECTED by Step 0.B per §5.5.5 Decision 1)

```python
@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus  # per §5.5.3: Literal[ "still_valid" | "invalidated" | "unknown" ]
    binding_items: BindingItems  # echo of input artifact's binding for caller convenience
```

Trade-off:minimal,easiest to prove no over-design. Risk:no provenance — narrative renderer cannot say *which* atom invalidated. **Rejected reason(per §5.5.5 Decision 1):** would force narrative renderer to re-run rechecker logic to attribute invalidation,duplicating work and blurring capability boundary.

### Shape B — Per-frame result with per-atom verdict(SELECTED by Step 0.B per §5.5.5 Decision 1)

Shape B uses the **same `ProofFrameRecheckRequest(support_artifact, overlay)` as Shape A**(per master plan §5.4 mandatory DTO requirement);only the result shape differs by adding per-atom verdicts.

**Final selected DTO**(replaces the original draft sketch with §5.5.5 Decision 1 refinements:shared `ProofFrameStatus` enum,`affected_action_indices: tuple[int, ...]`,aggregation invariant):

```python
ProofFrameStatus: TypeAlias = Literal["still_valid", "invalidated", "unknown"]

@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class ProofFrameAtomVerdict:
    atom_key: str  # pred_atom_key or non_fact_step_key from SupportArtifact
    verdict: ProofFrameStatus  # shared enum with frame status
    affected_action_indices: tuple[int, ...]  # indices into overlay.fact_actions; () if untouched

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus  # MUST equal aggregate(atom_verdicts) per §5.5.2 priority rule
    binding_items: BindingItems  # echo of input artifact's binding for caller convenience
    atom_verdicts: tuple[ProofFrameAtomVerdict, ...]
```

Trade-off:enables provenance-rich narrative;atom-level coverage. The original Shape B "second status set" risk is **eliminated** by the Decision 1 refinement(shared `ProofFrameStatus` enum for both frame status and atom verdict);drift impossible at the type level.

### Shape C — Multi-frame request / result(closed pre-Step 0.B;not active candidate)

```python
@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifacts: tuple[SupportArtifact, ...]
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    frames: tuple[SingleFrameResult, ...]
```

Trade-off:matches future Why-not / multi-binding scenarios. Risk:premature batching — fact-overlay current callers always have one primary frame from Check;multi-frame is an extension not justified by Batch 4 entry criteria.

### Shape D — Pure function,no DTO request(parent-plan deviation path,not a normal candidate)

```python
def recheck_proof_frame(
    support_artifact: SupportArtifact,
    overlay: EvaluationOverlay,
    *,
    store: Store,
) -> ProofFrameRecheckResult: ...
```

Trade-off:smallest API surface,no `Request` ceremony. Risk:future engine / context options have nowhere to go;`Request` shape is a forward-compat investment that pure-function shape forfeits.

**⚠️ Parent-plan conflict:** Master plan §5.4 exit criteria explicitly require `ProofFrameRecheckRequest / Result` **DTO 冻结**. Shape D forfeits the Request DTO and therefore **violates** Batch 4 exit criteria as currently written. This shape is listed for falsification value only(it forces Step 0.B to defend why Request DTOs are necessary). If Step 0.B genuinely prefers Shape D,Batch 4 must:

- **(a)** suspend Batch 4 and open a master-plan amendment that updates §5.4 exit criteria to allow runtime-only surface,then resume after the amendment is committed;OR
- **(b)** record the deviation explicitly in the audit log,with rationale acceptable to the master-plan owner,before any implementation.

Do **not** silently choose Shape D as if it were a normal Step 0.B alternative.

## 7. Boundaries And Invariants

- Rechecker is native + fact-overlay only;non-native `SupportArtifact.kind` returns explicit unsupported result.
- Rechecker reads `SupportArtifact` + `EvaluationOverlay` + projected witness rows from `Store`;writes nothing(no ledger,no Store cache,no artifact sidecar).
- Rechecker does not call `evaluate_native_where(...)` or any other capability runtime;it operates purely on the passed-in artifact + overlay-projection logic that Batch 3 already established.
- Rechecker does not modify any shipped capability's status enum.
- Narrative renderer is deterministic — same input produces same output bytes.
- No new SDK shell surface. **No application-layer helpers in Batch 4** per §5.5.5 Decision 3 — `kernel.application.capability_helpers` is not touched(grep test in §8 acceptance enforces this).

## 8. Acceptance(Draft)

**Step 0.A / Step 0.B output traces(meta — checked when Step recorded):**
- [x] Step 0.A records the falsifiability checklist conclusion for each item with concrete reason(see §5.5.1).
- [x] Step 0.A records the per-atom recheck decomposition map(filled in §5.5.2,no TBD).
- [x] Step 0.A explicitly chooses ship / narrow / suspend / abandon → **narrow ship**(action set + status set in §5.5).
- [x] Step 0.B chooses one candidate shape from §6 and records rejected reason → **Shape B selected**;Shape A rejected per §5.5.5 Decision 1.
- [x] Step 0.B chooses narrative renderer scope per §5.3 with rejected alternatives → **single-frame English-only deterministic** per §5.5.5 Decision 2.
- [x] Step 0.B decides helper migration scope → **no helpers in Batch 4** per §5.5.5 Decision 3.
- [x] Step 0.B decides `not` re-evaluation → **defer**(verdict `unknown`)per §5.5.5 Decision 4.

**Implementation acceptance(unchecked until impl lands):**
- [ ] `ProofFrameRecheckRequest` / `ProofFrameRecheckResult` / `ProofFrameAtomVerdict` DTOs frozen with protocol tests per §5.5.5 final shape(shared `ProofFrameStatus` enum,`affected_action_indices: tuple[int, ...]`).Shape D selection requires the §6 parent-plan deviation path before this checkbox can be re-interpreted.
- [ ] Rechecker runtime `recheck_proof_frame(request, *, store, registry=None) -> ProofFrameRecheckResult` ships;native + fact-overlay only.
- [ ] **Aggregation invariant test:** `result.status == _aggregate(result.atom_verdicts)` per §5.5.2 priority rule(`invalidated > unknown > still_valid`).
- [ ] Each of the 3 statuses(`still_valid` / `invalidated` / `unknown`)has a focused test firing it from concrete input per §5.5.3 examples.
- [ ] **`not` step verdict invariant test:** any `NonFactStep` with `kind == "not"` always emits `ProofFrameAtomVerdict(verdict="unknown", affected_action_indices=())` per §5.5.5 Decision 4.
- [ ] Non-native `SupportArtifact.kind` returns frame-level `unsupported`-equivalent.
- [ ] Non-empty `rule_ref_edges` returns frame-level `unsupported`-equivalent per §5.5.2 row 6.
- [ ] Empty overlay behavior documented and tested.
- [ ] Narrative renderer `render_proof_frame_narrative(result, *, overlay) -> str` ships with deterministic output tests(byte-equal across re-runs;single-frame;English-only;consumes `atom_key` + `affected_action_indices`,not `asrt_id`)per §5.5.5 Decision 2.
- [ ] No ledger writes,no Store cache writes,no `SupportArtifact` sidecar writes tested for the rechecker entry point(no-write invariant per §5.5.1 item 6).
- [ ] **No application-layer helpers added to `kernel.application.capability_helpers`** per §5.5.5 Decision 3(grep test).
- [ ] `src/kernel/application/docs/01_overview.md` and `_en.md` updated.
- [ ] `python -m unittest src.kernel.tests.test_application_proofframe_protocol src.kernel.tests.test_application_proofframe_runtime_native src.kernel.tests.test_application_proofframe_narrative` passes.
- [ ] `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` passes.
- [ ] `git diff --stat -- src/kernel/sdk` is empty.
- [ ] `git diff --stat -- src/kernel/application/derivation_check_runtime.py src/kernel/application/diagnose_runtime.py src/kernel/application/fact_overlay_runtime.py src/kernel/application/why_not_runtime.py src/kernel/application/capability_helpers.py` is empty(no shipped capability runtime or existing helper touched).

## 9. Implementation Plan(Draft)

1. ✅ Step 0.A:completed(see §5.5):**narrow ship**;action set `replace + remove`;status set `still_valid | invalidated | unknown`;reject `rule_ref_edges`;native-only.
2. ✅ Step 0.B:completed(see §5.5.5):**Shape B selected**(refined with shared `ProofFrameStatus` enum + `affected_action_indices: tuple[int, ...]` + aggregation invariant);narrative renderer single-frame English-only;**no helpers**;**defer `not` re-evaluation**(`unknown` verdict).
3. Add `src/kernel/application/protocol/proofframe.py` with `ProofFrameRecheckRequest`,`ProofFrameRecheckResult`,`ProofFrameAtomVerdict`,`ProofFrameStatus` per §5.5.5 final shape;protocol tests for DTO shape + frozen invariants.
4. Add `src/kernel/application/proofframe_runtime.py` with `recheck_proof_frame(request, *, store, registry=None) -> ProofFrameRecheckResult`. Implements per-element recheck per §5.5.2 decomposition map;`not` steps always emit `verdict="unknown"`(Decision 4);frame-level aggregation per §5.5.2 priority rule.
5. Reject paths in runtime:non-native `SupportArtifact.kind` → `unsupported`-equivalent;non-empty `rule_ref_edges` → same.
6. Add narrative renderer `render_proof_frame_narrative(result, *, overlay) -> str`(co-located in runtime module or `proofframe_narrative.py`)per §5.5.5 Decision 2 format;deterministic output tests.
7. Runtime tests:each status fires from concrete input per §5.5.3 examples;aggregation invariant(`result.status == aggregate(atom_verdicts)`);`not` step verdict invariant;no-write invariant;multi-witness pred_atom recheck.
8. Drift-prevention tests:no SDK substrate;no sibling capability runtime imports;no `_apply_fact_overlay_projection` import from Fact Overlay runtime(Q1 Sibling);no helpers added to `capability_helpers.py`;no shipped capability runtime touched.
9. Docs update:`src/kernel/application/docs/01_overview.md` + `_en.md` mention ProofFrame Rechecker module + narrative renderer.
10. Close-out:fill §11 Outcome,archive blueprint + audit,update archive inventory.

## 10. Docs To Update

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`

No `docs/README.md` update expected unless this batch adds a new durable top-level docs entry.

## 11. Outcome / Deviations

任务完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
