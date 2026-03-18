# Task Blueprint: AML Suspicious-Account Scenario Anchoring

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
  - [2026-03-18_aml-suspicious-account-anchoring.audit.md](./2026-03-18_aml-suspicious-account-anchoring.audit.md)

## 1. Problem

`ECSS` 线已经完成了从 `Scenario B` 到 `Scenario A` 再到 explain delivery 的一整轮闭环。当前更高价值的问题不再是继续抛光同一条线，而是验证这套 substrate 是否能 **跨域泛化**。

在现有蓝图与 working reference 中，最强的候选跨域场景是：

- `AML/KYC suspicious-account scenario`

这个场景的结构已经被明确描述为：

- 有限时间窗口内出现多笔接近阈值但未越阈的转账；
- 后续资金被汇总并流向高风险受益方；
- 同时存在若干单独较弱、但可组合的 supporting signals，例如共享设备、共享受益人、不一致的受益所有人信息；
- 系统需要回答“为什么在此刻触发 SAR / suspicious-activity obligation”，而不是只给一个分数。

这条 scenario line 适合作为下一轮锚点，因为它能同时检验：

- 当前 explain delivery 栈是否真正脱离了 ECSS 特定词汇；
- temporal / uncertainty / deontic 压力是否在跨域场景中仍然成立；
- Rainbird 类 evidence-chain 对照是否会在 live case-review 形态上暴露新的缺口。

因此，本切片的目标不是立即做 AML 规则实现，而是先把 `AML suspicious-account` 收口成一个可驱动后续蓝图的具名场景锚点。

## 2. Goals

- 把 `AML/KYC suspicious-account` 从 reference scenario 收口成具名 scenario line。
- 至少拆出 2 个不同压力级别的 AML 候选切片：
  - 一个近期、与当前 explain/delivery substrate 高契合的切片；
  - 一个中期、明确要求 temporal / deontic / uncertainty 进一步扩展的切片。
- 为每个候选切片明确：
  - 问题粒度
  - 输入证据类型
  - 期望输出形态
  - 所需推理能力
  - 与当前 substrate 的契合度
- 给后续新实现型蓝图提供 adopted 起点，而不是直接跳去更抽象的 temporal/LLM 讨论。

## 3. Non-goals

- 不在本蓝图中实现 AML/KYC 规则、schema、或 case-review UI。
- 不在本蓝图中把 AML 参考场景写成监管真相或法律意见。
- 不在本蓝图中验证 FATF / 4AMLD / SAR 具体条款原文。
- 不在本蓝图中直接设计完整 deontic ontology。
- 不在本蓝图中引入新的 probabilistic engine 或 LLM workflow。

## 4. Current Context

- 当前实现基座已经具备：
  - raw `rule_run` explain
  - runtime/audit parity 的 `rule_run_summary`
  - runtime/audit parity 的 deterministic narrative
  - runtime-first deterministic `NL explain`
  - audit static proof-entry page
- 当前已经被证明可支撑：
  - threshold / temporal / conjunction style checks 的 explainability
  - requirement-scoped audit artifact 与 evidence drill-down
- 当前仍明确缺少：
  - 事件序列聚合后的 state propagation
  - 具名 `judgment` / deontic result contract
  - 弱信号组合的 certainty/probability 口径统一
- `runtime-traceability-explainability` 已明确把 `AML/KYC suspicious-account scenario` 列为 reference scenario，但还没有进一步收口成后续实现切片的锚点。

authority note:

- `docs/references/working/cross-domain-compliance-framing.md` 是内部 working note，不是监管依据。
- `docs/references/external/rainbird-evidence-chain-compare.md` 是外部比较材料，不是本项目 contract 模板。
- 因此，本蓝图只把 AML 场景当成 **design pressure / delivery-shape pressure**，不把其中监管表述视为已核实事实。

## 5. Proposed Shape

### 5.1 First-round Output

第一轮输出是一份 `scenario comparison memo`，聚焦同一条 AML scenario line 下的两个候选切片：

1. `AML-Review`: suspicious-account case-review evidence package
2. `AML-Trigger`: suspicious-account obligation / risk-state trigger

这两者共享同一个叙事背景，但给系统施加的压力不同：

- `AML-Review` 主要检验 explain/delivery substrate 是否已足够跨域复用
- `AML-Trigger` 主要检验 temporal / uncertainty / deontic 语义是否仍是硬缺口

### 5.2 Comparison Dimensions

两个候选切片至少按以下维度比较：

1. `data readiness`
   - 账户、交易事件、受益人、设备、BO mismatch 等输入是否能用当前 facts/meta 直接表示
2. `temporal pressure`
   - 是否需要“36 小时窗口内多笔事件”的显式聚合语义
3. `uncertainty pressure`
   - 是否需要把多个弱信号组合成 certainty / probability style judgment
