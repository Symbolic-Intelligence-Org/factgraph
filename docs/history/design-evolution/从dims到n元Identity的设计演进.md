# 从 dims/fact_key 到 n元 Identity 的设计演进

> 里程碑标记：Phase 1-4 契约基线已冻结（冻结日期：2026-03-03）

## 问题起点

原始设计中出现了这样的字段定义：

```python
name_by_lang: str = Field(
    cardinality="functional",
    dims=[("lang", "string"), ("channel", "string")],
    fact_key=["lang"],
)
```

表面问题是 `dims` 和 `fact_key` 语义模糊——为什么 `lang` 升格为 `fact_key` 而 `channel` 不是？深层问题是：一个"属性字段"本身携带了区分自身不同取值的"键"，这违背了属性的语义前提。这个设计既有复杂度，又有困惑，是最差的组合。

## 根本原因

GNF 要求每个事实只有一个值。`name_by_lang` 试图用一个字段表达多个事实，然后用 `dims` 来打补丁区分它们。这等于把一个 **n 元原子事实** 强行劈成了：

```
Identity（user）+ 附属的 dims 机制
```

`dims` 和 `fact_key` 的全部复杂度都来源于这个劈分。

## 理论上的正确方向

原子事实的原子性与元数无关：

```
Name(user, lang, channel) = "Alice"   # 三元，同样原子，不可再分
```

因此正确的做法是允许 Identity 原生是 n 元的，`lang` 和 `channel` 本来就应该属于 Identity，而不是挂在 Field 上的附属物。

## 实践中的问题

如果把所有 Identity 都提升为对等的维度，实例化时没有一个明确的字段能够唯一标识实体，其他 Identity 字段的填入时机也不明确。此外，Rule 里需要表达"同一实体的不同事实"时，没有内置的联结依据。

## 最终方案：扁平 GNF 与隐式联结锚点

```python
class User(Entity):
    user_id: str = Identity(primary_key=True, default_factory="uuid4")
    work_id: int = Identity()
    lang: str = Identity()

    address: str = Field(cardinality="multi")
    nationality: Country = Field(cardinality="single")
```

**建议**：Identity 字段应指向实体自身的业务属性，而非 `source_system`、`data_version` 等数据管理维度——后者属于 batch meta，不属于 Identity。这只是设计建议，引擎不强制。

`primary_key=True` 显式声明联结锚点职责，`default_factory` 声明生成策略，两者正交、各管各的。没有标记 `primary_key=True` 的实体，若 Rule 里出现跨 Field 联结，引擎在此时报错要求显式声明，而不是在 Schema 定义阶段报错。

实例化时在单个实例上分步绑定 Identity，不支持从一个实例派生子视图：

```python
with sdk.batch(meta={"source": "hr", "valid_from": "2024-01"}) as tx:
    # 分步绑定：在同一个实例上逐步填入 Identity
    user_zh = tx.entity(User, user_id="u-001")
    user_zh = user_zh.bind(lang="zh", work_id=42)
    user_zh.address.add("北京市", meta={...})
    user_zh.nationality.set("中国", meta={...})

    # 另一条事实坐标，独立实例化
    user_en = tx.entity(User, user_id="u-001", lang="en", work_id=42)
    user_en.address.add("Beijing", meta={...})
    user_en.nationality.set("Chinese", meta={...})
```

`.add()` / `.set()` 时按 `参数绑定值 → 参数默认值` 的优先级合并，Identity 不完整则抛异常。对 Identity 字段调用 `.set()` / `.add()` 时抛异常——Identity 一旦确定不可变。

底层存储是完全扁平的 GNF 原子事实：

```
(user_id, work_id, lang) → address
(user_id, work_id, lang) → nationality
```

Rule 里 `user_id` 自然地充当联结锚点，无需额外机制。head 和 where 遵循统一规则：**primary_key 字段无论有多少个，一律由 where 里的实体绑定隐式携带，head 里完全不出现；非 primary Identity 字段必须在 head 里显式给出**：

```python
with vars("u", "ad", "id", "l") as (u, ad, id, l):
    R_derive_address = Rule(
        id="derive_user_address",
        version="1.0.0",
        head=User.address(work_id=id, lang=l, address=ad),  # user_id 不出现，非 primary Identity 必须给出
        where=[
            User(u),
            u.work_id == id,
            u.lang == l,
            SomeSource(u, address=ad),
        ],
    )
```

