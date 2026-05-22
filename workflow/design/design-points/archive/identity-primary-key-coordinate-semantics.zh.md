# Identity 机制、Primary Key 锚点与 Field 事实内容

Status: working / non-authoritative
Authority: 研究笔记。当前实现真相仍以 `src/kernel/sdk/`、`src/kernel/application/`、`src/kernel/authoring/` 及其模块文档为准。本文用于沉淀设计点解释，未来可反哺 SDK 用户文档，但它本身不是 release 契约。

## 1. 这份文档要解释什么

FactPy 的 `Entity` schema 里有两类最基础的声明：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    name: str = Field(cardinality="single")
```

表面看，它们都像“字段”。但在 FactPy 的模型里，`Identity` 和 `Field` 承担的是两种不同职责：

- `Identity` 定义 entity 的坐标；
- `Field` 定义挂在这个坐标下的事实内容；
- `primary_key=True` 标记 identity 坐标里的逻辑连接锚点。

这不是数据库建模文档，也不是把 FactPy 映射成 ORM 的说明。这里要讲的是 FactPy 自己的事实模型：**一个 entity 先由 identity coordinate 定位，然后普通 field facts 挂在这个 coordinate 上。**

## 2. 核心模型

当前实现可以用这条链路理解：

```text
Entity class declaration
  -> identity_fields + fields
  -> all identity_fields materialize into an identity coordinate
  -> identity coordinate encodes into idref_v1
  -> Field facts attach to that idref_v1
```

对于：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    name: str = Field(cardinality="single")
```

概念上是：

```text
(User, user_id, locale) -> idref_v1
idref_v1 -> name
```

所以：

```python
u_en = fg.ref(User, user_id="u1", locale="en")
u_zh = fg.ref(User, user_id="u1", locale="zh")
```

`u_en` 和 `u_zh` 是两个不同的 entity refs。它们共享同一个 primary identity 值 `user_id="u1"`，但完整 coordinate 不同。

这一点很重要：**所有 `Identity` 字段都参与 entity ref 的生成。** `primary_key=True` 不会把其他 `Identity()` 字段排除在 entity ref 之外。

## 3. 抽象层次：primary anchor、domain coordinate、field fact

如果只说“所有 Identity 都进入 `idref_v1`”，还不够解释设计理念。更重要的是区分三层抽象：

```text
primary identity      -> logical anchor / logical entity handle
non-primary identity  -> domain / coordinate dimension
Field                 -> fact content under one complete coordinate
```

以 `User(user_id, locale, name)` 为例：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    name: str = Field(cardinality="single")
```

可以把它读成：

```text
user_id="u1"                 -> 逻辑上的 User 锚点
locale="en" / locale="zh"    -> 这个 User 的不同 domain / coordinate
name="Alice"                 -> 某个具体 coordinate 下的事实内容
```

所以抽象层次不是：

```text
User -> fields
```

而更像：

```text
User logical anchor
  -> coordinate/domain variant
    -> mutable field facts
```

这解释了三个看似矛盾、实际上互补的设计点：

1. **所有 Identity 都决定 ref**：运行时 token `idref_v1` 必须对应完整 coordinate，所以 `user_id` 和 `locale` 都进入 ref。
2. **primary identity 有特殊地位**：它标记 logical anchor，用于 batch handle 的第一步锚定、rule 层跨坐标比较、field head 的隐式携带。
3. **Field 不参与定位**：`name`、`email`、`status` 这类值是某个 coordinate 下的可变事实内容，而不是决定“这是哪个 coordinate”的一部分。

用查询语义表达，就是：

```text
get(User, user_id="u1", locale="en")
  -> 读取一个完整 coordinate

find(User, user_id="u1")
  -> 读取同一个 primary anchor 下的多个 coordinate/domain variants
```

用写入语义表达，就是：

```text
tx.entity(User, user_id="u1")
  -> 先创建 primary-anchored handle

handle.bind(locale="en")
  -> 选择完整 coordinate/domain

handle.set(User.name, "Alice")
  -> 在该完整 coordinate 下写 Field fact
