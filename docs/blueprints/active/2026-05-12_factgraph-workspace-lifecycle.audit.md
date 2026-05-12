# Task Blueprint Audit: FactGraph Workspace Lifecycle

- Blueprint: [2026-05-12_factgraph-workspace-lifecycle.md](./2026-05-12_factgraph-workspace-lifecycle.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Blueprint 1 public `Inference`, the inference wire/registry vocabulary slice, and Blueprint 2 authoring asset persistence facade all shipped. Source audit focused on `SDKStore` creation paths, file-backed `Ledger`, `FileAuthoringRegistry`, `FileArtifactSidecar`, `fg.views`, package export, batch `save`, and the absence of an application workspace runtime. Load-bearing constraints: first-slice load still needs Python schema classes; Level 4 workspace scope can include ledger + schema IR + registry assets but should exclude artifacts/views/audit/package; and graph-level `fg.save(...)` must be clearly separate from `_SDKBatchTx.save(...)`. |
| 2026-05-12 | draft-polish | Manifest and constructor boundary refined | Made the `factgraph_workspace.json` v1 shape explicit, including `save_scope`, relative component paths, and timestamps. Locked the unbound `fg.save()` error anchor for G1 tests, clarified when SQLite backup/copy applies, added an idempotent-save invariant, and added Q19 recommending that `path=` stays on `FactGraph.create(...)` only while `from_schema_classes(...)` remains lower-level. |
| 2026-05-12 | scoped | Scope freeze | Locked W1a + W2b + W3a + W4a + W5a + W6a + W7a + W8a + W9a + W10a + W11a + W12a + W13a + W14a + W15a + W16a + W17a + W18a + W19b. Blueprint 3 will add graph-level `path=` on `FactGraph.create(...)`, Level 4 workspace persistence, compact v1 layout and manifest, bound `fg.save(...)`, `FactGraph.load(path, schema_classes=[...])`, application-layer `workspace_runtime`, explicit exclusions for artifacts/views/audit/package, and no `path=` expansion for `from_schema_classes(...)`. |
| 2026-05-12 | red-baseline | G1 tests added | Added `test_factgraph_workspace_lifecycle` with 29 tests covering `FactGraph.create(..., path=...)`, path conflict behavior, bound/unbound `fg.save(...)`, v1 manifest/layout, registry-less save, idempotent save, save-to-other-path, registry sync, `FactGraph.load(...)`, schema mismatch/missing manifest rejection, `kernel.application.workspace_runtime`, artifacts/views/audit exclusions, package boundary, Blueprint 2 persistence preservation, batch `tx.save(...)`, direct runtime, in-memory views, rules inspect, and `from_schema_classes(...)` remaining lower-level. Expected baseline: 20 errors + 9 passing guards. |

## Decision Notes

- 2026-05-12 draft: The central G0 choice is save scope. Level 3 omits authoring assets that Blueprint 2 just made first-class; Level 5 absorbs artifact/view/audit/package lifecycles that are not ready. The draft recommends Level 4.
- 2026-05-12 draft: Class-less `FactGraph.load(path)` is intentionally deferred because current SDK hydration still depends on Python `Entity` classes and ledger metadata stores only `schema_digest`.
- 2026-05-12 draft: Workspace save/load should introduce `kernel.application.workspace_runtime` rather than putting layout/copy logic directly in the SDK shell.
- 2026-05-12 draft polish: `from_schema_classes(...)` should not be expanded with `path=` in the same slice. `FactGraph.create(...)` is now the canonical lifecycle constructor; the older class-first constructor remains explicit lower-level surface.
- 2026-05-12 G0: Level 4 workspace scope is locked as the capstone of the lifecycle/assets sequence. The v1 workspace is for continued editing/running, not package export or artifact archival.
