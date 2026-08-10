# Design-Point: Meander × FactGraph 统一设计对抗审核处置矩阵

- Status: working
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: candidate design / non-authoritative reference. **Not current behavior.** Becomes a constraint only when cited by an adopted decision, an implemented blueprint, current module docs (`src/factgraph/*/docs/`), or `workflow/foundations/architecture_principles.md`.
- Inputs:
  - [`meander-factgraph-unified-design-review-candidate.zh.md`](./meander-factgraph-unified-design-review-candidate.zh.md), current intake SHA-256 `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7`
  - `/Users/zhenzhili/obsidian_workspace/symb-Intelli./claude_report/2026-08-10_meander-factgraph统一设计对抗审核报告.zh.md`
  - 同目录 7 份维度报告与 2 份攻击案例报告
  - `/Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/` 调研包
  - 2026-08-10 对关键 finding、pinned 代码与候选文本的独立只读复核
- Outputs / Downstream:
  - 可能的统一设计候选下一修订版；须经用户逐项授权，不由本文自动改写 Review Freeze
  - 产品门、Policy 语义、迁移拓扑、Translator、Run/replay、Assessment/UI 等后续离散 decisions
- Related:
  - [`rule-addressing-semantic-ports-and-evaluation-target.zh.md`](./rule-addressing-semantic-ports-and-evaluation-target.zh.md)
  - [`premise-effective-view-and-scenario-resolution.zh.md`](./premise-effective-view-and-scenario-resolution.zh.md)
  - [`scenario-plan-what-if-run-and-policy-aware-explain.zh.md`](./scenario-plan-what-if-run-and-policy-aware-explain.zh.md)

> **Authority reminder** (per Q2 §4.4): a design-point cannot directly override shipped behavior. Implementation must reach the codebase via the downstream consumption chain (decision → blueprint → impl), not by direct reference to this essay.

## 1. 目的与边界

本文不是对 Review Freeze 的静默修订，也不是把 83 条 finding 全部转成 backlog。它只回答四个问题：

1. 原 finding 的事实内核是否成立；
2. 它是否误读了 Review Freeze、目标架构与阶段切片之间的关系；
3. 它最迟必须在哪个产品门或实现阶段前关闭；
4. 它应进入候选文本、实验协议、正式 decision、blueprint/preflight，还是应被拒绝。

本文维持两项彼此独立的裁定：

- **架构裁定：`REVISE`**。中央语义链没有被否决，但需要分阶段补足具名 gate。
- **产品授权：停留在 `Phase -1 / STOP-except-discovery`**。本文既不禁止也不授权与产品楔子独立的 FactGraph 内核工作；任何这类实现仍需自己的 decision、blueprint 与用户授权。它同时禁止把架构可行性误写成产品建设授权。

没有任何 finding 授权修改代码、启动产品建设、发布新 API 或覆盖现有 shipped 行为。

## 2. 审核快照与可复核性限制

| 对象 | 本次 intake 状态 | 说明 |
|---|---|---|
| 候选文档 | 2185 行；SHA-256 `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7` | 当前工作区实际文件 |
| 对抗主报告 | 458 行；SHA-256 `8ac1c7638a82f0a26a5ba2f4a722255370424086f506727af1a8108aa6a41166` | 报告自述 28 个子代理、83 条正式 finding |
| pinned repositories | hnsm-backend `dbe79d70`；Meander `4ddb8e36`；meander-agent `e4b04491`；factgraph-new `b92d6bf5` | 本次独立复核与报告基线一致 |

审核包没有记录被审候选的内容哈希；主报告与部分支撑文件写 2186 行，另一些支撑文件写 2185 行。当前文件为 2185 行。因此：

- 报告中的候选行号只作导航，不作快照身份；
- 本矩阵只把已经对当前哈希重新核对的结论称为“独立确认”；
- 下一次冷启动审核必须同时记录候选 SHA-256、行数、仓库 commits 与审核包 manifest。

正式 finding 数为 83：PM 10、SC 12、SF 8、AS 11、RR 11、UI 10、CE 11、AC 10。`AC-17` 在报告中被交叉提及，但没有独立的正式 finding section，不计入 83。

本矩阵的处置分布为：`ACCEPT` 32、`ACCEPT_WITH_NARROWING` 23、`NEEDS_DECISION` 16、`DEFER_TO_PHASE_GATE` 10、`REJECT_AS_MISREAD` 2。它反映的是证据与阶段归属，不是新的严重度加权总分。

## 3. 处置词汇与阶段语义

### 3.1 处置状态

| 状态 | 含义 |
|---|---|
| `ACCEPT` | 原问题事实与影响基本准确；应在指定落点吸收。 |
| `ACCEPT_WITH_NARROWING` | 根因成立，但原严重度、影响链、修正方式或适用范围被夸大；只吸收收窄后的主张。 |
| `DEFER_TO_PHASE_GATE` | 风险真实，但已有开放 gate 或尚未进入其可达面；现在记录义务，在对应阶段前关闭。 |
| `REJECT_AS_MISREAD` | 原结论依赖范围误读、把 conditional target 当已授权 MVP，或把不同语义等同；不按原 finding 修设计。可能保留低成本澄清。 |
| `NEEDS_DECISION` | 证据暴露了真实分叉，无法靠措辞或一次实验自动决定；须进入正式 decision/ADR。 |

### 3.2 “最迟关闭阶段”不是实现授权

`现在` 表示下一版候选若继续存在，应先消除会误导当前授权或评审的文字矛盾。`Gate -1`、`Phase 1`、`Phase 2` 等表示：只有当用户以后明确授权进入该阶段时，才必须在入口或出口前关闭。远期 gate 不因出现在本表而提前成为当前工作。

## 4. 综合裁定

### 4.1 立即成立的修订方向