```

这个模型比“primary key 是唯一 ID”更准确，也比“non-primary Identity 和 Field 差不多”更准确。non-primary Identity 不是 Field；它仍然是 coordinate 的一部分。只是它不承担 logical anchor 的角色。

### 3.1 三层之间的边界

| 层级 | 例子 | 作用 | 是否进入 `idref_v1` | 是否可变事实 |
|---|---|---|---|---|
| Primary identity / anchor | `user_id` | 定义逻辑锚点；支持 primary-first handle、rule join、跨坐标比较 | 是 | 否 |
| Non-primary identity / domain | `locale` | 区分同一锚点下的不同 coordinate/domain | 是 | 否 |
| Field fact | `name` | 描述某个完整 coordinate 下的业务事实 | 否 | 是 |

因此：

```text
primary identity      = “先找到哪个 logical thing”
non-primary identity  = “再进入这个 thing 的哪个 coordinate/domain”
field                 = “这个 coordinate/domain 下有什么事实内容”
```

这里的 “domain” 是本文为了说明抽象层次使用的解释词，不是当前 public API 里的新类型。当前实现没有 `Domain` 类、没有 `EntityDomainSet` DTO、没有 primary-only ref token。domain 仍然通过普通 non-primary `Identity` 字段表达，并最终参与完整 `idref_v1`。

### 3.2 为什么不把 domain 做成 Field

如果把 `locale` 写成 `Field(...)`：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Field(cardinality="single")
    name: str = Field(cardinality="single")
```

那 `locale` 就只是 `User(user_id="u1")` 这个 coordinate 下的一个可变事实。它不再区分两个 coordinate：

```text
User(user_id="u1") -> locale = "en"
User(user_id="u1") -> name = "Alice"
```

这种模型适合“用户当前语言偏好”这类可变属性；不适合“同一个 user 在不同 locale 下有不同 name / status / claims”这种坐标化事实。

如果希望出现：

```text
User(user_id="u1", locale="en") -> name = "Alice"
User(user_id="u1", locale="zh") -> name = "艾丽丝"
```

那么 `locale` 必须是 `Identity()`，因为它决定了 `name` 这个 Field fact 挂在哪一个 coordinate 下。

### 3.3 为什么 primary anchor 不是单独的中间实体

这个设计容易让人自然联想到：

```text
User(user_id="u1")                -> logical entity
User(user_id="u1", locale="en")   -> domain entity
```

概念上这样理解很有帮助，但当前 runtime 并没有创建一个单独的 primary-only entity ref。`User(user_id="u1")` 在 batch handle 里是一个“未补全 coordinate 的 SDK handle”，在 read side 是 `find(...)` 的 partial identity filter；它不是 `idref_v1` 层面的独立实体。

这是一条有意的边界：

- runtime token 只认完整 coordinate；
- primary anchor 是 schema / authoring / SDK ergonomics 层的抽象；
- domain collection 是 read-side `find(...)` 的结果集合，而不是一个新的 DTO 或 ref 类型；
- write side 不支持 primary-only fan-out。

这样可以保留 primary-first 的用户心智模型，同时避免引入第二套 entity reference 系统。

## 4. `Identity` 的完整声明字段

在当前 SDK schema 代码中，`Identity` 的构造参数是：

```python
Identity(
    *,
    default: Any = None,
    default_factory: str | None = None,
    primary_key: bool = False,
)
```

此外，Python 类型注解和属性名也会进入 authoring schema。因此一个 identity 声明最终携带的信息包括：

| 来源 | 字段 | 含义 |
|---|---|---|
| Python 属性名 | `name` | identity field 名称，例如 `user_id` |
| Python 类型注解 | `type_domain` | runtime / authoring 使用的类型域，例如 string / int / entity_ref 等 |
| `Identity(default=...)` | `default` | 缺省 identity 值 |
| `Identity(default_factory=...)` | `default_factory` | 缺省值生成策略；当前常见值是 `uuid4` |
| `Identity(primary_key=True)` | `primary_key` | 是否是逻辑连接锚点 |

注意：`primary_key` 只在为 `True` 时写入 authoring dict；未设置时等价于 `False`。

`Identity` 声明进入 `EntityMeta` 收集出的 `identity_fields`。当前每个非基类 `Entity` 必须至少有一个 `Identity`，并且至少有一个 `Identity(primary_key=True)`。

