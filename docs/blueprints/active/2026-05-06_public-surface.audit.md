# Task Blueprint Audit: Public Surface Decision(Batch 8)

- Blueprint: [2026-05-06_public-surface.md](./2026-05-06_public-surface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 8 draft opened on `v0.1-public-surface-2026-05-06` off Batch 7 hardening final `3baf4ac`. Scope is deliberately Step-0-first:the draft does not assume SDK shell,service routes,release projection,and README updates are one capability;Path B no-expand close-out and Path C split remain live options. Release branches `v0.1-oss-prep` and `master` remain frozen. |
| 2026-05-06 | draft | Step 0.A spike completed | Answered 18 falsifiers from current SDK/application/audit/release-projection sources. Decision:Path A narrowed to docs/checklist first slice(A1 + A4),with no SDK/service code,application/audit protocol drift,release branch action,or projection expansion by default. Broad SDK shell,service routes,example projection add-back,and release projection changes are deferred unless Step 0.B finds the docs/checklist close-out impossible without a scoped change. |
| 2026-05-06 | draft | Step 0.B spike completed | Froze Batch 8 public boundary implementation as docs/checklist only. Public tiers:product public=`kernel.sdk`;advanced importable=`kernel.application` + `kernel.audit`;internal/deferred=service/agent/domains,deferred Batch 6/7 families,SDK shells,service routes,example projection add-back,and Batch 4 `rule_refs` hardening. Scoped files are README/README.en,selected SDK/application/audit docs,the active release-candidate checklist,and this blueprint/audit. Release projection allowlist,release scripts,`pyproject.toml`,SDK/application/audit Python code,service,agent,and domains are all out of scope. |
| 2026-05-06 | scoped | Scope freeze | Status changed from `draft` to `scoped` after Step 0.A/0.B froze a docs/checklist-only first slice. Implementation may edit only the scoped docs/checklist files listed in §5.5.2. |

## Decision Notes

- Batch 8 is the final Round Story Completion Plan batch and must treat public exposure as a product decision,not a mechanical export of all internal application/audit capabilities.
- The draft carries forward the application-first invariant:SDK/service wrappers may delegate to application/audit,but must not create new runtime substrate.
- The draft also carries forward release-surface cleanup:public source projection remains default-deny and no publish/release operation happens without explicit user authorization.
- Step 0.A selected no-code public boundary work as the first slice because the current source already exposes `kernel.application` and `kernel.audit` as importable advanced layers,while SDK docs explicitly reserve `kernel.sdk` for ergonomic product surface and warn against turning application internals into SDK public API.
- Step 0.B intentionally avoids release allowlist changes. Batch 8 should close the routemap by clarifying the public boundary of files already projected,not by expanding the projection in the terminal batch.
