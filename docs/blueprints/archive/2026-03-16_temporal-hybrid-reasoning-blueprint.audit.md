# Task Blueprint Audit: Temporal Hybrid Reasoning Blueprint

- Blueprint: [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-16 | draft | Blueprint created | Established a discussion entry for temporal semantics, hybrid execution, and future LLM/rule-governance boundaries. |
| 2026-03-18 | draft | Scenario-anchoring child blueprint linked | Added a bridge note to `2026-03-18_ecss-scenario-anchoring.md` so the next concrete step starts from named ECSS/ESA scenarios rather than abstract engine selection. |
| 2026-03-22 | superseded | Successor designated | Replaced by `2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md` as the current stage mother blueprint after the domain-first pivot. |

## Decision Notes

- 2026-03-16
  - 当前先把问题收口为"统一语义内核 + 复合执行器"的讨论入口，不预设单一万能引擎。
  - 将 `PyReason` 视为候选角色之一，而不是默认主内核。
  - 将"时间是否进入 kernel 语义"列为后续首要决策点；在该问题未定前，不启动 runtime temporal contract 实现。

- 2026-03-16 (讨论轮次 2: ESA 回复分析 + 三个核心问题回答)
  - **ESA 回复要点**: ESA 关注 explainability、traceability、certainty estimation；建议场景为 ECSS 标准合规验证和碎片缓解(ESSB-ST-U-007)；入口为 ESA Discovery element；未提及实时轨道计算或时间状态传播。
  - **Staged pipeline 可行性评估**: 技术上可行但存在核心风险 -- Souffle 关系元组到 PyReason 标注图的语义映射无自然对应，跨引擎 provenance 维护成本极高，且无已知成熟先例。ESA 最关注的 traceability 正是此风险的放大器。
  - **Q1 回答 (ECSS 场景)**: 尚无具体条款。这意味着近期 ESA demo 的优先方向缺乏锚点，Implementation Plan step 2 实际处于阻塞状态。已在蓝图 5.4 中记录为高风险。
  - **Q2 回答 (PyReason spike)**: 已有初步实验但未覆盖 annotation 功能（"半生不熟"）。确认 `pyreason-integration-spike-blueprint` 为硬性前置条件，在其完成前 PyReason 架构角色标记为"待定"。
  - **Q3 回答 (可视化)**: 长期目标三者兼备，无固定偏好。建议面向 ESA 近期接触按 audit-log -> proof-tree -> graph-based 排序，理由为与 ESA stated concerns 的对齐程度和现有基础设施的复用度。
  - **待解决**: ECSS 条款级调研（ECSS-M-ST-10, ESSB-ST-U-007）是当前最关键的下一步行动。

- 2026-03-16 (讨论轮次 3: 单引擎 vs. 混合系统的核心概念澄清)
  - **提出的质疑**: "如果需要概率计算，那就一直需要概率计算，一个引擎从头跑到底"——为什么要拆成多引擎？
  - **澄清结果**: 这个直觉在大多数场景下是正确的，应该作为默认选择。
  - **确立设计原则**: "单引擎优先，复合执行是逃生通道而非默认路径"。已写入蓝图 5.1 顶层设计立场。
  - **staged pipeline 的定位修正**: 从"建议探索的架构方向"修正为"当单引擎遇到性能瓶颈或语义能力缺口时的 escape hatch"。
  - **更简单的替代方案**: ProbLog + certainty=1.0 跑全程（确定性部分标注概率为 1.0）。在中小规模规则集下，这种方案的性能开销可能完全不重要。只有在大规模递归闭包导致概率引擎性能不可接受，或者需要单引擎根本不支持的语义（如时间区间状态传播）时，staged pipeline 才值得引入。
  - **影响范围**: 蓝图 5.1 重写（加入设计原则和触发条件），5.3 Q4 追加讨论进展。

- 2026-03-18
  - 在继续进入 `PyReason`、temporal runtime contract 或更强 uncertainty semantics 之前，当前更高优先级的动作是先把 ESA / ECSS 方向锚定到具名 reference scenarios。
  - 新子蓝图 `2026-03-18_ecss-scenario-anchoring.md` 用来收口这一前置问题，避免后续优先级讨论继续漂浮在抽象架构偏好上。
  - `ecss-scenario-anchoring` 的第一轮结论进一步表明：近期更适合先走 `ECSS-M-ST-10` 风格的 compliance-matrix / VCD delivery，而不是先开 `PyReason` 或 temporal runtime semantics。
  - `ecss-vcd-compliance-delivery` 现已实现并归档，说明近期 ECSS-M-ST-10 锚点已经形成一个真实的 offline compliance delivery 路径，而不再只是讨论中的下游入口。

- 2026-03-22
  - The blueprint is no longer the right active parent because the current stage is not “temporal/hybrid exploration” but “ECSS fit + provenance feasibility”.

## Rejected Options

- 2026-03-16
  - **单一万能引擎路径**: 否决。时间、递归、概率来自不同技术传统，当前仓库已是多引擎形态，强行收敛成本过高。
  - **立即做出 PyReason 架构定位**: 推迟。在 annotation 语义未充分探索之前，任何定位都缺乏技术依据。
  - **默认采用 staged pipeline**: 修正。Staged pipeline 不应作为默认架构路径。单引擎执行全程才是默认选择，staged pipeline 仅在遇到性能瓶颈或语义能力缺口时才引入。此前蓝图措辞倾向于将复合执行作为建议探索方向，现修正为 escape hatch 定位。

## Unresolved Risks

- 2026-03-16
  1. 近期 ESA demo 无具体 ECSS 条款锚点，整个近期优先级排序的前提未验证。
  2. PyReason annotation 语义未覆盖，staged pipeline 核心技术风险（元组-标注图映射）无法评估。
  3. 跨引擎 provenance 链维护无已知成熟先例，而这恰是 ESA 最关注的 traceability 的基础。
  4. 可解释性三种可视化方式的资源分配尚未决定，可能影响 ESA 首次接触的演示聚焦度。