## 5. `Field` 的完整声明字段

当前 `Field` 的构造参数是：

```python
Field(
    *,
    cardinality: str,
    description: str | None = None,
)
```

同样，Python 属性名和类型注解也会进入 authoring schema。因此一个 field 声明最终携带的信息包括：

| 来源 | 字段 | 含义 |
|---|---|---|
| Python 属性名 | `py_name` | field 名称，例如 `name` |
| Python 类型注解 | `type_domain` | value 类型域 |
| `Field(cardinality=...)` | `cardinality` | 事实基数；当前用户侧常见为 `single` / `multi` |
| `Field(description=...)` | `description` | 可选说明 |

历史设计里曾经讨论过 `dims`、`fact_key`、`temporal` 等 Field 参数，但它们已经从当前 public Field 声明中清理出去。这个决定来自 n-ary Identity 设计：原先挂在 Field 上的维度，应该提升为 Entity 的 Identity coordinate，而不是继续作为 Field 自己的附属 key。

## 6. Identity 和 Field 的职责边界

可以把 `Identity` 和 `Field` 看成 schema 层平级但职责不同的两种声明：

| 维度 | `Identity` | `Field` |
|---|---|---|
| 定位角色 | 定义 entity coordinate | 不参与 coordinate |
| 是否进入 `idref_v1` | 是 | 否 |
| 是否可作为普通事实写入 | 否 | 是 |
| 写侧语义 | 一旦确定即定位另一个 coordinate | 可 `set` / `add` / `edit` / `retract` |
| rule 语义 | 可约束；primary identity 可作为连接锚点 | 可约束；作为事实内容进入 head |
| 当前声明参数 | `default` / `default_factory` / `primary_key` | `cardinality` / `description` |

这解释了为什么 `Identity` 和 `Field` 在底层都可能出现成 predicate，但语义仍然不同。

例如 ledger 中可能能观察到：

```text
user:user_id(user_ref, "u1")
user:locale(user_ref, "en")
user:name(user_ref, "Alice")
```

这不表示 `user_id`、`locale`、`name` 是同一类东西。

更准确地说：

```text
user:user_id / user:locale 解释 user_ref 对应的 identity coordinate
user:name                   是挂在 user_ref 下的业务事实内容
```

## 7. 定义了 `primary_key=True` 之后会发生什么

`primary_key=True` 不是一个用户每天都要手动操作的开关。更准确地说，它是 schema 里的锚点声明：你在 class 上声明一次，后续 runtime、authoring 和 rule lowering 会在不同位置使用这个标记。

用户需要记住三件事：

1. 普通 `fg.ref(...)` / `fg.write.*` / `fg.read.*` 使用时，primary identity 和 secondary identity 都仍然是 identity 字段；所有 identity 都参与 entity ref。
2. `primary_key=True` 主要在 schema validation 和 rule/authoring 语义里发挥作用。
3. 写规则时，primary identity 有特殊机制：它由 entity binding 隐式携带，不应该在 head kwargs 里重复写。

### 7.1 定义 class 时：没有 primary identity 会失败

当 Python 执行这个 class 定义时：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
```

`EntityMeta` 会立即收集 schema 声明：

```text
identity_fields = [user_id, locale]
fields          = [name]
```

它还会检查：这个 entity 至少要有一个 `Identity(primary_key=True)`。如果写成：

```python
class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field(cardinality="single")
```

当前代码会在 class 定义阶段报错，因为这个 entity 没有逻辑锚点。

这意味着 `primary_key=True` 首先是一个 schema 入口约束。它保证每个 entity 至少有一个字段能承担后续 rule / join 语义中的锚点职责。

### 7.2 调用 `fg.ref(...)` 时：所有 identity 都参与 ref

定义了 `primary_key=True` 之后，普通 ref 生成并不会只看 primary 字段。

```python
u_en = fg.ref(User, user_id="u1", locale="en")
u_zh = fg.ref(User, user_id="u1", locale="zh")
```

这里 `user_id` 和 `locale` 都会被收集进 identity coordinate，然后一起编码成 `idref_v1`。

所以用户需要注意：

```text
same primary + different secondary identity = different entity refs
```

也就是说，`primary_key=True` 不会让 `locale` 变成普通属性。只要 `locale` 是 `Identity()`，它就是 coordinate 的一部分。

### 7.3 普通读写时：把 primary identity 当作普通 identity 传入

在普通 SDK read/write 路径里，用户通常不需要额外关心 primary identity 的特殊性。它仍然只是 identity kwargs 的一部分：

```python
u = fg.ref(User, user_id="u1", locale="en")
fg.write.set(User.name, u, "Alice")

