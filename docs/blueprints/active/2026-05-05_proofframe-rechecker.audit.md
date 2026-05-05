# ProofFrame Rechecker(narrow)— Audit Log

- Blueprint: [2026-05-05_proofframe-rechecker.md](./2026-05-05_proofframe-rechecker.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.4

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 4 branch `v0.1-proofframe-2026-05-05` cut off `319d879`(Batch 3 final);draft adopts the Batch 3 falsifiability-first framing template:Step 0.A checklist,decomposition map,4 candidate shapes,Goals/Acceptance/Plan all conditional on Step 0.A outcome |
| 2026-05-06 | draft | Pre-scope review pass 1 | 4 review findings addressed before scope freeze:(P1)Shape D reframed as parent-plan deviation path with explicit suspend / amendment requirement,not normal selection;(P2)`unknown` status examples rewritten to use current Batch 3 substrate(overlay can't directly touch `non_fact_steps`),marked collapse-prone until Step 0.A proves a current-substrate trigger;(P2)decomposition map ruleref row split — one row for in-body ruleref step entry in `non_fact_steps`,one row for paired `RuleRefEdge` metadata,with explicit substrate note that they're two elements not one atom;(P3)§6 prelude added stating common runtime contract(`store` and `registry` are keyword-only side-channel args,never in DTO),so reviewers don't read Shape A/B/C Request DTOs as insufficient |
| 2026-05-06 | draft | Pre-scope review pass 2 | One P1 residual fixed:§8 Acceptance and §9 Implementation Plan still wrote `protocol DTOs (if any beyond runtime function)` and `Protocol tests for chosen DTOs (if any)`,which silently re-introduced the same parent-plan §5.4 exit-criteria deviation that §6 Shape D was tightened against. Both lines now name `ProofFrameRecheckRequest / Result` DTOs explicitly and route any Shape D selection through the §6 deviation path |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 3 closed at `319d879` with `EvaluationOverlay` shipped narrowed to `replace + remove`,no fact-side `add`,2 hardening rounds completed,scope-clean. Batch 4 is the second round-story batch that introduces new application protocol surface and the **first** to operate on cross-capability artifacts(`SupportArtifact` produced by Check). The blueprint starts in `draft` and uses the same falsifiability-first framing the Batch 3 review-cycle validated.

### 2026-05-06 — Batch 3 Outcome Affects Entry Criteria

Per master plan §9.3 abandonment-protocol "依赖前批输出的批 abandon 时,后批 Step 0.A 重审 entry criteria",Batch 3 was not abandoned but its action set was narrowed(`add` deferred). Step 0.A must therefore verify the rechecker design does not assume `EvaluationOverlay` carries `add` or rule actions. This is captured in §4.4 of the blueprint and must be answered explicitly by Step 0.A.

### 2026-05-06 — Initial Risk Framing

The principal decomposition risk is whether the 4-status set(`still_valid / invalidated / unknown / superseded_by_full_eval`)is genuinely four cases. `unknown` vs `superseded_by_full_eval` is the suspected collapse pair — they may differ only in the recheck implementation's confidence rather than in observable input,which would reduce them to one case. Step 0.A must produce concrete inputs that fire each status independently;if it cannot,the status set must shrink before Step 0.B.

A secondary risk is the validity-vs-narrative split:per-frame validity computation and narrative rendering are bundled by master plan §5.4 but may be two capabilities. If narrative requires per-atom provenance attribution that validity does not naturally compute,Step 0.B must surface that and either expand validity output or split narrative to a follow-up.

A tertiary risk is the future-action backward-compatibility question:Batch 4 ships ahead of Batch 5 rule ops,which are the primary consumer. A status set / DTO shape fit only for fact-overlay scenarios may need rework when Batch 5 lands. Step 0 should imagine future rule-overlay scenarios and check whether the chosen design extends without breaking;if not,record the limitation explicitly.

### 2026-05-06 — Date Naming Note

The local environment date is 2026-05-06,but the branch and blueprint basename use `2026-05-05` to match the cross-session anchor and round-story branch sequence(Batch 3 used the same convention). The audit records the actual creation date as 2026-05-06.
