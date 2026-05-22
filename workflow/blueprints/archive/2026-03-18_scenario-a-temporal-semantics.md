# Task Blueprint: Scenario A Temporal Semantics

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/authoring`
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/adapters`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_ecss-scenario-anchoring.md](./2026-03-18_ecss-scenario-anchoring.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/authoring/docs/01_overview.md](../../../src/factpy_kernel/authoring/docs/01_overview.md)
  - [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](../../../src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-18_scenario-a-temporal-semantics.audit.md](./2026-03-18_scenario-a-temporal-semantics.audit.md)

## 1. Problem

`Scenario A`（`ESSB-ST-U-007` 风格的碎片缓解 / debris-mitigation）已经被母蓝图明确为中期驱动场景，但当前代码基线仍缺少一层最关键的 runtime contract：

- 读侧已有业务时态过滤：`.at(t)` / `.version(v)`
- 写侧已有 `valid_from / valid_to / version` 元数据承载
- 但 runtime rule / derivation / service 链路明确不接受 `temporal_view`
- derivation head 也还没有时态写语义

这说明项目今天只有“时间作为数据 / 读视图过滤”，还没有“时间作为推理语义”。

对于 `Scenario A`，这会直接卡住以下问题：

- 处置时限是否在规定窗口内满足；
- conjunction / risk 事件是否落在具名时间窗口内；
- 某个 obligation 是否在一段连续时间或事件序列上成立；
- explain / audit 如何把“命中的时间锚点与窗口”一起交付。

如果不先收敛 temporal semantics，就会把 `Scenario A` 的压力错误地分摊到：

- `uncertainty-and-confidence`
- 某个具体引擎（如 `PyReason`）
- 或某种 proof / UI 交付形态

因此，这个切片先解决“最小 temporal semantics contract 是什么”，再决定后续实现顺序。

## 2. Goals

- 为 `Scenario A` 定义第一条可实现的 temporal semantics 子切片。
- 明确区分：
  - 读侧 business-time filter
  - runtime temporal reasoning
  - 未来可能的 temporal write/materialization
- 收敛出一个 **engine-neutral** 的时间语义 contract，避免先让某个 adapter 偷偷拥有语义。
- 明确第一轮真正需要支持的 temporal pressure：
  - point-in-time comparison
  - interval containment / overlap
  - named deadline / bounded window checks
- 指出哪些内容必须延后到后续切片：
  - state propagation
  - richer uncertainty semantics
  - staged multi-engine planning
- 为后续进入 `scoped` 的实现任务准备接受标准、文档落点和测试入口。

## 3. Non-goals

- 不在本蓝图中把 `ESSB-ST-U-007` working note 的数值阈值写成系统事实。
- 不在本蓝图中直接恢复 `temporal_view` 参数。
- 不在本蓝图中直接决定 `PyReason` 的架构角色。
- 不在本蓝图中设计完整的 temporal materialization / temporal head write 协议。
- 不在本蓝图中解决完整的 `uncertainty-and-confidence` 语义。
- 不把 Rainbird 的 evidence tree / certainty 模型当作本项目的 target contract。

## 4. Current Context

- 当前实现入口：
  - SDK 读视图已经支持 `.at(t)` / `.version(v)`。
  - 写入路径可通过 `meta` 携带 `valid_from / valid_to / version`。
  - `authoring` / `sdk` / `service` runtime 链路都显式拒绝 `temporal_view`。
  - explainability 第一阶段已完成，已有 `support artifact`、`rule trace`、`explain_ref` 和 audit package export。
- 当前已知约束：
  - append-only ledger、accept 语义、audit/provenance 不能被新的时间语义破坏。
  - 时间语义必须先在 kernel/authoring contract 层收敛，再讨论 adapter 分工。
  - 当前 `Body.confidence`、`CandidateSet.confidence`、`confidence_strategy` 还不足以承载 `Scenario A` 的 uncertainty pressure。
  - 近期 explainability 的排序仍是 `audit-log first / proof-tree next`，不应被 Scenario A 反向打乱。
- 当前相关蓝图与参考：
  - 母蓝图已把 `Scenario A` 判定为真正需要 `temporal semantics + uncertainty semantics` 的场景。
  - `Scenario B` 已闭环，因此当前可以把注意力转回中期时间语义。
  - `docs/references/external/rainbird-evidence-chain-compare.md` 只作为证据链交付和 proof-entry 讨论的参考，不构成当前实现真相。

## 5. Proposed Shape

### 5.1 Adopted Narrowing

`Scenario A` 的第一条 active 子蓝图先只处理 **temporal semantics**，不把 `uncertainty-and-confidence` 混进来。

原因：

- 当前 runtime 最大硬缺口是“没有时间推理 contract”，而不是“已经有时间 contract 但不够精细”。
- 若在这个阶段同时引入 uncertainty，会把问题混成：
  - 时间窗口判定
  - 概率/certainty 语义
  - 引擎选择
  三个维度一起动，无法稳定冻结边界。

因此，当前 adopted narrowing 是：