snap = fg.read.get(User, user_id="u1", locale="en")
```

这里没有额外的 primary-key 操作。你不需要调用某个“primary lookup” API，也不需要手动告诉 write path 哪个字段是 primary。

特殊点只在于：

- 如果某个 identity 字段没有默认值，`fg.ref(...)` 或读侧 selector 需要提供它；
- 如果某个 identity 字段有 literal `default`，SDK `get(...)` 可以省略该字段；`default_factory="uuid4"` 会被 `fg.ref(...)` materialize，但 SDK `get(...)` 通常需要显式 identity 值；
- application 层 selector 只有在 `allow_identity_defaults=True` 时才会 materialize defaults；
- identity 字段定位 coordinate，不能像普通 `Field` 一样被当作业务事实随意修改。

### 7.4 Batch handle：primary identity 必须先锚定

在 SDK 的 batch / transaction ergonomics 里，`primary_key=True` 还有一个更直接的用户侧含义：**如果要创建一个可继续补全的 entity handle，第一步必须先给出 primary identity。**

也就是说，下面这种分步绑定是允许的：

```python
tx = fg.write.batch()

u = tx.entity(User, user_id="u-002")
u_en = u.bind(locale="en")
u_en.set(User.name, "Alice")
```

这里 `user_id` 是 primary identity，`locale` 是 non-primary identity。`tx.entity(...)` 先建立 primary anchor，`bind(...)` 再补全 domain / coordinate dimension。这个写法表达的是：

```text
先定位 logical anchor: User(user_id="u-002")
再选择具体 coordinate/domain: locale="en"
最后在完整 coordinate 上写 Field fact
```

反过来，下面这种写法会被拒绝：

```python
tx.entity(User, locale="en")
```

原因不是 `locale` 不重要，而是它不是 primary anchor。一个 handle 如果只知道 non-primary identity，系统无法把它解释为“某个 logical User 的待补全 domain”。因此当前 SDK ergonomics 的规则是：

- `tx.entity(...)` 创建 handle 时必须具备所有 primary identity；
- 多 primary identity 的 entity 需要一次性给齐所有 primary identity；
- `Identity(primary_key=True, default=...)` 和 `default_factory="uuid4"` 会在 handle 创建时 materialize，因此可以算作 primary identity present；
- `bind(...)` 只能补全 non-primary identity；
- `bind(...)` 不能新增、补交或修改 primary identity，即使传入的是同一个值也不应这么写；
- 写侧操作仍然要求完整 coordinate：primary-only handle 必须先 `bind(...)` 补全所有 non-primary identity，才能 `set` / `add` / `edit` / `preview` / `commit`。

这让 `primary_key=True` 在 SDK ergonomics 层获得了清晰位置：它不是唯一决定 entity ref 的字段，但它是**分步构造 handle 时必须最先出现的锚点**。

这也解释了为什么我们没有引入 primary-only `idref_v1`。上面的 `u = tx.entity(User, user_id="u-002")` 不是一个已经可写入的完整 entity ref；它是一个 SDK handle，内部仍然要等 `locale` 等 non-primary identity 补齐后，才能落到完整 coordinate 对应的 `idref_v1`。

### 7.5 写规则时：先区分 head 形态

`primary_key=True` 真正开始“显得特殊”的地方，是 authoring / derivation。

历史文档里对这点有明确描述：

```text
primary_key 字段无论有多少个，一律由 where 里的实体绑定隐式携带，
head 里完全不出现；非 primary Identity 字段必须在 head 里显式给出。
```

这句话是设计原则，当前代码中需要更精确地区分两类 head。

先定义两个词：

- **field head**：rule 要推出某个 entity 的某个字段事实，例如 `User.name(...)`、`User.address(...)`。它的目标是一个 field predicate。
- **entity head**：rule 要推出 entity-level predicate，例如 `User(...)` 这类 entity 构造 / 匹配形态。它不是某个普通 `Field(...)` 的 value 写入。

下面只用 field head 解释，因为这是 `primary identity` / `non-primary identity` 最容易混淆的地方。

假设：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    display_name: str = Field(cardinality="single")
```

