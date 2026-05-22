# Task Blueprint Audit: Native Derivation RuleRef Execution Decision

- Blueprint: [2026-03-19_native-derivation-ruleref-execution-decision.md](./2026-03-19_native-derivation-ruleref-execution-decision.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a dedicated capability-decision slice to answer whether native derivation should formally support `RuleRef` execution semantics, after the recursive-proof blueprint review exposed an execution-level blocker. |
| 2026-03-19 | implemented | Decision recorded | Concluded that native derivation should support `RuleRef` execution semantics, but only as a separate capability line that precedes recursive candidate proof work. |
| 2026-03-19 | implemented | Follow-on blueprint opened | The implementation discussion was split into a new `native where RuleRef execution substrate` draft, with `query + derivation` as the first-round owners rather than derivation alone. |

## Decision Notes

- 2026-03-19
  - Evidence rule: current core runtime rejects `ruleref` in the formal `Store.evaluate(...)` path, but SDK/authoring docs and adjacent blueprints already treat `RuleRef` as part of the intended where-language surface.
- 2026-03-19
  - Position rule: the mismatch is treated as capability drift, not as a stable design boundary that permanently keeps `RuleRef` inside `run_rule` only.
- 2026-03-19
  - Sequencing rule: implementation should not start inside the recursive-proof blueprint. A separate implementation-facing blueprint must first decide how native derivation acquires registry-backed `RuleRef` execution substrate and child support capture.