1. Phase 0/1 也必须服从 Gate -1；唯一例外是用户显式批准、预算封顶、可丢弃的 discovery 并行实验。
2. Phase -1 与 §18.7 不应维护一份弱化的本地产品门副本；应规范引用调研包 Gate -1/DoD，并按原语义保留四臂、双包装、付费意愿门、客户共同定义的 30% 改善目标，以及只适用于 semantic customization 工时的 `>50%` kill 条件；不得把后二者复制成新的统一阈值。
3. `MVP` 只指已授权的人工/native MVP-0；P0 Plan 应改称 post-gate Agent/compatibility profile。
4. 产品核心应以 source-bound case/draft review 为轴，Agent output/intent 是输入类别之一；这不否决条件性的 Agent target architecture。
5. “11 个下个实验前 blocker”应改称“按阶段关闭的 required revisions/gates”。审计综合层已经判定没有存活的 `BLOCKER`，不应继续混用术语。

### 4.2 两项关键反向裁定

- **SC-01 既不是已证实的 shipped bug，也不是有语义测试背书的有意设计。** 当前 `RuleExpr` 构造测试允许 `(a & (b | c)).join(a.x.eq(b.x))`，但只断言 AST 保留 join；lowering 代码会在不含 `b` 的分支过滤该约束，却没有 asymmetric `join × Any` lowering golden 证明这是预期语义。因此准确结论是：构造被允许，当前 lowering 行为可观察，但其语义未测试、未规格化。D03 必须在 branch-scoped 与 reject-on-partial 之间裁定，不能先把任一解释称为正确。
- **SF-02 不应复制第二份 authority 状态。** 候选定义中的 `GovernanceSnapshot` 已规定承载 Agent authority。真实缺口是 legacy projection 没有规定 suspension 在所有证明/FactGraph 求值分支之前短路为 `needs_review`；更早的 stale-goal 与 blocked-selection guard 仍保持原顺序。修正应消费候选已有 snapshot、保留 suspension reason 并记录 `factgraph_consulted=false`，而不是给 `LegacyDecisionProfileSnapshot` 再造一份真值源。

### 4.3 审核最有价值的真实穿透

以下根因最值得保留，且比 finding 数量本身更重要：

| 根因簇 | Finding | 性质 |
|---|---|---|
| 产品门可被阶段编号和定性措辞绕开 | PM-01、PM-04、CE-11、PM-08 | 现在修 |
| 包装与真实 source 获取未进入 Gate -1 | PM-03、PM-10、PM-07 | 产品 discovery gate |
| Translator 自报 coverage/round-trip | AS-03、AS-09、AS-11、AC-01 | Translator benchmark / L0 gate |
| routing 输入污染可确定性选错 mandatory Policy | AS-05、AC-24 | A1/L1 gate |
| 多租户行为禁令没有覆盖存储键、缓存、索引与导出 | AS-02、CE-05 | 真实数据 gate |
| old/new evaluator 双跑拓扑未定义 | CE-03、SF-04、RR-08 | Phase 3 gate |
| 历史 Explain 可能混用旧身份与活证据 | RR-01、AC-02、RR-04、RR-06 | Phase 3/4 gate |
| UI/Assessment 轴与理解门不可操作化 | UI-01–UI-04、UI-08、UI-10 | Phase 1/3 gate |
| 合成命名空间与运行预算仍有真实代码面缺口 | AC-21、AC-22、SC-11/12 | Phase 2 gate |
| legacy authority suspension 未进入兼容投影 | SF-02 | Phase 3 adapter preflight |
| AssessmentSubject 可作为自己的唯一证据 | AC-16 | Plan Lab/source-lineage gate |
| redaction、最小披露与 retention kill 无可执行 privacy 实验 | 攻击案例 17 完备性缺口（非独立 finding） | Gate -1 / 真实数据 gate |
| case bundle 可能漏掉隐藏工作流与级联后果 | 证伪实验 4 完备性缺口（非独立 finding） | Gate -1 evidence-coverage gate |
| Meander artifact 未与原生/原始日志做盲审对照 | 证伪实验 7 完备性缺口（非独立 finding） | Gate -1 reviewer-value gate |

## 5. 完整 finding disposition

“审计严重度”保留维度报告到综合报告的变化；它不是本文重新给出的严重度。

### 5.1 产品与市场（PM，10 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| PM-01 | BLOCKER→HIGH | `ACCEPT` | Phase 0/1 未明确服从 Gate -1，与调研规定“Phase 0 仅 Gate -1 后”冲突。 | 现在 | §17 总前言、Phase 0/1、D01；仅保留显式预算封顶的 discovery 例外。 |
| PM-02 | HIGH→MEDIUM | `ACCEPT_WITH_NARROWING` | 报告混淆了无 Agent 的 MVP-0 与 post-gate target，但有效内核成立：wedge/D01 仍开放时，§1.1 已把 Agent 轴产品核心标成 `SETTLED DIRECTION`，存在状态标签与证据顺序错配。 | 现在澄清 | §1.1 改为 case/draft review，Agent output 为一种输入；P0/Plan Lab 保持 post-gate，不保留原 HIGH 影响链。 |
| PM-03 | HIGH | `NEEDS_DECISION` | standalone 与 incumbent plugin/OEM 的包装轴未登记，但 §13 的 provisional read model 尚未等于已选择 standalone。 | Gate -1 出口 | D01 子决定或独立 packaging decision；阻断生产 UI 与正式 UI 测试对象。 |
| PM-04 | HIGH→MEDIUM | `ACCEPT` | 本地定性 stop/kill 摘要弱于调研包的四臂、双报价、付费意愿、共同定义的 30% 改善目标与 semantic-customization `>50%` kill 条件。 | 现在 | Phase -1、§18.7、D01 规范引用 Gate -1/DoD；摘要不得覆写或泛化各指标口径。 |
| PM-05 | HIGH | `ACCEPT_WITH_NARROWING` | 缺少“规则正确、来源自洽但错误/过时”的验证与 automation-bias 测量；这是验证缺口，不是自动判真的要求。 | Phase 3 gate；Gate -1 先测偏差 | §18 wrong-premise gate；Assessment/UI 明示结论对 source authority/freshness 条件成立。 |
| PM-06 | MEDIUM | `NEEDS_DECISION` | observed/valid time 已有，但 source freshness policy/status 与 replay pin 未形成独立语义。 | Phase 1 定义；最迟 Phase 4 | §14.1 freshness 轴；D08/D10 记录 policy、版本与 disposition。 |
| PM-07 | MEDIUM | `ACCEPT_WITH_NARROWING` | kill #5 的 incumbent 面偏窄，但候选无需复制完整竞争对手目录。 | Gate -1 | §18.7#5 扩至 native QA、detect API、vertical incumbent；baseline 绑定调研 competitor set。 |
| PM-08 | MEDIUM | `ACCEPT` | `default MVP candidate` 会把 post-gate P0 Plan profile 误读为已授权 MVP-0。 | 现在 | §9.3 改为 post-gate Agent/compatibility profile；§1.3 去除授权暗示。 |
| PM-09 | LOW | `ACCEPT_WITH_NARROWING` | HR 年龄示例是叙事卫生问题，不证明楔子漂移。 | 低优先，下一版 | §15 增一条中性的 source-bound regulated workflow，或声明示例不代表垂直选择。 |
| PM-10 | MEDIUM | `DEFER_TO_PHASE_GATE` | 权威 source 获取路径未进入阶段文本；安全边界存在，但没有可运行的数据供给链。 | Gate -1 出口 | Phase -1/3 使用合法、脱敏的一次性 bundle；D08 记录 acquisition，connector 明确 deferred。 |

