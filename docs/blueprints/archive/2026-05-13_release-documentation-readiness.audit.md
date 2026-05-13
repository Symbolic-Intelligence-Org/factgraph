# Task Blueprint Audit: Release Documentation Readiness

- Blueprint: [2026-05-13_release-documentation-readiness.md](./2026-05-13_release-documentation-readiness.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Release-facing docs audit found README, examples README, service docs, and OpenAPI drift after rc.3, schema mutation, schema field-add, and confidence cleanup. |
| 2026-05-13 | draft | Source audit expanded | Verified current SDK export/namespace count (`__all__` 41; 10 top-level namespaces) and added candidate stale-grep gates for G0 scope freeze. |
| 2026-05-13 | scoped | G0 scope frozen | Locked release-docs cleanup scope to README, examples README, service docs, OpenAPI scope wording, and focused stale-grep gates; no code or release-ref changes. |
| 2026-05-13 | scoped | README/examples updated | Refreshed root README around `FactGraph.create`, `Inference`, 10 SDK namespaces, and examples README around current SDK shells. |
| 2026-05-13 | scoped | Service/OpenAPI updated | Removed stale confidence echo from service examples, corrected runtime DTO title, and removed extraction route/tag/components from kernel OpenAPI. |
| 2026-05-13 | implemented | G4 close-out | Filled Outcome / Deviations, verified stale-grep gate, OpenAPI parse/ref check, and `git diff --check`; ready to archive. |

## Decision Notes

- 2026-05-13: Treat this as release documentation readiness, not a product
  redesign. No code behavior, release refs, or public API changes are in scope.
- 2026-05-13: OpenAPI field-schema completion remains out of scope unless a
  focused follow-up is explicitly created; this slice may only correct current
  scope wording, stale routes/tags, and doc paths.
- 2026-05-13: `derivation_id` / `derivation_version` may remain in release
  docs only when explicitly framed as candidate/internal substrate fields.