`User.display_name(...)` 是一个 field head。它要表达的是：

```text
在某个 User coordinate 下，推出 display_name 这个 Field fact。
```

在 rule lowering 里，目标 coordinate 来自 `where` 中已经绑定的 entity variable，例如概念上：

```python
where=[
    User(u),
    u.locale == loc,
    SomeSource(u, name=n),
]
head=User.display_name(locale=loc, value=n)
```

这里的 `User(u)` 绑定的是完整 entity ref。这个 ref 背后已经包含完整 identity coordinate，包括 `user_id` 和 `locale`。因此 primary identity `user_id` 不需要、也不允许在 head kwargs 中再次出现：

```python
# 不应写成这样
head=User.display_name(user_id=uid, locale=loc, value=n)
```

原因不是 `user_id` 不重要，而是它已经由 `where` 里的 entity binding 承担。重复写 primary identity 会让 head 同时从两个地方声明同一个锚点，当前编译器直接拒绝。

那为什么 non-primary identity `locale` 还要写？

因为 `locale` 是 coordinate dimension。field head 需要确认目标 field fact 属于哪个完整 coordinate。当前 schema-aware lowering 要求 non-primary identity kwargs 显式出现，用来校验 / 消歧目标 coordinate 与 where-bound entity variable 是否一致。它不是额外输出项，不会单独 emitted 成新的 head term，也不是重新创建一个 coordinate；最终 lowered head 仍然是：

```text
target entity ref + field value
```

所以 field head 的规则是：

- primary identity 字段不能出现在 head kwargs 中；
- non-primary identity 字段目前必须出现在 head kwargs 中；
- lowering 最终仍然使用 `where` 中绑定出来的 entity variable 作为目标 ref，再加上 field value；
- non-primary identity kwargs 在这里主要承担 schema-aware lowering 的校验 / 消歧职责，不是单独 emitted 成新的 head terms，也不是重新创建一个 coordinate。

**Entity head**，例如 `User(...)`：

- identity kwargs 不按 field-head 规则处理；
- primary identity kwargs 会被拒绝；
- identity predicates 不作为普通 entity fields 加入 head role specs；
- 这类 head 更接近“构造 / 匹配 entity-level predicate”的形态，不能直接套用 `User.name(...)` 的 non-primary identity 规则。

这就是用户写规则时最需要注意的地方：**不要把 primary identity 写进 field head；non-primary identity 在 field head 中目前需要显式给出，但它不是额外的输出项，而是帮助编译器确认目标完整 coordinate。**

```text
field head primary identity: 不写，由 where 绑定的 entity ref 承担
field head non-primary identity: 显式写，用于 schema-aware lowering 校验 / 消歧
entity head identity kwargs: 不按 field-head 规则使用，需单独看 entity-head lowering
```

### 7.6 做跨坐标比较时：primary identity 是严格锚点

另一个特殊机制发生在 cross-coordinate comparison。

假设一个 logical user 有多个 locale coordinate：

```text
User(user_id="u1", locale="en")
User(user_id="u1", locale="zh")
```

这两个 coordinate 不同，但它们可以通过 `user_id` 被理解为同一个 logical user 的不同坐标。这里 `user_id` 能承担这个角色，是因为它被标记为 `primary_key=True`。

where schema lowering 会限制跨 coordinate 的 attribute-to-attribute comparison。当前允许的形态更严格：

- 需要 schema-aware compile context；
- 两边变量都必须已经绑定为 entity 变量；
- 两边必须是同一个 entity type；
- 两边比较的字段名必须相同；
- 该字段必须是 `primary_key=True` 的 identity field。

这样系统才能明确知道你是在表达“同一个逻辑对象的不同 coordinate”，而不是误把普通维度字段当成同一性锚点。