### 5.2 复杂度与经济性（CE，11 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| CE-01 | HIGH→LOW/REFUTED | `ACCEPT_WITH_NARROWING` | 真实问题只是 `smallest` 的比较口径未定义；把完整 target review map 的类型数当一次实现负担是范围误读。 | 现在 | §0.1/§23 改为 `smallest coherent review map for the stated scope`；各 phase 列最小 artifact 集。 |
| CE-02 | HIGH | `ACCEPT` | §3.3 的“总负担下降”没有基线、主体、计时维度或 gate。 | Phase 3 前定义，Phase 4 出证据 | §3.3/§18 burden ledger：authoring、mapping、fixture、review、运维对比。 |
| CE-03 | HIGH | `NEEDS_DECISION` | 同名 `factgraph` 包使单进程双 import 不自然；Phase 3 未指定双跑拓扑、投影与 owner，但双进程可行。 | Phase 3 blueprint 前 | migration topology decision：双 venv/IPC/批处理、pins、projection、artifact owner、rollback。 |
| CE-04 | MEDIUM | `DEFER_TO_PHASE_GATE` | “三 spike 必耗 3–5 人月”证据不足；真实风险是小团队盲化、角色冲突与预算。 | Phase 1 前 | 实验协议固定串并行、预算、语料/阈值时间隔离与独立 adjudication。 |
| CE-05 | HIGH | `NEEDS_DECISION` | 已有 tenant ownership/字段/禁令，但缺 object/cache/index/export/content-addressing 的操作性隔离合同。 | Phase 3 真实数据；最迟 Phase 6 | 独立 tenant-isolation decision；关闭前仅用合成/脱敏单租户材料。 |
| CE-06 | MEDIUM | `NEEDS_DECISION` | retention、erasure 与 replay degradation 的裁决主体和优先级未定。 | Phase 4 前 | 扩 D10：retention/erasure/replay 三角、legal hold、删除后状态与 UI。 |
| CE-07 | MEDIUM | `DEFER_TO_PHASE_GATE` | L1 延迟、超时、依赖失败和异步降级合同只在 Phase 6 承重。 | Phase 6 前 | 扩 D17 或新增 L1 runtime contract；timeout 不得投影为 pass。 |
| CE-08 | MEDIUM | `NEEDS_DECISION` | 跨仓 fixture/schema 缺唯一归属、版本 pin 与共同 CI 锚。 | Phase 0 交付时 | Phase 0/J1 指定 canonical owner、commit/version pin 与双仓兼容测试。 |
| CE-09 | MEDIUM | `DEFER_TO_PHASE_GATE` | scaffold 原则已有；真实欠缺是实际启用后的 owner、复审窗口和可测退出条件。 | Phase 3 blueprint | 为实际 scaffold 填 owner、telemetry、review date、exit/rollback。 |
| CE-10 | LOW | `REJECT_AS_MISREAD` | Package/learning shape 已标 provisional/optional；在 Review Freeze 中提供可攻击形状不等于授权建表。 | 无强制阶段 | 可保留或移附录；加强 D13/D14 与 `not prerequisite` 交叉引用。 |
| CE-11 | MEDIUM | `ACCEPT` | 与 PM-04 同根：Phase -1 摘要可能被误当完整 Gate -1，且 sponsor 不等于付费。 | 现在 | 与 PM-04 合并；规范引用完整完成/停止条件。 |