- 先定义 `Scenario A` 的最小时间语义
- 再决定 uncertainty 子蓝图怎么切

### 5.2 Semantic Ladder

本蓝图建议把时间能力分成三层，不一次吃完：

1. `T0: existing business-time reads`
   - 已存在的 `.at(t)` / `.version(v)`
   - 只影响读视图，不是 runtime reasoning

2. `T1: explicit temporal checks in runtime reasoning`
   - 在 rule / derivation 的 runtime contract 中支持有限的时间判断
   - 目标是表达：
     - 某事件是否早于/晚于某锚点
     - 某事件是否落在某 deadline/window 内
     - 两个区间是否包含/重叠
   - 这一层不要求 state propagation，也不要求 temporal head write

3. `T2: state propagation / temporal materialization`
   - 例如连续状态、区间传播、窗口累计状态、事件驱动状态更新
   - 这一层更接近长期的 temporal-hybrid 目标，不作为第一步

当前蓝图只收敛 `T1`，不直接推进到 `T2`。

### 5.3 Authoring / Runtime Contract Direction

第一轮 temporal semantics 不应通过恢复全局 `temporal_view` 来实现。

当前更合理的方向是：

- 继续保持 runtime “基于 active assertion set” 的主路径不变；
- 通过 **显式 temporal predicates / temporal builtins / IR extension points** 表达时间比较；
- 把“命中哪些 assertion + 用了哪个时间锚点/窗口”纳入 support / trace 交付。

这样做的好处：

- 不会把一个全局 view knob 重新塞回 runtime；
- 语义更局部、更可审计；
- 更容易被多个 engine 共享；
- 不会提前承诺 temporal write/materialization 形态。

> **L1（adopted）：T1 temporal checks 通过显式 temporal predicates + 已有比较语法（`>= <= < >`）表达，不新增 where atom tag 或 `temporal_check` 内置类型。**
>
> - deadline satisfaction：obligation timestamp predicate + 比较 `$event_ts < $cutoff_ts`
> - window membership：event timestamp + window_start/window_end predicates + 双侧比较
> - interval relation：通过带 `expose=True` 的 helper rule 表达，不新增 core AST 节点
>
> **T1 temporal predicates 使用 canonical scalar 时间值：schema/protocol tag `"time"`，表示 int epoch 纳秒时间戳。不复用读侧 `valid_from/valid_to` 的 ISO 8601 业务时间口径。** 混用两种口径会在 authoring 和 explain 上产生返工。
>
> 这样做不需要改 `where_ast`、`where_eval`、`validate_where_ast`；比较链已足够承载 T1 语义。

### 5.4 Minimum Scenario-A Target

为了避免 scope 发散，第一轮只针对以下问题类型建模：

1. `deadline satisfaction`
   - 某 obligation 是否在一个具名截止点之前满足

2. `window membership`
   - 某事件或事实是否落在具名时间窗口内

3. `interval relation`
   - 两个区间是否包含、重叠或相离

明确暂不纳入第一轮的内容：

- 连续状态传播
- 多步事件序列上的状态机语义
- 带不确定性传播的时间聚合
- deontic / waiver 全量语义

> **L3（adopted）：第一轮 Scenario A temporal predicates 归属 `factpy_kernel.ecss.temporal` 模块，不提升为顶层通用模块。**
>
> - 该模块只拥有 Scenario A 驱动的 domain preset（temporal predicate schema constants、`ecss_temporal_predicates()`、`extend_schema_ir_with_ecss_temporal_predicates()`）
> - 不把通用 runtime semantics 或 explain helper 塞入该模块
> - 与 `factpy_kernel.ecss.vcd` 对称，等 temporal semantics 成熟到跨 domain 时再评估是否提升

### 5.5 Explain / Delivery Expectations

Rainbird 可以作为“证据链交付要让用户摸得到”的参考，但不能照搬它的 certainty 或 backward-chaining 模型。

对当前蓝图更有用的 adopted conclusion 是：

- temporal reasoning 一旦进入 runtime，就必须能在 explain / audit 中带出：
  - evaluation anchor
  - matched interval or deadline
  - contributing assertions
- proof entry point、structured JSON explain、shareable audit page 这些交付形状可以参考 Rainbird，但不是本蓝图第一轮 acceptance 的阻塞项
- 当前仍以 audit-log / trace-first 为优先，而不是先做 visual evidence tree

> **L2（adopted）：temporal anchor 在 explain / audit 中的落点：**
>
> - **主路径（C）：`pred_witnesses`**。凡是参与 temporal check 的 predicate assertion（如 `ecss:obligation_timestamp`、`ecss:window_start`），其 `asrt_id` 会进入 `pred_witnesses`，消费方可通过 `explain_ref(kind="assertion")` 下钻。
> - **辅助路径（A）：`non_fact_steps.details.binding` opaque passthrough**。比较变量的绑定值（如 `$event_ts = 1741234567000000000`）通过已有 opaque passthrough 带出，不新增 `RuleTraceArtifact` schema 字段。
>
> **凡是希望用户能 drill-down 的 temporal anchor，必须 fact-backed（predicate assertion）或至少 var-bound（通过变量出现在 `pred_witnesses`/`details.binding` 中）。把 cutoff/window 边界直接写成裸常量的比较，只能留在 `details.atom` opaque 里，不支持 `explain_ref` 下钻。** 这条约束在 predicate schema 设计阶段就要执行，不能留到 explain 实现阶段再补。