用户在写 head 时不需要知道 primary_key 叫什么，只需关注非 primary Identity 和目标 Field 值。

---

## Identity 与 Field 的平级关系

一个完整的事实记录本质上就是：

```
(key₁, key₂, ..., keyₙ) → value
```

Identity 和 Field 分别对应这两侧，地位对等，只是职责不同：

|  | Identity | Field |
|--|---------|-------|
| 角色 | 定位这条事实 | 承载这条事实的内容 |
| 唯一性要求 | 组合唯一 | 无要求 |
| 可变性 | 不可变 | 可变（有历史版本） |
| 参与 Rule | 可直接约束，读取与 Field 一致 | 可直接约束和操作 |

Identity 的值一旦确定就不应该再变——改变 Identity 意味着这是另一条事实，而不是同一条事实的更新。Field 则天然支持随时间演变。这个不对称不是说它们不平级，而是说**它们承载数据的语义不同**：Identity 的数据是定位信息，Field 的数据是内容信息。

因此在 Schema 定义层两者应该有对称的能力：

```python
class User(Entity):
    # Identity 侧
    user_id: str = Identity(primary_key=True, default_factory="uuid4")
    lang: str = Identity()

    # Field 侧
    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
```

两者都能指定类型、默认值、约束，只是语义标签不同。

读取侧完全对称，Identity 字段与 Field 字段使用体验一致：

```python
u.user_id    # Identity 字段，可读
u.lang       # Identity 字段，可读
u.name       # Field 字段，可读可写
```

Rule 里约束 Identity 字段与约束 Field 字段写法完全一致：

```python
where=[
    User(u),
    u.lang == "zh",      # 约束 Identity 字段
    u.name == n,         # 约束 Field 字段
]
```

唯一的差异在写入侧：对 Identity 字段调用 `.set()` / `.add()` 时抛异常。

---

## Field 参数的清理

随着 `dims` 和 `fact_key` 的删除，Field 的参数表需要系统性整理：

| 参数 | 处理结论 | 原因 |
|------|---------|------|
| `cardinality` | 保留，但重新定义 | 见下节 |
| `pred_id` | 降为内部实现细节 | 默认从字段名派生，不暴露给用户 |
| `type_domain` | 保留 | 类型系统必须，但优先从类型注解推断 |
| `dims` | **删除** | 职责迁移到 Identity |
| `fact_key` | **删除** | 随 dims 一并消失 |
| `name` / `value_name` | 降为编译期内部概念 | `pred_id` 能从字段名派生后失去独立意义 |
| `aliases` / `display_name` | 收进 `description` 或元数据层 | 运行期无消费逻辑，不应与有实际语义的参数平铺 |
| `description` | 保留 | 面向 LLM 和文档的唯一元数据参数 |

清理后，Field 的公开参数极其精简：

```python
name: str = Field(
    cardinality="single" | "multi",
    description="...",               # 唯一保留的元数据
)
```

---

## Cardinality 的重新定义

原枚举 `functional | multi | temporal` 混合了两个正交维度，层级不一致：

- `functional` / `multi` 表达基数约束（同一视图下允许 1 条还是多条）
- `temporal` 表达时间视图语义，实质是 `multi` 的修饰符，而非与前两者并列的第三种基数

正确的拆分是将其分为两个独立字段：

| cardinality | 历史管理 | 语义 |
|------------|---------|------|
| `single` | 无 | 单值，永远只有最新一条 |
| `multi` | 无 | 多值，全部保留 |
| `multi` | 有 | 多值 + 支持时间视图查询 |

`single` + 历史管理的组合意义不大，可直接禁止或忽略。

历史管理不作为 cardinality 枚举值，也不作为 Field 的参数——而是通过 batch meta 的业务时态字段（`valid_from`、`valid_to`、`version`）驱动，见下节。

---

## 断言视图

去掉 `dims` 后，断言视图从三层简化为两层：

- `.active`：当前未撤销的断言。由 store 的注册机制处理，与 Field 参数无关。
- `.history`：完整历史，含已撤销（revoked）的断言。

原有的 `.chosen` 视图仅适用于"无 dims 的 functional 字段"，随 `dims` 和 `fact_key` 的删除，其存在前提消失，自然一并移除。

---

## 历史管理与 meta

### 历史管理不放在 Schema，放在写入上下文

