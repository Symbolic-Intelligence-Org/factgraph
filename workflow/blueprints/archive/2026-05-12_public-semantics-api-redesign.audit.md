# Task Blueprint Audit: Track 2 Public Semantics API Redesign

- Blueprint: [2026-05-12_public-semantics-api-redesign.md](./2026-05-12_public-semantics-api-redesign.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Track 3 and Track 1 publish. Source audit found that SDK can resolve branch ids only while SDK `Rule` / `Derivation` objects are still in hand; service and compiled paths currently carry only canonical `SemanticsProfile`. PyReason per-branch head bounds are mechanically feasible via per-branch rule compilation but not yet represented by `PyReasonRuleExt`. |
| 2026-05-12 | scoped | Scope freeze | Locked D1-D15. Track 2 is a bounded SDK public-wrapper slice: add `ProbLogSemantics` / `PyReasonSemantics`, derive engine from semantics objects, preserve public `SemanticsProfile`, keep service/compiled paths canonical, and defer PyReason `branch_bounds` carrier reshape to Track 3-post. |
| 2026-05-12 | g1-red | Red + guard baseline | Added `test_public_semantics_api_redesign.py`. New Track 2 suite currently runs 17 tests with expected 13 errors + 2 failures + 2 guard passes: wrapper classes/exports/engine derivation/inspection are absent, service light-shape rejection text is not yet locked, while native default and compiled `SemanticsProfile` guards pass. Track 1 + B/C/D/E preservation suite remains 103 OK. |
| 2026-05-12 | implemented | G2 implementation | Added SDK-local `ProbLogSemantics` / `PyReasonSemantics`, SDK lowering to canonical `SemanticsProfile`, engine auto-derivation, wrapper inspection preview, compiled/service/shell boundary rejections, and SDK `__all__` invariant migration. Track 2 suite 17 OK, Track 1+B/C/D/E preservation 103 OK, SDK `__all__` invariant suite 81 OK. |
| 2026-05-12 | docs | G3 docs sync | Documented `ProbLogSemantics` / `PyReasonSemantics` as the preferred SDK public wrappers, preserved `SemanticsProfile` as advanced/canonical, kept service and compiled paths canonical, and recorded that PyReason `branch_bounds` remains Track 3-post scope. |
| 2026-05-12 | implemented | Closed and archived | Filled §10 outcome/deviations, marked Track 2 implemented, and archived the blueprint pair. Track 2 completes the public wrapper layer; Track 3-post PyReason `branch_bounds` carrier reshape is the next available semantics slice. |

## Decision Notes

- 2026-05-12 draft: Track 2 starts from the post-Track-3 design-point doc plus Track 1 archive. The key design tension is whether Track 2 is a thin SDK wrapper layer over `SemanticsProfile`, or whether it absorbs the larger PyReason branch-bound carrier reshape currently identified as Track 3-post.

- 2026-05-12 G0: D1/D12 place new wrappers in SDK-local `src/kernel/sdk/semantics.py`; they are ergonomic public wrappers over canonical `SemanticsProfile`, not core protocol objects.
- 2026-05-12 G0: D2/D11 keep `SemanticsProfile` public and accepted to avoid churn on Track 3 / E just-published API.
- 2026-05-12 G0: D3 preserves Track 1 P1a inspect-only branch identity; branch-id maps are resolved only while SDK `Rule` / `Derivation` objects are available.
- 2026-05-12 G0: D4 resolves the duplicate-engine UX by deriving engine from wrappers and `SemanticsProfile`; explicit `engine=` remains a mismatch guard.
- 2026-05-12 G0: D6 selects T6a, not T6c. Track 2 will not add PyReason `branch_bounds`; Track 3-post owns the per-branch carrier and compiler change.
- 2026-05-12 G0: D7/D8 keep service and compiled paths on canonical `SemanticsProfile`, because neither path currently carries branch ids.
- 2026-05-12 G0: D13-D15 lock rejection anchors, SDK `__all__` migration, and the Track 3-post forward commitment so G1/G4 can verify the boundary.
