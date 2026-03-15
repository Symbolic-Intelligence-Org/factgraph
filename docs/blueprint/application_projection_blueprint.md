# Application Projection Blueprint

## Goal

定义一套独立于前端文档的 application / projection 蓝图，用于约束：

- 分层边界
- SDK 与 service 的关系
- 单一 `Entity` 模型下的表示方式
- 关系归并与绑定机制
- 公共层抽取方向

相关补充文档见：

- `docs/frontend_entity_ui_design.md`
- `docs/application_protocol_spec.md`
- `docs/blueprint/实时服务与物化层蓝图.md`
- `src/factpy_kernel/application/docs/README.md`

## Scope

本蓝图关注 `core` 之上的产品应用层。

职责包括：

- entity-centric read model
- entity-centric write planning
- graph projection
- relationship family
- binding and auto-completion
- service DTO

不包括：

- core storage kernel 规则重写
- 前端视觉样式
- Python authoring ergonomics

## Layering

本设计要求明确分层：

- `core`: `Entity / Identity / Field / entity_ref / assertions / derivation / conflicts`
- `application/projection`: 实体读模型、批量写入规划、图投影、关系归并、绑定、推荐写入口
- `service`: session、HTTP API、参数校验、DTO 编排
- `frontend`: 只消费 service DTO

约束：

- 不修改底层事实模型
- 不在 schema 中新增 projection 专用 meta
- 不建议把产品逻辑直接堆在 HTTP handler 中

## SDK Boundary

### Principle

`SDK` 是 authoring facade，不应成为前端 service 的 foundation。

service 可以兼容 SDK 输入，但核心实现不应绑定 `SDKStore`。

更准确地说：

- SDK 独有的是 Python 包装方式
- 不是 SDK 独有的是其背后的运行机制

因此目标关系应当是：

- `sdk/` 与 `service/` 都是对共享中性机制的不同包装
- 而不是 `service` 建立在 `SDKStore` 之上

推荐数据流：

`SDK classes / authoring payload -> schema_ir / compiled payload -> application/projection -> service DTO -> frontend`

而不是：

`SDKStore -> service -> frontend`

### SDK-Specific Facade Objects

以下对象本身属于 SDK facade：

- `Entity` Python class
- `Rule` / `Derivation` / `Query` Python DSL object
- `SDKStore`
- `SDKBatchTx`
- `EntitySnapshot`
- `EntityEditor`

它们适合：

- Python 开发者 authoring
- 本地脚本
- 测试
- 示例

它们不应成为前端 service 的基础抽象。

这些对象的价值在于：

- authoring ergonomics
- Python 可读性
- 开发者体验

而不是作为产品 runtime 的统一内部模型。

### Shared Runtime Concepts

以下能力本质上不是 SDK 独有，应尽量依赖公共层：

- `schema_ir`
- authoring payload
- compiled rule / derivation payload
- `Store`
- rule execution
- derivation evaluation
- conflicts / chosen / mapping resolution

也就是说：

- `Entity` / `Rule` / `Derivation` / `Query` 这些 SDK 类本身不应原样迁出
- 但它们背后的中性声明、payload、IR、compile/lower/validate 机制应进入共享层

## Current Gap In Code Structure

从当前代码结构看，确实存在“有些高层能力目前只在 SDK 内实现”的情况。

## Implementation Status

截至当前阶段，Blueprint 的核心迁移目标已经完成第一轮验证：

- `application/protocol` 已定义并落地 Phase 0 DTO
- `application/schema_runtime.py` 已落地
- `application/entity_view.py` 已落地
- `application/entity_write.py` 已落地
- SDK 读侧已委托 `application/entity_view.py`
- SDK 批写 preview/apply 已保守委托 `application/entity_write.py`

当前状态可概括为：

- `service` 已具备不依赖 `SDKStore` 的 entity-centric read/write 基础能力
- SDK facade 已不再独占这些运行机制
- `core` 事实模型与 ledger/store 未被修改

### Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: protocol DTO | completed | `application/protocol/*` 与协议文档已落地 |
| Phase 1: `schema_runtime` | completed | `SchemaIndex`、selector/ref 解析、field type 信息已落地 |
| Phase 2: `entity_view` | completed | hydration、`get/find` read path 已落地 |
| Phase 3: `entity_write` | completed | 单目标 write planning / apply 已落地 |
| Phase D-read: SDK read delegation | completed | `sdk_get` / `sdk_find` 已委托 application |
| Phase D-write: SDK write delegation | completed | `SDKBatchTx.preview/apply` 已保守委托 application |
| Phase 4: `query_view` | pending | 仍主要在 SDK query lowering/runtime 中 |
| Phase 5: `authoring_normalize` | pending | 仍主要在 `sdk/store.py` |
| Phase 6: `graph_projection` | pending | 尚未开始 |
| Phase 7: `binding` | pending | 尚未开始 |

### Verified Outcome

当前已经验证的核心结论：

- SDK 独有的是 facade 形式，不是背后的运行机制
- `sdk/` 与未来 `service/` 可以共同依赖 `application/`
- `service` 不需要建立在 `SDKStore` 之上
- 不需要修改底层事实模型，也能把 entity-centric read/write 从 SDK 中抽出来

### Current Conservative Boundaries

当前实现刻意保守，以下边界仍然保留：

- SDK batch 写侧只有在整批 staged writes 都能被 application 协议表达时才委托 application
- 如果批中存在 raw `entity_ref` token、`bytes`、非 JSON-safe meta，或 application planner 无法稳定表示的值，整批回退到 legacy batch 路径
- `BatchPlan.ops` / `export()` / `to_json()` / `WireBatchPlan.apply()` 保持 legacy 语义，不依赖 application DTO
- `application/entity_write.py` 当前仍以单目标 `EntityWriteCommand` 为 canonical planner，不直接表达 multi-root atomic batch
- `query_view`、`graph_projection`、`relationship_family`、`binding` 仍未开始实现

### Already Shared

以下能力已经比较健康，service 不需要依赖 SDK facade：

- rule compile
- derivation compile
- core rule execution
- runtime store/session

### Migration Status Of Higher-Level Capabilities

以下能力在迁移后的状态如下：

1. entity-centric read model
   - 已抽取到 `application/entity_view.py`
   - SDK `sdk_get` / `sdk_find` 已委托 application
2. entity-centric write planning
   - 已抽取到 `application/entity_write.py`
   - SDK batch preview/apply 已委托 application，保留保守 fallback
3. schema runtime helpers
   - 已抽取到 `application/schema_runtime.py`
   - SDK 与未来 service 可共享相同索引与 selector/ref 解析逻辑
4. entity-centric edit facade
   - `sdk_edit`
   - `EntityEditor`
   - 仍保留在 SDK facade 层
5. query object lowering and hydrated results
   - `QueryPlan`
   - `execute_query_plan`
   - 仍主要在 SDK

这些能力说明了两个事实：

- 部分运行机制已经成功迁出 SDK
- 剩余未迁部分更多是 query / projection / authoring normalize，而不是 entity-centric read/write 本身

## Representation Patterns

当前底层只有一个灵活的 `Entity` 类，这本身不是问题。

真正缺少的不是新类型，而是“如何用同一个 `Entity` 表示不同语义对象”的设计约定。

本设计在不修改 core 的前提下，引入一套 application/projection 可识别的表示模式。

### Pattern 1: Primary Entity

表示独立的领域对象。

例子：

- `User`
- `Country`
- `Language`
- `Company`

特征：

- 有稳定业务身份
- 会被独立搜索、列表展示、打开详情页
- 即使包含多个 `entity_ref` 字段，也仍然是 node

identity 建议：

- 优先使用自然键或业务键
- 不因图展示需求修改 identity 结构

### Pattern 2: Summary Field

表示主实体上的“当前状态摘要”。

例子：

- `User.can_speak: Language`
- `User.lives_in: Country`
- `User.employer: Company`

特征：

- 属于主实体的一部分
- 适合高频读写
- 表示“当前认定的状态”，而不是关系对象本身

### Pattern 3: Relation State Entity

表示“关系本身是一个对象”，但它仍然描述当前状态，而不是一次事件。

例子：

- `Speaks(user, language, level)`
- `LivesIn(user, country, since)`

适用条件：

