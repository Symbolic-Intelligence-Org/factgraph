# Task Blueprint Audit: Candidate Evidence Tree Salience / Impact

- Blueprint: [2026-03-20_candidate-evidence-tree-salience-impact.md](./2026-03-20_candidate-evidence-tree-salience-impact.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Opened a narrow salience / impact draft focused on owner-layer and compute-time questions before any carrier or annotation expansion. |
| 2026-03-20 | scoped | Freeze confirmed | 4 freeze decisions: (1) owner = annotation/value-semantics; (2) compute-time = query-time/read-time for salience itself, input source independent; (3) blocked on certainty/weight vocabulary; (4) no implementation slice, doc-and-contract freeze only. Native/degraded coverage deferred. |

## Decision Notes

- 2026-03-20: 本轮先不把 salience / impact 直接写成 carrier 扩展字段；要先冻结它是否本来就不属于 carrier。
- 2026-03-20: Rainbird comparison 只用于强调 salience 是真实的 consumer-facing gap，不直接采纳其 certainty semantics。
- 2026-03-20: `missing optional conditions` 明确排除在本轮之外，避免与 salience / impact 的归属问题缠绕。
- 2026-03-20: 这条线的第一优先问题不是 UI，而是 owner layer / compute-time / input truth。
- 2026-03-20: **Freeze: owner layer** — salience / impact 属于 annotation / value-semantics 层，不属于 proof carrier。
- 2026-03-20: **Freeze: compute-time** — salience 本身在 query-time / read-time 计算。这不约束 certainty/weight 输入的来源（输入可在 evaluate-time capture 或 query-time 派生）。
- 2026-03-20: **Freeze: input prerequisite** — 现有 tree/summary 结构信号不足以产出有意义的 salience。Blocked on certainty / weight vocabulary。"Structural salience proxy" 被否决——它只会是 summary 的 rephrasing。
- 2026-03-20: **Freeze: native/degraded** — deferred until prerequisites exist。Invariant: degraded 不应伪装成 native impact breakdown。
- 2026-03-20: **Freeze: output** — 不产出 salience surface 或 implementation slice。本蓝图作为 decision-only archive 收归。
