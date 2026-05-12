# Task Blueprint Audit: FactGraph Workspace Lifecycle

- Blueprint: [2026-05-12_factgraph-workspace-lifecycle.md](./2026-05-12_factgraph-workspace-lifecycle.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Blueprint 1 public `Inference`, the inference wire/registry vocabulary slice, and Blueprint 2 authoring asset persistence facade all shipped. Source audit focused on `SDKStore` creation paths, file-backed `Ledger`, `FileAuthoringRegistry`, `FileArtifactSidecar`, `fg.views`, package export, batch `save`, and the absence of an application workspace runtime. Load-bearing constraints: first-slice load still needs Python schema classes; Level 4 workspace scope can include ledger + schema IR + registry assets but should exclude artifacts/views/audit/package; and graph-level `fg.save(...)` must be clearly separate from `_SDKBatchTx.save(...)`. |

## Decision Notes

- 2026-05-12 draft: The central G0 choice is save scope. Level 3 omits authoring assets that Blueprint 2 just made first-class; Level 5 absorbs artifact/view/audit/package lifecycles that are not ready. The draft recommends Level 4.
- 2026-05-12 draft: Class-less `FactGraph.load(path)` is intentionally deferred because current SDK hydration still depends on Python `Entity` classes and ledger metadata stores only `schema_digest`.
- 2026-05-12 draft: Workspace save/load should introduce `kernel.application.workspace_runtime` rather than putting layout/copy logic directly in the SDK shell.
