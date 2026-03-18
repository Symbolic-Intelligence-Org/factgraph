# Task Blueprint Audit: Scenario A Composite Reference Check

- Blueprint: [2026-03-18_scenario-a-composite-reference-check.md](./2026-03-18_scenario-a-composite-reference-check.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Composite check is framed as an integration/validation slice over existing temporal + uncertainty contracts. |
| 2026-03-18 | scoped | Scope freeze | Composite rule uses shared `assessment_ref` join by default; audit package parity is in-scope; substrate sufficiency judgment is now part of acceptance. |
| 2026-03-18 | implemented | Composite regression landed | Added a live/audit parity regression covering shared `assessment_ref`, seven predicates, four comparisons, and assertion-page drill-down. |
| 2026-03-18 | implemented | Sufficiency judgment recorded | Current `T1 + U1` substrate is sufficient for a first-round Scenario A reference check; no immediate `T2` escalation is required. |
| 2026-03-18 | archive | Blueprint archived | Scope satisfied without changing runtime contracts or adding new delivery surfaces. |

## Decision Notes

- 本切片默认不新增语义，先验证 `T1 temporal + U1 uncertainty` 的组合是否已经足够支撑 Scenario A reference check。
- Rainbird 在本切片中只作为 evidence-chain / proof-entry 形状参考，不作为 certainty model 或 API target。
- 第一轮 composite scenario 默认假设 temporal 与 uncertainty facts 共享同一个 `assessment_ref`；若现实数据建模不满足此假设，再通过显式 join predicate 桥接。
- 组合验证结果表明：现有 where 比较链、trace carrier、audit package 已足够承载 first-round Scenario A conjunction；下一步更自然的入口是 delivery/demo 或更具体的数据建模，而不是立刻进入 `T2`。