历史策略是写入时的行为约定，放在 batch 上下文比放在 Schema 定义里更符合直觉。Schema 描述"这个字段是什么"，batch 描述"这次写入怎么处理"：

```python
with sdk.batch(meta={"source": "hr", "valid_from": "2024-01"}) as tx:
    user_zh = tx.entity(User, user_id="u-001", lang="zh", work_id=42)
    user_zh.name.add("艾丽西亚")                                    # 自动继承 batch meta
    user_en = tx.entity(User, user_id="u-001", lang="en", work_id=42)
    user_en.name.add("Alicia", meta={"valid_from": "2024-03"})      # 单条覆盖
```

这样 Field 上不需要 `history` 参数，定义保持干净。

### meta 字段分类

meta 不是自由字典，字段按职责分为四类：

**系统保留（ingest 流程写入，用户不可写）**

`ingested_at`、`ingest_key`、`revoked_asrt_id`

**操作追踪（约定字段，推荐填写）**

`source`、`source_loc`、`trace_id`、`confidence`、`approved_by`、`note`

**推导链（accept 流程自动写入）**

`derived_rule_id`、`derived_rule_version`、`run_id`、`support_digest`、`support_kind`、`candidate_id`、`candidate_key`、`candidate_kind`、`key_tuple_digest`、`cand_key_digest`、`schema_digest`、`policy_digest`、`derivation_id`、`derivation_version`、`accepted_at` 等

**业务时态（新增分类，用于解锁时间视图）**

`valid_from`、`valid_to`、`version`

业务时态字段是约定字段级别——用户可写，视图层感知，但不强制。不填则只有 `.active` / `.history` 两个视图；填写后解锁 `.at(t)`、`.version(v)` 等时间查询。

注意：`ingested_at` 是系统写入时间，不等同于 `valid_from`（业务有效时间）。用 `ingested_at` 代替 `valid_from` 做时间视图会导致视图语义与业务语义错位。

### meta 字段的防漂移约定

视图层只依赖系统保留字段和业务时态字段，这两类由 SDK 明确约定并在校验层强制。用户自定义字段完全自由，视图层透传不感知。字段漂移的风险只存在于 SDK 自己控制的命名空间内。

去重依据为：`claim` + `source` + `source_loc` + `trace_id` + `valid_from` + `valid_to` + `version`。

`trace_id` 是操作级幂等键，不是数据级唯一键。同一条数据的不同业务有效期版本应使用不同 `trace_id`。

---

## 三层结构的风险与放弃

讨论过程中曾考虑引入 ID/Key/Value 三层结构，以表达"同一实体在不同坐标下的多个事实"：

```
ID 层：确定"是哪个实体"
Key 层：确定"是这个实体的哪个坐标"
Value 层：这个坐标下的值
```

这个结构的问题在于：一个 ID 绑定了多个事实，形成了**事实组**。事实组引入了 GNF 原本没有的隐式耦合——这些事实共享同一个 ID，但这个共享关系没有被任何一条事实显式表达。具体风险包括：

- 部分事实存在、部分不存在时，整体语义不明（实体是"完整的"还是"残缺的"？）
- 删除一条事实可能影响整个组的语义，违背原子事实的独立性

GNF 的扁平结构已经足够表达所需语义。三层结构带来的表达能力扩展，代价是稳定性下降。最终决定放弃三层结构，回归扁平 GNF。`Identity` 和 `Field` 的区分只是 Schema 层的约束声明，不在存储层引入任何额外的层次语义。

---

## 实体消解

"不同表达指向同一现实对象"（如 "Alicia"、"艾丽西亚" 指同一个人）不是 Identity 层的职责。这类判断本质上是**可错的推断**，不是事实自证的内容。将其压入 ID 层会导致：一旦消解错误，所有绑定到该 ID 的事实都受到牵连，且难以回滚。

正确的处理方式是通过显式的 `SameAs` Relation 来表达，保持事实的原子性和可撤销性：

```python
class SameAs(Relation):
    entity_a: User = Identity()
    entity_b: User = Identity()
    confidence: float = Field(cardinality="single")
```

消解结果是可追溯、可撤销的独立事实，不污染 Identity 层的稳定性。

---

## Rule 层的语法变化

### Identity 字段从隐式 context 变为直接访问

Identity 和 Field 的访问语法现在完全一致，不再需要任何特殊机制：