- 关系本身有附加属性
- 关系需要被独立查询
- 关系可能需要自己的生命周期、来源或审批信息

identity 建议：

- 如果语义上“同一组角色只能存在一个当前关系”，优先用角色组合作为 identity
- 不要默认使用随机 `uid`
- 只有在允许并存多条记录时，才使用合成 id

### Pattern 4: Association Entity

表示多元关系或复杂关系对象。

例子：

- `EmploymentEvent(user, company, contract, start_date)`
- `Transfer(from_account, to_account, operator, currency, amount)`

特征：

- 有 3 个及以上角色
- 或关系本身在领域上很重要
- 不适合压成单条图边

### Pattern 5: Event / Observation Entity

表示一次事件、观察、证据或记录，而不是当前状态本身。

例子：

- `LanguageObservation`
- `ResidenceRecord`
- `EmploymentChangeEvent`

特征：

- 强调“发生过一次”
- 往往有时间、来源、证据、操作者、批次等上下文
- 多条记录可以并存

identity 建议：

- 通常使用 `uid` 或其他合成键
- 不应与“当前状态摘要”混为同一个写入面

## Representation Selection Guide

新建 schema 表达时，建议按下面顺序决策：

1. 这是独立领域对象吗？
   如果是，使用 `Primary Entity`
2. 这是主实体的当前状态摘要吗？
   如果是，使用 `Summary Field`
3. 这是一个具有自身属性的当前关系吗？
   如果是，使用 `Relation State Entity`
4. 这是三元以上关系或复杂关系吗？
   如果是，使用 `Association Entity`
5. 这是事件、证据或观察吗？
   如果是，使用 `Event / Observation Entity`

## Representation Rules

### Rule 1: Separate State From Event

“当前状态”和“事件记录”不能混为一种表示。

例如：

- `User.lives_in` 表示当前居住地
- `ResidenceRecord` 表示一次居住记录

两者可以共存，但不应共享同一个写入语义。

### Rule 2: Avoid Dual Canonical Writes

如果同一业务关系同时存在：

- 一个 `Summary Field`
- 一个 `Relation State Entity`

则只能有一个 canonical write path。

另一个只能是：

- 读投影
- 汇总结果
- 推导结果
- 对账视图

### Rule 3: Identity Encodes Semantics

在不增加 meta 的前提下，identity 设计本身要承担一部分“表示语义”。

经验规则：

- 角色组合 identity 更像“当前状态关系”
- 随机 `uid` identity 更像“事件/记录/观察”

这不是绝对规则，但足够作为 application 层的保守判断基础。

## Graph Projection Model

application/projection 层负责图投影，不修改底层 schema。

### Phase 1: Raw Graph

先构建一个保守的原始图：

- 每个 `Entity` 实例都是 node
- 每个 `entity_ref` 字段都是 field edge

这一步不做折叠。

### Phase 2: Visual Collapse

在 raw graph 之上，才尝试把一部分 relation-like entity 折叠为边。

折叠条件：

1. 恰好存在 2 个核心 `entity_ref` 字段
2. 其余字段为少量附加标量或系统型 identity
3. 该实体主要用于连接两个端点
4. 当前视图下不存在明显歧义

一旦不满足条件：

- 退回 node 表示

### Conservative Rule

不能采用“只要有两个 `entity_ref` 就是边”的简化规则。

例如：

- `User.can_speak -> Language`
- `User.lives_in -> Country`

这里 `User` 只是“有两条字段边的节点”，不是关系边。

## Relationship Family

同一业务连接可能同时以多种形式出现，例如：

- `User.can_speak: Language`
- `Speaks(user: User, language: Language)`

这类重叠不一定是坏事，可以被 application/projection 利用为“多层表示”机制。

### Read Side

application 层可以把结构上相近的表示聚合到同一个 relationship family 中统一展示。

统一展示的目标是：

- 前端只看到一个关系族
- 每条关系可展示多个来源
- 相同端点对的多条支持证据可以合并呈现

### Write Side

写入侧不能自动双写。

必须遵循：

1. 每个交互动作只写一个 canonical path
2. 另一种表示如果存在，应通过推导、投影、汇总或读取聚合获得
3. application 层可以给出推荐写入口，但不应静默同时写两个模型

