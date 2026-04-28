# Task Blueprint Audit: Release Surface Cleanup

- Blueprint: [2026-04-28_release-surface-cleanup.md](./2026-04-28_release-surface-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-28 | draft | Blueprint created | Created after confirming that v0.1 is wheel-RC ready but not repo/source publish ready. The private monorepo tracks `.claude`, `memory`, blueprint/audit history, agent/service/domain packages, third-party code, tools, and other materials outside the kernel-only OSS surface. |

## Decision Notes

1. **Wheel readiness is not source readiness**
   - **Decision**:Treat release-surface cleanup as separate from OS-prep readiness and RC wheel verification.
   - **Why**:`pyproject.toml` can build a kernel-only wheel while the tracked repository still contains non-public materials.
   - **Impact**:No GitHub/source publishing should proceed until projection, allowlist, denylist, and sdist policy are scoped and verified.

2. **Private monorepo should not be made public as-is**
   - **Decision**:The draft assumes a sanitized public projection is required.
   - **Why**:Tracked source includes operational memory, Claude workflow files, internal blueprints, agent/service/domain code, third-party/vendor material, and benchmark artifacts.
   - **Impact**:Implementation should favor a separate public `factpy-kernel` projection over making the private monorepo public.
