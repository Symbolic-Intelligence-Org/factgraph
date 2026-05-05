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

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 3 closed at `319d879` with `EvaluationOverlay` shipped narrowed to `replace + remove`,no fact-side `add`,2 hardening rounds completed,scope-clean. Batch 4 is the second round-story batch that introduces new application protocol surface and the **first** to operate on cross-capability artifacts(`SupportArtifact` produced by Check). The blueprint starts in `draft` and uses the same falsifiability-first framing the Batch 3 review-cycle validated.

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

### 2026-05-06 — Date Naming Note

The local environment date is 2026-05-06,but the branch and blueprint basename use `2026-05-05` to match the cross-session anchor and round-story branch sequence(Batch 3 used the same convention). The audit records the actual creation date as 2026-05-06.
