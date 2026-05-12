# Task Blueprint Audit: Track 3-post PyReason Branch Bounds Carrier

- Blueprint: [2026-05-12_pyreason-branch-bounds-carrier.md](./2026-05-12_pyreason-branch-bounds-carrier.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Track 2 publish. Source audit found that Track 2 exposes `PyReasonSemantics` without `branch_bounds`, SDK lowering can already resolve branch ids while SDK objects are in hand, `PyReasonRuleExt` has only global `head_bound`, and `where_compile.py` already emits one PyReason rule per branch using `_b{branch_idx}` names. |

## Decision Notes

- 2026-05-12 draft: Track 3-post is the final remaining slice in the post-Track-3 3-track plan. It should stay focused on PyReason `branch_bounds`, the internal per-branch head-bound carrier, and branch-specific PyReason head annotation compilation.
- 2026-05-12 draft: The load-bearing G0 questions are public field name, public branch-key namespace, internal carrier shape, canonical profile target, and global-vs-branch head-bound conflict rules.
- 2026-05-12 draft: The draft recommendation is to keep the Track 2 lowering pattern: `PyReasonSemantics.branch_bounds` resolves branch ids at the SDK boundary, lowers to canonical `SemanticsProfile.rule_projection.pyreason`, and adapter consumption materializes an index-keyed `PyReasonRuleExt` carrier.
