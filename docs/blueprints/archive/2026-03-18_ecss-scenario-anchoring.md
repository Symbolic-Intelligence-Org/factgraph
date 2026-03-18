# Task Blueprint: ECSS Scenario Anchoring

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_ecss-scenario-anchoring.audit.md](./2026-03-18_ecss-scenario-anchoring.audit.md)

## 1. Problem

`temporal-hybrid-reasoning` 当前最大的现实阻塞，不是某个 adapter 还没实现，而是 **缺少可验证的具名场景锚点**。

目前蓝图中已经多次把 ESA / ECSS 合规验证、碎片缓解、explainability、traceability、certainty estimation 当作潜在方向，但这些讨论仍停留在主题级别，没有落到：

- 具体是哪一条 ECSS / ESSB 要求；
- 该要求需要什么输入证据；
- 需要的推理形态更接近：
  - audit-log / requirement matrix
  - proof-tree / explain chain
  - graph-based dependency view
- 当前系统基座是否已经足够支撑一个最小演示

在缺少这一层锚点时，后续几个技术讨论都会漂浮：

- `temporal-semantics` 是否真的优先；
- `PyReason` 是否值得进入下一轮 spike；
- `ProbLog` 的 `confidence` 语义要不要继续扩；
- explainability 第二阶段是 proof-tree 还是 evidence-view；
- service/application 的对外交付形态该先做哪一种

因此，这个切片的目标不是先做新引擎，而是先选出 1 到 2 个足够具体、足够可评估的 ECSS/ESA reference scenarios，作为下一阶段 architecture work 的共同坐标系。

## 2. Goals

- 把“ESA / ECSS 方向”从抽象主题，收口成 1 到 2 个具名 reference scenarios。
- 为每个候选 scenario 明确：
  - requirement / question 的粒度
  - 需要的输入证据类型
  - 需要的推理能力
  - 需要的 explain / audit 交付形态
  - 与当前实现基座的契合度
- 给 `temporal-hybrid-reasoning` 提供一个可落地的近期优先级锚点：
  - 哪个 scenario 适合先走 audit-log / requirement-matrix
  - 哪个 scenario 真正需要 temporal semantics 或更强引擎
- 明确当前 explainability substrate 在这些 scenarios 上能支撑到哪里，哪些能力仍是后续阶段工作。

## 3. Non-goals

- 不在本蓝图中直接实现新的 temporal runtime contract。
- 不在本蓝图中直接决定 `PyReason`、`Souffle`、`ProbLog` 的长期角色。
- 不在本蓝图中产出正式领域本体、ECSS 全量知识库或完整合规模型。
- 不把 unsourced working note 写成 ECSS/ESA 事实。
- 不把 scenario anchoring 直接扩成市场/产品路线图。

## 4. Current Context

- 当前架构与文档基线已经支持一部分“规则推理 + traceability + audit”能力：
  - append-only ledger
  - derivation / rule evaluation
  - audit package export
  - unified `explain_ref`
  - engine degraded explain semantics
- 当前明确不支持的一些 runtime 能力：
  - `temporal_view` 不再进入 runtime derivation/rule/service 链路
  - temporal write semantics 仍未进入 rule/derivation head contract
  - engine true witness / proof-tree 仍是后续切口
- `temporal-hybrid-reasoning` 已经明确记录：
  - ECSS-M-ST-10 与 ESSB-ST-U-007 是候选锚点
  - 但条款级落点尚未完成
  - 在缺少此锚点前，后续优先级判断带有明显不确定性
- `runtime-traceability-explainability` 第一阶段已完成：
  - 这使得 “audit-log-first / proof-tree-next” 的评估现在可以建立在真实 substrate 上，而不只是空想

## 5. Proposed Shape

### 5.1 First-round Output

本切片第一轮不做代码实现，目标输出是一份 **scenario comparison memo**，至少覆盖 2 个候选：

1. `ECSS-M-ST-10` 风格的设计评审 / requirement-compliance scenario
2. `ESSB-ST-U-007` 风格的碎片缓解 / debris-mitigation scenario

每个 scenario 至少要回答：

- 目标问题是什么
- 输入证据是什么
- 输出是：
  - binary compliance
  - scored certainty
  - ranked evidence
  - 还是 proof/explain artifact
- 当前基座是否已经足够支撑一个最小演示
- 若不够，缺口属于：
  - data modeling
  - temporal semantics
  - uncertainty semantics
  - engine capability
  - explain/delivery shape

### 5.2 Comparison Dimensions

候选 scenarios 至少按以下维度比较：

1. `data readiness`
   - 输入是否能用当前 facts/meta/schema 形状表示
2. `temporal pressure`
   - 是否真的需要 point/interval/state semantics
3. `uncertainty pressure`
   - 是否真的需要概率/置信度而不是纯规则判定
