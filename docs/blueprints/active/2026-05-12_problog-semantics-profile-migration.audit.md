# Task Blueprint Audit: ProbLog SemanticsProfile Migration

- Blueprint: [2026-05-12_problog-semantics-profile-migration.md](./2026-05-12_problog-semantics-profile-migration.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Track 3 / C opened after B shipped `SemanticsProfile` scaffolding. Source audit found ProbLog has a concentrated adapter-local bridge: `legacy_body_confidences` and `ProbLogRuleExt.branch_probabilities` already normalize through `resolve_problog_engine_ext(...)`, while SDK/service profile kwargs remain rejected by B. Draft frames C around profile-to-ProbLog rule projection consumption and leaves runtime call-site scope for G0. |
| 2026-05-12 | scoped | Scope frozen | Locked C2 core advanced call-site: `Store.evaluate(..., semantics_profile=...)` becomes the first observable ProbLog profile-consumption path, while SDK/service profile kwargs continue rejecting until E. Locked omitted branch default `1.0`, strict `engine="problog"` consumption, three-carrier conflict rules, adapter-local branch validation, ProbLog-positive / PyReason-negative adapter guards, and exporter normalization through `ProbLogRuleExt`. |

## Decision Notes

- 2026-05-12: C is the first adapter-consumption slice after B. It must distinguish adapter consumption from public runtime call-site design; E still owns SDK/service profile acceptance unless C explicitly expands.
- 2026-05-12: The natural adapter-local target remains `ProbLogRuleExt`. C should normalize `SemanticsProfile.rule_projection.problog` into that internal type rather than making the exporter consume profile dicts.
- 2026-05-12: Legacy bridges cannot be removed at draft time because E has not introduced a durable profile call-site yet. `legacy_body_confidences` and `ProbLogRuleExt` must remain guard-tested unless G0 records a different replacement plan.
- 2026-05-12: C2 was chosen over C1 because an uncalled adapter helper would be hard to validate and would leave B's profile shape unproven in execution. C2 is still narrower than E because SDK/service profile payloads remain rejected.
- 2026-05-12: Omitted `rule_projection.problog` branch targets default to `1.0`, matching existing `ProbLogRuleExt(None)` deterministic semantics. These defaulted values still participate in conflict checks against explicit carriers.
- 2026-05-12: `SemanticsProfile.engine == "problog"` is enforced at ProbLog consumption time, not profile construction time, preserving B's generic profile validation boundary while preventing cross-engine profile misuse.
- 2026-05-12: Branch index range validation remains adapter-local because it requires evaluated rule structure. The core `SemanticsProfile` module continues to validate only generic projection shape.
- 2026-05-12: Adapter import guards split in C: ProbLog is expected to consume `SemanticsProfile`; PyReason remains forbidden from importing or consuming it until D.