### 5.6 Scalar Time Convention

T1 实现中所有时间值统一遵守以下约定：

| 用途 | 口径 | 类型 |
| --- | --- | --- |
| T1 temporal predicate 的时间参数 | epoch 纳秒整数 | schema tag `"time"`，Python `int` |
| `meta.valid_from / valid_to` 读侧 | ISO 8601 字符串 | SDK 读视图 `.at(t)` |

两者不能混用。T1 temporal predicates 的 arg spec 必须声明 `type_domain: "time"`（`int` epoch ns），不能用 `string`。这保证了 where 比较链可以直接对两个 `"time"` tag 值做整数大小比较，不需要解析字符串。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `temporal_view` 继续保持移除状态，不能作为简单回滚方案重新引入
  - 时间语义先定义为 shared contract，再谈 adapter-specific 支持
  - `Scenario B` 已归档的 VCD/compliance 路径不被重新打开
  - unsourced ESSB 数值只能作为 scenario pressure，不作为标准真相
- 明确不做的内容：
  - 不在本蓝图中实现完整 uncertainty semantics
  - 不在本蓝图中承诺 proof-tree UI 或 live trace API
  - 不在本蓝图中定义完整 deontic ontology
- 兼容性约束：
  - 现有 `.at(t)` / `.version(v)` 读契约保持不变
  - 现有 `accept`、`support artifact`、`rule trace`、`audit package` 行为保持兼容
  - 若新增 temporal contract，需在 `core` / `authoring` / `sdk` / `service` docs 中同步说明

## 7. Acceptance

- [ ] `Scenario A` 的第一轮时间语义范围已冻结为 `T1`，没有偷偷扩成 uncertainty 或 engine selection 任务
- [ ] 新的 temporal semantics contract 与现有 `.at(t)` / `temporal_view removed` 边界不冲突
- [ ] T1 temporal predicates 已定义，归属 `factpy_kernel.ecss.temporal`，不在 `ecss.vcd` 或独立顶层模块
- [ ] 所有 temporal predicate arg spec 使用 `type_domain="time"`（int epoch ns），不使用 ISO 8601 string
- [ ] deadline / window / interval relation 可通过 temporal predicate + 已有比较语法在 rule/derivation 中表达，不需要新 where atom tag
- [ ] temporal anchor 的 drill-down 路径已明确：fact-backed predicates 进 `pred_witnesses`，var-bound 比较进 `details.binding`
- [ ] `RuleTraceArtifact` schema 不因 T1 实现而新增字段
- [ ] `ecss.temporal` 模块只拥有 Scenario A domain preset，不包含通用 runtime semantics 或 explain helper
- [ ] 受影响模块 docs 已明确更新落点（`ecss/docs/01_overview.md`、`sdk/docs/03_rules_and_derivations.md` §9）
- [ ] 若进入实现，蓝图已从 `draft` 移到 `scoped`

## 8. Implementation Plan

1. 把 `Scenario A` 的时间压力收敛成最小问题集：deadline、window、interval relation。
2. 对齐 `core` / `authoring` / `sdk` / `service` 当前边界，明确第一轮 temporal contract 不能走 `temporal_view` 回滚。
3. 明确 explain / audit 在 temporal 场景下最小需要带出的 anchor 信息。
4. 形成第一轮 contract 草案后，再判断是直接进入实现，还是先拆出 `uncertainty-and-confidence` 兄弟蓝图。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/authoring/docs/01_overview.md`
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `factpy_kernel.ecss.temporal` shared preset owner，提供 `obligation_timestamp`、`window_start/window_end`、`interval_start/interval_end` 以及 `extend_schema_ir_with_ecss_temporal_predicates(...)`
  - 第一轮 `T1` 时间语义以 existing comparisons 落地：deadline / window check 直接通过 predicate + `<=` / `>=` 表达，interval relation 通过 helper rule + `RuleRef` 回归验证
  - explain / audit 沿用现有 contract：fact-backed temporal anchors 进入 `pred_witnesses`，比较绑定值进入 `non_fact_steps.details.binding`，未新增 `RuleTraceArtifact` 字段
  - `ecss`、`core`、`authoring`、`sdk`、`service` 模块文档已同步更新
- 与 blueprint 不同的地方：
  - 没有新增 `sdk` 层 temporal convenience wrapper
- 为什么会有这些调整：
  - 当前切片的核心是 shared preset owner 与 existing comparison contract；新增 `sdk` facade 会扩大表面，但对验收不构成必需条件
- 归档说明：
  - 本蓝图已完成第一轮 `Scenario A / T1 temporal semantics` 最小落地，归档到 `docs/blueprints/archive/`
