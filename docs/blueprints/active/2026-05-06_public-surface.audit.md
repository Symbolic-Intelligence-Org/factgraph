# Task Blueprint Audit: Public Surface Decision(Batch 8)

- Blueprint: [2026-05-06_public-surface.md](./2026-05-06_public-surface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 8 draft opened on `v0.1-public-surface-2026-05-06` off Batch 7 hardening final `3baf4ac`. Scope is deliberately Step-0-first:the draft does not assume SDK shell,service routes,release projection,and README updates are one capability;Path B no-expand close-out and Path C split remain live options. Release branches `v0.1-oss-prep` and `master` remain frozen. |

## Decision Notes

- Batch 8 is the final Round Story Completion Plan batch and must treat public exposure as a product decision,not a mechanical export of all internal application/audit capabilities.
- The draft carries forward the application-first invariant:SDK/service wrappers may delegate to application/audit,but must not create new runtime substrate.
- The draft also carries forward release-surface cleanup:public source projection remains default-deny and no publish/release operation happens without explicit user authorization.