4. `traceability pressure`
   - 是否必须有 audit-log / proof-tree / evidence chain
5. `delivery pressure`
   - 面向 ESA 的首轮消费形态更像 report、matrix、API explain，还是 graph UI
6. `current-fit`
   - 与当前 substrate 的契合度

authority note:

- `docs/references/working/cross-domain-compliance-framing.md` 只是一份 **non-authoritative internal notes**。
- 因此，本节若引用其中整理的 ESSB-ST-U-007 数值（例如 `Pc 1x10^-4`、`5 年窗口`、`>=90%` 成功率），这些数字只用于讨论 **scenario pressure**，不构成对标准原文的核实或解释。

### 5.3 Scenario Comparison Memo

#### Scenario A: ESSB-ST-U-007 Debris-Mitigation Compliance

目标问题：

- 给定一个在轨任务（卫星系统），验证其是否满足 ESSB-ST-U-007 风格的碎片缓解义务，至少覆盖以下三类要求：
  1. 近地轨道处置时限
  2. conjunction 碰撞概率阈值监控
  3. 处置成功概率阈值

说明：

- 当前以下阈值和窗口来自 `cross-domain-compliance-framing.md` 的 working-note 摘录，而非已核实的标准原文：
  - `Pc 1x10^-4`
  - `5 年`处置窗口
  - `>=90%` 处置成功率

输入证据：

- 任务参数（轨道高度、倾角、剩余推进剂等）
- CDM / conjunction 事件流
- 可靠性分析报告或成功率估计
- 历史处置操作记录

输出形态：

- 逐条款合规状态（binary + uncertainty summary）
- 每条不符合项的风险/证据链
- 必要时的 waiver 支撑材料

比较评估：

| 维度 | 状态 | 说明 |
| --- | --- | --- |
| data readiness | 中 | 轨道参数、CDM、成功率估计都可建模，但需要额外 schema 与样例数据 |
| temporal pressure | 高 | `5 年窗口` 和 conjunction 序列都是真实时间语义，且更接近 point/interval reasoning |
| uncertainty pressure | 高 | `Pc` 阈值、处置成功率都要求比当前窄 `confidence` 更强的口径 |
| traceability pressure | 高需求，基座已有一部分 | audit-log / explain substrate 已有，但尚不等于 requirement-scoped debris evidence chain |
| delivery pressure | 中 | 更像 SDMR / risk evidence package，而非单纯 API |
| current-fit | 低到中 | traceability substrate 已具备，但 temporal + uncertainty 是当前硬缺口 |

缺口分类：

- temporal semantics
- uncertainty semantics
- data modeling
- engine capability

#### Scenario B: ECSS-M-ST-10 VCD / Design-Review Compliance Matrix

目标问题：

- 给定一个设计评审（如 PDR/CDR），自动生成或验证一份 ECSS-M-ST-10 风格的 Verification Control Document / compliance matrix，至少覆盖：
  1. 每条 requirement 是否已分配验证方法（Test / Analysis / Inspection / Review）
  2. 每条 requirement 的验证状态是否已关闭（open / closed / waived）
  3. 每条未关闭 requirement 是否有对应 RID 与评审节点

输入证据：

- requirement 条款列表
- 验证方法分配记录
- 评审结论与 RID 记录
- 评审里程碑 / deadline 信息

输出形态：

- VCD / compliance matrix
- 未关闭项清单 + 证据引用
- 评审就绪度判断

比较评估：

| 维度 | 状态 | 说明 |
| --- | --- | --- |
| data readiness | 高 | requirement、status、RID、method assignment 都可用当前 facts + meta 表达 |
| temporal pressure | 低 | 这里仍有时间因素，但主要是离散里程碑 / deadline 级，而不是 interval/state propagation |
| uncertainty pressure | 低 | 主要是 binary / workflow-style compliance，不依赖概率语义 |
| traceability pressure | 高需求，基座已有 | audit package、explain substrate、sidecar durability 已足够支撑 requirement-level evidence chain 的第一轮 |
| delivery pressure | 低到中 | 更像 matrix / table export，符合当前 audit/evidence delivery 扩展方向 |
| current-fit | 高 | 除 data modeling 与 matrix delivery 外，当前 substrate 基本可用 |

缺口分类：

- data modeling
- delivery shape

明确不构成当前硬缺口的内容：

- 不需要新的 temporal runtime semantics
- 不需要新的 uncertainty semantics
- 不需要 `PyReason`

### 5.4 Adopted Conclusion

第一轮 scenario anchoring 结论：

- **Scenario B** 应作为近期优先锚点
- **Scenario A** 应保留为中期驱动场景

理由：

1. `Scenario B` 与当前 substrate 契合度更高，缺口主要是：
   - data modeling
   - compliance-matrix / VCD delivery
