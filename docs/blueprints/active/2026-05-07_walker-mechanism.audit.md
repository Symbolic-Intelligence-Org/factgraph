# Task Blueprint Audit: Walker Mechanism

- Blueprint: [2026-05-07_walker-mechanism.md](2026-05-07_walker-mechanism.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-07 | draft | Blueprint created | Drafted from `post-routemap-direction-selection-input` bundle (committed at `177b116` on `v0.1-public-surface-2026-05-06`). Primary design sketch: [40_walker-mechanism-design-sketch.md](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md). Contract test sketch: [40_ §6](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md). Handoff checklist: [50_migration-path.md §8](../../references/working/post-routemap-direction-selection-input/50_migration-path.md). Scope: B1 IR walker + frozen tuple wrapper + B2 evidence cross-reference + per-DTO wrapper views (`SupportArtifactView` / `ProofFrameView` / `ProofFrameDiffView`); B3 audit / store stream walker is reserved future-only (NOT B1/B2 acceptance). Honors 11 walker invariants `#7`-`#19` operationalized in 40_ §4. Parallel-safe sibling: [2026-05-07_application-ergonomic-helpers-extension.md](2026-05-07_application-ergonomic-helpers-extension.md) per [50_ §5](../../references/working/post-routemap-direction-selection-input/50_migration-path.md). |

## Decision Notes

- Draft retains Step 0 unknowns for module split, error hierarchy layout, final `ProofFrameDiffView` method names, and fixture layout. No code implementation has started.
