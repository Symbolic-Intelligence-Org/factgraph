# Mother Blueprint Audit: Multi-Engine Semantic Delivery

- Blueprint: [2026-03-27_multi-engine-semantic-delivery.md](./2026-03-27_multi-engine-semantic-delivery.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | draft | Blueprint created | Core transition: "多引擎可以跑" → "多引擎语义被 framework 正式消费和交付". Supersedes 2026-03-22 mother blueprint. 5 direction lines (L1/L2/L3a/L3b/L4), 3 decision gates. |
| 2026-03-27 | draft | 3 P1/P2 fixes | (1) L4 engine_options removed from mainline, moved to future design branch — eliminates contradiction with Gate 3. (2) L3 split into L3a (decision-only) + L3b (implementation) — D7 supersede now requires explicit decision blueprint, consistent with §7. (3) L5 renamed to "ProbLog semantic-delivery parity" — ProbLog already has basic evaluate, goal is annotation/provenance/consumer parity, not "make it run". |
| 2026-03-27 | draft | Framing clarification | §1 新增"关于事实语义属性的澄清"：probability/bound/active_from 是事实语义属性，不是引擎运行参数。Namespace 中的引擎名记录计算来源，不意味着这些值"只属于"该引擎。框架分层不变，叙事精确化。 |
| 2026-03-27 | scoped | 3 P2/P3 fixes + status升级 | Gate 1 失败分支改为 L2/L3a/L3b/L4。归档蓝图数修正为 101（非 audit）。Audit log 方向线编号同步为 L1/L2/L3a/L3b/L4。 |
| 2026-03-27 | scoped | engine_options branch opened | Added explicit link to `2026-03-27_engine-options-runtime-dispatch-decision.md`. Clarifies again that engine_options is a future design branch, not mainline L4. |