因此：

```text
user_id = logical anchor
locale  = coordinate dimension
```

这就是 `primary_key=True` 在 rule 层的实际意义。

如果一个 entity 有多个 primary identity，当前 `attr_eq` 语义仍然是逐字段比较。也就是说，要表达完整 composite primary identity 相等，需要对每个 primary 字段分别写比较；单个 `u1.pk == u2.pk` 只覆盖该字段本身。

### 7.7 用户侧注意事项

定义 `primary_key=True` 后，用户可以按下面几条规则使用：

- 每个 `Entity` 至少放一个 `Identity(primary_key=True)`。
- 不要把 `primary_key=True` 理解为“只有这个字段参与 ref”；所有 `Identity` 都参与 ref。
- 普通 SDK 读写里，把 primary identity 当作 identity kwargs 正常传入即可。
- 在 batch handle 里，`tx.entity(...)` 必须先给出 primary identity；`bind(...)` 只用于补全 non-primary identity。
- 如果某个字段只是可变内容，不要声明成 `Identity()`，应声明成 `Field(...)`。
- 如果某个字段区分 entity coordinate，即使它不是 logical anchor，也应声明成 `Identity()`。
- 写 derivation / rule 时，先区分 field head 和 entity head；field head 中 primary identity 不写，non-primary identity 目前需要显式写作 schema-aware lowering 的校验 / 消歧信息。
- 做跨坐标 join / comparison 时，只能在同 entity type、同字段名、primary identity 字段上做 attribute-to-attribute comparison；composite primary identity 需要逐字段比较。

## 8. 从历史模型到当前实现

历史设计笔记 [从 dims/fact_key 到 n元 Identity 的设计演进](<../../../blueprint_history/从dims到n元Identity的设计演进.md>) 给出的核心判断是：

> 原先挂在 Field 上的 `dims` / `fact_key` 机制语义混乱；正确方向是把这些区分事实自身坐标的维度提升为 Entity 的 n-ary Identity。

所以早期文档会使用这样的概念模型：

```text
(user_id, work_id, lang) -> address
```

这句话表达的是：`address` 不是只挂在 `user_id` 上，它挂在完整 identity coordinate 上。

当前实现没有把每个 field predicate 都物理展开成：

```text
user:address(user_id, work_id, lang, address)
```

而是引入稳定的 surrogate entity ref：

```text
(user_id, work_id, lang) -> idref_v1
idref_v1 -> address
```

这样做让运行时拥有统一的 entity reference token，可以在 SDK、application runtime、audit、proof frame 等层之间传递，同时保留 n-ary identity coordinate 的语义。

需要同时保留历史设计的另一条边界：这是当前 runtime / storage tokenization，不是在语义层引入“事实组”或层次存储。语义上仍然是完整 identity coordinate 下的扁平事实。

另一个历史文档 [Authoring 层契约](<../../../blueprint_history/Authoring 层契约.md>) 里也强调过：

```text
Identity != fact_key
```

这份 v1 契约的重点是把 Identity 与 Field `fact_key` 分开：Identity 用于生成和解释 EntityRef，Field `fact_key` 当时仍映射到字段事实的 grouping 语义。后续 [从 dims/fact_key 到 n元 Identity 的设计演进](<../../../blueprint_history/从dims到n元Identity的设计演进.md>) 才进一步把 public `Field.fact_key` / `Field.dims` 清理掉，把这类坐标维度迁移到 n-ary Identity。

## 9. 一条完整写入链路如何理解