```python
# 之前：Identity 字段通过 context 机制访问，和 Field 不同
u.name(lang="zh") == n      # dims 作为额外参数传入

# 现在：统一直接访问
User(u), u.lang == "zh", u.name == n
```

### dims 参数从 where 子句中消失

`dims` 删除后，原本挂在 Field 上的维度参数全部迁移为 Identity 字段，在 where 里作为普通约束出现，没有任何特殊语法。

### cardinality 名称变化影响视图调用

```python
# 之前
u.nationality.functional    # 或 .chosen

# 现在
u.nationality.active        # single 字段，取当前未撤销值
u.address.active            # multi 字段，取所有未撤销值
u.address.history           # 完整历史
u.address.at("2024-01")     # 需要 valid_from 才解锁
```

`.chosen` 完全消失，任何引用 `.chosen` 的 Rule 语法失效，统一改为 `.active`。

### 实体绑定语义变化

`User(u)` 绑定的不再是只含 primary_key 的抽象实体，而是完整 Identity 坐标实例：

```python
User(u)   # u = (user_id, work_id, lang) 的某个具体组合
```

因此同一个 `user_id` 下不同 `lang` 的记录在 Rule 里是两个不同的 `u`。跨坐标联结时需要通过 primary_key 显式声明"同一个人"——这是 primary_key 在 where 里唯一显式出现的场景：

```python
# 比较同一用户中英文 address 是否一致
where=[
    User(u1), u1.lang == "zh", u1.address == a1,
    User(u2), u2.lang == "en", u2.address == a2,
    u1.user_id == u2.user_id,   # primary_key 跨坐标联结
]
```

---

## 结果汇总

`dims` 和 `fact_key` 完全消失。各层职责清晰分离：

- **存储层**：扁平 GNF，每条事实完全独立，不引入事实组或层次结构
- **Identity**：Schema 层的键约束声明，n元，不可变。`primary_key=True` 显式声明联结锚点职责，`default_factory` 独立声明生成策略。建议只用于业务属性，管理维度归入 meta
- **Field**：Schema 层的值约束声明，`cardinality` 只剩 `single | multi`，参数极简
- **Rule**：变量绑定到完整 Identity 坐标实例，联结锚点由 `primary_key=True` 字段显式提供。head 里 primary_key 字段一律不出现（由实体绑定隐式携带），非 primary Identity 字段必须显式给出
- **实体消解**：通过显式 `SameAs` Relation 表达，不污染 Identity 层
- **meta**：按四类分层，业务时态字段驱动历史视图，视图合约由 SDK 约定保证稳定

---

## v2 迁移说明（breaking 清单）

### Schema 层

- `Field.dims` 删除
- `Field.fact_key` 删除
- `Field.cardinality` 从 `functional|multi|temporal` 变为 `single|multi`
- `Identity` 新增 `primary_key` 参数；未声明 `primary_key=True` 的实体在跨坐标联结场景会编译期报错

### Rule / DSL 层

- `head` 中出现 primary_key 字段是编译期硬错误
- `temporal_view` 入口移除并显式报错
- 非 primary_key 字段参与跨坐标 `==` 比较是编译期硬错误
- 跨实体类型比较是编译期硬错误

### 第 4 阶段边界（时态能力拆分）

- ✅ 已完成：snapshot 读视图层 `assertions.<field>.at(t)` / `assertions.<field>.version(v)`
- ✅ 已完成：`.at(t)` 使用半开区间 `[valid_from, valid_to)`（`valid_to == t` 不命中）
- ✅ 已完成：`.at(t)` 对输入 `t` 与断言 `valid_from/valid_to` 做 ISO 8601 格式校验，非法即抛错
- ⚠️ 尚未开放：derivation/runtime 入口的 `temporal_view`（当前仍显式拒绝）
- 下一步 TODO：补齐 Rule head 产出时态断言的语义（`valid_from/valid_to/version` 由 Rule 元数据指定），再统一放开 derivation/runtime 的时态入口

### 协议层（`sdk_batch_plan_v1`）

- wire 协议删除 `dims`
- wire 协议删除 `fact_key`
- `cardinality` 枚举值变更到 `single|multi`

### 测试层

- 基于旧接口（`functional` / `dims` / `pred_id` / `temporal` / `chosen`）的测试全部删除
- 仅保留新契约测试（head primary_key 隐式语义、跨坐标 primary_key 联结、Identity 写入异常）

完整迁移说明见：

- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`（6.3 节）
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.en.md`（6.3 节）