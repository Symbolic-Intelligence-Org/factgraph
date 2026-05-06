# Rule Disable — Audit Log

- Blueprint: [2026-05-05_rule-disable.md](./2026-05-05_rule-disable.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.5a

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 5a branch `v0.1-rule-disable-2026-05-05` cut off `7b307d1`(Batch 4 final + post-archive hardening). Draft starts from parent-plan §5.5a constraints and reads old v0.1.3 disable-condition blueprint via `git show v0.1.1-evidence-tree-operational-overlay:docs/blueprints/archive/2026-05-02_v0.1.3-disable-condition.md` as historical reference only. No implementation authorized until Step 0.A/0.B prove DTO/runtime semantics are crisp and status moves to `scoped`. |
| 2026-05-06 | draft | Pre-commit review pass 1 | Four framing issues fixed before draft commit:(P2)§5.4 now explicitly asks whether `RuleDisableResult` surfaces variant rows/newly-emerged bindings under relaxed evaluation,while keeping that full-eval output separate from single-frame ProofFrame and forbidding `superseded_by_full_eval` revival;(P3)§7 acceptance adds explicit ProofFrame protocol/runtime drift guard and conditional FactOverlay protocol/runtime guard;(P4)§5.3 no longer presents Surface B/C as ordinary Step 0.B candidates — Surface A is the only active candidate unless Step 0.A finds a structural blocker,while B/C are closed with parent-plan/Q1 sibling reasons;(P5)§7 promotes `EvaluationOverlay` backward-compat constructor checks to acceptance,including fact-only positional/keyword construction and explicit empty construction if Shape A is selected. |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 5a starts after Batch 4 closed at `7b307d1`. The entry criteria from the master plan are met:ProofFrame exists,uses local 3-status output,and has no rule-action support yet.

The old v0.1.3 line validated useful disable-condition semantics but placed the substrate under SDK replay and authoring module IR,which the reset explicitly rejected. This batch therefore treats v0.1.3 as prior-art evidence,not as implementation authority.

### 2026-05-06 — Initial Risk Framing

The central Step 0 risk is semantic duality. Variant evaluation skips the disabled locator,making the rule body easier to satisfy. ProofFrame explanation should mark the disabled atom in an old proof path as invalidated. Step 0 must show these outputs are coherent views of one `RuleDisableAction`;otherwise the batch should split or abandon.

The second risk is layer drift. The most direct old implementation threads `disabled_locators` through native evaluator/support-capture loops. That may still be the right primitive,but the capability surface must start in `kernel.application.protocol` + `kernel.application/<runtime>.py`,with no SDK replay revival.

The third risk is `EvaluationOverlay` compatibility. Batch 3 shipped a fact-only container. Batch 5a likely needs to add a rule-action lane,so Step 0.B must freeze a backward-compatible constructor shape and tests before any code changes.