### 5.3 FactGraph 语义核心（SC，12 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| SC-01 | HIGH | `NEEDS_DECISION` | asymmetric `join × Any` 的构造被允许、当前 lowering 会过滤缺端点分支的 join，但没有 lowering test/spec 证明该语义是预期设计。 | spike 前预注册问题与 fixtures；Phase 1 出口、进入 Phase 2 前完成裁定 | D03 在 branch-scoped/reject-on-partial 间裁定；§18.3 paired golden；spike 不得把当前行为默认为正确。 |
| SC-02 | MEDIUM | `DEFER_TO_PHASE_GATE` | lowering 不保存 authored→generated alias map，branch id 也不具跨版本稳定性；候选已把 lineage 列为 compiler gate。 | Phase 1 lineage gate | compiler lineage DTO/trace；D15。 |
| SC-03 | MEDIUM | `NEEDS_DECISION` | Policy AST 排除 `Not` 不会自动排除被组合 Rule 体内的 `NotAtom`/aggregate，受管 Rule 准入边界缺失。 | D03/Phase 2 blueprint | D03 扩为 Policy AST + managed Rule body capability/closure profile。 |
| SC-04 | MEDIUM | `ACCEPT_WITH_NARROWING` | “future revised digest”只有在桥存续期内原地换算法才破坏身份链；应明确它是独立版本化迁移。 | D02/J1 冻结 | §6.1 限定；D02 定义双摘要/迁移窗口。 |
| SC-05 | MEDIUM | `NEEDS_DECISION` | `schema digest` 是端点局部还是全 ontology 未定；全局摘要会让无关演化造成指纹雪崩。 | D02/Phase 2 前 | D02；局部规范化摘要；无关 schema 演化 fixture。 |
| SC-06 | MEDIUM | `DEFER_TO_PHASE_GATE` | v0 AST 是否覆盖真实 AML 谓词，尤其 missing-record 与数据驱动全称，尚无代表性 fixture。 | Phase 1 compiler gate | 表达力 corpus；结果回填 D03 与 Phase 2 范围。 |
| SC-07 | LOW | `ACCEPT` | `ExpectationResult.status` 在 §6.6 四态、§14.1 五态，`inconsistent` 未定义。 | J1/J2 DTO 冻结 | 统一两节；若保留则由 D06 定义。 |
| SC-08 | LOW | `ACCEPT` | §6.5 把 count 留到 D06，§6.6 却无条件允许 count early termination。 | D06/Phase 2 冻结 | §6.6 加 count-after-D06 限定。 |
| SC-09 | MEDIUM | `ACCEPT` | 当 `ZERO/MULTIPLE_TARGETS` 的解析差异可被未授权调用者观察时，它会形成存在性/基数 oracle。 | D09；任何外部 Scenario 前 | D09 在授权 resolution view、外部错误粗化或二者组合中裁定；补安全 fixture。 |
| SC-10 | LOW | `ACCEPT_WITH_NARROWING` | Phase 5 gate 的 `missing/unknown/negated remain distinct` 可能被误读为 Scenario v1 必须生成这些状态；v1 实际只需保留 baseline 已有区分。 | Phase 5 blueprint | 明写 v1 的保真义务；`MASKED` 留到 `WITHOUT_FIELD` 等可产生该状态的后续 slice。 |
| SC-11 | LOW | `ACCEPT_WITH_NARROWING` | 当前 lowering 单次计划内会避碰；真实风险是目标 public grammar 尚未保留私有 alias/head namespace。 | Phase 2 J1/J2 | 保留目标私有前缀；不要无迁移地全面禁止历史 `__` Rule id。 |
| SC-12 | LOW | `NEEDS_DECISION` | DNF 超限应归发布 capability 失败还是请求 execution 失败，以及静态上限和 runtime budget 的关系未定。 | D06/Phase 2 发布路径 | D06、publication validator、失败归轴。 |

### 5.4 Shipped 兼容忠实度（SF，8 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| SF-01 | MEDIUM | `ACCEPT` | legacy 表漏掉 relaxed entailed 但 proof 无 `claimed_by_agent` premise 时的 `needs_review` 防御分支。 | Phase 3 adapter schema/preflight | §9.4 truth table；§18.4 fixture。 |
| SF-02 | HIGH | `ACCEPT_WITH_NARROWING` | 候选 `GovernanceSnapshot` 已规定 authority 输入；真实缺口是 suspension 未在所有 proof/FactGraph evaluation 分支前短路为 `needs_review`。 | Phase 3 adapter schema/preflight；cutover 前 | 消费既有 authority；保留 reason、记录 `factgraph_consulted=false`；suspended/restored fixture；不复制真值源。 |
| SF-03 | MEDIUM | `ACCEPT` | “same scope with allowed Agent claims”没有说明 relaxed 只撤销 ledger-wide provenance-class exclusion；predicate allowances 与 origin-binding blocks 仍原样生效。 | Phase 3 adapter schema/preflight | §9.4 精确定义 relaxed；跨 Plan claim fixture。 |
| SF-04 | MEDIUM | `NEEDS_DECISION` | 两个实现共用顶层包名，old/new evaluator 不能同进程直接共存。 | Phase 3 blueprint | 与 CE-03 合并为 dual-run topology decision。 |
| SF-05 | MEDIUM | `ACCEPT` | Meander 首次切到 hnsm workspace 要做 v0.2→v0.3 迁移，并验证 assertion id/顺序保留。 | 首次 hnsm workspace；最迟 Phase 4 | migration truth、blueprint 与迁移 fixture。 |
| SF-06 | LOW | `ACCEPT_WITH_NARROWING` | rejected write-failure 可能留下已撤销的 append-only 痕迹；准确说法是“无有效 Claim 状态”，不是“从未写入”。 | 下一版候选 | §9.4/§15.1 措辞。 |
| SF-07 | LOW | `ACCEPT` | §2.6 三组 pinned 行号漂移，主张本身仍成立。 | 下一版候选 | 刷新 evidence map。 |
| SF-08 | LOW | `ACCEPT_WITH_NARROWING` | “Inbox”可作产品统称，但 shipped 实体是 `needs_review`/operator-decision workflow。 | Phase 3/UI 命名冻结 | glossary 定义别名，后文统一。 |

### 5.5 Agent authority 与安全（AS，11 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| AS-01 | HIGH→MEDIUM | `ACCEPT_WITH_NARROWING` | A1 若允许敏感路径 bind 但不 select，exists/error 可成值恢复 oracle；风险依赖具体权限和值域。 | Phase 6 A1/L1 | D05：bind/披露单调性、错误粗化、双视图、审计。 |
| AS-02 | HIGH | `NEEDS_DECISION` | tenant 字段与行为禁令不足以约束 artifact/cache/index/export/content-addressed store 的键控。 | 真实多租户写入；最迟 Phase 3/4 | 横切 tenant decision；credential scope、统一 deny/404、cache key。 |
| AS-03 | HIGH | `ACCEPT` | TranslationArtifact 缺 coverage 分母、Phase A 冻结、Phase B revision/diff，生产者可自报绕过控制。 | §18.2 benchmark 前；最迟 Phase 6 | §10.3、D12、§18.2 服务端记账与 versioned rubric。 |
| AS-04 | MEDIUM | `REJECT_AS_MISREAD` | legacy proposal preview 是独立 advisory/proposal 通道；consumable 不等于 authoritative 或 authorization，不能直接等同 A2。 | 无阻断；下一版澄清 | §2.1/§9.1 加有界 legacy caller-logic 例外。 |
| AS-05 | HIGH | `ACCEPT` | 污染的 workflow/risk/jurisdiction 输入仍可确定性选错 mandatory Policy，且缺 excluded-candidate 审计。 | 任何 caller-routed pilot；最迟 Phase 6 | D07、PolicySelectionArtifact：字段 provenance、候选/排除原因。 |
| AS-06 | MEDIUM | `NEEDS_DECISION` | “widen review”及 caller/reviewer 对 mandatory Policy 与 Explanation 的可见性未定义。 | Phase 6 A1/L1 | D05+D07 双视图；caller 只见聚合后果。 |
| AS-07 | MEDIUM | `ACCEPT_WITH_NARROWING` | STALE_CONTRACT 自动刷新重试只校验提交身份，未证明新旧路径语义等价。 | Phase 6 vNext SDK | §9.5/D05：引用路径 digest 等价才自动重试。 |
| AS-08 | MEDIUM | `ACCEPT` | “disposition”同时指 rollout/enforcement 与产品 disposition；独立轴也不等于自由笛卡尔组合。 | Phase 1 fixture/DTO | §9.1 改名 enforcement/rollout；§14.3 合法组合矩阵。 |
| AS-09 | MEDIUM | `ACCEPT_WITH_NARROWING` | BYOK transport 只认证 runner 身份，不认证 blind-first/coverage/locator；服务端可复算程度取决于是否持有原文。 | Phase 6 L0 | D12 区分 claimed/verified；无原文时明确保证降级。 |
| AS-10 | LOW | `ACCEPT` | §16.4–16.6 缺候选自定状态标签，安全主张采用状态不清。 | 下一版候选 | 补 `SETTLED/PROVISIONAL/ADOPTED`。 |
| AS-11 | MEDIUM | `NEEDS_DECISION` | SourceLocator 有 round-trip/digest 字段，但 admission 与 premise policy 之间没有明确执行者。 | 首个 authoritative SourceRecord；最迟 Phase 4/6 | D08：Meander Source Resolver 验证并写 admission，FactGraph 消费。 |

