# Task Blueprint Audit: Scenario A Uncertainty And Confidence

- Blueprint: [2026-03-18_scenario-a-uncertainty-and-confidence.md](./2026-03-18_scenario-a-uncertainty-and-confidence.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | scoped | Blueprint created | Scenario A uncertainty first slice frozen as threshold-bearing probability lane, not a global confidence redesign. |
| 2026-03-18 | scoped | Scope freeze | Adopted U1/U2/U3: int `ppm` scalar, `factpy_kernel.ecss.uncertainty` owner, and existing explain carrier reuse. |
| 2026-03-18 | implemented | Shared preset landed | Added `factpy_kernel.ecss.uncertainty` plus targeted regressions for schema helper and threshold compare trace anchors. |
| 2026-03-18 | implemented | Module docs synced | Updated `ecss` / `authoring` / `sdk` / `core` / `service` docs to record lane separation and `ppm` scalar convention. |
| 2026-03-18 | archive | Blueprint archived | Scope satisfied without expanding into global confidence redesign or float comparison runtime changes. |

## Decision Notes

- 第一轮 uncertainty 切片不改 `meta.confidence` / `CandidateSet.confidence` 稳定语义。
- 为了复用现有比较链，threshold probability 统一用 `int ppm` 表达，而不是 float compare。
- explain / audit 继续走 `pred_witnesses` + `non_fact_steps.details.binding`，不引入 uncertainty 专用 trace schema。