4. `deontic pressure`
   - 是否必须显式表示“SAR obligation triggered / not triggered / review-required”这类 judgment
5. `traceability pressure`
   - 是否需要 rule_run explain、evidence chain、assertion drill-down
6. `delivery pressure`
   - 消费形态更像 case-review packet、live explain API、还是 investigator-facing narrative
7. `current-fit`
   - 与当前 runtime/audit/narrative/NL explain substrate 的契合度

### 5.3 Scenario Comparison Memo

#### Scenario AML-Review: Suspicious-Account Case-Review Evidence Package

目标问题：

- 给定一组已经识别出的 suspicious-account candidate / rule_run，系统能否输出 investigator 可消费的 case-review evidence package，回答：
  - 为什么这个账户被标记；
  - 依赖了哪些主要 predicates / checks；
  - 哪些 assertion / drill-down pages 可以继续查看；
  - 是否存在一条 shareable proof-entry。

输入证据：

- 已写入 ledger 的交易事件 facts
- 风险受益方 / 共享设备 / BO mismatch 等 supporting facts
- 某次 rule run 的 `rule_run_id`

输出形态：

- runtime explain / summary / narrative / NL explain
- audit package 中的 trace + assertion detail
- case-review style narrative walkthrough

比较评估：

| 维度 | 状态 | 说明 |
| --- | --- | --- |
| data readiness | 中到高 | 账户、交易、受益人、设备关联都可用当前 schema/fact 形状建模 |
| temporal pressure | 低到中 | 第一轮可先假定上游已把“可疑账户候选”或“窗口内聚合结果”写成 facts |
| uncertainty pressure | 低到中 | 可先不做弱信号数值组合，只检验 explain/delivery 能否跨域复用 |
| deontic pressure | 低 | 第一轮可停在 suspicious/risk candidate explain，不要求正式 judgment kind |
| traceability pressure | 高需求，当前基座已具备 | 正适合压 `raw -> summary -> narrative -> NL explain -> proof-entry` 这条链 |
| delivery pressure | 高 | investigator-facing case review 正是当前 runtime/audit delivery 栈的自然消费面 |
| current-fit | 高 | 几乎不需要新 runtime semantics，主要是 domain modeling + scenario walkthrough |

这个切片并不只是“再做一次别的领域 demo”，它至少要回答两个新的 substrate 问题：

- `multi-entity explain fan-out`
  - ECSS `Scenario A` 的 rule-run trace 更接近单个 requirement / obligation conjunction；
  - `AML-Review` 则天然跨越 `account -> transactions -> beneficiaries -> devices -> ownership signals` 这类多实体关系；
  - 需要判断单个 `rule_run_id` proof-entry 是否已经足够，还是 investigator case-review 实际需要一个 `case_id -> [rule_run_id]` 聚合层。
- `investigator-facing narrative vs compliance-facing narrative`
  - ECSS narrative 面向的是 requirement/compliance reviewer；
  - `AML-Review` narrative 面向的是 investigator 组案；
  - 即便底层 DTO 完全一致，也需要判断现有 prose composition 是否已足够，还是 case-review 需要新的 delivery shape。

缺口分类：

- data modeling
- delivery shape / walkthrough packaging

#### Scenario AML-Trigger: Suspicious-Account Obligation / Risk-State Trigger

目标问题：

- 在 36 小时窗口内出现多笔接近阈值但未越阈的转账，后续资金被汇总并流向高风险受益方，且伴随共享设备 / 共享受益人 / BO mismatch 等弱信号时，系统是否能推导：
  - suspicious risk state 是否成立；
  - SAR / review obligation 是否在此刻被触发；
  - 为什么是“此刻”而不是更早或更晚。

输入证据：

- 交易事件流
- 时间戳 / 窗口边界
- 高风险司法管辖区 / 受益方标记
- 共享设备、共享受益人、BO mismatch 等 supporting signals

输出形态：

- risk / obligation judgment
- 触发时点 explain
- supporting proof chain + optional certainty breakdown

比较评估：

| 维度 | 状态 | 说明 |
| --- | --- | --- |
| data readiness | 中 | facts 可建，但需要更明确的事件、账户、受益方、signal schema |
| temporal pressure | 高 | “36 小时窗口内多笔转账 + 后续汇总”比 Scenario A 的 T1 更接近事件聚合和 sequence semantics |
| uncertainty pressure | 高 | 多个单独较弱的 signals 如何组合，是当前 certainty/probability 线尚未收口的问题 |
| deontic pressure | 高 | 最终输出不是普通 candidate，而是 obligation / review-required judgment |
| traceability pressure | 高需求，部分基座已有 | explain carrier 已有，但 judgment-level entry point 和 trigger rationale 仍缺口明显 |
| delivery pressure | 中到高 | 更像 investigator / reviewer decision support，而非单纯 matrix 或 trace page |
| current-fit | 低到中 | explain substrate 可复用，但 temporal aggregation、uncertainty semantics、judgment contract 都未具备 |