### 5.6 Run、replay 与持久化（RR，11 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| RR-01 | HIGH→MEDIUM | `ACCEPT_WITH_NARROWING` | 当前 live Explain 可混合旧 result identity 与新 ledger evidence；HIGH 影响依赖迁移期直接消费该输出。 | Phase 3 若消费 Explain，否则 Phase 4 | §2.3 迁移不变量；digest guard/`stale_view`；§18.5。 |
| RR-02 | HIGH→MEDIUM | `ACCEPT_WITH_NARROWING` | Phase 4 把 replay 存储能力与外层解释/UI 打包过大；这是规划风险而非架构矛盾。 | Phase 4 blueprint | 拆 4a replay、4b PolicyStructure/UI；D10 定 capture/as-of/hybrid。 |
| RR-03 | MEDIUM | `ACCEPT` | 多 EvaluationUnit 部分成功/失败无法由 request-level Attempt 表达，成功行也可能无可评审锚。 | Phase 4 Run schema | per-unit outcome 或 attempt-level ReviewTarget；与 D07 联动。 |
| RR-04 | MEDIUM | `ACCEPT` | “cutover”没有正式阶段，可能在 replay gate 前撤掉 eager-proof 底线。 | 任何权威 cutover 前 | §17 增 cutover gate，绑定 §18.4∧§18.5 与 capture。 |
| RR-05 | MEDIUM | `ACCEPT` | D11 未定身份列前，跨 Run 的 `changed` 只能退化为 removed+added。 | Phase 5 ScenarioDiff | D06+D11；或 v0 只支持 added/removed。 |
| RR-06 | MEDIUM | `ACCEPT` | 单一 explanation status 无法表达“逻辑可重执行、源/工件已擦除”等部分降级。 | Phase 4 replay/UI | replay level × artifact availability；tombstone/erasure event。 |
| RR-07 | LOW | `ACCEPT_WITH_NARROWING` | replay envelope 未显式 pin reference data/resolver version；只在使用 FX/日历/外部映射时承重。 | 相应 workflow 前 | §16.1 增 reference-data/resolver version。 |
| RR-08 | MEDIUM | `ACCEPT` | Phase 3 未列分叉包的数据桥、双跑拓扑及 premise/execution profile 治理来源。 | Phase 3 preflight | 与 CE-03/SF-04 合并；D13 与 migration work item。 |
| RR-09 | LOW | `ACCEPT` | manual explain 可换 config 重求值，目标历史 Explain 禁止；公开 API 会形成双重语义。 | Phase 4 API 接线 | 改名 `reevaluate_and_explain` 或正式弃用。 |
| RR-10 | LOW | `ACCEPT` | §2.6 只点名 native lazy probe，实际 Soufflé/ProbLog 首选路径也会读活 store。 | 下一版候选 | 修 evidence map。 |
| RR-11 | LOW | `ACCEPT` | §8.1 “FactGraph apply source admission”与 Meander 拥有 SourceAdmissionArtifact 存在职责歧义。 | D08/D09；最迟 Phase 5 | 改为 FactGraph consume pinned admission/premise inputs。 |

### 5.7 UI 与失败语义（UI，10 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| UI-01 | MEDIUM | `ACCEPT` | ExpectationResult 在 §6.6 无 `inconsistent`，§14.1 却有；冲突归 FactGraph 还是 Meander 不唯一。 | Phase 2 evaluator contract | D06；统一两节并定义 combining 边界。 |
| UI-02 | MEDIUM | `ACCEPT_WITH_NARROWING` | Assessment 轴缺 freshness、governance ambiguity 与 typed unavailable；materiality 分母与 AS-03 同根。 | Phase 3 Assessment schema | D07/D08 与 Assessment/Combining decision；分母归 AS-03。 |
| UI-03 | MEDIUM | `ACCEPT` | gaps-first、partial/incomplete/unavailable 不用绿色、无单一 pass/fail 尚未成为 §13 的硬约束。 | Phase 1 UI experiment | §13.1、D15、§18.6 判卷规则。 |
| UI-04 | HIGH | `ACCEPT` | UI gate 无目标角色、fixture、盲测、答案、评分与通过线，无法支撑 kill #6；审计建议的 `n≥5` 本身也无依据。 | Phase 1 UI gate 宣布通过前 | §18.6 标 `EXPERIMENT REQUIRED`；D15 加预注册方法，不硬编码任意 n。 |
| UI-05 | MEDIUM | `DEFER_TO_PHASE_GATE` | 概率引擎流缺 certainty 轴与阈值归属，但 first slice 为 native-only。 | Phase 7 非参考引擎 | D16+D15；ExecutionProfile threshold，或 canonical flow 改 native。 |
| UI-06 | LOW | `ACCEPT` | engine/scenario unsupported、request underdetermined、STALE_CONTRACT 可落多个轴，无唯一归属优先表。 | Phase 3 shadow comparison | §14.1 failure-to-axis table；D06/D16。 |
| UI-07 | MEDIUM | `ACCEPT_WITH_NARROWING` | legacy label 基本对齐；真正脆弱的是自由文本 reason/proof shape 被 §18.4 要求 exact 比较。 | Phase 3 fixture | 定义结构性对齐面与 expected-difference normalization。 |
| UI-08 | MEDIUM | `ACCEPT` | 轴→disposition/consumability 的 CombiningProfile 是产品语义核心，却无值域、映射或 D 项。 | Phase 3 首个 Assessment | 新 decision；§11.3/§14.2 v0 mapping。 |
| UI-09 | LOW | `DEFER_TO_PHASE_GATE` | PyReason EvidenceTimeline 无节点锚，需要 tree overlay 之外的显式降级 UI；首片不触发。 | Phase 7 PyReason | D15/D16 capability banner 与 timeline read model。 |
| UI-10 | MEDIUM | `ACCEPT` | deterministic NL 模板仍可能误译否定、量词和 checked scope；归属与保真门缺失。 | Phase 1 UI spike | 后端 renderer、golden fixtures、强制条件从句。 |