假设：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    name: str = Field(cardinality="single")
```

当用户写：

```python
u = fg.ref(User, user_id="u1", locale="en")
fg.write.set(User.name, u, "Alice")
```

可以拆成几步：

1. `fg.ref(...)` 验证 `User` 已注册。
2. 它检查传入的 kwargs 是否都是 `User` 的 identity 字段。
3. 它按 schema 中的 `identity_fields` 顺序收集所有 identity 值。
4. 对缺省 identity 字段应用 `default`，并在 `default_factory="uuid4"` 时生成默认 ref 值。
5. 它把完整 identity triples 编码成 `idref_v1`。
6. `fg.write.set(...)` 把 `User.name` 这个 Field fact 写到该 `idref_v1` coordinate 下。

所以 `ref` 不写 ledger；它只是生成和缓存一个 managed e_ref。真正的 field fact 写入发生在 `set` / `add` / `edit` 等写侧操作中。

在写入计划里，当前实现还会为目标 entity materialize identity helper predicates 和 exists predicate。这些 identity helper predicates 用来解释 / 恢复 `idref_v1` 对应的 coordinate；它们不是普通业务 `Field` claims。

## 10. 读侧 primary-anchor 查询：`find(...)`，不是 `get(...)`

上一节说的是写侧：写入必须落到一个完整 coordinate 上。读侧可以更宽松一点，因为“观察多个 coordinate”不会产生 fan-out mutation 的歧义。

当前设计里，primary-anchor / domain 查询走现有的 `find(...)`，而不是新增 `domains(...)`、`entity(...)` 或让 `get(...)` 改变返回类型。

假设：

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
```

完整 coordinate 查询仍然用 `get(...)`：

```python
snap = fg.read.get(User, user_id="u-1", locale="en")
```

它的语义保持不变：

```text
完整 identity coordinate -> 一个 EntitySnapshot 或 None
```

如果只提供 primary identity，则使用 `find(...)`：

```python
rows = fg.read.find(User, user_id="u-1")
```

它的语义是：

```text
primary anchor filter -> 所有匹配的完整 coordinate snapshots
```

例如可能返回：

```text
User(user_id="u-1", locale="en")
User(user_id="u-1", locale="zh")
```

这不是新的 DTO，也不是新的 logical entity ref。返回值仍然是普通的 `list[EntitySnapshot]`。每个 `EntitySnapshot` 仍然代表一个完整 coordinate，而不是 primary-only aggregate。

这个语义有几个边界：

- `fg.read.get(...)` 不重载：它仍然要求足够明确的 full-coordinate lookup，不返回集合；
- `fg.read.find(...)` 可以接受 partial identity filters，包括 primary-only filters；
- identity filters 和 field filters 使用 AND 语义；
- unknown filter name 仍然是 SDK schema error；
- partial identity `find(...)` 返回的每个 snapshot 应暴露完整 recovered identity coordinate，`snapshot.identity_available=True`；
- 没有新增 `EntityDomainSet`、`NotFound` sentinel、lookup helper、primary-only ref token 或新的 `kernel.sdk.__all__` 导出。

用户可以用普通 Python 继续筛选：

```python
rows = fg.read.find(User, user_id="u-1")
en = next(row for row in rows if row.identity["locale"] == "en")
```

这个选择背后的原则是：**读侧可以枚举多个完整 coordinate；写侧不能把 primary-only handle 隐式 fan out 到多个 coordinate。**

因此可以把当前读写分层理解成：

```text
read.get(full coordinate)      -> one snapshot / None
read.find(partial identity)    -> list of full-coordinate snapshots
write handle with primary only -> not writable yet
write handle with full identity -> writable coordinate
```

## 11. Relationship 的相关但不同问题

Identity 机制也解释了为什么不能简单用普通 `Entity` 完全替代 `Relationship`。

如果写：

```python
class Authored(Entity):
    from_entity: User = Identity(primary_key=True)
    to_entity: Document = Identity(primary_key=True)
    role: str = Field(cardinality="single")
```

这看起来像一条边。SDK 声明 / ref 层可以表示 `entity_ref` typed token，但当前 application identity materialization 和普通 FactGraph write path 会拒绝把 `entity_ref` 当作 entity identity domain；普通写路径也不会把它当作 relationship edge 来处理。

`Relationship` 是另一个 schema 概念：它专门表达二元关系，端点是 `from_entity` / `to_entity`，属性是 relationship fields。它最初主要服务 PyReason / graph adapter 方向，而不是 beginner FactGraph CRUD。

因此：

```text
Identity coordinate model != Relationship edge model
```

二者有关联，但不是彼此的语法糖。

## 12. 当前需要继续打磨的边界

### 12.1 命名需要解释

`primary_key` 是当前 public API 名称，短期不应随意改动。但用户文档需要明确：

```text
primary_key=True 是 logical anchor，不是唯一 identity determinant。
```

