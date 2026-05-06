# Rule Condition Replace — Audit Log

- Blueprint: [2026-05-05_rule-condition-replace.md](./2026-05-05_rule-condition-replace.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.5b

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Batch 5b branch `v0.1-rule-replace-step0-2026-05-05` cut off `7969dab`(Batch 5a Rule Disable final + post-archive hardening). Draft is intentionally Step-0-first and records the parent-plan A/B/C decision gate:literal-only ship,abandon,or split. No implementation is authorized until Step 0 chooses one path and,for Path A only,status moves to `scoped`. |
| 2026-05-06 | draft | Pre-commit review pass 1 | Four P3 framing polish items landed before draft commit:§1 now states the master-plan default lean is Path B abandonment;§5.2 explains why predicate term constants are riskier than comparison/filter literals;§5.5 warns that generalizing Batch 5a `RuleDisableResult` would conflict with archived drift-gate posture and sets a separate result DTO as default expectation;§6 strengthens the `evaluate_native_where(...)` boundary using the Batch 5a frontier-drift correction as hard precedent. |

## Decision Notes

### 2026-05-06 — Batch Origin

Batch 5b starts after Batch 5a closed at `7969dab`. Entry criteria are met:Rule Disable exists application-first,`EvaluationOverlay.rule_actions` exists,Fact Overlay / ProofFrame reject rule actions rather than silently ignoring them,and the lower-level disabled-locator primitive exists without `evaluate_native_where(...)` signature drift.

The active parent plan explicitly marks Batch 5b as a Step 0 decision batch,not an implementation-first batch. It requires one of three outputs:

- Option A — literal-only ship;
- Option B — abandon;
- Option C — split into separate capability DTOs.

The default posture is conservative:if the DTO is not crisp,choose Option B rather than recreating a generalized `param_override`.

### 2026-05-06 — v0.1.4 Negative Result Applied

The old v0.1.4 `param_override` blueprint is used as negative evidence. It found four distinct semantic lanes:

- literal / term changes;
- condition weight changes;
- ProbLog probability carriers;
- PyReason bounds / thresholds.

Batch 5b therefore only asks whether the first lane can be made useful and crisp as **literal-only rule condition replace**. The other three lanes are non-goals unless Step 0 selects Option C and records an explicit split.

### 2026-05-06 — Draft Framing

The draft is deliberately falsifiability-first. It does not present Path A as the default implementation. It requires Step 0 to prove target identity, literal-path semantics, atom-kind scope, variable-binding safety, ProofFrame compatibility, RuleRef boundary, and layer boundary before any code changes.

If Step 0 selects Path B,that is a valid close-out and should be archived as abandoned. If Step 0 selects Path C,the split should become separate blueprints rather than a merged implementation inside this batch.

### 2026-05-06 — Pre-commit Review Pass 1

Review accepted the draft framing as structurally sound and requested wording tighteners only. The changes make conservative defaults visible earlier, clarify predicate-term risk, protect Batch 5a result DTOs from accidental generalization, and restate `evaluate_native_where(...)` signature stability as a hard frontier-gate boundary rather than a soft preference.