## Binding Mechanism

当两个表示存在明确绑定关系时，application 层可以做自动补齐。

关键原则：

- 不做无脑双向同步
- 做“单真相源 + 派生补齐”

### Hard Constraints

binding 机制必须满足以下硬约束：

- 每个 relationship family 只能有一个 canonical write path
- `summary` 写入必须先被规范化为 canonical 写入，再允许派生补齐
- 派生补齐不能反向再触发新的 canonical 写入
- 禁止基于监听器或隐式双向同步实现 binding

也就是说：

- 允许“写 A，内部转成写 B，再重算 A 的读视图”
- 不允许“A 改了写 B，B 改了再写 A”这种循环同步

### Binding Modes

#### 1. Mirror

适合几乎等价的关系状态表示。

例子：

- `User.can_speak`
- `Speaks(user, language)`

行为：

- 写 `summary` 时，规范化为 `record` 写入
- 写 `record` 后，重算 `summary`

#### 2. Reduce

适合“当前状态 + 历史记录”。

例子：

- `User.current_country`
- `ResidenceRecord(user, country, valid_from, valid_to)`

行为：

- `record -> summary` 是归约
- `summary -> record` 不是直接改摘要，而是生成或关闭记录

#### 3. Expand

适合摘要写入需要展开成多步关系操作。

例子：

- 用户修改 `current_country`

application 层可以：

- 关闭旧 active record
- 创建新的 `ResidenceRecord`
- 重算 `User.current_country`

### Execution Semantics

如果 binding 涉及多步写入，例如：

- 关闭旧 record
- 创建新 record
- 重算 summary

则这些步骤应当被视为一次 application command 的内部执行流程。

推荐要求：

- application 层先生成完整 write plan
- 再一次性提交到底层事务能力
- 重算 summary 必须属于同一条 command 的确定性后处理

如果当前底层能力无法保证这些步骤在一次一致性边界内完成，则：

- 不应启用自动 binding
- 退回为显式冲突或人工确认流程

### Capability Gating

是否允许启用自动 binding，不应在每次请求时临时猜测。

推荐方式：

- 在 service 启动时或 session 打开时进行 capability check
- 由 application/runtime 生成能力清单，例如：
  - 是否支持一次 command 内的原子多写入
  - 是否支持确定性的 post-write recompute
  - 是否支持同一 command 内的 write + retract 组合
- family registry 在编译时根据 capability check 决定：
  - `enabled`
  - `read_only`
  - `disabled`

如果某个 binding mode 所需能力不满足：

- 该 family 只能保留 read-side aggregation
- 写入侧退回为显式 command 或人工确认
- 不允许在运行时尝试执行后再回滚判断

### Cycle Prevention

为避免 binding 引发无限循环，application 层应采用保守规则：

- 每次请求只允许一个 canonical 写入阶段
- 派生补齐最多执行一轮
- 派生结果只更新 read model / summary materialization，不再重新触发 family binding
- 如需重复归约，必须由新的显式 command 触发

### Safe Auto-Binding Conditions

只有在以下条件成立时，才适合自动绑定：

- 角色能稳定识别
- 当前值的选择规则明确
- 缺失字段能合理补默认值
- 多条候选不会导致歧义

如果不满足，就不要自动补齐，只报冲突。

## Conflict Policy

当多个表示在数据层面不一致时：

- application 层可以自动给出当前推荐显示值
- 但不能静默覆盖其他来源
- 冲突必须在 DTO 中显式返回
- 用户可在 UI 中看到来源、差异和推荐结果

这与底层已有的 `chosen/conflicts` 思路一致，但“跨表示归并”仍然属于 application 层能力，而不是 core 能力。

## Service-Level Projection Config

由于不希望把这些规则下沉到底层 schema，application/service 可以维护独立的 projection config。

它不属于 core schema，只服务应用层统一与展示。

建议配置能力：

- relationship family 定义
- canonical write path
- summary path
- preferred graph projection
- conflict presentation policy
- binding mode
- schema 版本或 digest 绑定
- role mapping 与字段兼容规则

示意：