缺口分类：

- temporal semantics / event aggregation
- uncertainty semantics
- deontic judgment contract
- data modeling

### 5.4 Current Recommendation

当前 draft 倾向的 adopted direction 是：

- `AML-Review` 应作为这条新 scenario line 的近期优先锚点
- `AML-Trigger` 应保留为中期驱动场景

理由：

1. 它与刚闭环的 explain delivery 栈最直接同构，能最快验证当前 substrate 是否真正跨域可复用。
2. 它不要求立刻引入新的 temporal aggregation、judgment kind 或 certainty semantics，避免刚结束 explain phase 就又跳回未收口的 kernel 扩展。
3. 一旦 `AML-Review` 跑通，`AML-Trigger` 的剩余缺口会更具体：到底缺的是 event aggregation、judgment contract，还是 uncertainty combination。

进入下一条实现型蓝图前，还应通过一个显式 gate：

1. 单个 `rule_run_id` 是否已经足够作为 case-review proof-entry，还是 scenario 需要一个 multi-run aggregation layer。
2. 现有五层 explain delivery 栈（raw -> summary -> narrative -> NL -> static）是否已经足够服务 investigator-facing consumption，还是“case-review”语义要求新的 delivery shape。

若这两个问题都得到“当前 substrate 足够”的结论，则 `aml-case-review-walkthrough`（或等价命名）可以直接进入实现。若任一问题暴露真实缺口，则该缺口应先单独收口成新的 scoped blueprint，再进入 walkthrough 实现。

### 5.5 Expected Downstream Decisions

这个 anchoring 切片结束后，至少应能更清楚地回答：

- 下一条实现型蓝图是否应是：
  - `aml-case-review-walkthrough`
  - 而不是直接进入：
    - `aml-obligation-trigger-semantics`
    - 新的 probabilistic engine 扩展
    - LLM-led investigator explain
- `Rainbird` 参考在这条场景线中最应对照的是：
  - live proof-entry
  - investigator-facing evidence path
  - NL explain 作为派生层
  - 而不是 certainty mechanism 本身

## 6. Boundaries And Invariants

- 必须保持的边界：
  - AML reference 只作为 scenario pressure，不作为监管事实承诺
  - 下一轮若进入实现，应优先复用当前 explain/delivery substrate，而不是先改 carrier
- 明确不做的内容：
  - 不在本蓝图中定义正式 AML ontology
  - 不在本蓝图中产出 live case management product design
  - 不在本蓝图中决定是否最终进入 LLM-backed investigator workflow
- 兼容性约束：
  - 不重新打开已经归档的 ECSS Scenario A/B 实现切片
  - 不把这条新场景线写成对现有 explain delivery contract 的否定

## 7. Acceptance

- [x] 至少 2 个 AML 候选切片已形成具名 comparison memo
- [x] 每个切片的缺口已明确分类（data / temporal / uncertainty / deontic / delivery）
- [x] authority boundary 已写清：working note 与 external comparison 只作 scenario pressure，不作事实承诺
- [x] 已形成当前推荐的下一条实现型切片

## 8. Implementation Plan

1. 以 `AML/KYC suspicious-account` 为同一 scenario line，拆出近端 `AML-Review` 与中期 `AML-Trigger` 两个候选切片。
2. 对这两个切片按 `current-fit / temporal pressure / uncertainty pressure / deontic pressure / delivery pressure` 做 memo 级比较。
3. 给出 adopted next slice recommendation，供后续实现型蓝图直接承接。

## 9. Docs To Update

- 无；本切片第一轮为纯分析型蓝图，不改模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 本切片将 `AML/KYC suspicious-account` 收口为新的具名 scenario line，并形成了两个候选切片的 comparison memo：
    - `AML-Review`（近期）
    - `AML-Trigger`（中期）
  - gate question 已被明确回答：
    - 单个 `rule_run_id` 对 first-round walkthrough 足够，但对通用 case-review 不足；当前不存在 `case_id -> [rule_run_id]` aggregation layer。
    - 现有五层 explain delivery 栈（raw -> summary -> narrative -> NL -> static）对 single-rule-run investigator walkthrough 足够，但对 case-folder / multi-run rollup / cross-entity case summary 不足。
  - 基于这一 gate resolution，下一条实现型蓝图应直接是 `aml-case-review-walkthrough`，并将 scope 锁定为：
    - single composite rule run
    - single `rule_run_id` proof-entry
    - 复用现有五层 explain delivery 栈
- 与 blueprint 不同的地方：
  - 无实质偏离；仍保持纯分析型输出，没有进入代码、测试或模块 docs 变更。
- 为什么会有这些调整：
  - 不适用。
- 归档说明：
  - 该 anchoring memo 在给出 adopted next slice recommendation 与 gate resolution 后完成职责，归档到 `docs/blueprints/archive/`。