### 5.8 强制攻击案例（AC，10 项）

| ID | 审计严重度 | 处置 | 准确问题 | 最迟关闭 | 建议落点 |
|---|---|---|---|---|---|
| AC-01 | MEDIUM | `ACCEPT` | 与 AS-03/AS-11 同根：coverage/remainder/round-trip 若由 Translator 自报，案例 2/11 的防线为空。 | §18.2 benchmark；最迟 Phase 6 | 合并 D08/D12 服务端核算。 |
| AC-02 | MEDIUM | `ACCEPT_WITH_NARROWING` | 与 RR-01 同根：当前 Explain 漂移真实，迁移影响取决于是否进入评审工件。 | Phase 3 若消费，否则 Phase 4 | 合并 RR-01；§2.3/SDK digest guard。 |
| AC-03 | MEDIUM | `ACCEPT_WITH_NARROWING` | 合法重复查询也可黑盒推断 Policy 阈值；无法完全消除，只能明确接受范围、限速与审计。 | Phase 6 A1 | D05；§16.5 收窄“防外泄”声称。 |
| AC-04 | LOW | `DEFER_TO_PHASE_GATE` | Plan Lab release corpus 不会自动证明生产分布可靠；当前 shadow-only，尚非即时缺陷。 | 任何非-shadow disposition 前 | §18.1 生产抽样复标与持续门。 |
| AC-05 | LOW | `ACCEPT_WITH_NARROWING` | legacy v3 会把假设句存为 `claimed_by_agent`；权威闭包已防住，残余是 advisory、审计与学习污染。 | Phase 3/learning integration | D08/D14：append-only suspect-hypothesis annotation。 |
| AC-16 | MEDIUM | `NEEDS_DECISION` | “subject 不得自证”有文字不变量，却没有 subject/evidence 来源血缘可比对机制。 | Plan Lab metric；最迟 Phase 6 | §7.1/D08 source-lineage identity 与 `excluded(self_support)`。 |
| AC-18 | MEDIUM | `ACCEPT_WITH_NARROWING` | 错误差异与存在性查询可泄漏；严格恒定时延未必现实，应由威胁模型裁决。 | Phase 6 A1/跨租户查询 | D04/D05：统一外部错误、授权域求值、限速/审计、timing risk decision。 |
| AC-21 | MEDIUM | `ACCEPT` | 目标 `__query__` 与现行 generated/projection 命名都缺公共 authored-id 保留合同，存在真实碰撞与身份污染面。 | Phase 2 native slice | D02/D03、ID validator、collision fixture；synthetic/authored 分域。 |
| AC-22 | LOW | `DEFER_TO_PHASE_GATE` | branch cap 已实现，但 native/Soufflé row/time/memory 上限未兑现；D06 已登记预算。 | Phase 2 接真实 ledger 前 | D06、ExecutionProfile、巨基数 fixture。 |
| AC-24 | LOW | `NEEDS_DECISION` | D07 未写 mandatory 全枚举、遗漏 fail-closed 与部分执行失败语义。 | Phase 6 A1/J4 | D07、PinnedValidationRequest completeness、per-unit outcome。 |

## 6. 合并后的阶段队列

### 6.1 下一版候选文本前

- PM-01：把 Phase 0/1 收进产品门。
- PM-04/CE-11：恢复 Gate -1 的规范来源与量化证据纪律。
- PM-02/PM-08：拆开 MVP-0 与 post-gate Agent profile，产品核心改为 case/draft subject。
- CE-01：限定 `smallest` 的比较范围。
- 把“11 个 blocker”改成 phase-specific gates。
- 修正文档卫生项：SF-06/07、AS-10、RR-10；它们不改变架构。

### 6.2 Gate -1 产品 discovery

- 对 PM-03 做 standalone concierge / embedded evaluator 双包装验证，并产出 `standalone / embedded / both / neither` 的证据化处置；Gate -1 不预设必须选出唯一赢家。
- 绑定 PM-07 的真实 incumbent/native baseline，不用抽象“observability”替代。
- 用合法、脱敏、一次性 source bundle 关闭 PM-10，而不是先建 connector。
- 加入证伪实验 4 的 hidden-workflow/cascade coverage：检查 case bundle 是否覆盖直接决定之外的上下游依赖、级联后果与必要 sources；缺口必须显式形成 coverage gap，不能被逻辑结果吞成 false/pass。
- 加入证伪实验 7 的 blind native-log baseline：让目标 reviewer 在不知道实验臂的情况下对比 Meander artifact 与现有 QA/case-tool 原生或原始日志，测 reviewer minutes、追问次数、material-defect recall 与 false challenge；它与 UI 理解门不是同一实验。
- 对 PM-05 只做低成本错误来源对照与 automation-bias 测量；完整 wrong-but-consistent-source gate 留在 Phase 3。
- 预检 privacy/retention 可行性：合法数据访问、redaction fidelity、最小披露与 Translator prompt scope；这不替代真实数据阶段的正式 privacy gate。
- 产品门失败时，不进入 Phase 0/1。纯设计/审计可以继续；任何 spike 或内核实现必须另获用户显式批准，并满足预算封顶、可丢弃、不倒逼产品结论的条件。