```yaml
relationship_families:
  - family_id: user.language.speaking
    schema_digest: sha256:...
    family_schema_digest: sha256:...
    members:
      - User.can_speak
      - Speaks(user, language)
    canonical_write_path: Speaks
    summary_path: User.can_speak
    binding_mode: mirror
```

### Config Load Strategy

relationship family config 不应在每次查询时动态猜测。

推荐方式：

- service 启动时或 session 打开时加载 config
- 按 `family_schema_digest` 编译 family registry，并记录当前 `schema_digest`
- runtime 只在已编译 registry 中做匹配与投影

这样可以避免：

- 每次查询重复结构匹配
- schema 演化后 family 定义失配而不自知

### Config Validation

family config 在加载时应至少校验：

- `family_id` 唯一
- `family_schema_digest` 与当前 family 相关 schema 片段对应
- `schema_digest` 如存在，应与当前全局 schema 对应
- 每个 member path 在 schema 中存在
- `summary_path` 与 `canonical_write_path` 角色可对齐
- family 内只能有一个 canonical write path
- 字段不完全一致时，必须有明确兼容策略

### Digest Scope

`family_schema_digest` 的作用是检测 family 配置与相关 schema 片段的匹配关系。

推荐策略：

- 优先使用 family-local digest
- family-local digest 仅覆盖该 family 引用到的 entity / field / role 定义
- full-schema digest 可作为保守兜底，但不建议作为默认绑定键

原因：

- full-schema digest 过于敏感
- 与 family 无关的 schema 变更，不应导致 family registry 全量失效

建议保留两种值：

- `schema_digest`: 当前全局 schema digest，用于运维排障与整体版本识别
- `family_schema_digest`: family-local digest，用于 family config 绑定与校验

如果只实现一种，优先实现 `family_schema_digest`。

对于成员结构不完全一致的情况，例如一个有 `level`，另一个没有，必须明确声明处理策略：

- 忽略缺失字段
- 仅作为 read-side enrichment
- 或禁止归并

## Service DTO Responsibilities

service 输出给前端的 DTO 建议至少包含：

- `nodes`
- `field_edges`
- `collapsed_relation_edges`
- `association_nodes`
- `relationship_families`
- `conflicts`
- `recommended_write_path`

说明：

- `field_edges` 表示原始字段引用
- `collapsed_relation_edges` 表示视觉折叠结果
- `relationship_families` 表示 application 层对多种表示的归并结果
- `recommended_write_path` 表示本次交互应落到哪个 canonical path

## Wire Protocol First

在正式抽代码之前，应先定义 application 层的中性输入输出协议。

目标不是先迁文件，而是先稳定边界。

建议至少定义：

- entity read request / response DTO
- entity write command DTO
- entity write plan DTO
- query request / plan / result DTO
- graph projection config schema
- relationship family registry DTO

只有这些协议稳定后，`sdk` 与 `service` 才能分别做自己的包装，而不再共享 facade 代码。

Phase 0 初版协议见：

- `docs/application_protocol_spec.md`

## Recommended Extraction Plan

为了避免 service 依赖 `SDKStore` 或复制逻辑，建议把一部分高层能力从 `sdk/` 抽到中立层。

本节只讨论 application/common 抽取边界，不讨论前端交互或页面表达。

推荐新层级：

- `core/`
- `application/`
- `sdk/`
- `service/`

其中：

- `sdk/` 与 `service/` 都依赖 `application/`
- `application/` 依赖 `core/`
- `service/` 不依赖 `SDKStore`

### Candidate Modules To Extract

建议优先抽取以下模块能力：

1. entity hydration
   - 当前来源：`sdk/facade.py`
   - 目标：`application/entity_view.py`
   - 当前状态：已完成第一轮抽取，SDK read facade 已委托
2. entity batch planning
   - 当前来源：`sdk/batch.py`
   - 目标：`application/entity_write.py`
   - 当前状态：已完成第一轮抽取，SDK batch preview/apply 已保守委托
3. schema runtime helpers
   - 当前来源：`sdk/store.py`
   - 目标：`application/schema_runtime.py`
   - 当前状态：已完成第一轮抽取
