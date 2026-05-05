# EvaluationOverlay + Fact Scenario Core — Audit Log

- Blueprint: [2026-05-05_evaluation-overlay.md](./2026-05-05_evaluation-overlay.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.3

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 3 branch `v0.1-evaluation-overlay-2026-05-05` cut off `37ec62b`;draft captures Step 0 crispness gates for replace/add/remove and compatibility path |
| 2026-05-06 | draft | Step 0 framing hardened | Review found confirmation bias and pre-baked DTO shape;blueprint rewritten to use falsifiability checklist, decomposition map, candidate shape alternatives, and explicit compatibility paths |
| 2026-05-06 | draft | Remaining action-set pre-bake removed | Goals / acceptance / implementation plan now refer to the action set chosen by Step 0.A, rather than assuming replace+add+remove all ship |
| 2026-05-06 | scoped | Scope frozen for Step 0.A | Falsification-first framing reviewed;scope permits Step 0.A spike only, not implementation;Step 0.A must fill checklist and decomposition map before Step 0.B/implementation |

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

### 2026-05-06 — Date Naming Note

The local environment date is 2026-05-06, but the branch and blueprint basename use `2026-05-05` to match the already-synced cross-session anchor and round-story branch sequence. The audit records the actual creation date as 2026-05-06.
