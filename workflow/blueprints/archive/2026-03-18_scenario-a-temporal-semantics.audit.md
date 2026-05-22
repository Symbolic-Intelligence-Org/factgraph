# Task Blueprint Audit: Scenario A Temporal Semantics

- Blueprint: [2026-03-18_scenario-a-temporal-semantics.md](./2026-03-18_scenario-a-temporal-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Scenario A narrowed to temporal semantics first; uncertainty remains a sibling follow-up. |
| 2026-03-18 | draft | Reference stance recorded | Rainbird comparison is kept as external delivery/proof-shape rationale only, not as implementation truth or target contract. |
| 2026-03-18 | scoped | Scope freeze | Adopted L1/L2/L3: temporal predicates + existing comparisons, `pred_witnesses`-first anchor path, and `factpy_kernel.ecss.temporal` as preset owner. |
| 2026-03-18 | implemented | Shared preset landed | Added `factpy_kernel.ecss.temporal` and targeted regressions for schema helper, deadline/window checks, and helper-rule interval relation. |
| 2026-03-18 | implemented | Module docs synced | Updated `ecss` / `authoring` / `sdk` / `core` / `service` docs to record the T1 scalar-time and explain-anchor contract. |
| 2026-03-18 | archive | Blueprint archived | Scope satisfied; first-round Scenario A T1 slice closed without expanding into uncertainty semantics or adapter-specific runtime changes. |

## Decision Notes

- `Scenario A` 的第一条子蓝图先聚焦 `temporal semantics`，不与 `uncertainty-and-confidence` 合并。
- 当前 adopted narrowing 是 `T1 explicit temporal checks`，不回滚到 `temporal_view`，也不直接跳到 `T2 state propagation`。
- `docs/references/working/cross-domain-compliance-framing.md` 中 ESSB 阈值只用于 scenario pressure 讨论，不作为标准原文依据。
- `T1` 的 scalar time convention 已冻结：使用 schema/protocol tag `"time"` 的 `int` epoch 纳秒值，不复用 `valid_from/valid_to` 的 ISO 8601 读视图口径。
