# EvaluationOverlay + Fact Scenario Core — Audit Log

- Blueprint: [2026-05-05_evaluation-overlay.md](./2026-05-05_evaluation-overlay.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](../active/2026-05-05_round-story-completion-plan.md) §5.3

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 3 branch `v0.1-evaluation-overlay-2026-05-05` cut off `37ec62b`;draft captures Step 0 crispness gates for replace/add/remove and compatibility path |
| 2026-05-06 | draft | Step 0 framing hardened | Review found confirmation bias and pre-baked DTO shape;blueprint rewritten to use falsifiability checklist, decomposition map, candidate shape alternatives, and explicit compatibility paths |
| 2026-05-06 | draft | Remaining action-set pre-bake removed | Goals / acceptance / implementation plan now refer to the action set chosen by Step 0.A, rather than assuming replace+add+remove all ship |
| 2026-05-06 | scoped | Scope frozen for Step 0.A | Falsification-first framing reviewed;scope permits Step 0.A spike only, not implementation;Step 0.A must fill checklist and decomposition map before Step 0.B/implementation |
| 2026-05-06 | scoped | Step 0.A completed | Falsification spike narrowed Batch 3 to `replace + remove`;fact-side `add` deferred because `single + add` requires chosen-policy semantics, not a projection-local row action |
| 2026-05-06 | scoped | Step 0.B completed | Chose Shape D(`EvaluationOverlay.fact_actions: tuple[FactValueOverride | FactRemoveAction, ...]`) and compatibility Path 1(`overlay: tuple[FactValueOverride, ...] | EvaluationOverlay`);helper scope limited to application-layer remove + overlay builders |
| 2026-05-06 | implemented | Implementation complete | Protocol/runtime/helpers/tests/docs updated for `replace + remove`;focused unittest/ruff/diff guards pass;ready for archive |
| 2026-05-06 | implemented | Post-review hardening | Removed legacy validation-name drift, documented remove-helper multi-row disambiguation, made non-native unsupported short-circuit before ruleref preflight, and guarded malformed ruleref atoms |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 2 closed at `37ec62b` with helper ergonomics and no SDK/protocol/runtime algorithm drift. Batch 3 is the first round-story batch that intentionally introduces new protocol DTO design, so this blueprint starts in `draft` and keeps Step 0 questions explicit.

### 2026-05-06 — Initial Risk Framing

The main risk is semantic decomposition. `replace`, `add`, and `remove` can share a projection-local overlay container only if add/remove can be expressed without durable ledger identity, persistence, or chosen-policy semantics. If add requires durable identity or persistence to be meaningful, Batch 3 should suspend or abandon rather than smuggle Batch 6 behavior into the DTO.

### 2026-05-06 — Review-Driven Falsification Rewrite

Review identified two confirmation-bias problems in the initial draft:the "default hypothesis" effectively answered Step 0 before the spike, and the single-field `add` options made semantic decomposition look like an implementation choice. The blueprint now requires Step 0.A to attempt falsification through a checklist and a `replace/add/remove × single/multi` decomposition map.

Step 0.B also now requires explicit candidate DTO shape comparison(three dataclasses + flat union / typed buckets / single polymorphic action / narrow subset) and explicit compatibility-path comparison. At this stage, no scope freeze or implementation was allowed until the pre-baking review completed.

Follow-up review found the same pre-baking still present in Goals, Acceptance, and Implementation Plan wording. Those sections now refer to "the action set chosen by Step 0.A" so a valid Step 0.A outcome may be full ship, narrowed ship, suspend, or abandon without contradicting the blueprint.

### 2026-05-06 — Scoped For Step 0.A

Final spot review verified no residual pre-bake in Goals / Acceptance / Implementation Plan. Scope is frozen only for Step 0.A falsification spike; no DTO or runtime implementation is authorized until Step 0.A records checklist conclusions, decomposition map, and ship/narrow/suspend/abandon decision.

### 2026-05-06 — Step 0.A Narrowed Action Set

Step 0.A reviewed the current projected witness substrate, Fact Overlay runtime, chosen-policy projector, and existing set/add write semantics. `replace` and `remove` both close over visible projected rows: they can validate `asrt_id`, `pred_id`, `e_ref`, and `old_fact_tuple` against copied witness rows, then evaluate before/after without ledger writes or live Store cache mutation.

`add` failed the crispness gate for this batch. Multi-field add has a plausible append-row meaning, but single-field add diverges into reject-on-single, shadow-current, or only-if-no-visible-row semantics. Those are product/policy choices, not implementation details. Batch 3 therefore narrows to `replace + remove`; Step 0.B may choose the DTO shape and compatibility path only for that narrowed action set.

### 2026-05-06 — Step 0.B Shape And Compatibility Freeze

Step 0.B chose the minimal narrowed shape: keep `FactValueOverride` as the replace action, add `FactRemoveAction`, and wrap both in `EvaluationOverlay.fact_actions`. A duplicate `FactReplaceAction` was rejected because it would need to remain behaviorally identical to `FactValueOverride`; typed buckets were rejected as over-structured for two row actions; a polymorphic `kind` action was rejected because nullable `new_fact_tuple` repeats the merged-parameter smell.

Compatibility Path 1 was selected: widen `FactOverlayCheckRequest.overlay` to accept either legacy `tuple[FactValueOverride, ...]` or `EvaluationOverlay`. V2 request types, runtime-only magic acceptance, and request renaming were rejected as too much churn or too weak as protocol truth. Helper scope is application-only: add `build_fact_remove_action(...)` and `build_evaluation_overlay(...)`, keep `build_fact_value_override(...)`, and do not introduce SDK shell surface.

### 2026-05-06 — Implementation Closeout

Implementation followed Step 0.B: `FactRemoveAction` and `EvaluationOverlay` were added to application protocol, legacy `FactValueOverride` tuples remain accepted, runtime normalizes both shapes and applies replace/remove over copied projected witness rows, and application helpers gained remove-action and overlay builders. No SDK files changed. Verification: focused Fact Overlay protocol/runtime/helper unittest suite passed, ruff passed for `src/kernel` plus the capabilities demo, `git diff --stat -- src/kernel/sdk` was empty, `git diff --check` passed, and full kernel unittest ran 1111 OK / 1 skipped.

### 2026-05-06 — Post-Review Hardening

Post-ship review found two cleanup items and two preflight risks. The old `_validate_fact_value_overrides(...)` shim was removed so tests call `_validate_fact_overlay_actions(...)` directly, and `build_fact_remove_action(...)` now documents that multi-cardinality fields require `current_value` to avoid ambiguous remove targets. Runtime preflight now returns `ENGINE_OVERLAY_NOT_SUPPORTED` for non-native engines before native-only ruleref registry validation, and malformed ruleref atoms return `RULE_REF_MALFORMED` instead of escaping as `IndexError`. Verification after hardening: focused Fact Overlay protocol/runtime/helper unittest suite ran 101 OK, ruff passed for `src/kernel` plus the capabilities demo, `git diff --stat -- src/kernel/sdk` was empty, `git diff --check` passed, and full kernel unittest ran 1113 OK / 1 skipped.

One residual risk remains deferred: `OverlayCheckPhase` stores only the representative matched binding, so `OverlayCheckDiff.bindings_added/removed` remains representative rather than exhaustive when a partial/empty requested binding has multiple matches. Fixing that would require a protocol expansion, so it is not included in this hardening patch.

### 2026-05-06 — Date Naming Note

The local environment date is 2026-05-06, but the branch and blueprint basename use `2026-05-05` to match the already-synced cross-session anchor and round-story branch sequence. The audit records the actual creation date as 2026-05-06.