4. query lowering/runtime hydration
   - 当前来源：`sdk/query_lower.py` 与 `sdk/query_runtime.py`
   - 目标：`application/query_view.py`
   - 当前状态：未开始
5. authoring payload normalization
   - 当前来源：`sdk/store.py`
   - 目标：`application/authoring_normalize.py`
   - 当前状态：未开始
6. graph projection / relationship family / binding
   - 当前尚未实现
   - 目标：`application/graph_projection.py`、`application/binding.py`
   - 当前状态：未开始

### Specific Extraction Scope

上面的模块名还不够具体。按当前代码结构，真正应抽的是下面这些“高层机制”。

#### 1. Entity Read Model And Hydration

这部分当前主要在 `sdk/facade.py`。

应抽内容：

- snapshot 构建
- field assertion 聚合
- entity 可见性判断
- `get/find` 风格的实体读取
- 面向前端/service 的 entity-centric read DTO

原因：

- 它本质上是“把底层事实投影成实体视图”
- 不是 Python SDK 独有能力
- 前端 service 也需要同样的实体化读模型

建议落点：

- `application/entity_view.py`

#### 2. Entity Write Planning

这部分当前主要在 `sdk/batch.py`。

应抽内容：

- entity handle staging 背后的规划逻辑
- identity 补齐与 materialize
- 引用实体依赖解析
- staged ops 去重与排序
- `set/add/retract` 归并
- record-exists 补写
- wire plan 导出与应用

原因：

- service 如果要支持“编辑实体”“提交关系对象”，不能只停留在底层 `pred_id + e_ref + rest_terms`
- 这层本质上是 entity-centric write planner，而不是 SDK 专用体验

建议落点：

- `application/entity_write.py`

当前进展说明：

- 单目标 write planning / apply 已经在 `application/entity_write.py` 落地
- SDK batch preview/apply 已可在保守条件下委托 application planner
- 但 `BatchPlan.export()` / `WireBatchPlan.apply()` 仍保持 legacy 实现，以避免破坏现有 wire compatibility

#### 3. Schema Runtime Helpers

这部分当前散在 `sdk/store.py`。

应抽内容：

- `ref(...)` 背后的 identity -> `entity_ref` 编码
- schema index 构建
- field descriptor 到 schema predicate 的映射能力
- field value -> `rest_terms` 的 runtime coercion
- identity predicate 补写的通用支撑

原因：

- `entity_view` 和 `entity_write` 都依赖这层 helper
- 如果不抽，service 侧还是会被迫依赖 `SDKStore`

建议落点：

- `application/schema_runtime.py`

#### 4. Query Lowering And Result Hydration

这部分当前在 `sdk/query_lower.py` 和 `sdk/query_runtime.py`。

应抽内容：

- `QueryPlan`
- return contract 校验
- query lowering
- query 结果的批量 hydration
- entity snapshot 渲染
- return contract 应用与结果去重

原因：

- 这部分本质上是“结构化查询 -> 运行 -> 实体化结果”
- 不应被 SDK `Query` 包装方式绑死

建议落点：

- `application/query_view.py`

#### 5. Authoring Payload Normalization

这部分当前主要在 `sdk/store.py`，但它本质上不是 Python DSL 本身，而是 authoring payload 的归一化逻辑。

应抽内容：

- `where/body` wrapper normalize
- derivation head expand
- authoring derivation payload normalize
- body confidence merge / validate
- 规则与推导 payload 的中性预处理

原因：

- 这些逻辑既可服务 SDK，也可服务 service 输入适配
- 它们处理的是 payload，不是 Python facade 本身

建议落点：

- `application/authoring_normalize.py`

### What Should Stay In SDK

以下对象或能力不建议原样迁出：

- `Entity` Python class
- `Rule` / `Derivation` / `Query` Python DSL class
- `SDKStore` 整体对象
- `to_authoring_payload()` 这类 Python facade 方法
- `dependency_rules()` 这类 DSL 依赖遍历语法糖
- descriptor / metaclass / Python authoring ergonomics

原因：

- 它们和 Python SDK 的 authoring 体验深度绑定
- 迁出后只会把 application/common 污染成另一套 SDK
- application 层应共享“机制”，不是共享“Python facade 形式”

### What Is Already Shared Enough