### 6.3 Phase 0–1 fixtures / spikes

- CE-08：冻结 fixture/schema owner 与跨仓 pin。
- SC-01 在 spike 前先预注册 branch-scoped 与 reject-on-partial 两个候选语义及 paired fixtures；spike 可提供裁决证据，但不得默认沿用当前 lowering。SC-03/05/06 同样用编译器与领域 fixture 关闭 Policy v0 分叉；SC-02 authored→lowered lineage 必须在 spike 出口形成可验收结果，不能推迟给 Phase 2 临场决定。
- PM-06：定义 evidence freshness 的独立状态、policy 归属及最小 fixture；replay pin 留给 Phase 4。
- UI-03/04/10、AS-08：冻结读模型、语言渲染和理解门方法。
- CE-04：给小团队实验设置预算、盲化与独立 adjudication。
- AC-16：在 Plan Lab 的 self-support 指标冻结前，先裁定 subject/evidence source-lineage identity 与排除规则。

### 6.4 §18.2 Translator benchmark entry gate

- AS-03/AC-01 必须先关闭：coverage 分母、Phase A freeze、Phase B revision/diff 与服务端可核算字段须在 benchmark 开跑前确定。
- 若 benchmark 声称验证 authoritative source admission 或 locator round-trip，AS-11 也必须先指定 Meander Source Resolver 的执行职责；否则只能报告 translation fidelity，不能把自报字段称为 verified。
- D12 必须区分 producer-claimed、transport-attested 与 server-verified；BYOK 无原文场景要显式降级保证。

### 6.5 Phase 2 FactGraph native slice

- 关闭 SC-07/08/11/12、UI-01、AC-21/22。
- 不把 SC-01 当现行 bug 修；先由 decision 选择 branch-scoped 或 reject-on-partial。
- Phase 2 只消费已经通过 Phase 1 gate 的 authored→lowered lineage 语义；实现合成与 authored identity 分域。

### 6.6 Phase 3 dual-run / Assessment

- 关闭 CE-03/SF-04/RR-08 的双跑拓扑与投影 owner。
- 在 adapter schema/preflight 前关闭 SF-01/02/03；同时关闭 SF-05 workspace migration。
- 关闭 UI-02/06/07/08 的 Assessment 轴、CombiningProfile 与 comparison normalization。
- CE-02 在入口前定义 burden ledger 的基线、主体与计时维度；CE-09 为实际启用的 scaffold 指定 owner、复审日期与退出条件。
- 执行 PM-05 正式 wrong-but-consistent-source gate，验证条件化警示与 reviewer automation bias。
- shadow comparison 一旦消费 Explain，必须先为 RR-01/AC-02 启用 digest guard，或明确只消费 eager frozen proof。
- 若使用真实多租户数据，必须先关闭 AS-02/CE-05 及正式 privacy gate；否则严格限制为合成或脱敏单租户材料。

### 6.7 Phase 4 Run / replay / Explain

- 先做 4a bundle capture/replay，再做 4b outer PolicyStructure/UI。
- 关闭 RR-01/02/03/04/06/09；RR-07 仅在 workflow 使用 reference data/resolver 时前置。RR-05/11 留在 Phase 5，RR-08 应已在 Phase 3 关闭。
- 完成 PM-06 freshness policy 的 replay pin、CE-02 burden evidence 与 CE-06 retention/erasure/replay decision。
- 若 authoritative SourceRecord admission 首次在此出现，先关闭 AS-11；否则它随更早的 Translator benchmark gate 关闭。
- 历史 Explain 不得换 config，也不得以旧结果身份读取活证据。

### 6.8 Phase 5 Scenario

- 关闭 SC-09/10、RR-05/11；v1 只承诺它实际能产生的状态。
- Scenario resolution/error semantics 不得形成隐藏事实的存在性或基数 oracle；D09/信息边界 decision 决定采用授权 resolution view、外部错误粗化或二者组合，而不是由本文预选唯一机制。

### 6.9 Phase 6 Agent/Translator pilot

- 关闭 AS-01/05/06/07/09 与 AC-03/18/24；落实已由 Plan Lab/source-lineage gate 裁定的 AC-16 机制。
- CE-07：冻结 L1 latency、timeout、异步/polling 与 dependency-failure 合同。
- 若启用 L0，执行已在 §18.2 entry gate 关闭的 AS-03/AS-11/AC-01 协议；Translator 的 coverage、round-trip、admission 不得由同一不可信 producer 自证。
- A1 的 bind/select/exists、mandatory Policy、caller/reviewer 双视图必须先有可执行合同。

### 6.10 Phase 7 / deferred

- UI-05、UI-09 仅在概率/非参考引擎进入产品面时关闭。
- CE-10 不构成删除 Package/learning shape 的理由；是否保留在正文属于编辑选择。

## 7. 不采纳的修订方式

1. 不把全部 83 条转为当前 backlog。
2. 不把所有 HIGH 都改写为“下一个实验前 blocker”。
3. 不因 SC-01 直接修改现行 lowering；先裁定目标 Policy 语义。
4. 不在 legacy snapshot 中复制 `GovernanceSnapshot.agent_authority`。
5. 不把 UI gate 的样本数机械写成 `n≥5`；方法、角色、判分和阈值须预注册并说明依据。
6. 不为 packaging、tenant、dual-run 等不同问题重复抢用同一个 `D19`；正式决策时统一编号。
7. 不因 CamelCase 类型数量删除承重不变量，也不把完整 target map 误作一次实现切片。
8. 不把“conditional Agent architecture”误判为“已经授权以 Agent 为 MVP 楔子”。
9. 不把 `0 undefended` 当作已建成防御；很多 partial defense 仍依赖未来 gate。

## 8. 候选 decision backlog（尚未 adopted）

下列只是从矩阵提取的 load-bearing questions，不分配正式 D 编号，也不替代 ADR：

