# Frontend Entity UI Design

## Goal

为当前后端定义一套稳定的前端交互约束：

- 后端 canonical model 保持为 `Entity + Identity + Fields`
- 前端图视图允许使用 neo4j 风格进行展示
- neo4j 风格只是投影，不反向约束底层模型

本文件只讨论前端表达与交互。

分层、SDK 边界、表示模式、绑定机制、application/projection 抽取计划，统一放在：

- `docs/application_projection_blueprint.md`

## Decision

不引入两种特殊基类 `fact` / `relation`。

前端采用以下原则：

1. 领域建模层只有 `Entity`
2. `Identity` 与 `Field` 是一等概念
3. `Field` 可为标量，也可为 `entity_ref`
4. 图谱中的边是前端/服务端投影结果，不是 canonical object

## Canonical UI Model

每个 `Entity` 在 UI 中都必须被拆成以下两部分：

- `Identity`
- `Fields`

### Identity

`Identity` 用于确定实体引用与编辑定位，UI 必须单独展示，不应与普通字段混排。

交互约束：

- 创建时优先填写 identity
- 若 identity 可由 default/default_factory 补齐，UI 允许延迟展示最终值
- identity 一旦实体创建成功，不允许在编辑态直接修改

### Fields

`Field` 在 UI 层分为四类：

1. scalar-single
2. scalar-multi
3. ref-single
4. ref-multi

说明：

- `scalar-*` 用普通表单控件编辑
- `ref-*` 用实体选择器编辑
- `multi` 必须采用列表式交互，而不是单输入框覆盖写入

## Graph UI Model

图视图是 projection，不是 schema 本体。

### Node

以下对象默认显示为节点：

- 所有主实体
- 所有未被折叠的 relation-like entity
- 所有存在歧义的实体
- 所有复杂关系实体

### Field Edge

所有 `entity_ref` 字段都可以显示为字段边。

字段边的含义是：

- 某个实体引用了另一个实体
- 这不代表当前实体本身是关系实体

例如：

- `User.can_speak -> Language`
- `User.lives_in -> Country`

在这类场景中，`User` 仍然是节点，而不是边。

### Collapsed Relation Edge

只有 relation-like entity 才允许在图视图中折叠显示为边。

折叠是视觉优化，不是数据结构改变。

折叠显示时：

- 两个核心 `entity_ref` 字段作为边两端
- 其余标量字段作为边属性
- 点击该边时，实际打开的是背后的实体详情

### Association Node

以下情况必须显示为“关系节点”而不是边：

1. 关系包含 3 个及以上角色
2. 关系本身带重要状态、证据、审批、来源或上下文
3. 当前视图下无法稳定折叠

表现形式：

- 中间实体显示为 node
- 每个角色字段显示为 role-labeled edge

## UI Modes

前端建议明确分为四种视图，而不是试图用一个图视图承载全部语义。

### 1. Schema Authoring View

用于定义实体结构。

应展示：

- entity name
- description
- identity fields
- field list
- field type
- field cardinality
- field target entity

该视图中不引入“边”概念，只讨论 schema。

### 2. Instance Editor View

用于创建和编辑实例。

应展示：

- identity 区块
- scalar fields 区块
- reference fields 区块
- assertions / provenance 区块
- graph preview 侧栏

reference fields 交互建议：

- `ref-single`: autocomplete + preview card
- `ref-multi`: token list + add/remove

### 3. Graph View

用于理解实体之间的连接。

显示规则：

- 主实体显示为节点
- 字段引用显示为字段边
- relation-like entity 可显示为折叠边
- 复杂关系显示为 association node

### 4. Rule View

用于表达查询、推导与约束。

规则不要和实体混成同一种图元。规则更适合表达为“模式 + 结果”。

建议固定为四个区块：

- `Header`: 名称、类型、版本、状态
- `Bindings`: 变量与实体类型绑定
- `Conditions`: `where` 条件列表
- `Outcome`: query 返回、derivation 生成、check 校验结果

## Editing Rules

### Create

创建实体时流程建议为：

1. 选择 entity type
2. 填写 identity
3. 填写 scalar fields
4. 选择 referenced entities
5. 确认并提交

### Edit

编辑实体时：

- identity 只读
- scalar single 使用 set
- scalar multi 使用 add/retract
- ref single 使用 set
- ref multi 使用 add/retract

如果前端提供“图上拖线改关系”，也必须最终落回对背后 `Entity` 字段的编辑，而不是绕开实体直接修改图结构。

## Query And Detail Behavior

点击图元素时建议遵循以下规则：

- 点击普通节点: 打开 entity detail
- 点击字段边: 高亮对应 field，并打开拥有该 field 的实体详情
- 点击折叠边: 打开 relation-like entity detail
- 点击 association node: 打开该 node detail
- 点击 association node 的 role edge: 高亮对应字段，但详情仍归属于中间实体

## Example

### Example A: simple entity

```python
class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
```

图视图：

- `Country` 显示为普通节点

### Example B: binary relation-like entity

```python
class LivesIn(Entity):
    uid: str = Identity(default_factory="uuid4")
    user: User = Field(cardinality="single")
    country: Country = Field(cardinality="single")
    since: int = Field(cardinality="single")
```

图视图：

- 可折叠为 `User -[LIVES_IN {since: 2020}]-> Country`
- 点击边时仍打开 `LivesIn` 实体详情

### Example C: node with two field edges

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    can_speak: Language = Field(cardinality="multi")
    lives_in: Country = Field(cardinality="single")
```

图视图：

- `User` 仍然显示为节点
- `can_speak` 显示为 `User -> Language` 的字段边
- `lives_in` 显示为 `User -> Country` 的字段边
- 不能因为它有两个 `entity_ref` 字段就把 `User` 误判为边

### Example D: n-ary relation

```python
class EmploymentEvent(Entity):
    uid: str = Identity(default_factory="uuid4")
    user: User = Field(cardinality="single")
    company: Company = Field(cardinality="single")
    contract: Contract = Field(cardinality="single")
    start_date: str = Field(cardinality="single")
```

图视图：

- 必须显示为 association node
- 不应强行压成单条边

## Final Recommendation

最终推荐方案如下：

1. 前端围绕 `Entity + Identity + Fields` 设计
2. 图视图先表达 `node + field edge`
3. relation-like entity 只在合适时被折叠为边
4. 复杂关系保持为 association node
5. 规则使用独立的规则视图，不与实体图混合建模

这套方案的好处是：

- 不牺牲后端表达能力
- 兼容 neo4j 风格视觉习惯
- 支持未来更复杂的关系建模
- 避免把 UI 表达误当成底层数据模型