2. `Scenario A` 虽然更能代表 temporal-hybrid 的长期挑战，但它的核心阻塞就是：
   - temporal semantics
   - uncertainty semantics
   这两者都不适合在没有具名锚点和更细 scope 的情况下直接开实现任务。

### 5.5 Expected Downstream Decisions

这个切片结束后，至少应能更清楚地回答：

- 下一条实现型子蓝图更适合是：
  - `ecss-vcd-compliance-delivery`
  - 而不是优先进入：
    - `temporal-semantics`
    - `uncertainty-and-confidence`
    - `pyreason-integration-spike`
- “近期 ESA 演示”更像：
  - audit-log / requirement matrix
  - 而不是 proof-tree-first 或更重的 temporal reasoning demo

进一步的优先级影响：

| 下一条子蓝图 | 是否被 Scenario B 驱动 | 是否被 Scenario A 驱动 |
| --- | --- | --- |
| `ecss-vcd-compliance-delivery` | 直接需要 | 间接需要 |
| `temporal-semantics` | 不需要 | 必须 |
| `uncertainty-and-confidence` | 不需要 | 必须 |
| `pyreason-integration-spike` | 不需要 | 可能需要 |

基于这一结论，后续实现型子蓝图已完成并归档为 [2026-03-18_ecss-vcd-compliance-delivery.md](../archive/2026-03-18_ecss-vcd-compliance-delivery.md)，第一轮已按该切片收口 Scenario B 的 data modeling、delivery shape 与 service boundary。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 以当前模块 docs 和代码为实现真相
  - 以已归档 explainability substrate 为当前能力基线
  - 不把 unsourced working note 直接升级成系统事实
  - 所有 ECSS / ESSB 条款数值若来自 `cross-domain-compliance-framing.md`，都只作为 working-note 讨论素材，不构成对标准原文的解释
- 明确不做的内容：
  - 不在 scenario 未锚定前就开 `PyReason` 实现工作
  - 不在 scenario 未锚定前就恢复 runtime `temporal_view`
  - 不提前承诺某个 ESA/ECSS 方向就是产品主线
- 兼容性约束：
  - 若后续要引用外部标准或 requirement，需把 adopted conclusion 写回 blueprint/audit，而不是只留在聊天上下文

## 7. Acceptance

- [x] scenario anchoring memo 已形成（§5.3），覆盖 Scenario A（ESSB-ST-U-007 碎片缓解）和 Scenario B（ECSS-M-ST-10 VCD 合规矩阵）两个具名候选
- [x] 两个 scenarios 已按 6 个统一维度（data readiness / temporal pressure / uncertainty pressure / traceability pressure / delivery pressure / current-fit）完成对比评估
- [x] 每个 scenario 的缺口类别已明确分类（Scenario A：temporal + uncertainty + data modeling + engine；Scenario B：data modeling + delivery shape）
- [x] adopted conclusion 已写入 §5.4：Scenario B 作为近期优先锚点，Scenario A 作为中期驱动场景
- [x] `temporal-hybrid-reasoning` 下一步优先级已从抽象引擎讨论收口为具名子蓝图入口：`ecss-vcd-compliance-delivery`（§5.5）
- [x] ESSB 数值阈值的 authority 边界已写死：来源为非权威 working note，不构成对标准原文的核实（§5.2 authority note）

## 8. Implementation Plan

1. 收口 scenario anchoring 子蓝图，明确它只解决“场景锚点”而不直接碰 engine 实现。
2. 收集可用的 reference materials，选出 1 到 2 个具名候选 scenario。
3. 形成 scenario comparison memo，并把 adopted conclusion 回写到母蓝图或后续子蓝图入口。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.md`
- `docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.audit.md`
- `docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md`（若结论足以影响其优先级描述）
- `docs/README.md`（仅当新增持久 reference/doc 入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - scenario comparison memo 已完成（§5.3–§5.5）
  - adopted conclusion 已写入蓝图
  - `temporal-hybrid-reasoning` 的优先级 note 已同步更新
  - 后续实现切片已按该锚点推进并归档：
    - `ecss-vcd-compliance-delivery`
    - `audit-compliance-matrix-ui`
    - `ecss-requirement-authoring-surface`
    - `scenario-a-temporal-semantics`
    - `scenario-a-uncertainty-and-confidence`
    - `scenario-a-composite-reference-check`
    - `scenario-a-audit-delivery-shape`
- 与 blueprint 不同的地方：
  - 无实质偏差。§5.3 直接在蓝图内写成 memo，而不是拆成独立文档
- 为什么会有这些调整：
  - scenario comparison memo 体量适中，独立文档只会增加引用负担；直接内嵌更利于追溯
- 归档说明：
  - 本切片为纯分析型输出，无代码实现、无测试；其锚点职责已被后续 Scenario A / Scenario B 子切片消费完成，因此归档退出 active 集合
