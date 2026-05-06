# ProofFrame Rechecker(narrow)— Audit Log

- Blueprint: [2026-05-05_proofframe-rechecker.md](./2026-05-05_proofframe-rechecker.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.4

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 4 branch `v0.1-proofframe-2026-05-05` cut off `319d879`(Batch 3 final);draft adopts the Batch 3 falsifiability-first framing template:Step 0.A checklist,decomposition map,4 candidate shapes,Goals/Acceptance/Plan all conditional on Step 0.A outcome |
| 2026-05-06 | draft | Pre-scope review pass 1 | 4 review findings addressed before scope freeze:(P1)Shape D reframed as parent-plan deviation path with explicit suspend / amendment requirement,not normal selection;(P2)`unknown` status examples rewritten to use current Batch 3 substrate(overlay can't directly touch `non_fact_steps`),marked collapse-prone until Step 0.A proves a current-substrate trigger;(P2)decomposition map ruleref row split — one row for in-body ruleref step entry in `non_fact_steps`,one row for paired `RuleRefEdge` metadata,with explicit substrate note that they're two elements not one atom;(P3)§6 prelude added stating common runtime contract(`store` and `registry` are keyword-only side-channel args,never in DTO),so reviewers don't read Shape A/B/C Request DTOs as insufficient |
| 2026-05-06 | draft | Pre-scope review pass 2 | One P1 residual fixed:§8 Acceptance and §9 Implementation Plan still wrote `protocol DTOs (if any beyond runtime function)` and `Protocol tests for chosen DTOs (if any)`,which silently re-introduced the same parent-plan §5.4 exit-criteria deviation that §6 Shape D was tightened against. Both lines now name `ProofFrameRecheckRequest / Result` DTOs explicitly and route any Shape D selection through the §6 deviation path |
| 2026-05-06 | draft | Step 0.A spike completed | Falsifiability checklist + decomposition map + status set decomposition all filled in new §5.5. Decision = **narrow ship**:action set = `replace + remove`(matches Batch 3);status set = `still_valid / invalidated / unknown`(`superseded_by_full_eval` **collapsed** — detecting universe shift requires re-eval which defeats the narrow rechecker's purpose);substrate scope = `pred_witnesses + non_fact_steps`(recognized kinds);**reject** artifacts with non-empty `rule_ref_edges`(defer recursive ruleref recheck to follow-up batch);native-only(`SupportArtifact.kind == "native_binding_v1"`). Step 0.B carry-overs:Shape C(multi-frame)rejected pre-Step 0.B;Shape D remains parent-plan deviation only;Step 0.B chooses between Shape A(status only)and Shape B(status + per-atom verdicts),narrative renderer scope,and helper migration scope. Blueprint stays `draft` — no scope freeze until Step 0.B records its decisions |
| 2026-05-06 | draft | Pre-commit review pass on Step 0.A | 4 review findings addressed in §5.5 / §6 before commit:(P1)decomposition map row for "non_fact_steps recognized kinds" was wrong — it implied binding values change via replace, but frame's `binding_items` is fixed at original eval;rewrote into 2 rows(binding-driven kinds:never `unknown`;`not` kind:`unknown` only if rechecker defers re-eval);concrete `unknown` trigger documented(`not(BlockedAtTime(...))` falsified by `replace` introducing new match);(P1)umbrella names `cmp / arith / not` replaced with concrete `where_eval.py` tags(`eq, ne, in, gt, ge, lt, le, neg, add, sub, addc, mulc` for binding-driven;`not` for absence-checking);Shape A status enum literal updated to 3-status set per §5.5.3;§6 prelude restructured to make Step 0.B choose A vs B only, with C(rejected pre-Step 0.B)and D(parent-plan deviation)kept for traceability;Shape C heading marked closed;(P3)Shape B sketch now explicitly inherits the same `ProofFrameRecheckRequest` as Shape A so Step 0.B does not have to re-debate DTO presence per master plan §5.4 |
| 2026-05-06 | draft | Step 0.B spike completed | 4 decisions filled in new §5.5.5;§3 non-goals + §8 acceptance + §11 plan updated to reflect choices;blueprint stays `draft` pending review then `scoped` transition. Decisions:**(1)Shape B selected**(Shape A rejected — would push per-atom attribution work into narrative renderer,duplicating rechecker logic);Shape B refined with shared `ProofFrameStatus` enum(no separate `AtomVerdict` literal),`affected_action_indices: tuple[int, ...]`(supports multi-witness atoms touched by multiple actions),and runtime aggregation invariant(`result.status == aggregate(atom_verdicts)` per §5.5.2 priority rule). **(2)Narrative renderer:** single-frame,English-only deterministic,consumes `atom_key` + `affected_action_indices`(not `asrt_id`),signature `render_proof_frame_narrative(result, *, overlay) -> str`. **(3)No helpers in Batch 4:** Request DTO is 2 trivial fields,no projection / asrt_id / schema mechanical setup like Batch 2 helpers — adding helper would be zero value(narrow public API). **(4)Defer `not` re-evaluation:** 3 structural problems block in-scope implementation — atom_repr is brittle to parse,sibling-import of `_apply_fact_overlay_projection` violates Q1 Sibling,inline duplication adds DRY burden;`not` steps emit `verdict="unknown"`,follow-up batch may bundle re-eval with substrate enhancement(structured atom field) |
| 2026-05-06 | draft | Pre-commit review pass on Step 0.B | 3 review findings reconciled before commit:(P1)Decision 4 said "regardless of overlay actions" but §5.5.2 `not` row still kept `still_valid` for untouched/remove cases — internal inconsistency. Reconciled to **strict deferral**:`not` row in §5.5.2 now emits `unknown` in all 3 columns;§5.5.3 `unknown` row rewritten as deterministic trigger("any frame with at least one `not` step → `unknown`")with the "may not fire under typical patterns" wording removed;`invalidated` focused test acceptance still uses pred_witnesses path(unaffected). (P1)§6 Shape B legacy code block contradicted §5.5.5 final shape(`AtomVerdict` literal,`affected_action_index: int | None`)— replaced inline with the §5.5.5 final DTO sketch(shared `ProofFrameStatus`,`affected_action_indices: tuple[int, ...]`,aggregation invariant comment),and noted the original "second status set drift" risk is eliminated by the shared-enum refinement. (P2)Front-matter "Related Modules" still listed `capability_helpers.py (only if Step 0 chooses)` and §7 still said "helpers, if shipped, live in capability_helpers" — both updated to make Decision 3(no helpers)deterministic;Related Modules now lists explicit new module paths(`protocol/proofframe.py`,`proofframe_runtime.py`)and explicitly says `capability_helpers.py` is **NOT** touched |
| 2026-05-06 | scoped | Scope frozen for implementation | Step 0.A and Step 0.B are complete and reviewed. Implementation is authorized only for the frozen scope:Shape B DTOs in `protocol/proofframe.py`,native `proofframe_runtime.py`,single-frame English narrative renderer,no helpers,no rule-ref recursion,no SDK/service/agent changes,and strict `not` deferral to `unknown` |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 3 closed at `319d879` with `EvaluationOverlay` shipped narrowed to `replace + remove`,no fact-side `add`,2 hardening rounds completed,scope-clean. Batch 4 is the second round-story batch that introduces new application protocol surface and the **first** to operate on cross-capability artifacts(`SupportArtifact` produced by Check). The blueprint starts in `draft` and uses the same falsifiability-first framing the Batch 3 review-cycle validated.

### 2026-05-06 — Scoped For Implementation

Step 0.A and Step 0.B have both completed and the reviewed outcomes are now scope-freezing constraints. Implementation must stay inside the selected Shape B protocol/runtime/narrative surface, leave `capability_helpers.py` untouched, reject non-native and rule-ref artifacts explicitly, and preserve the strict `not` deferral behavior recorded in §5.5.5.

### 2026-05-06 — Batch 3 Outcome Affects Entry Criteria

Per master plan §9.3 abandonment-protocol "依赖前批输出的批 abandon 时,后批 Step 0.A 重审 entry criteria",Batch 3 was not abandoned but its action set was narrowed(`add` deferred). Step 0.A must therefore verify the rechecker design does not assume `EvaluationOverlay` carries `add` or rule actions. This is captured in §4.4 of the blueprint and must be answered explicitly by Step 0.A.

### 2026-05-06 — Initial Risk Framing

The principal decomposition risk is whether the 4-status set(`still_valid / invalidated / unknown / superseded_by_full_eval`)is genuinely four cases. `unknown` vs `superseded_by_full_eval` is the suspected collapse pair — they may differ only in the recheck implementation's confidence rather than in observable input,which would reduce them to one case. Step 0.A must produce concrete inputs that fire each status independently;if it cannot,the status set must shrink before Step 0.B.

A secondary risk is the validity-vs-narrative split:per-frame validity computation and narrative rendering are bundled by master plan §5.4 but may be two capabilities. If narrative requires per-atom provenance attribution that validity does not naturally compute,Step 0.B must surface that and either expand validity output or split narrative to a follow-up.

A tertiary risk is the future-action backward-compatibility question:Batch 4 ships ahead of Batch 5 rule ops,which are the primary consumer. A status set / DTO shape fit only for fact-overlay scenarios may need rework when Batch 5 lands. Step 0 should imagine future rule-overlay scenarios and check whether the chosen design extends without breaking;if not,record the limitation explicitly.

### 2026-05-06 — Step 0.A Outcome:Narrow Ship,3-Status Set,No Rulerefs

**Decision recorded in blueprint §5.5.** Spike walked the 7 falsifiability items and the 5×3 decomposition map honestly against current substrate(`_support.py` SupportArtifact / PredWitness / NonFactStep / RuleRefEdge structure;`_support_capture.py:170-222` build logic;Batch 3 `EvaluationOverlay` = `replace + remove` on projected facts).

**Three substantive narrowings,each with concrete reason:**

1. **`superseded_by_full_eval` collapsed:** detecting whether overlay enabled new bindings or shifted primary selection requires running `evaluate_native_where(...)` on overlaid view facts. That is precisely Fact Overlay Check's job;the narrow rechecker has no other signal. Status is either always-on(useless)or unreachable. The collapse is honest. Future Batch 5 rule actions(especially `add condition` enabling new derivations)may justify reintroducing this status,**but per blueprint §5.2 directive,Batch 5's needs are not Batch 4 justification**.

2. **Rulerefs out of scope:** `RuleRefEdge.child_support_digest` is a sha256 reference to a recursive child SupportArtifact. Recursive recheck would multiply the batch's complexity(a new traversal protocol,sidecar lookup,potential cycle handling)and lacks any caller pressure at narrow scope. Rejecting artifacts with non-empty `rule_ref_edges` keeps the batch boundary crisp. The dual-element substrate trap(`NonFactStep` step + `RuleRefEdge` edge sharing `step_key`)is sidestepped by the rejection — no need to coordinate two elements when both are out-of-scope together.

3. **Recognized non_fact_step kinds only:** unrecognized kinds → `unknown`. Avoids the rechecker quietly mis-evaluating exotic step kinds. Concrete `NonFactStep.kind` tags(per `where_eval.py` enumeration):
   - **Binding-driven**(`eq`, `ne`, `in`, `gt`, `ge`, `lt`, `le`, `neg`, `add`, `sub`, `addc`, `mulc`, ...):input from `pred_witnesses` → under `replace + remove` either still_valid(witness preserves bound value)or upstream-invalidated. **Never fires `unknown` in narrow Batch 4.**
   - **`not`(absence-checking):** reachable `unknown` trigger if rechecker defers `not` re-evaluation. `replace` can introduce new positive matches that falsify a `not` step;`remove` cannot. Step 0.B / impl may implement `not(<pred>)` re-evaluation to keep `unknown` empirically rare.
   - **Future unrecognized kinds:** always `unknown`.

**Frame-level aggregation rule explicit:** worst per-element verdict wins in priority `invalidated > unknown > still_valid`. This was not in the master plan;recording it here so Step 0.B / implementation does not invent it ad hoc.

**Carry-overs to Step 0.B(not decided here):** Shape A vs Shape B(per-atom verdicts in DTO?);narrative renderer scope and language;helper migration shape. Shape C and Shape D are removed from active candidates(C premature multi-frame;D parent-plan deviation only,not normal alternative).

**Blueprint stays `draft`.** Step 0.B must complete before any scope freeze;implementation must wait for Step 0.B.

### 2026-05-06 — Step 0.B Outcome:Shape B + No Helpers + Defer `not` Re-eval

**Recorded in blueprint §5.5.5.** Four design decisions before scope freeze:

1. **Shape B selected**(per-frame result with per-atom verdicts;same `ProofFrameRecheckRequest` as Shape A per master plan §5.4 mandatory DTO). Shape A rejected because per §5.5.1 item 4 finding(validity + narrative are one capability),hiding per-atom data in Shape A would force narrative to re-run rechecker logic — capability boundary blurred. Shape B exposes the natural by-product of validity computation.

   **Refinements over §6 sketch under Step 0.B review:**
   - Drop separate `AtomVerdict` literal alias;reuse `ProofFrameStatus` for both frame status and atom verdict so coupling drift is impossible at the type level. The "second status set" risk noted in §6 Shape B trade-off is eliminated by sharing the type.
   - `affected_action_index: int | None` → `affected_action_indices: tuple[int, ...]`. A multi-witness `pred_witnesses` entry can have several `asrt_ids` each touched by different overlay actions;`int | None` cannot represent this case honestly.
   - Runtime aggregation invariant:`result.status == aggregate(result.atom_verdicts)` per §5.5.2 priority rule(`invalidated > unknown > still_valid`). Enforced by test.

2. **Narrative renderer single-frame,English-only deterministic.** Consumes `atom_key`(useful for debugging)and `affected_action_indices`(per §5.5.5 Decision 1 refinement);does **not** consume `asrt_id`(internal-opaque,should not leak to user-facing text). Signature:`render_proof_frame_narrative(result, *, overlay) -> str`. Output is sorted by atom_key(already sorted in `SupportArtifact` per `_support.py` ordering rules)so re-runs produce byte-equal output. Multi-frame and localization deferred — multi-frame matches Shape C closure rationale,localization is Batch 8 public-surface concern.

3. **No application-layer helpers in Batch 4.** Request DTO is `(support_artifact, overlay)` — both caller-provided primitives. No projection extraction,no asrt_id reverse lookup,no schema reasoning like Batch 2 `build_fact_value_override` etc. Adding `build_proof_frame_recheck_request(...)` would expand application surface for zero ergonomic gain,violating `feedback_narrow_public_api.md`. Future trigger fire(non-Check sources or multi-frame extension)can re-open this in a follow-up batch.

4. **Defer `not` step re-evaluation.** Three concrete blockers ruled out in-scope implementation:
   - `NonFactStep.details["atom_repr"]` is `repr(atom)` string — re-parsing requires `ast.literal_eval` which is fragile against future kinds carrying non-literal payloads;substrate-clean fix is to store structured atoms in `details`,but that is a substrate change outside narrow Batch 4.
   - Re-evaluating `not(<pred>)` requires applying overlay actions to projected witness rows;`_apply_fact_overlay_projection` lives in `kernel.application.fact_overlay_runtime`. Importing it from ProofFrame violates Q1 Sibling discipline(per `project_fact_overlay_operation_shipped.md`);inline duplication of ~30 lines violates DRY and creates two parallel projection-apply paths.
   - Honest test coverage for `not(<sub_kind>)` combinations(`pred / eq / in / nested not` etc.)plus negative cases exceeds narrow Batch 4 budget.

   **Honest signal under deferral:** `not` steps always emit `ProofFrameAtomVerdict(verdict="unknown", affected_action_indices=())`. Frame-level aggregation may then yield `unknown` for any rule body containing `not` clauses,unless other elements force `invalidated`. Callers needing binding-level pass/fail can use Fact Overlay Check;ProofFrame is honest about its narrow-scope limit. Follow-up batch can implement `not` re-evaluation,possibly bundled with substrate enhancement(structured atom field replacing `atom_repr` string).

**Cascading edits:** §3 non-goals updated with Decision 3(no helpers)and Decision 4(`not` defer);§8 acceptance updated with concrete signatures + invariants(aggregation,`not` verdict,reject paths,deterministic narrative);§11 implementation plan updated to reflect Step 0.B selections;§6 Shape A heading marked **REJECTED** with rejection reason,Shape B heading marked **SELECTED** with reference to §5.5.5 refined sketch.

**Blueprint stays `draft`** — Step 0.B outcome is review-pending. After framing review and any tightening,blueprint may move `draft → scoped`;implementation begins after that transition.

### 2026-05-06 — Date Naming Note

The local environment date is 2026-05-06,but the branch and blueprint basename use `2026-05-05` to match the cross-session anchor and round-story branch sequence(Batch 3 used the same convention). The audit records the actual creation date as 2026-05-06.
