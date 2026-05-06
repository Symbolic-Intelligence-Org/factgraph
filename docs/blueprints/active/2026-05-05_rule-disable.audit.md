# Rule Disable — Audit Log

- Blueprint: [2026-05-05_rule-disable.md](./2026-05-05_rule-disable.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.5a

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 5a branch `v0.1-rule-disable-2026-05-05` cut off `7b307d1`(Batch 4 final + post-archive hardening). Draft starts from parent-plan §5.5a constraints and reads old v0.1.3 disable-condition blueprint via `git show v0.1.1-evidence-tree-operational-overlay:docs/blueprints/archive/2026-05-02_v0.1.3-disable-condition.md` as historical reference only. No implementation authorized until Step 0.A/0.B prove DTO/runtime semantics are crisp and status moves to `scoped`. |
| 2026-05-06 | draft | Pre-commit review pass 1 | Four framing issues fixed before draft commit:(P2)§5.4 now explicitly asks whether `RuleDisableResult` surfaces variant rows/newly-emerged bindings under relaxed evaluation,while keeping that full-eval output separate from single-frame ProofFrame and forbidding `superseded_by_full_eval` revival;(P3)§7 acceptance adds explicit ProofFrame protocol/runtime drift guard and conditional FactOverlay protocol/runtime guard;(P4)§5.3 no longer presents Surface B/C as ordinary Step 0.B candidates — Surface A is the only active candidate unless Step 0.A finds a structural blocker,while B/C are closed with parent-plan/Q1 sibling reasons;(P5)§7 promotes `EvaluationOverlay` backward-compat constructor checks to acceptance,including fact-only positional/keyword construction and explicit empty construction if Shape A is selected. |
| 2026-05-06 | draft | Step 0.A spike completed | New §5.6 records **NARROW SHIP**. The action is crisp if Batch 5a keeps variant evaluation rows separate from ProofFrame explanation:disabled locator is skipped for full native evaluation,and the same locator invalidates the old proof frame only when present in the passed-in `SupportArtifact`. `superseded_by_full_eval` remains rejected;newly-emerged bindings are variant rows,not ProofFrame status. Step 0.A also records explicit rule identity requirement(`rule_id`, `version`, `branch_index`, `atom_index`),RuleRef reject/defer,existing variable-binding error behavior,and the carry-over that Step 0.B must decide whether variant support capture ships now. |
| 2026-05-06 | draft | Pre-commit review pass on Step 0.A | Three P3 cleanup findings reconciled before commit:§7 Step 0.A meta-acceptance is now checked and points to §5.6.1;§5.6.3 includes the multi-action MVP carry-over(DTO may be tuple-shaped while runtime may restrict to one action);§5.6.3 also records the two-entry-point contract so `check_rule_disable_action(...)` owns rule actions while Batch 4 `recheck_proof_frame(...)` and Fact Overlay runtime stay fact-only instead of silently becoming rule-action runtimes. |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 5a starts after Batch 4 closed at `7b307d1`. The entry criteria from the master plan are met:ProofFrame exists,uses local 3-status output,and has no rule-action support yet.

The old v0.1.3 line validated useful disable-condition semantics but placed the substrate under SDK replay and authoring module IR,which the reset explicitly rejected. This batch therefore treats v0.1.3 as prior-art evidence,not as implementation authority.

### 2026-05-06 — Initial Risk Framing

The central Step 0 risk is semantic duality. Variant evaluation skips the disabled locator,making the rule body easier to satisfy. ProofFrame explanation should mark the disabled atom in an old proof path as invalidated. Step 0 must show these outputs are coherent views of one `RuleDisableAction`;otherwise the batch should split or abandon.

The second risk is layer drift. The most direct old implementation threads `disabled_locators` through native evaluator/support-capture loops. That may still be the right primitive,but the capability surface must start in `kernel.application.protocol` + `kernel.application/<runtime>.py`,with no SDK replay revival.

The third risk is `EvaluationOverlay` compatibility. Batch 3 shipped a fact-only container. Batch 5a likely needs to add a rule-action lane,so Step 0.B must freeze a backward-compatible constructor shape and tests before any code changes.

### 2026-05-06 — Step 0.A Outcome:Narrow Ship With Separate Variant Rows And ProofFrame

Step 0.A confirmed the semantic duality is manageable rather than a v0.1.4-style false merge. The same `RuleDisableAction` has two legitimate outputs:

- native variant evaluation skips the disabled atom and returns the relaxed rule's rows;
- original-frame ProofFrame marks the matching old atom locator as `invalidated`.

The design stays crisp only if those outputs remain separate. Universe shift(new rows from the relaxed body)is not a ProofFrame status and must not revive `superseded_by_full_eval`. Batch 5a should surface variant rows separately if it wants to expose newly-emerged bindings.

Rule identity must be part of the action target. A bare `b0.a1` locator is only meaningful inside a specific `rule_id@version`. The DTO shape should therefore carry `rule_id`, `version`, `branch_index`, and `atom_index`,with any locator string treated as derived display or helper material.

RuleRef is rejected/deferred for 5a. A parent ruleref call site and child support digest require recursive traversal and sidecar lookup,which would exceed the 1-2 session disable slice and re-open Batch 4's deferred recursive ProofFrame work.
