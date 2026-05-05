# ProofFrame Rechecker(narrow)(Batch 4 of Round Story Completion Plan)

- Status: draft
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Parent: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.4
- Scope: Batch 4 — narrow per-frame proof validity over native + fact-overlay; deterministic narrative formatting
- Branch: `v0.1-proofframe-2026-05-05`(off `319d879`)
- Related Modules:
  - `src/kernel/application/protocol/`(new module pending Step 0.B)
  - `src/kernel/application/`(new runtime pending Step 0.B)
  - `src/kernel/application/capability_helpers.py`(only if Step 0 chooses)
  - `src/kernel/application/docs/`
  - `src/kernel/tests/`
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
- No new helper categories beyond what Step 0 confirms is needed.

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

## 6. Candidate Shapes(Draft)

Step 0.B must choose among explicit alternatives and record rejected reasons. All shapes assume Step 0.A confirmed the action set + status set; if Step 0.A narrowed either, only matching shapes are valid candidates here.

**Common runtime contract(applies to every Request/Result shape below):** the rechecker entrypoint takes `*, store: Store, registry: RuleRegistry | None = None` as keyword-only side-channel arguments(matching the existing `check_fact_overlay_binding` / `check_derivation_binding` pattern). Request DTOs carry only caller intent;`Store` and `registry` are not part of any DTO.

### Shape A — Per-frame request / result with status enum

```python
@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus  # Literal[ "still_valid" | "invalidated" | "unknown" | "superseded_by_full_eval" ]
    binding_items: BindingItems  # echo of input artifact's binding for caller convenience
```

Trade-off:minimal,easiest to prove no over-design. Risk:no provenance — narrative renderer cannot say *which* atom invalidated.

### Shape B — Per-frame result with per-atom verdict

```python
@dataclass(frozen=True)
class ProofFrameAtomVerdict:
    atom_key: str  # pred_atom_key or non_fact_step_key
    verdict: AtomVerdict  # Literal[ "still_valid" | "invalidated" | "unknown" ]
    affected_action_index: int | None  # index into overlay.fact_actions, or None if untouched

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus
    binding_items: BindingItems
    atom_verdicts: tuple[ProofFrameAtomVerdict, ...]
```

Trade-off:enables provenance-rich narrative;atom-level coverage. Risk:atom verdict status enum is a second status set — risk of coupling drift between frame status and atom status.

### Shape C — Multi-frame request / result

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
- No new SDK shell surface;helpers,if shipped,live in `kernel.application.capability_helpers` only.

## 8. Acceptance(Draft)

- [ ] Step 0.A records the falsifiability checklist conclusion for each item with concrete reason.
- [ ] Step 0.A records the per-atom recheck decomposition map(filled,not TBD).
- [ ] Step 0.A explicitly chooses ship / narrow / suspend / abandon and records the action set + status set chosen.
- [ ] Step 0.B chooses one candidate shape from §6 and records at least one rejected reason for each other shape.
- [ ] Step 0.B chooses the narrative renderer scope per §5.3 and records rejected alternatives.
- [ ] Step 0 decides helper migration scope(ship helpers,or runtime-only).
- [ ] `ProofFrameRecheckRequest` / `ProofFrameRecheckResult` DTOs are frozen with protocol tests(per master plan §5.4 exit criteria).Shape D requires the parent-plan deviation path described in §6 before this checkbox can be re-interpreted.
- [ ] Rechecker runtime supports the action set + status set chosen by Step 0.A;each chosen status has a focused test that fires it from concrete input.
- [ ] Non-native `SupportArtifact.kind` returns the chosen unsupported representation.
- [ ] Empty overlay behavior is documented and tested.
- [ ] No ledger writes,no Store cache writes,no artifact sidecar writes are tested across all chosen status outputs.
- [ ] Narrative renderer has deterministic output tests(byte-equal across re-runs).
- [ ] `src/kernel/application/docs/01_overview.md` and `_en.md` updated.
- [ ] `python -m unittest <focused proofframe modules>` passes.
- [ ] `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` passes.
- [ ] `git diff --stat -- src/kernel/sdk` is empty.
- [ ] `git diff --stat -- src/kernel/application/derivation_check_runtime.py src/kernel/application/diagnose_runtime.py src/kernel/application/fact_overlay_runtime.py src/kernel/application/why_not_runtime.py` is empty(no shipped capability runtime touched).

## 9. Implementation Plan(Draft)

1. Step 0.A:complete falsifiability checklist + per-atom decomposition map;decide ship / narrow / suspend / abandon;record action set + status set chosen.
2. Step 0.B:choose shape from §6 + narrative renderer scope from §5.3;record rejected alternatives;decide helper migration scope.
3. Protocol tests for `ProofFrameRecheckRequest` / `ProofFrameRecheckResult` DTOs(per master plan §5.4 exit criteria;Shape D selection requires the §6 parent-plan deviation path before this step is skipped).
4. Rechecker runtime that consumes the chosen inputs and produces the chosen status set;explicitly handles non-native `SupportArtifact.kind` rejection.
5. Narrative renderer at the chosen scope;deterministic-output tests.
6. Optional helpers per Step 0 decision.
7. Drift-prevention tests:no-write invariant,no sibling capability import,no SDK substrate,no rule-action assumption.
8. Docs update.
9. Close-out:outcome,archive,inventory.

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
