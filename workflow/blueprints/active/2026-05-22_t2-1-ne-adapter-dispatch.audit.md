# Task Blueprint Audit: T2.1 — `ne` adapter dispatch gap close

- Status: implemented
- Created: 2026-05-22
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-22_t2-1-ne-adapter-dispatch.md](./2026-05-22_t2-1-ne-adapter-dispatch.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
- Blueprint: [2026-05-22_t2-1-ne-adapter-dispatch.md](./2026-05-22_t2-1-ne-adapter-dispatch.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | Drafted from shipped adapter reads requested by user: Souffle `eq`/comparison dispatch, ProbLog `eq` dispatch, and core `_CMP_OPS`/validator semantics. |
| 2026-05-22 | review-tightening | Step 4.2 cross-flip review applied | P1 ProbLog `\=` term-inequality semantics documented; P2 Current Context file:line citations added; P3 Souffle variable example corrected to `V0`. |
| 2026-05-23 | scoped | Scope anchored | Status changed `draft` → `scoped`; implementation must fork an independent impl branch from this commit. |
| 2026-05-23 | implemented | Implementation closed | Commit `575d48d7` landed adapter `ne` dispatch; reviewer pass found 0 P1 findings. Blueprint marked implemented with import-cycle baseline note. |

## Decision Notes

### 2026-05-22 — Initial scope lock

- T2.1 is adapter-only.
- Core AST already includes `ne`; this slice does not change core atom shape.
- Core validator treats `ne` as filter-only, so Souffle implementation must follow ordering-comparison dataflow, not `eq` binding dataflow.
- SDK DSL non-eq AttrRef authoring remains deferred per T1.2 closure; T2.1 must not re-open that boundary.
- PyReason support remains out of scope per track plan.

### 2026-05-22 — Step 4.2 review findings applied

- P1 Required: ProbLog `\=` is term inequality / cannot-unify, not arithmetic inequality. Blueprint §5.4 + §6 now state this explicitly and §7 requires nested `not` export coverage.
- P2 Required: §4 Current Context now includes exact shipped file:line references for core AST, core validator, Souffle dispatch sites, and ProbLog dispatch / recursive `not`.
- P3 Minor: §7 Souffle output example now uses `V0` rather than `C0`, matching shipped `_symbol_for_var` output.
- Calibration note: review suggested `where_ast.py:33` for `_CMP_OPS`, but current shipped file has `_CMP_OPS` at `where_ast.py:95`; the blueprint uses the current shipped line.
