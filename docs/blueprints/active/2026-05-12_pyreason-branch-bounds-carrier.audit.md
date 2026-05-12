# Task Blueprint Audit: Track 3-post PyReason Branch Bounds Carrier

- Blueprint: [2026-05-12_pyreason-branch-bounds-carrier.md](./2026-05-12_pyreason-branch-bounds-carrier.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Track 2 publish. Source audit found that Track 2 exposes `PyReasonSemantics` without `branch_bounds`, SDK lowering can already resolve branch ids while SDK objects are in hand, `PyReasonRuleExt` has only global `head_bound`, and `where_compile.py` already emits one PyReason rule per branch using `_b{branch_idx}` names. |
| 2026-05-12 | scoped | Scope freeze | Locked D1-D14. Track 3-post adds public `PyReasonSemantics.branch_bounds`, resolves explicit/fallback branch ids at the SDK boundary, lowers to canonical `rule_projection.pyreason` `branch:{index}` interval entries, materializes an index-keyed `PyReasonRuleExt.branch_head_bounds` carrier, and compiles per-branch head annotations while preserving service/compiled canonical boundaries. |
| 2026-05-12 | g1-red | Red + guard baseline | Added `test_pyreason_branch_bounds_carrier.py` and inverted the Track 2 `branch_bounds` guard. New Track 3-post suite runs 16 tests with expected 11 errors + 4 failures + 1 guard pass; Track 2 suite has 1 expected error from the inverted guard; Track 1+B/C/D/E preservation suite remains 103 OK. |

## Decision Notes

- 2026-05-12 draft: Track 3-post is the final remaining slice in the post-Track-3 3-track plan. It should stay focused on PyReason `branch_bounds`, the internal per-branch head-bound carrier, and branch-specific PyReason head annotation compilation.
- 2026-05-12 draft: The load-bearing G0 questions are public field name, public branch-key namespace, internal carrier shape, canonical profile target, and global-vs-branch head-bound conflict rules.
- 2026-05-12 draft: The draft recommendation is to keep the Track 2 lowering pattern: `PyReasonSemantics.branch_bounds` resolves branch ids at the SDK boundary, lowers to canonical `SemanticsProfile.rule_projection.pyreason`, and adapter consumption materializes an index-keyed `PyReasonRuleExt` carrier.
- 2026-05-12 G0: D1-D4 lock the core shape: public `branch_bounds`, explicit/fallback id keys, index-keyed internal carrier, and canonical `target="branch:{index}", kind="interval"`.
- 2026-05-12 G0: D5-D7 lock semantics: branch bounds override global `head_bound`, adapter validates indexes against rule context, and single-branch `b0` remains valid.
- 2026-05-12 G0: D8-D14 preserve Track 2 boundaries, require wrapper/profile equivalence, lock rejection anchors, treat empty dict as no-op, invert Track 2's branch_bounds rejection guard, and commit docs/memory updates at G4.
