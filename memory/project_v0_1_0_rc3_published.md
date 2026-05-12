# v0.1.0-rc.3 Published

- Date: 2026-05-13
- Source milestone: `milestone/rc-0.1.0-rc.3-2026-05-13`
- Source commit: `f49ccc58`
- Release branch: `release/0.1.x`
- Release commit: `e996aa5b`
- Tag: `v0.1.0-rc.3`
- Tag object: `efb44868`
- Tag target: `e996aa5b`

## What Shipped

`v0.1.0-rc.3` packages the post-Track-3 and lifecycle/assets public surface:

- public `Inference` vocabulary in the SDK;
- inference service and registry vocabulary;
- public semantics wrappers and PyReason branch bounds;
- graph-bound authoring asset persistence via `fg.rules.*` and `fg.inferences.*`;
- FactGraph workspace lifecycle via `FactGraph.create(path=...)`, `fg.save(...)`, and `FactGraph.load(...)`.

## Verification

- Final dry-run from current HEAD `f49ccc58` matched the prior dry-run:
  - projection: `361` files;
  - staging verification: `1633` tests OK, `1` skipped;
  - dry-run release commit would have been `e4ffdae9`.
- Live publish verification:
  - `origin/master = f49ccc58`;
  - `origin/milestone/rc-0.1.0-rc.3-2026-05-13 = f49ccc58`;
  - `origin/release/0.1.x = e996aa5b`;
  - `v0.1.0-rc.3^{}` = `e996aa5b`;
  - prior milestone branch refs remain present.

## Release-Surface Fixes

Two release blockers were fixed before publish:

1. `scripts/release_surface_allowlist.txt` still referenced renamed/deleted SDK files:
   - `src/kernel/sdk/docs/03_rules_and_derivations.en.md`;
   - `src/kernel/sdk/dsl/body.py`.
2. The projection omitted modules introduced by post-Track-3 / lifecycle-assets work:
   - `kernel.core.semantics`;
   - `kernel.sdk.semantics`;
   - `kernel.application.authoring_runtime`;
   - `kernel.application.workspace_runtime`.

These fixes are recorded in the archived rc.3 blueprint:
`docs/blueprints/archive/2026-05-13_v0.1.0-rc.3-release.md`.