| 临时问题键 | 问题 | 来源 |
|---|---|---|
| Q-PRODUCT-GATE | Phase 0/1 的唯一合法前置与量化 Gate -1 证据是什么？ | PM-01/04、CE-11 |
| Q-PACKAGING | standalone concierge、embedded evaluator、OEM 的证据化处置是 standalone、embedded、both 还是 neither？ | PM-03/07 |
| Q-WORKFLOW-COVERAGE | case bundle 如何衡量 hidden workflow、上下游依赖与级联后果的 source coverage，并如何呈现缺口？ | 证伪实验 4、PM-10 |
| Q-BLIND-BASELINE | Meander artifact 与原生/原始日志盲审的统计单位、实验臂和 reviewer-value 指标是什么？ | 证伪实验 7、PM-04/07、UI-04 |
| Q-JOIN-ANY | partial-branch explicit join 是 branch-scoped 还是编译拒绝？ | SC-01 |
| Q-RULE-CAPABILITY | Policy v0 允许组合哪些含 Not/Aggregate 的 managed Rule？ | SC-03/06 |
| Q-CONTRACT-DIGEST | semantic port/schema digest 的局部粒度与迁移机制是什么？ | SC-04/05 |
| Q-DUAL-RUN | 同名包、双环境、输入投影、artifact owner 与 rollback 如何组织？ | CE-03、SF-04、RR-08 |
| Q-TENANT | 所有 artifact/cache/index/export/content address 如何绑定 credential-derived tenant？ | AS-02、CE-05 |
| Q-PRIVACY | redaction fidelity、最小 source disclosure、Translator prompt scope、UI/export 权限与 retention kill 如何被可执行地验证？ | 攻击案例 17 完备性缺口、AS-02、CE-06 |
| Q-TRANSLATION-PROTOCOL | 谁冻结 Phase A、定义 coverage 分母、验证 round-trip，并记录 Phase B revision？ | AS-03/09/11、AC-01 |
| Q-SOURCE-LINEAGE | AssessmentSubject 与 candidate evidence 如何比较来源身份、派生血缘并执行 `excluded(self_support)`？ | AC-16、D08 |
| Q-POLICY-ROUTING | routing provenance、mandatory 完备性、excluded candidate 与 caller/reviewer 视图是什么？ | AS-05/06、AC-24 |
| Q-ASSESSMENT | outcome axes、CombiningProfile、disposition/consumability 的合法映射是什么？ | UI-01/02/06/08、AS-08 |
| Q-REPLAY-RETENTION | capture/as-of、retention/erasure、部分 replay 与 cutover 如何共同成立？ | RR-01/02/04/06、CE-06 |
| Q-INFORMATION-BOUNDARY | bind/select/exists/error/timing 与黑盒 Policy 推断接受什么风险？ | AS-01、AC-03/18、SC-09 |

## 9. 下一步决策门

本矩阵完成后，不应立即把全部 accepted 行回填候选。下一步应先由用户选择以下之一：

1. **仅修当前一致性**：只处理 §6.1 的“现在”项，生成 Review Freeze v0.1.1；
2. **形成第二版候选**：将 accepted gates 与 decision backlog 分阶段吸收，生成 v0.2 review candidate；
3. **先闭合产品门协议**：只处理 Q-PRODUCT-GATE/Q-PACKAGING，保持技术设计冻结；
4. **先攻最高语义风险**：只处理 Q-JOIN-ANY、Q-TRANSLATION-PROTOCOL、Q-SOURCE-LINEAGE、Q-POLICY-ROUTING。

非约束性的风险顺序建议是：先做选项 1，得到不误导授权的 v0.1.1；若用户随后仍要推进产品论证，再做选项 3。选项 2/4 应等待产品门信号，或另获预算封顶、可丢弃的研究授权。

这些选项均不授权实现。正式修改候选或起草 adopted decision 需要新的明确授权。

## 10. 输入 manifest

| 文件 | SHA-256 |
|---|---|
| 主报告 | `8ac1c7638a82f0a26a5ba2f4a722255370424086f506727af1a8108aa6a41166` |
| `dim1_product-market.zh.md` | `bdf840bfa593f4603f48101ecd463e44f546316eb8653e8b3b2627282e3ba34d` |
| `dim2_semantic-core.zh.md` | `5056a8bed0b7f71d9dec2ea9f4c84c9fd445159802652fdcfd3e6ea536438c05` |
| `dim3_shipped-fidelity.zh.md` | `5245e7be4b74827abf9c05ea9e5af8313e4ce41b565fbf0bca3c301b14ce4b48` |
| `dim4_agent-authority-security.zh.md` | `9bde0d28e400117c039eb3345b7d3f9124518e1d685224b652ba7878c26a8349` |
| `dim5_run-replay-persistence.zh.md` | `f0283b50b5b6d0b9b851e751b0dd5fa9a050a7b8a82746feeb442331d1dc9e5c` |
| `dim6_ui-failure-semantics.zh.md` | `33a1b46c6c3e560288b7480f4aa2eeb6c04b9b79c55db289d5bdf509b3e13310` |
| `dim7_complexity-economics.zh.md` | `c94da00e5f67ebfab08f0b4b3d321b98ef9a4247462006a8804011a802a8e7c4` |
| `attack_cases_01-13.zh.md` | `c008adddc7c208960f3cb07e31227bafb87c84a6adae13b79fcfa5951ca58dd9` |
| `attack_cases_14-25.zh.md` | `1bfead11fbe67b847bdabc12a19f9799147febf738da585d5a113e92c48fd603` |

## 11. Status notes

- 2026-08-10：建立首版完整 disposition；Review Freeze 与 Meander/FactGraph shipped 源码均未修改，仅新增本 design-point 并更新 design-point 索引。
- 2026-08-10：对抗审核方复核后的收敛修订——SC-01 改为“构造合法、当前 lowering 行为可观察，但 asymmetric 语义未测试/未规格化”；PM-02 改为 `ACCEPT_WITH_NARROWING`；补入证伪实验 4 hidden-workflow/cascade coverage 与实验 7 blind native-log baseline；处置分布更新为 `32/23/16/10/2`。Review Freeze 与 shipped 源码保持不变。
- 当前状态为 `working`。它是下一轮讨论的索引，不是已 adopted 的修订决定。
