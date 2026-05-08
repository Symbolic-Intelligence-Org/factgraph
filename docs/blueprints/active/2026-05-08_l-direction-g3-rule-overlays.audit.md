# L Direction G3 — Rule Overlay SDK Shells Audit Log

| Date | Event | Notes |
|---|---|---|
| 2026-05-08 | Draft seeded | Created G3 draft blueprint on `codex/v0.1-l-g3-rule-overlays-2026-05-08` after G2 publish. Captures Round 8 G3 mismatch, G1/G4/G2 inherited constraints, and nine Step 0 questions. No implementation scoped yet. |

## Decision Notes

- G3 starts from the G2 combined baseline: `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-2026-05-08` @ `d658390`.
- The draft deliberately does not answer §5.1-§5.9. Per `feedback_iterative_gap_design`, each Step 0 decision needs a source-grounded falsifier pass before `scoped`.
- Core tension to resolve: A preserves three rule-overlay families under `#3`, while Round 8 flags raw `RuleSpec` exposure and three-sister SDK naming as SDK-layer mismatch.
