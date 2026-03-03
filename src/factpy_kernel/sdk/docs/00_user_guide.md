# FactPy SDK 使用指南

> 本文描述已实现行为；未实现能力明确标注"当前边界"。  
> 文档中的行为按三类标签区分：**稳定合约**（建议写强断言测试）、**当前行为**（可能演进）、**规划中**（尚未实现）。

---

## 目录

1. [安装与初始化](#1-安装与初始化)
2. [Schema 定义](#2-schema-定义)
3. [写入数据](#3-写入数据)
4. [meta 字段](#4-meta-字段)
5. [读取数据](#5-读取数据)
6. [Rule / Query / Derivation](#6-rule--query--derivation)
7. [Provenance 校验](#7-provenance-校验)
8. [选哪个写入入口？](#8-选哪个写入入口)
9. [错误处理速查](#9-错误处理速查)
10. [Registry](#10-registry)
11. [高级 API](#11-高级-api)
12. [迁移速记（v2）](#12-迁移速记v2)

---

## 1. 安装与初始化

### 1.1 初始化 Store

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

需要持久化时指定 `ledger_path`：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

如需默认把 Rule 查询结果返回为 dict 行：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    default_row_format="dict",
)
```

**稳定合约**
- `classes` 必须是非空 `list[Entity 子类]`；`from_schema_classes(...)` / `schema_preflight_from_classes(...)` 路径抛 `SDKSchemaError`，`SDKStore(...)` 构造器路径抛 `SDKStoreError`。
- `ledger` 与 `ledger_path` 互斥；两者不能同时传入。
- `ledger_path` 首次写入时记录 `schema_digest`；重新打开时校验，不一致抛 `SDKStoreError`。
- `default_row_format` 仅作用于 `sdk.run(rule, ...)`，合法值为 `"tuple"` / `"dict"`，默认 `"dict"`。
- 解析结果为 `"tuple"` 时会触发 `DeprecationWarning`；推荐统一改为 `"dict"`。
- `FACTPY_ROW_FORMAT` 环境变量在 `SDKStore` 初始化时读取并缓存（非每次 `run()` 动态读取）。

### 1.2 Schema 预检

在不需要运行时 store 的场景（CI 校验、模块导入阶段），可单独做预检：

```python
from factpy_kernel.sdk import schema_preflight_from_classes

preflight = schema_preflight_from_classes([User, Country, LivesIn])

print(preflight["ok"])
print(preflight.get("warnings", []))
print(preflight.get("summary", {}))   # entity_count / predicate_count / pred_ids
```

**稳定合约**：返回 `dict`，核心键包括 `ok`、`warnings`、`errors`、`diagnostics`、`summary`（成功时）。

---

## 2. Schema 定义

### 2.1 基本结构

```python
from factpy_kernel.sdk import Entity, Identity, Field

class User(Entity):
    user_id: str = Identity(primary_key=True, default_factory="uuid4")
    lang: str = Identity()

    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
    country: Country = Field(cardinality="single")
```

`Identity` 定位一条事实，`Field` 承载这条事实的值。读取侧有限度的对称：快照的**值访问**（`snap.lang`、`snap.name`）对两者一致；但 `snap.assertions.lang` 不可用——`assertions` 命名空间只覆盖 `Field` 字段，不覆盖 `Identity` 字段。写入侧区别：对 `Identity` 字段调用 `.set()` / `.add()` 会抛异常。

**稳定合约**：每个 `Entity` 至少需要一个 `Identity`，否则类定义时报 `SDKSchemaError`。

### 2.2 Identity 参数

| 参数 | 含义 |
|------|------|
| `primary_key=True` | 标记为联结锚点；Rule 跨 Field 推理时隐式携带，head 里不出现 |
| `default` | 静态默认值 |
| `default_factory="uuid4"` | 缺省时自动生成 UUID |

`primary_key=True` 与 `default_factory` 是正交的——前者声明语义职责，后者声明生成策略，可以同时使用也可以分开。没有标记 `primary_key=True` 的 Entity，若 Rule 里出现跨 Field 联结，编译期报错。

**建议**：`Identity` 字段应指向实体的业务属性（如 `user_id`、`lang`），而非 `source`、`version` 等数据管理维度。后者属于 meta，不属于 Identity。这只是设计建议，引擎不强制。

### 2.3 Field 参数

| 参数 | 含义 |
|------|------|
| `cardinality="single"` | 单值视图：读取 `snap.<field>` 返回标量；写入接口用 `.set()` |
| `cardinality="multi"` | 多值，同一坐标下保留全部 |
| `description` | 面向文档和 LLM 的说明文字 |

**当前行为补充**：`single` 不会在写入时自动清理旧断言；`active/history` 里仍可能看到多条未撤销断言，`snap.<field>` 返回的是当前单值视图。

**当前边界**：`dims` / `fact_key` / `pred_id` / `functional` / `temporal` 已移除。

### 2.4 Reified Record（关系节点）

所有实体都基于 `Entity`，关系节点只是一种用法约定：

```python
class LivesIn(Entity):
    uid: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single")
    country: Country = Field(cardinality="single")
    since: int = Field(cardinality="single")
```

**稳定合约**：编译后 schema 会为所有 `Entity` 生成 `<T>:exists` predicate；batch 写入字段时会自动补 `<T>:exists` 写入 op。

### 2.5 常用类型映射

| Python 注解 | type_domain |
|------------|------------|
| `str` | `string` |
| `int` | `int` |
| `bool` | `bool` |
| `float` | `float64` |
| `bytes` | `bytes` |
| `datetime` | `time` |
| `UUID` | `uuid` |
| 其他 `Entity` 子类 | `entity_ref` |

**当前行为**：也支持字符串注解（如 `"str"`、`"datetime"`、`"uuid"`、`"entity_ref"`）；无法识别的注解会回退为 `entity_ref`。

### 2.6 内存对象 vs 托管对象

```python
# 普通内存对象（不绑定 store）
alice = User(user_id="u-001")
alice.name = "Alice"      # 普通 Python 赋值

# sdk.batch 托管对象（支持 .set/.add/.retract）
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice_h = tx.entity(User, user_id="u-001", lang="zh")
    alice_h.name.add("Alice")
    tx.commit()
```

**稳定合约**：`.set` / `.add` / `.retract` 是 batch/edit 托管句柄能力，不是普通内存对象能力。

---

## 3. 写入数据

### 3.1 `sdk.batch`

批量写入主入口，适合 ETL、样本数据构造、以及需要 preview / wire plan 的场景。

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "hr"}) as tx:
    de = tx.entity(Country, iso_code="DE")
    de.name.set("Germany")

    # 一次性提供所有 Identity
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")
    u.age.set(30)
    u.country.set(de)   # 可直接引用同 tx 内的 handle

    # 或分步绑定 Identity
    u2 = tx.entity(User, user_id="u-002")
    u2 = u2.bind(lang="en")
    u2.name.add("Alicia")

    plan = tx.preview()   # 只读预览，不落盘
    res = tx.commit()     # 实际写入
```

`batch` 的 `meta` 会被所有写入操作继承；单条操作可以用自己的 `meta` 覆盖：

```python
with sdk.batch(meta={"source": "hr", "valid_from": "2024-01"}) as tx:
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")                                  # 继承 batch meta
    u.name.add("Alice", meta={"valid_from": "2024-06"})    # 单条覆盖
    tx.commit()
```

**meta 合并优先级**（高覆盖低）：`commit_meta > field_op_meta > entity_meta > batch_meta`

**稳定合约**
- `single` 字段用 `.set()`；`multi` 字段用 `.add()`，用错抛 `SDKStoreError`（batch handle 路径；`sdk.edit` 路径抛 `CardinalityError`）。
- batch handle 用 `.retract(assertion_id)` 撤销；edit 的 `FieldEditor` 用 `.retract(asrt_id=...)` 撤销；两者均不支持按值撤销。
- Identity 不完整时 `.set()` / `.add()` 会立即抛 `SDKStoreError`（错误信息会列出缺失字段；可先 `bind(...)` 补齐后再写）。
- 对 Identity 字段调用 `.set()` / `.add()` 立即抛 `SDKStoreError`——Identity 一旦确定不可变。
- `preview()` 不落盘，可重复调用；`commit()` 才落盘。
- `SDKBatchTx` 的 context manager 本身不自动 commit，也不自动 rollback（`__exit__` 是空操作）；需要显式调用 `commit()`，异常处理也需要调用方自行负责。

**entity_ref 字段**（稳定合约）：可传"同 tx 句柄"或"canonical idref_v1 token"；不能传普通业务字符串（如 `"DE"`）。

**字段基数规则速查**

| 字段类型 | 允许 | 禁止 |
|---------|------|------|
| `single` | `.set(value)` | `.add(value)` → `SDKStoreError`（batch）/ `CardinalityError`（edit） |
| `multi` | `.add(value)` | `.set(value)` → `SDKStoreError`（batch）/ `CardinalityError`（edit） |
| 任意 | `.retract(assertion_id)` (batch) / `.retract(asrt_id=...)` (edit) | 按值撤销（不支持） |

```python
# batch handle 路径
u.age.set(30)         # single ✅
u.age.add(30)         # ❌ SDKStoreError
u.name.add("Alice")   # multi ✅
u.name.set("Alice")   # ❌ SDKStoreError
```

### 3.2 Wire Plan（可序列化 / 可回放）

```python
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("Alice")
    wire_json = tx.preview().to_json(sdk)

# 跨进程/跨时间回放
from factpy_kernel.sdk.batch import WireBatchPlan

plan2 = WireBatchPlan.from_json(wire_json)
plan2.apply(sdk, strict_schema=True)
```

**当前行为**：`strict_schema=True` 会检查 wire plan 的 `schema_digest` 与当前 SDK schema 一致性。

**当前行为补充**：wire 导出（`to_json` / `export`）不接受 raw `idref_v1` 字符串值作为 `entity_ref` 写入；要做可回放 wire plan，请在 batch 里使用“同 tx 句柄引用”表达实体关系。

### 3.3 依赖闭包（`include_deps`）

默认 `include_deps=True`：提交某个对象会自动包含它引用到的依赖对象。缺依赖不是静默跳过，会直接报错（**稳定合约**）。

### 3.4 `sdk.edit`

适合"已知完整 identity，只改少量字段"的场景：

```python
with sdk.edit(User, user_id="u-001", lang="zh") as editor:
    editor.name.add("Alicia")
    editor.age.set(31)
    # 正常退出 with：自动 commit()
    # with 块内抛异常：自动 rollback()
```

显式控制版本：

```python
editor = sdk.edit(User, user_id="u-001", lang="zh")
editor.__enter__()
try:
    editor.name.add("Alicia")
    plan = editor.preview()
    editor.commit(meta={"trace_id": "manual-fix", "approved_by": "admin"})
except Exception:
    editor.rollback()
    raise
```

**稳定合约**
- 找不到实体抛 `EntityNotFoundError`（不会隐式创建，新建请用 `sdk.batch()`）。
- `commit()` 或 `rollback()` 后 editor 关闭，再调用任何方法抛 `EditorClosedError`。

### 3.5 `sdk.ingest`

适合外部导入、或只有 `ref + asrt_id`（拿不到完整 identity）的场景：

```python
result = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": alice_ref, "value": "Alicia"},
        {"kind": "set", "field": User.age, "e_ref": alice_ref, "value": 31},
        {"kind": "retract", "asrt_id": "asrt_old_xxx"},
    ],
    meta={"source": "hr", "trace_id": "hr-001"},
)

print(result.written_assertion_ids)
print(result.skipped_count)
print(result.duplicate_count)
print(result.warnings)
print(result.diagnostics)
```

**Item 结构**

| `kind` | 必填字段 | 可选字段 |
|------|---------|---------|
| `set` | `field`, `e_ref`, `value` | `meta` |
| `add` | `field`, `e_ref`, `value` | `meta` |
| `retract` | `asrt_id` | `meta` |

**稳定合约**
- 顶层 `meta` 与 item `meta` 合并，item 同名键覆盖顶层。
- `kind=set` 对应 `single` 字段；`kind=add` 对应 `multi` 字段。
- 只要 `diagnostics` 中存在任一 `severity="error"`，整批不写（collect-and-stop）。
- `allow_sensitive_meta=True` 只会关闭 sensitive warning，不会放宽 hard reserved 约束。

### 3.5.1 典型场景：实体迁移

当通过 `find` 拿不到完整 identity 时，`ingest` 是可行的兜底方案：

```python
records = sdk.find(LivesIn, user=alice.ref)
li = records[0]

old_asrt_id = li.assertions.country.active[0].asrt_id
fr_ref = sdk.get(Country, iso_code="FR").ref

sdk.ingest(
    [
        {"kind": "retract", "asrt_id": old_asrt_id},
        {"kind": "set", "field": LivesIn.country, "e_ref": li.ref, "value": fr_ref},
    ],
    meta={"source": "hr", "trace_id": "relocation-001", "note": "Alice 搬到法国"},
)
```

### 3.6 低层写入口

```python
alice_ref = sdk.ref(User, user_id="u-001", lang="zh")
sdk.set(User.age, alice_ref, 31, meta={"source": "hr"})
sdk.add(User.name, alice_ref, "Alicia", meta={"source": "hr"})
sdk.retract("asrt_xxx", meta={"source": "hr"})
```

最少封装，直接落 ledger，不提供 preview/wire 能力。

---

## 4. meta 字段

meta 不是自由字典，字段按职责分四类：

**系统保留（ingest 流程写入，用户不可写）**

`ingested_at`、`ingest_key`、`revoked_asrt_id`

**操作追踪（约定字段，推荐填写）**

`source`、`source_loc`、`trace_id`、`confidence`、`approved_by`、`note`

**推导链（accept 流程自动写入）**

`derived_rule_id`、`derived_rule_version`、`run_id`、`support_digest`、`support_kind`、`candidate_id`、`candidate_key`、`accepted_at` 等

**业务时态（用于解锁时间视图）**

`valid_from`、`valid_to`、`version`

业务时态字段用户可写，视图层感知，但不强制。不填则只有 `.active` / `.history` 两个视图；填写后解锁 `.at(t)` / `.version(v)` 查询。

**meta key 分层**（稳定合约）

| 层级 | 代表字段 | 行为 |
|------|---------|------|
| hard reserved | `ingested_at`、`ingest_key`、`revoked_asrt_id` | 用户不可写 |
| sensitive semantic | `derived_rule_id`、`run_id`、`support_digest` 等推导链字段 | 默认 warning，不阻塞写入 |
| convention | `source`、`source_loc`、`trace_id`、`confidence`、`approved_by`、`note` | 正常写入 |
| free | 业务自定义 key | 正常写入 |

**去重依据**：`claim + source + source_loc + trace_id + valid_from + valid_to + version`

注意：`ingested_at` 是系统写入时间，不等同于 `valid_from`（业务有效时间）。用 `ingested_at` 代替 `valid_from` 做时间视图会导致语义错位。

**`trace_id` 语义**：`trace_id` 参与幂等计算，但不是唯一决定因素；`valid_from` / `valid_to` / `version` 也参与去重。同一 `trace_id` 下，只要时态维度不同，仍会生成不同断言。

---

## 5. 读取数据

### 5.1 `sdk.get`

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

if snap is None:
    print("不存在")
else:
    print(snap.ref)                 # canonical idref_v1 token
    print(snap.entity_type)         # "User"
    print(snap.identity_available)  # True
    print(snap.identity)            # 可用于 sdk.edit(...) 的 identity kwargs
```

**稳定合约**
- `get` 只接受 Identity 参数；传非 Identity 字段抛 `SDKSchemaError`。
- 返回 `EntitySnapshot | None`。
- `get` 路径返回的快照 `identity_available=True`。

### 5.2 `sdk.find`

```python
# single 字段：精确匹配
rows = sdk.find(User, age=30)

# multi 字段：包含匹配
rows = sdk.find(User, name="Alice")

# entity_ref 字段
de = sdk.get(Country, iso_code="DE")
rows = sdk.find(User, country=de.ref)   # ✅
rows = sdk.find(User, country=de)       # ✅（内部取 .ref）

rows = sdk.find(User, age=30, limit=20)
```

**稳定合约**
- `limit` 必须是非负整数（`limit=0` 返回空列表）。
- 使用 Identity 过滤时必须提供该实体全部 Identity 字段。
- 不支持 `temporal_view` 参数。
- 传未知过滤字段抛 `SDKSchemaError`。

**`find` 结果的 identity 可用性**（当前行为）

```python
records = sdk.find(LivesIn, user=alice_ref)
for rec in records:
    if rec.identity_available:
        with sdk.edit(LivesIn, **rec.identity) as editor:
            ...
    else:
        # 走 ingest：用 rec.ref + asrt_id 做 retract/set
        ...
```

- 无 identity filter 路径：快照通常 `identity_available=False`。
- 使用完整 identity filter 路径：返回快照 `identity_available=True`。

### 5.3 `EntitySnapshot` 断言视图

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

# 当前视图值
snap.name      # multi -> tuple[...]
snap.age       # single -> 标量或 None
snap.country   # single entity_ref -> idref_v1 token 或 None

# 断言视图
snap.assertions.name.active           # 当前未撤销断言
snap.assertions.name.history          # 完整历史（含已撤销）
snap.assertions.name.at("2024-03-01") # 业务时态过滤
snap.assertions.name.version("v2")    # 版本过滤
snap.field("name").active             # 等价写法
```

**视图语义**（稳定合约）

| 视图 | 语义 |
|------|------|
| `.active` | 当前未撤销，由 store 注册机制维护 |
| `.history` | 完整历史，含已撤销 |
| `.at(t)` | active 集合上：`valid_from <= t` 且（`valid_to` 为空或 `valid_to > t`） |
| `.version(v)` | active 集合上：`version == v` |

**时态视图边界**
- `valid_from` 缺失的断言不命中 `.at(t)`，只出现在 `.active` 里。
- `version` 缺失的断言不命中 `.version(v)`。
- `.at(t)` 校验 ISO 8601 格式（`t` 参数和断言的 `valid_from`/`valid_to` 都校验）；非法格式抛 `SDKStoreError`。
- `.version(v)` 仅接受 `str | int`（`bool` 非法）。
- 时态过滤在 active 集合上叠加，不从 history 里取。
- `EntitySnapshot` 和 `assertions` 命名空间都是只读；赋值抛 `FrozenSnapshotError`。

---

## 6. Rule / Query / Derivation

### 6.1 变量声明

```python
from factpy_kernel.sdk import vars

# 推荐写法
with vars("u", "l", "n") as (u, l, n):
    ...

# 工厂写法
with vars() as V:
    u, l, n = V("u", "l", "n")
```

**稳定合约**：不支持 `with vars() as (u, l)` 无参解包，会抛 `SDKDSLError`。

### 6.2 Rule：即时查询

```python
from factpy_kernel.sdk import Rule, Pred, Not, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_rule = Rule(
        id="q_speaks",
        version="1.0.0",
        select=[u, l],
        where=[
            LivesIn(li),
            li.user == u,      # 两步写法（链式不支持）
            li.country == c,
            HasLanguage(hl),
            hl.country == c,
            hl.language == l,
        ],
    )

rows = sdk.run(speaks_rule, row_format="dict")
# [{"u": "...", "l": "..."}, ...]
```

**稳定合约**
- `LivesIn(li).user == u` 链式写法不支持；请使用两步写法。
- OR 使用 `where=[[...], [...]]`（OR-of-AND）。
- `row_format` 三层优先级：`run(..., row_format=...) > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`。
- 非法 `row_format` 值抛 `SDKStoreError(code="INVALID_ROW_FORMAT")`。
- `RuleRef` 目标规则需要 `expose=True`，否则报 `RuleCompileError`；不允许出现在 `Not(...)` 体内。

**当前行为**：支持线性算术 `+/-/常数倍`（如 `age == (2026 - by)`）；不支持 `x * y` 非线性乘法。

### 6.3 Query DSL

Identity 和 Field 字段在 where 子句里访问语法完全一致：

```python
from factpy_kernel.sdk import Query, vars

with vars("u", "l", "n") as (u, l, n):
    q = Query(
        head=[User(u), User.name(lang=l, name=n)],
        where=[
            User(u),
            u.lang == l,    # 约束 Identity 字段
            u.name == n,    # 约束 Field 字段
        ],
    )

rows = sdk.run(q)   # 默认返回 list[dict]
```

**稳定合约**
- Query 支持 `row_format="dict"|"instance"`；默认 `"dict"`。
- `row_format="instance"` 仅在 head 为“单个 `Entity(var)`”时可用；返回 `list[EntitySnapshot|None]`。
- Query head 形态不满足 instance 约束，或 Query 使用非法 `row_format`，都会抛 `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`。
- 合法 head 形态：`Entity(var)`、`[Entity(var1), ...]`、`Entity.field(...)`。
- Query 构造期执行 alias 冲突校验（抛 `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`）和 where 变量绑定校验（抛 `SDKDSLError(code="QUERY_UNBOUND_VAR")`）。
- entity head 列返回 `EntitySnapshot`；field 投影列返回标量值。

**当前行为**：`on_missing` / `on_type_mismatch` 策略：
- `error`：抛 `SDKStoreError`（`QUERY_MISSING_REF` / `QUERY_TYPE_MISMATCH`）
- `skip`：丢弃该行
- `null`：该列置 `None`，行保留（仍参与去重）

### 6.4 Derivation

```python
from factpy_kernel.sdk import Derivation, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            LivesIn(li), li.user == u, li.country == c,
            HasLanguage(hl), hl.country == c, hl.language == l,
        ],
        head=Speaks(user=u, language=l),
    )

cands = sdk.evaluate(speaks_drv, mode="python")   # list[CandidateSet]
res = sdk.accept(cands[0], approved_by="alice")

# 多候选集原子提交
res = sdk.accept_many(cands, mode="atomic")
```

**稳定合约**
- `sdk.evaluate(...)` 产出候选，不写 ledger；`sdk.accept(...)` 才写 ledger。
- 支持 `head=[H1, H2, ...]` 多 head；`evaluate` 返回展平结果，共享同一个 `run_id`。
- `sdk.accept(CandidateSet, ...)` 只接受一个位置参数；允许覆盖键：`approved_by`、`note`、`dry_run`、`identity_override`（也可通过 `meta_overrides` 传入）；未识别参数抛 `SDKStoreError`。
- `sdk.run(Derivation(...))` 不支持；应使用 `sdk.evaluate(...)`。
- 存在依赖图时，优先使用 `sdk.accept_many(..., mode="atomic")` 保证原子性。

**当前边界**
- `sdk.evaluate(..., temporal_view=...)` 被显式拒绝。
- Derivation head 的时态写语义（head 直接产出带 `valid_from`/`valid_to`/`version` 的断言）尚未开放。时态信息目前只能在写入路径（`sdk.batch`/`sdk.ingest`）通过 meta 携带。

### 6.5 head 的 Identity 规则

```
head 里出现的字段 = 所有非 primary Identity + 目标 Field 值
```

- **`primary_key` 字段**：无论有多少个，一律不出现在 head 里，由 where 的实体绑定隐式携带。
- **非 primary Identity 字段**：必须在 head 里显式给出，否则写入目标不确定。

```python
# User 有 primary_key=user_id，非 primary Identity=lang
head=User.name(lang=l, name=n)   # user_id 不出现，lang 必须给出
```

head 里出现 `primary_key` 字段是编译期硬错误。

### 6.6 跨坐标联结

同一实体在不同坐标下的两个事实，在 Rule 里是两个不同的变量，通过 `primary_key` 显式联结：

```python
with vars("u1", "u2", "n1", "n2") as (u1, u2, n1, n2):
    q = Query(
        head=[],
        where=[
            User(u1), u1.lang == "zh", u1.name == n1,
            User(u2), u2.lang == "en", u2.name == n2,
            u1.user_id == u2.user_id,   # primary_key 跨坐标联结
        ],
    )
```

**稳定合约**
- 跨坐标联结只允许 `primary_key` 字段参与 `==` 比较。
- 非 `primary_key` 字段的跨坐标等值比较是编译期硬错误，报错会提示应使用哪个 `primary_key` 字段。
- 跨实体类型比较是编译期硬错误。

### 6.7 Rule / Derivation 当前限制速查

| 限制 | 说明 |
|------|------|
| 字符串 DSL | `sdk.run("...")` / `sdk.evaluate("...")` 不支持 |
| `sdk.run(Derivation(...))` | 不支持；应使用 `sdk.evaluate(...)` |
| 链式路径比较 | `LivesIn(li).user == p` 不支持，请分两步 |
| 跨坐标非 primary_key 比较 | 编译期硬错误 |
| 非线性算术 | `x * y` 不支持 |
| `Not(...)` 体 | 需非空；与外层绑定关系有安全校验 |
| `RuleRef` 在 `Not(...)` 体内 | 编译期错误 |

---

## 7. Provenance 校验

`sdk.validate_provenance(...)` 是纯校验入口，不写 ledger，不自动阻塞 ingest/accept。

```python
report = sdk.validate_provenance(candidate_set, standard="derivation_v1")

# 或校验 dict
report = sdk.validate_provenance(
    {"derived_rule_id": "drv.speaks", "derived_rule_version": "1.0.0",
     "run_id": "run-001", "support_kind": "exact", "support_digest": "sha256:...."},
    standard="derivation_v1",
)

print(report.ok)
print(report.errors)
print(report.warnings)
```

**`derivation_v1` 必填项**（稳定合约）

| 字段 | 要求 |
|------|------|
| `derived_rule_id` | 非空字符串 |
| `derived_rule_version` | 非空字符串 |
| `run_id` | 非空字符串 |
| `support_kind` | 非空字符串 |
| `support_digest` | `sha256:<64hex>` |

可选键 `schema_digest` / `policy_digest` 格式不符时写入 `warnings`（不进入 `errors`）。

---

## 8. 选哪个写入入口？

| 场景 | 推荐入口 |
|------|---------|
| 构造有引用关系的对象，需要先预览再提交 | `sdk.batch()` |
| 已知完整 identity，只改少量字段 | `sdk.edit(...)` |
| 外部系统推送 item 列表，或只有 `ref + asrt_id` | `sdk.ingest(...)` |
| 推导候选的审阅与物化 | `sdk.evaluate(...) + sdk.accept(...)` |
| 单条低层写入 | `sdk.set / sdk.add / sdk.retract` |

**决策树**

```text
要不要先看写入计划（ops）？
  ├─ 要 -> sdk.batch()
  └─ 不要
      ├─ 有完整 identity 且只改一个实体？
      │    ├─ 是 -> sdk.edit(...)
      │    └─ 否
      │         ├─ 是推导候选写入？
      │         │    ├─ 是 -> sdk.evaluate(...) + sdk.accept(...)
      │         │    └─ 否 -> sdk.ingest(...)
```

**常见误选**

| 误选 | 正确做法 |
|------|---------|
| `find(...)` 拿不到 identity 还想走 `edit` | 改用 `ingest(retract + set/add)` |
| 需要跨进程回放写入 | 用 `batch.preview().to_json(sdk)` 导出 wire plan |
| 外部导入时把 hard reserved meta 当普通 key | 去掉保留 key，必要时先 `validate_provenance(...)` |

---

## 9. 错误处理速查

### 9.0 错误分层

| 层级 | 代表错误 | 典型触发 |
|------|---------|---------|
| SDK facade 层 | `SDKSchemaError` / `SDKStoreError` | 入参形态错误、约束不满足、功能边界不支持 |
| 实体读写对象层 | `EntityNotFoundError` / `FrozenSnapshotError` / `CardinalityError` / `EditorClosedError` | edit/get/snapshot/assertions 相关 |
| DSL 构造层 | `SDKDSLError` | vars/Rule/Derivation 对象构建不合法 |
| Core 编译/执行层 | `RuleCompileError` | 规则语义约束（如 RuleRef 目标未 expose=True） |
| ingest 诊断层 | `result.diagnostics`（非异常） | item 级校验失败（collect-and-stop） |

`SDKError` 及其子类统一提供结构化字段：`code`（机器可读错误码）、`path`（未设置时为 `None`）。

### 9.1 常见错误速查

| 错误 | 常见触发 | 处理建议 |
|------|---------|---------|
| `EntityNotFoundError` | `sdk.edit(...)` 目标不存在 | 核对 identity；新建用 `sdk.batch()`；`err.entity_type` 和 `err.identity_kwargs` 可辅助排查 |
| `FrozenSnapshotError` | 对 `EntitySnapshot` 或 `assertions` 赋值 | 改用 `sdk.edit(...)` / `sdk.ingest(...)` |
| `CardinalityError` | `sdk.edit` 路径：`single` 字段用 `.add`，或 `multi` 字段用 `.set`（`sdk.batch` 路径同类错误抛 `SDKStoreError`）| 按字段 cardinality 选择正确 API |
| `EditorClosedError` | `commit/rollback` 后继续使用 editor | 重新打开 `sdk.edit(...)` |
| `SDKSchemaError` | `get` 传非 identity 字段；`find` 字段非法或 identity 不完整 | 对照 schema 修正参数 |
| `SDKStoreError` | 写入类型不匹配；`accept` 传未知参数；`run/evaluate` 传字符串 DSL | 检查参数类型和接口边界 |
| `SDKStoreError(code="INVALID_ROW_FORMAT")` | `row_format` 非法值 | 改为 `"dict"` |
| `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")` | Query 使用非法 `row_format`、`row_format="instance"` 但 head 不满足约束，或对 Derivation 调用 `sdk.run(...)` | Query 用 `"dict"`/`"instance"` 且满足 head 约束；Derivation 用 `sdk.evaluate(...)` |
| `SDKDSLError(code="QUERY_ALIAS_CONFLICT")` | Query head 输出 alias 重复 | 调整 head 变量命名 |
| `SDKDSLError(code="QUERY_UNBOUND_VAR")` | Query where 使用未绑定变量 | 在 head 或前序原子中绑定该变量 |
| `SDKDSLError` | 链式实体写法；`with vars() as (u,)` 无参解包 | 改用支持语法（两步写法） |
| `RuleCompileError` | `RuleRef` 目标未 `expose=True` | 修正规则声明 |
| `IngestResult.diagnostics` 含 `error` | item 结构非法；unknown retract asrt_id | 按 `path` 逐条修复；有 error 时整批不写 |

### 9.2 ingest 诊断排查

```python
res = sdk.ingest(items, meta=meta)
for d in res.diagnostics:
    print(d["severity"], d["code"], d["path"], d["message"])
```

排查顺序：先看 `diagnostics`（结构错误定位最快）→ 再看 `warnings`（语义敏感 key）→ 最后看 `written_assertion_ids`。

---

## 10. Registry

### 10.1 初始化

```python
from factpy_kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
```

**稳定合约**：构造方式二选一：`SDKRegistry(root_dir=...)` 或 `SDKRegistry(registry=...)`；同时传且路径不一致抛 `SDKRegistryError`。

### 10.2 应用 Schema

```python
res = reg.apply_schema_classes(
    [User, Country],
    apply_request_id="req-001",
    transaction_policy="best_effort_no_rollback_v1",
)

print(res["ok"])
print(res["apply_execute"]["idempotency"]["replayed"])
```

同一个 `apply_request_id` 重放时走幂等 replay（当前行为）。

### 10.3 注册 Rule / Derivation

```python
with vars("u", "l") as (u, l):
    rule = Rule(
        id="rule.speaks", version="1.0.0",
        select=[u, l],
        where=[Pred("speaks:language", u, l)],
        expose=True,
    )
reg.register_rule(rule)

with vars("u", "l", "n") as (u, l, n):
    drv = Derivation(
        id="drv.copy_lang", version="1.0.0",
        head=User.name(lang=l, name=n),
        where=[User(u), u.lang == l, u.name == n],
    )
reg.register_derivation(drv)
```

也可直接注册已编译 spec（跳过 DSL compile）：

```python
reg.register_rule_spec(compiled_rule_spec_dict)
reg.register_derivation_spec(compiled_derivation_spec_dict)
```

**当前行为**：多 head Derivation 仅在运行时 `sdk.evaluate(...)` 路径支持；`register_derivation(...)` 按单 head 处理，需要发布多 head 逻辑时请先展开为多个单 head 分别注册。

### 10.4 读取与列举

```python
reg.list_rule_ids()
reg.list_derivation_ids()
reg.list_rule_versions("rule.speaks")
reg.list_derivation_versions("drv.copy_lang")
reg.get_latest_rule_spec("rule.speaks")
reg.read_rule_spec("rule.speaks", "1.0.0")
reg.get_latest_derivation_spec("drv.copy_lang")
reg.read_derivation_spec("drv.copy_lang", "1.0.0")
```

**稳定合约**：`get_latest_*` / `read_*` 在目标不存在时返回 `None`。

### 10.5 发布流水查询

```python
reg.list_apply_run_ids()
reg.list_apply_runs()
reg.show_apply_run("req-001")
```

**当前行为**：`show_apply_run(...)` 不存在时返回 `None`；`list_apply_runs()` 返回 apply execute run 记录列表（`list[dict]`）。

### 10.6 底层统一入口：`apply_authoring_bundle`

```python
res = reg.apply_authoring_bundle(
    authoring_schema=authoring_schema_dict,
    rule_request={"rule_spec_payload": compiled_rule_spec_dict},
    apply_request_id="req-002",
)
```

**当前行为**：`apply_authoring_bundle(...)` 是 `apply_schema_classes(...)` 的底层总入口，适合一次性组合 schema/rule/derivation 变更。

### 10.7 Schema 元数据

```python
manifest = reg.read_manifest()          # registry manifest dict
entry = reg.get_schema_entry()          # schema entry 元数据（dict | None）
res = reg.upsert_schema_ir(schema_ir)   # 直接写入已编译 schema_ir
```

---

## 11. 高级 API

### 11.1 编译后直通

```python
cands = sdk.evaluate_compiled(...)
res = sdk.accept_compiled(...)
```

适合已持有编译后参数并希望跳过 SDK 对象 compile 的场景（当前行为）。

### 11.2 包导出与执行

```python
sdk.export_package("./pkg", options)
sdk.run_package("./pkg", entrypoints=["__query__"], engine="souffle")
```

依赖适配器实现，当前主要是 Souffle 适配器（当前行为）。

### 11.3 调试属性

```python
sdk.store        # 底层 Store 对象
sdk.ledger       # 底层 Ledger 对象
sdk.schema_ir    # 当前 store 实际使用的编译 schema
```

### 11.4 审计查询

```python
audit = sdk.explain_fact("user:age", alice_ref)
conf  = sdk.conflicts("user:age", alice_ref)
```

两者都基于当前 active 断言集合计算（**稳定合约**）。

`explain_fact(pred_id, e_ref, *val_atoms)` 返回（当前行为）：
- `pred_id`、`e_ref`
- `active_claims`：`list[dict]`，每项包含 `asrt_id`、`args`、`meta`
- `chosen_asrt_id`

`*val_atoms` 参数按"值原子精确匹配"过滤 `active_claims`。

`conflicts(pred_id, e_ref)` 返回（当前行为）：
- `pred_id`、`e_ref`
- `active_asrt_ids`
- `chosen_asrt_id`

`pred_id` 传谓词 ID（如 `"user:age"`）；`e_ref` 传 canonical `idref_v1` token。

---

## 12. 迁移速记（v2）

**Schema 层**
- `Field.cardinality`：`functional` / `temporal` → `single`
- `Field.dims`、`Field.fact_key`、`Field.pred_id` 已删除
- `Identity` 新增 `primary_key` 参数；无 `primary_key=True` 的 Entity 在 Rule 跨 Field 联结时编译报错

**Rule / DSL 层**
- `head` 里出现 `primary_key` 字段是编译期硬错误
- `temporal_view` 参数从 evaluate/runtime 入口移除（显式报错）
- 非 `primary_key` 字段参与跨坐标 `==` 比较是编译期硬错误
- `.chosen` 视图已移除，统一使用 `.active`

**协议层（`sdk_batch_plan_v1`）**
- `dims`、`fact_key` 从 wire 协议删除
- `cardinality` 枚举值变更（`functional` / `temporal` → `single`）

**时态语义现状**

| 能力 | 状态 |
|------|------|
| 写入：`valid_from`/`valid_to`/`version` 持久化并进入去重 | ✅ 已实现 |
| 读取：`snapshot.assertions.<field>.at(t)` / `.version(v)` | ✅ 已实现 |
| Rule/Derivation head 产出时态断言 | ⬜ 规划中 |
