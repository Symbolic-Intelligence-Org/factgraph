# Task Blueprint Audit: T2.1 — `ne` adapter dispatch gap close

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
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

## Decision Notes

### 2026-05-22 — Initial scope lock

- T2.1 is adapter-only.
- Core AST already includes `ne`; this slice does not change core atom shape.
- Core validator treats `ne` as filter-only, so Souffle implementation must follow ordering-comparison dataflow, not `eq` binding dataflow.
- SDK DSL non-eq AttrRef authoring remains deferred per T1.2 closure; T2.1 must not re-open that boundary.
- PyReason support remains out of scope per track plan.