中文文档可以写作：

```text
primary_key=True 表示该 identity 字段是规则和跨坐标比较使用的逻辑锚点。
```

### 12.2 `EntitySnapshot.identity` 与默认值恢复需要复核

当前读侧在 identity defaults 生效时，某些 snapshot 展示的 `identity` 可能只反映 selector 显式提供的值，而不是完整 materialized coordinate。

因此正式用户文档暂时不应过度承诺：

```text
EntitySnapshot.identity 总是完整 identity coordinate。
```

更稳妥的表述是：

```text
ref generation 和 runtime resolution 使用完整 materialized identity coordinate。
```

但需要区分一个已经被新设计明确锁定的例外：partial identity `find(...)` 返回的 snapshots 必须暴露完整 recovered coordinate identity，并且 `identity_available=True`。这条承诺只针对 partial-identity `find(...)` 结果，不应被扩大解释成所有 read path snapshot 在所有 defaults 情况下都已经具备同等展示行为。

### 12.3 rule-level 测试需要进一步锁定

源码中已经实现了 primary / non-primary identity 在 derivation head 和 where comparison 中的区分。但如果要把这些语义作为强用户承诺写入正式 SDK 文档，最好增加或确认更直接的测试覆盖。

尤其需要覆盖：

- field head 中出现 primary identity 应报错；
- field head 缺少 non-primary identity 应报错；
- entity head 的 identity kwargs 行为需要单独测试；
- 跨 coordinate comparison 使用 non-primary identity 应报错；
- primary identity comparison 只在 same entity type / same field name / both vars bound 时被允许；
- composite primary identity equality 需要逐字段比较。

## 13. 推荐写入用户文档的表述

推荐英文表述：

> `Identity` fields define an entity coordinate. All identity fields participate in the generated `idref_v1` entity reference. Mark one or more identity fields as `primary_key=True` to identify the logical anchor used by rule authoring and cross-coordinate joins. Ordinary `Field(...)` values do not participate in entity identity; they are mutable facts attached to an entity coordinate.

> In batch writes, primary identity must be supplied when the entity handle is created; `bind(...)` only completes non-primary identity dimensions. In reads, use `get(...)` for a full coordinate and `find(...)` for partial identity filters such as a primary anchor.

推荐中文表述：

> `Identity` 字段定义 entity 的坐标。所有 identity 字段都会参与生成 `idref_v1` entity reference。把一个或多个 identity 字段标记为 `primary_key=True`，是为了声明 rule authoring 和跨坐标 join 使用的逻辑锚点。普通 `Field(...)` 值不参与 entity identity；它们是挂在某个 entity coordinate 下的可变事实。

> 在 batch 写入里，创建 entity handle 时必须先给出 primary identity；`bind(...)` 只用于补全 non-primary identity dimension。在读取里，完整 coordinate 用 `get(...)`，primary-anchor 这类 partial identity filter 用 `find(...)`。

应避免：

```text
primary key 是唯一决定 entity 的字段。
```

也应避免：

```text
非 primary 的 Identity 和 Field 差不多。
```

更准确的是：

```text
非 primary Identity 仍然参与 entity coordinate，只是它不是 rule 层的主要连接锚点。
```

## 14. 总结

FactPy 的 `Identity` 机制不是一个数据库主键机制，也不是普通字段上的额外 metadata。它是 entity coordinate 的声明机制。

最稳定的理解方式是：

```text
Identity            = entity coordinate
primary_key=True    = coordinate 中的 logical anchor
non-primary Identity = coordinate 中的 domain dimension
Field               = coordinate 下的 mutable fact content
idref_v1            = complete identity coordinate 的稳定运行时 token
tx.entity(...)      = batch handle 必须先由 primary identity 锚定
fg.read.find(...)   = 可用 partial identity 枚举完整 coordinate snapshots
```

从历史设计上看，FactPy 是从 `dims` / `fact_key` 这类 Field 局部维度机制，演进到 n-ary Identity coordinate；从当前实现上看，这个 coordinate 通过 `idref_v1` 落到运行时。`primary_key=True` 的意义是在这个 coordinate 中指定逻辑锚点，而不是把其他 identity 字段变成普通属性。