以下能力当前已经基本不需要再从 SDK 中抽：

- rule compile
- derivation compile
- core rule execution
- runtime session/store

这部分 service 已经可以直接使用公共机制，而不是依赖 `SDKStore`。

### Extraction Priority

推荐优先级：

0. `completed` 定义 wire protocol / DTO / config schema
1. `completed` `schema_runtime`
2. `completed` `entity_view`
3. `completed` `entity_write`
4. `pending` `query_view`
5. `pending` `authoring_normalize`
6. `pending` `graph_projection`
7. `pending` `binding`

排序原因：

- 第 0 步先把边界固定下来
- 第 1 到 3 步决定 service 能否真正脱离 `SDKStore`
- 第 4 步决定查询结果能否直接服务前端
- 第 5 步减少 SDK 与 service 的输入适配重复
- 第 6 步建立新的 projection 能力
- 第 7 步复杂度最高，应最后落地

binding 的实施建议：

- 初期只支持 `mirror`
- `reduce` 与 `expand` 在 read/write path 稳定后再引入

### Extraction Rule

是否应从 SDK 抽取某能力，可按以下标准判断：

- 如果它依赖 Python descriptor / DSL authoring 体验，保留在 SDK
- 如果它面向产品 runtime 读写、前端 DTO、图投影、实体 hydration，应抽到 application 层
- 如果它只依赖 `Store + schema_ir + payload`，就不应继续留在 SDK 独占

## Compatibility And Rollout

迁移过程中应尽量保持 SDK 对外行为稳定。

建议策略：

- 先抽共享机制，再让 SDK 改为委托 application 层
- SDK 对外 API 在迁移期保持兼容
- 如需废弃旧路径，使用显式 deprecation 周期，而不是一次性替换
- service 不直接调用旧 SDK facade，只调用新中层

验证要求：

- 对同一输入，迁移前后的 SDK 输出应一致
- service 新接口应有独立 contract test
- 如果 application 与 SDK 同时存在双实现，必须有对比测试防止语义漂移

## Operational Requirements

### Error Model

application 层建议使用 typed exception 或结构化错误对象表达失败原因。

推荐边界：

- application 内部保留语义化错误
- service 负责映射为 API DTO
- 不把 HTTP 错误语义下沉到 application 层

### Performance

需要预留以下优化点：

- entity hydration 的批量化
- graph projection 的缓存或分批加载
- relationship family registry 的预编译
- query result hydration 的去重与批处理

### Observability

新层建议至少具备：

- command / query 级日志
- projection 与 binding 的调试日志
- 关键路径耗时指标
- family 命中率与冲突率统计

### Testing Strategy

建议测试分层：

- `application` 单元测试：mock 或最小化 `Store` 依赖，验证 planning / hydration / projection 逻辑
- `service` contract test：验证 DTO 形状与错误映射
- `sdk` 回归测试：验证 facade 在迁移后行为不变
- 关键 migration path 做双实现对比测试

双实现对比测试的生命周期建议如下：

- 在迁移窗口期，将其作为 CI 必跑项覆盖已迁移路径
- 如果成本过高，可对大批量场景降为 nightly 或预发布校验，但核心路径仍应保留在 CI
- 当 SDK 已完全委托新 application 实现，且旧实现删除后，对比测试可以下线
- 下线后保留 contract test、golden test 和回归测试，防止迁移完成后再次漂移

## Packaging Principle

最终包装关系应当如下：

- `core` 提供底层事实与执行机制
- `application/common` 提供中性声明、hydration、planning、projection、binding
- `sdk` 提供面向 Python 开发者的 authoring 包装
- `service` 提供面向前端产品的 API 包装

因此：

- 不是“service 复用 SDK 包装”
- 而是“SDK 和 service 复用同一套中层机制，各自提供不同包装”

## Final Recommendation

最终推荐方案如下：

1. 保持底层 `core` 不变
2. 不让前端 service 绑定 `SDKStore`
3. 在 `core` 之上建立独立的 `application/projection` 层
4. 用表示模式、relationship family、binding registry 解决“单一 Entity 模型”的表达问题
5. 用 service DTO 向前端提供稳定的产品语义接口
