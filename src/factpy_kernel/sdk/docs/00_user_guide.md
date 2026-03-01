# FactPy SDK 使用指南

> 当前实现基线：commit `7252468`  
> 本文面向 SDK 使用者，按“声明 schema -> 写入 -> 读取 -> 推导”的实际流程组织。  
> 当前文件已收录第 1-12 章。

---

## 目录

1. [安装与初始化](#1-安装与初始化)
2. [Schema 定义](#2-schema-定义)
3. [写入数据：`sdk.batch`](#3-写入数据sdkbatch)
4. [读取数据：`sdk.get` / `sdk.find`](#4-读取数据sdkget--sdkfind)
5. [编辑数据：`sdk.edit`](#5-编辑数据sdkedit)
6. [外部导入：`sdk.ingest`](#6-外部导入sdkingest)
7. [规则与推导](#7-规则与推导)
8. [Provenance 校验](#8-provenance-校验)
9. [选哪个写入入口？](#9-选哪个写入入口)
10. [错误处理速查](#10-错误处理速查)
11. [Registry 发布与读取：`SDKRegistry`](#11-registry-发布与读取sdkregistry)
12. [API Surface 补充（高级）](#12-api-surface-补充高级)

---

## 约定：文档中的状态标签

文档中的行为描述按以下三类标签区分，方便你判断哪些测试应写强断言、哪些应保留演进空间：

| 标签 | 含义 |
|------|------|
| **稳定合约** | 对外承诺的行为，不应随意变化；建议写强断言测试 |
| **当前行为** | 当前实现如此，但未来可能优化；测试建议保留灵活性 |
| **规划中** | 尚未实现，已有方向或触发条件 |

术语约定：
- `canonical ref` = canonical `idref_v1` token（字符串）。

---

## 1. 安装与初始化

### 1.1 初始化 Store

```python
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore

# User/Country/Language/LivesIn 是你定义的 Entity 子类
sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

如需文件持久化，直接传 `ledger_path`：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

说明（稳定合约）：
- `SDKStore.from_schema_classes(...)` 会先编译 schema，再构造底层 `Store`。
- `ledger_path=...` 会打开或创建 file-backed Ledger，并在首次使用时写入 `schema_digest`。
- 使用同一 `ledger_path` 恢复时，会校验当前 schema 的 `schema_digest`；不一致会抛 `SDKStoreError`。
- `ledger` 与 `ledger_path` 互斥；两者不能同时传入。
- `classes` 必须是非空 `list[Entity 子类]`，否则抛 `SDKStoreError`。

### 1.2 Schema 预检（CI / import 阶段）

在不需要运行时 store 的场景（如 CI 校验、模块导入时），可以单独做预检：

```python
from factpy_kernel.sdk import schema_preflight_from_classes

# 返回值是 dict DTO（不是对象）
preflight = schema_preflight_from_classes([User, Country, LivesIn])

print(preflight["ok"])                # True / False
print(preflight.get("warnings", []))  # 预检 warning 列表
print(preflight.get("summary", {}))   # entity_count / predicate_count / pred_ids
```

说明（稳定合约）：
- `schema_preflight_from_classes(...)` 返回 `dict`，核心键包括：
  - `ok`
  - `warnings`
  - `errors`
  - `diagnostics`
  - `summary`（成功时）
- `schema_preflight_from_classes(...)` 与 `SDKStore.from_schema_classes(...)` 是独立步骤，可分开使用。

---

## 2. Schema 定义

### 2.1 基本声明

```python
from factpy_kernel.sdk import Entity, Field, Identity

class Country(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    name: str = Field(cardinality="functional", pred_id="country:name")
    population: int = Field(cardinality="functional", pred_id="country:population")

class User(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    name: str = Field(cardinality="multi", pred_id="user:name")
    # entity_ref 字段在写入层使用 canonical idref_v1 token（字符串）
    country: Country = Field(cardinality="functional", pred_id="user:country")
    age: int = Field(cardinality="functional", pred_id="user:age")
```

说明（稳定合约）：
- `Entity` 子类必须至少声明一个 `Identity` 字段，否则类定义阶段抛 `SDKSchemaError`。
- `Field.cardinality` 的有效值以 schema compile 为准：`functional` / `multi` / `temporal`。

### 2.2 `Identity(...)` 参数

| 参数 | 说明 |
|------|------|
| `default=...` | 固定默认值 |
| `default_factory="uuid4"` | 缺省时自动生成 UUID（当前仅该取值在 SDK ref 路径有明确支持） |

说明（当前行为）：
- `sdk.ref(...)` 和 `tx.entity(...)` 都走同一 identity 解析逻辑，因此会触发 `default` / `default_factory`。
- 非 `uuid4` 的 `default_factory` 不属于当前 SDK v1 的稳定支持面。

### 2.3 `Field(...)` 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `cardinality` | ✅ | `functional` / `multi` / `temporal` |
| `pred_id` | 推荐 | 显式谓词 ID |
| `name` | - | 字段命名覆盖（authoring 层） |
| `aliases` | - | 别名列表 |
| `display_name` | - | 展示名 |
| `description` | - | 描述文本 |
| `value_name` | - | value 参数名 |
| `fact_key` | - | 维度冲突组 key（需是 dims 子集） |
| `dims` | - | 维度规格（如 `[("lang", "string")]` 或 `[{name,type_domain}]`） |
| `type_domain` | - | 覆盖注解推导类型 |

说明（稳定合约）：
- 若设置 `fact_key`，其成员必须来自该字段 `dims`，否则 schema compile 报错。
- `dims` 为空时不能设置 `fact_key`。

### 2.4 Reified Record（关系节点）

关系实体/事件实体仍然基于 `Entity`，不需要显式 `is_record` 开关：

```python
class LivesIn(Entity):
    uid: str = Identity(default_factory="uuid4")
    user: User = Field(cardinality="functional", pred_id="livesin:user")
    country: Country = Field(cardinality="functional", pred_id="livesin:country")
    since: int = Field(cardinality="functional", pred_id="livesin:since")
```

说明（稳定合约）：
- 编译后 schema 会为所有 `Entity` 生成 `<T>:exists` predicate（`is_entity_exists`）。
- batch 写入实体字段时，会在计划中自动补 `<T>:exists` 写入 op，避免“有字段断言但实体不可见”。

### 2.5 常用注解类型映射

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

补充（当前行为）：
- 也支持字符串注解（如 `"str"`、`"datetime"`、`"uuid"`、`"entity_ref"`）。
- 无法识别的注解会回退为 `entity_ref`。

### 2.6 内存对象 vs 托管对象

这是最常见的混淆点：

```python
# 普通内存对象（不绑定 store）
alice = User(source_id="u-001")
alice.name = "Alice"      # ✅ 普通 Python 赋值

# sdk.batch 托管对象（支持 .set/.add/.retract）
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice_h = tx.entity(User, source_id="u-001")
    alice_h.name.add("Alice")   # ✅
    tx.commit()
```

说明（稳定合约）：
- `.set/.add/.retract` 是 batch/edit 托管句柄能力，不是普通内存对象能力。
- 在普通对象上误用这些方法时，报错形态取决于字段当前值（可能是 `SDKSchemaError`，也可能是普通 Python `AttributeError`）。

---

## 3. 写入数据：`sdk.batch`

`sdk.batch()` 是批量写入主入口，适合 ETL、样本数据构造、以及需要 `preview / wire plan` 的场景。

### 3.1 基本流程

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "HR"}) as tx:
    # 1) 声明实体句柄
    de = tx.entity(Country, source_system="ISO3166", source_id="DE")
    de.name.set("Germany")
    de.population.set(83_000_000)

    alice = tx.entity(User, source_system="APP", source_id="u-001")
    alice.name.add("Alice")
    alice.name.add("爱丽丝")
    alice.country.set(de)   # 可直接引用同一 tx 内 handle

    li = tx.entity(LivesIn, uid="li-uuid-001")
    li.user.set(alice)
    li.country.set(de)
    li.since.set(2020)

    # 2) 预览（不写入）
    plan = tx.preview()
    print(f"将写入 {len(plan.ops)} 条操作")

    # 3) 提交（写入 ledger）
    res = tx.commit()
```

说明（稳定合约）：
- `preview()` 是只读操作，不写入 ledger，可重复调用。
- `SDKBatchTx` 的 context manager 本身不自动 commit；需要显式调用 `commit()`。

### 3.2 字段基数规则（batch 托管句柄）

| 字段类型 | 允许 | 禁止 |
|---------|------|------|
| `functional` | `.set(value)` | `.add(value)` |
| `multi` | `.add(value)` | `.set(value)` |
| 任意 | `.retract(assertion_id=...)` | 按值撤销 |

```python
# functional
alice.age.set(30)   # ✅
alice.age.add(30)   # ❌ SDKStoreError

# functional entity_ref
alice.country.set(de_handle)  # ✅ 句柄
alice.country.set(de_ref)     # ✅ canonical idref_v1 token
alice.country.set("DE")       # ❌ 业务字符串，不是 canonical ref

# multi
alice.name.add("Alice")  # ✅
alice.name.set("Alice")  # ❌ SDKStoreError
```

补充（稳定合约）：
- entity_ref 字段可传“同 tx 句柄”或“canonical idref_v1 token”。
- 不能传普通业务字符串（如 `"DE"`）。

### 3.3 Retract（显式撤销断言）

```python
with sdk.batch(meta={"trace_id": "fix-001"}) as tx:
    alice = tx.entity(User, source_system="APP", source_id="u-001")
    alice.name.retract(assertion_id="asrt_old_xxx")
    tx.commit()
```

说明（稳定合约）：
- retract 仅支持按 `assertion_id` 撤销，不支持按值撤销。
- `assertion_id` 可来自 `snapshot.assertions.<field>.history[*].asrt_id`。

### 3.4 高级：Wire Plan（可序列化 / 可回放）

```python
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice = tx.entity(User, source_id="u-001")
    alice.name.add("Alice")
    plan = tx.preview()
    wire_json = plan.to_json(sdk)

# 跨进程/跨时间回放
from factpy_kernel.sdk.batch import WireBatchPlan

plan2 = WireBatchPlan.from_json(wire_json)
plan2.apply(sdk, strict_schema=True)
```

说明（当前行为）：
- `strict_schema=True` 会检查 wire plan 的 `schema_digest` 与当前 SDK schema 一致性。
- 如果 batch 里把 entity_ref 值直接写成 raw idref 字符串，`commit()` 可以成功，但 `plan.to_json(sdk)` 会拒绝导出（要求用 handle 关系导出）。

### 3.5 meta 合并优先级

当前合并顺序（高优先级覆盖低优先级同名 key）：

`commit_meta > field_op_meta > entity_meta > batch_meta`

```python
with sdk.batch(meta={"source": "batch"}) as tx:
    u = tx.entity(User, source_id="u1", meta={"source": "entity"})
    u.name.add("Alice", meta={"source": "field"})
    tx.commit(commit_meta={"source": "commit"})
# 最终 source=commit
```

### 3.6 依赖闭包（`include_deps`）

默认 `include_deps=True`：提交某个对象会自动包含它引用到的依赖对象。

```python
res = tx.commit(objects=[job], include_deps=True)
```

当 `include_deps=False` 且选择集合缺依赖时，错误会在 `preview()` / `commit()` 阶段抛出：

```python
# 若 job 引用了 alice，但 objects 仅给了 [job] 且 include_deps=False
plan = tx.preview(objects=[job], include_deps=False)  # ❌ SDKStoreError: missing dependency
```

说明（稳定合约）：
- 缺依赖不是“静默跳过”，会直接报错并携带 staging path（便于定位哪个句柄缺失）。

---

## 4. 读取数据：`sdk.get` / `sdk.find`

### 4.1 `sdk.get(...)`：按 identity 精确读取

```python
alice = sdk.get(User, source_system="APP", source_id="u-001")

if alice is None:
    print("不存在")
else:
    print(alice.ref)                # canonical idref_v1 token（字符串）
    print(alice.entity_type)        # "User"
    print(alice.identity_available) # True
    print(alice.identity)           # 可用于 sdk.edit(...) 的 identity kwargs
```

说明（稳定合约）：
- `sdk.get` 只接受 identity kwargs；传非 identity 字段会抛 `SDKSchemaError`。
- 返回值是 `EntitySnapshot | None`。
- `get` 路径返回的快照 `identity_available=True`。

补充（当前行为）：
- 对带 `default_factory="uuid4"` 的 identity 字段，`get(...)` 仍要求显式传值（避免随机 identity）。
- 对有 `default=...` 的 identity 字段，可省略该字段；`snapshot.identity` 会保留你实际传入的 kwargs 形态。

### 4.2 `sdk.find(...)`：按当前视图过滤

```python
# functional 字段：精确匹配
rows = sdk.find(User, age=30)

# multi/temporal 字段：包含匹配
rows = sdk.find(User, name="Alice")

# entity_ref 字段：建议传 ref 或 snapshot
de = sdk.get(Country, source_system="ISO3166", source_id="DE")
rows = sdk.find(User, country=de.ref)  # ✅
rows = sdk.find(User, country=de)      # ✅（内部取 .ref）
rows = sdk.find(User, country="DE")    # ⚠️ 不报错，但通常匹配不到

# 高级参数
rows = sdk.find(User, temporal_view="current", limit=20)
```

过滤语义（稳定合约）：

| 字段类型 | 语义 |
|---------|------|
| `functional` | 当前值精确匹配 |
| `multi` / `temporal` | 当前 tuple 中“包含”匹配 |
| `entity_ref` | 按 canonical ref 精确匹配 |

参数边界（稳定合约）：
- `temporal_view` 仅支持 `"active"` / `"current"`。
- `limit` 需为非负整数（`limit=0` 返回空列表）。
- 传未知过滤字段会抛 `SDKSchemaError`。

当前限制（当前行为）：
- 过滤 dims 字段暂不支持（抛 `SDKSchemaError`）。
- 只要在 `find` 中使用了 identity filter，就必须提供该实体全部 identity 字段（即使部分字段有 default）。

### 4.3 `EntitySnapshot` 常用 API

```python
snap = sdk.get(User, source_system="APP", source_id="u-001")

# 当前视图值
snap.name      # multi -> tuple[...]
snap.country   # functional entity_ref -> idref_v1 token 或 None
snap.age       # functional -> 标量或 None

# identity / ref
snap.ref
snap.identity_available
snap.identity

# assertions
snap.assertions.name.active
snap.assertions.name.history
snap.assertions.country.chosen
snap.field("name").active
```

值形态（稳定合约）：
- functional 字段：标量或 `None`
- multi/temporal 字段：`tuple[...]`
- dimmed 字段：`tuple[DimensionedValue, ...]`

断言视图（稳定合约）：
- `.active`：当前未撤销断言
- `.history`：完整历史（含 revoked）
- `.chosen`：仅适用于“无 dims 的 functional 字段”，否则抛 `CardinalityError`

只读约束（稳定合约）：
- `EntitySnapshot` 和 `assertions` 命名空间都是只读；赋值会抛 `FrozenSnapshotError`。

### 4.4 `temporal_view` 与 `assertions.history`

说明（稳定合约）：
- `temporal_view` 影响的是“当前视图值”与实体可见性。
- `snapshot.assertions.<field>.history` 来自 ledger 历史，不受 `temporal_view` 影响。

### 4.5 `find` 结果里的 identity 可用性

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

说明（当前行为）：
- `find` 无 identity filter 路径：快照通常 `identity_available=False`。
- `find` 使用完整 identity filter 路径：返回快照 `identity_available=True`，`identity` 为该过滤 kwargs。

---

## 5. 编辑数据：`sdk.edit`

`sdk.edit(...)` 适合“我知道目标实体 identity，想改几个字段”的场景。  
实现上它复用 batch 事务机制，但暴露的是更聚焦的单实体编辑接口。

### 5.1 基本用法（context manager）

```python
with sdk.edit(User, source_system="APP", source_id="u-001") as user:
    user.name.add("Alicia")
    user.name.retract(asrt_id="asrt_old_name_xxx")
    fr_ref = sdk.get(Country, source_system="ISO3166", source_id="FR").ref
    user.country.set(fr_ref)  # entity_ref: 传 canonical ref
    user.age.set(31)
```

说明（稳定合约）：
- 正常退出 `with`：自动 `commit()`。
- `with` 块内抛异常：自动 `rollback()`，并且异常不被吞掉。
- `sdk.edit(...)` 找不到目标时抛 `EntityNotFoundError`（不会隐式创建）。

### 5.2 编辑 Record

```python
with sdk.edit(LivesIn, uid="li-uuid-001") as rec:
    rec.country.set(fr_ref)
    rec.since.set(2024)
```

说明（稳定合约）：
- 实体与普通 entity 的 edit 语义一致，区别只在 identity 字段集合。

### 5.3 显式 `preview / commit / rollback`（高级用法）

```python
editor = sdk.edit(User, source_system="APP", source_id="u-001")
editor.__enter__()
try:
    editor.name.add("Alicia")
    plan = editor.preview()  # 查看将提交的 plan（不写入）
    print(f"将写入 {len(plan.ops)} 条")
    editor.commit(meta={"trace_id": "manual-fix", "approved_by": "admin"})
except Exception:
    editor.rollback()
    raise
```

说明（稳定合约）：
- `commit(meta=...)` 支持提交级 metadata 覆盖。
- `commit()` 或 `rollback()` 后 editor 关闭，再调用任何编辑/预览方法会抛 `EditorClosedError`。

### 5.4 `FieldEditor` 操作约束

```python
with sdk.edit(User, source_system="APP", source_id="u-001") as user:
    user.country.set(fr_ref)         # functional
    user.name.add("Alicia")          # multi
    user.name.retract(asrt_id="xxx") # 显式按断言撤销
```

基数规则（稳定合约）：

| 字段类型 | 允许 | 错误调用 |
|---------|------|---------|
| `functional` | `.set(...)` | `.add(...)` -> `CardinalityError` |
| `multi` | `.add(...)` | `.set(...)` -> `CardinalityError` |
| 任意 | `.retract(asrt_id=...)` | 缺少 `asrt_id` 不合法 |

补充（当前行为）：
- `temporal` 字段在 `FieldEditor` 上同样不支持 `.set/.add`（会命中基数检查错误）。

### 5.5 找不到实体时的错误信息

```python
from factpy_kernel.sdk import EntityNotFoundError

try:
    with sdk.edit(User, source_system="APP", source_id="not-exist") as e:
        e.name.add("Ghost")
except EntityNotFoundError as err:
    print(err.entity_type)      # "User"
    print(err.identity_kwargs)  # {"source_system": "...", "source_id": "..."}
```

说明（稳定合约）：
- 新建实体请使用 `sdk.batch()`（`edit` 不是 create/upsert 接口）。

---

## 6. 外部导入：`sdk.ingest`

`sdk.ingest(...)` 适合外部导入、脚本批量修正，或只有 `ref + asrt_id`（拿不到完整 identity）的场景。

### 6.1 基本用法

```python
result = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": alice_ref, "value": "Alicia"},
        {"kind": "set", "field": User.country, "e_ref": alice_ref, "value": fr_ref},
        {"kind": "retract", "asrt_id": "asrt_old_name_xxx"},
    ],
    meta={"source": "CSV_IMPORT", "trace_id": "import-2026-01"},
)

print(result.written_assertion_ids)
print(result.skipped_count)
print(result.duplicate_count)
print(result.warnings)
print(result.diagnostics)
```

说明（稳定合约）：
- 输入 `data` 当前必须是 `list` / `tuple`。
- 顶层 `meta` 与 item `meta` 合并时，item 同名键覆盖顶层。

### 6.2 Item 结构

| `kind` | 必填字段 | 可选字段 |
|------|---------|---------|
| `set` | `field`, `e_ref`, `value` | `dims`, `meta` |
| `add` | `field`, `e_ref`, `value` | `dims`, `meta` |
| `retract` | `asrt_id` | `meta` |

补充（稳定合约）：
- `field` 需要传 SDK `Field` descriptor（如 `User.country`）。
- `e_ref` 需要传 canonical `idref_v1` token（如 `sdk.ref(...)` 或 `snapshot.ref`）。
- `set/add` 在 ingest 层会做 cardinality 预检：  
  - `set` 仅适配 functional 字段  
  - `add` 仅适配 multi 字段

### 6.3 Meta key 分层

| 层级 | 代表 key（示例） | 行为 |
|------|------------------|------|
| hard reserved | `ingested_at`, `ingest_key`, `revoked_asrt_id` | 不能由用户写入 |
| sensitive semantic | `derived_rule_id`, `derived_rule_version`, `run_id`, `support_kind`, `support_digest`, `schema_digest`, `policy_digest`, `candidate_id`, `candidate_key`, `meta_origin` 等 | 默认 warning，不阻塞写入 |
| convention | `source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note` | 正常写入 |
| free | 业务自定义 key | 正常写入（需满足底层 meta 类型约束） |

补充（稳定合约）：
- `allow_sensitive_meta=True` 只会关闭 sensitive warning，不会放宽 hard reserved 约束。
- 影响 `ingest_key` 去重的 meta 物料主要是：`source`、`source_loc`、`trace_id`。

### 6.4 抛异常 vs diagnostics 的边界

`sdk.ingest(...)` 同时有两条错误通道：

| 场景 | 行为 |
|------|------|
| 顶层 `meta` 非法（如包含 hard reserved key） | 直接抛 `SDKStoreError` |
| item 结构非法 / item 内 meta 非法 / unknown `asrt_id` retract | 写入 `result.diagnostics`（`severity="error"`） |
| sensitive key（未开启 `allow_sensitive_meta`） | 写入 `result.warnings`（不阻塞） |

collect-and-stop（稳定合约）：
- 只要 `diagnostics` 中存在任一 `severity="error"`，整批不写入（`written_assertion_ids` 为空）。

### 6.5 典型场景：实体迁移

```python
records = sdk.find(LivesIn, user=alice.ref)
li = records[0]

old_asrt_id = li.assertions.country.chosen.asrt_id
fr_ref = sdk.get(Country, source_system="ISO3166", source_id="FR").ref

sdk.ingest(
    [
        {"kind": "retract", "asrt_id": old_asrt_id},
        {"kind": "set", "field": LivesIn.country, "e_ref": li.ref, "value": fr_ref},
    ],
    meta={"source": "HR", "trace_id": "relocation-001", "note": "Alice 搬到法国"},
)
```

说明（当前行为）：
- 在 `find` 路径拿不到 identity 时，`ingest(retract + set/add)` 是可行兜底方案。

---

## 7. 规则与推导

### 7.1 变量声明：`vars(...)`

```python
from factpy_kernel.sdk import vars

# 推荐写法
with vars("p", "c", "l") as (p, c, l):
    ...

# 工厂写法
with vars() as V:
    p, c, l = V("p", "c", "l")
```

说明（稳定合约）：
- 不支持 `with vars() as (p, c)` 无参解包；会抛 `SDKDSLError`。

### 7.2 Rule：即时查询（不写 ledger）

```python
from factpy_kernel.sdk import Rule, RuleRef, Pred, Not, vars

with vars("p", "c", "l", "li", "hl") as (p, c, l, li, hl):
    speaks_rule = Rule(
        id="q_speaks",
        version="1.0.0",
        select=[p, l],
        where=[
            LivesIn(li),      # 先绑定 实体变量
            li.user == p,     # 再写路径比较（两步）
            li.country == c,

            HasLanguage(hl),
            hl.country == c,
            hl.language == l,
        ],
    )

rows = sdk.run(speaks_rule)
```

语法要点（稳定合约）：
- `LivesIn(li).user == p` 这类链式写法不支持；请使用两步写法。
- 支持 `Pred(...)`、`RuleRef(...)`、`Not([...])`、比较运算（`== != > >= < <=`）。
- OR 使用 `where=[[...], [...]]` 表示“OR-of-AND”。

`RuleRef` 约束（稳定合约）：
- 目标规则需要 `expose=True`，否则运行时报 `RuleCompileError`。
- `RuleRef(base_rule_obj)` 支持对象依赖；在 `sdk.run(...)` 未显式传 `registry` 时，SDK 会自动注册对象依赖规则。

线性算术（当前行为）：
- 支持 `+/-/常数倍` 的比较 lowering（如 `age == (2026 - by)`、`x * 2`）。
- 不支持 `x * y` 非线性乘法。

### 7.3 Derivation：`evaluate` -> `accept`

Derivation 分两步：
- `sdk.evaluate(...)`：产出候选（不写 ledger）
- `sdk.accept(...)`：显式物化（写 ledger）

```python
from factpy_kernel.sdk import Derivation, Pred, vars

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

cands_list = sdk.evaluate(speaks_drv)   # list[CandidateSet]
rows = sdk.accept_many(cands_list, mode="atomic")
print(rows)
```

head 写法（稳定合约）：
- fact 目标常见：`SomeEntity.some_field(...)`（Field head）
- entity 目标常见：`EntityType(role1=..., role2=...)`（Entity head）
- `Field` head 只支持 kwargs，不支持位置参数。
- head 需要是 DSL head call；传普通实体对象会在 `Derivation(...)` 构造时报 `SDKDSLError`。

v2 行为（当前推荐）：
- 由 `head` 自动推断路径（Entity head -> entity candidate；Field head -> fact candidate）。
- `sdk.evaluate(...)` 的 `CandidateSet` 包含 `candidate_id/candidate_key/candidate_kind`。
- 存在依赖图时，优先使用 `sdk.accept_many(..., mode="atomic")`。

### 7.4 `accept(...)` 参数边界

SDK facade 的“候选物化”主路径：

```python
res = sdk.accept(candidate_set, approved_by="alice")
# 或
res = sdk.accept(candidate_set, meta_overrides={"approved_by": "alice", "note": "manual"})
```

说明（稳定合约）：
- `sdk.accept(CandidateSet, ...)` 只接受一个位置参数（候选集对象）。
- 允许的覆盖键仅：`approved_by`、`note`、`dry_run`。
- 未识别参数会抛 `SDKStoreError`。

### 7.5 当前限制（Rule / Derivation）

| 限制 | 说明 |
|------|------|
| 字符串 DSL | `sdk.run("...")` / `sdk.evaluate("...")` 不支持 |
| 链式路径比较 | `LivesIn(li).user == p` 不支持（请分两步） |
| 属性对属性比较 sugar | `a.country == b.country` 不支持 |
| 非线性算术 | `x * y` 不支持 |
| `Not(...)` 体 | 需非空；默认校验下要求与外层绑定关系安全 |

补充（当前行为）：
- SDK 对象 DSL 会先 lower，再进入带 schema 的 authoring compile；exists/path sugar 会被 schema-aware rewrite 到实际 predicate（含自定义 `pred_id`）。

---

## 8. Provenance 校验

`sdk.validate_provenance(...)` 是一个纯校验入口：  
只返回校验报告，不写 ledger，也不会自动阻塞 `ingest/accept`。

### 8.1 基本用法

```python
# 常见：直接校验 CandidateSet
report = sdk.validate_provenance(candidate_set, standard="derivation_v1")

# 也可校验 dict（当前按扁平键）
report = sdk.validate_provenance(
    {
        "derived_rule_id": "drv.speaks",
        "derived_rule_version": "1.0.0",
        "run_id": "run-001",
        "support_kind": "exact",
        "support_digest": "sha256:....",
    },
    standard="derivation_v1",
)

print(report.ok)
print(report.errors)
print(report.warnings)
```

说明（稳定合约）：
- 支持输入：`CandidateSet` 或 `dict`。
- 当前仅支持标准：`derivation_v1`。
- 返回类型：`ValidationReport`（`ok/errors/warnings/diagnostics_contract_version`）。

### 8.2 `derivation_v1` 必填项

| 字段 | 要求 |
|------|------|
| `derived_rule_id` | 非空字符串 |
| `derived_rule_version` | 非空字符串 |
| `run_id` | 非空字符串 |
| `support_kind` | 非空字符串 |
| `support_digest` | `sha256:<64hex>` |

补充（稳定合约）：
- 必填项不满足会进入 `errors`，并使 `ok=False`。

### 8.3 可选 digest 字段

可选键：
- `schema_digest`
- `policy_digest`

说明（当前行为）：
- 这两个键若存在但格式不是 `sha256:<hex>`，会写入 `warnings`（不进入 `errors`）。

### 8.4 dict 输入的形态注意事项

说明（当前行为）：
- `dict` 输入按“扁平键”读取。  
  例如要求 `derived_rule_id` 在顶层。
- 不会自动解包 `{"provenance": {...}}` 这种嵌套结构。

### 8.5 与写入流程的关系

说明（稳定合约）：
- `validate_provenance(...)` 不写入任何数据。
- 是否在 `sdk.accept(...)` 或 `sdk.ingest(...)` 前执行拦截，由调用方决定。

---

## 9. 选哪个写入入口？

这一章给“场景 -> API”的最短决策。

### 9.1 快速对照表

| 场景 | 推荐入口 | 核心理由 |
|------|---------|---------|
| 构造一组有引用关系的对象，并希望先预览再提交 | `sdk.batch()` | 有 handle 依赖闭包 + `preview()` + wire plan |
| 已知完整 identity，只改一个实体 的少量字段 | `sdk.edit(...)` | 语义最直接，自动 commit/rollback |
| 外部系统推送 item 列表，或只有 `ref + asrt_id` | `sdk.ingest(...)` | 不依赖 identity 查找，支持 per-item diagnostics |
| 推导候选的审阅与物化 | `sdk.evaluate(...) + sdk.accept(...)` | 明确区分“候选生成”与“写入落地” |
| 直接做单条低层写入 | `sdk.set/add/retract` | 最少封装，立即写 ledger |

### 9.2 决策树（最小版）

```text
要不要先看写入计划（ops）？
  ├─ 要 -> sdk.batch()
  └─ 不要
      ├─ 是否有完整 identity 且只改一个实体？
      │    ├─ 是 -> sdk.edit(...)
      │    └─ 否
      │         ├─ 是否是推导候选写入？
      │         │    ├─ 是 -> sdk.evaluate(...) + sdk.accept(...)
      │         │    └─ 否 -> sdk.ingest(...)
```

### 9.3 三句口诀

1. `batch`：先搭对象图，再看 plan，再提交。  
2. `edit`：我知道 identity，要改这一个对象。  
3. `ingest`：我有一批写入项，或只有 `ref + asrt_id`。

### 9.4 常见误选修正

| 常见误选 | 更合适的做法 |
|---------|-------------|
| `find(...)` 后拿不到 identity 还想走 `edit` | 改用 `ingest(retract + set/add)` |
| 需要跨进程回放写入却直接循环 `set/add` | 用 `batch.preview().to_json(sdk)` 导出 wire plan |
| 直接 `accept(list_of_candidate_sets)` | 逐个 `accept(candidate_set)`（单个候选集） |
| 外部导入时把 hard reserved meta 当普通 key 写入 | 去掉保留 key，必要时先 `validate_provenance(...)` |

---

## 10. 错误处理速查

### 10.0 错误分层（先判断在哪一层）

| 层级 | 代表错误 | 典型触发 |
|------|---------|---------|
| SDK facade 层 | `SDKSchemaError` / `SDKStoreError` | 入参形态错误、约束不满足、功能边界不支持 |
| 实体读写对象层 | `EntityNotFoundError` / `FrozenSnapshotError` / `CardinalityError` / `EditorClosedError` | `edit/get/snapshot/assertions` 相关 |
| DSL 构造层 | `SDKDSLError` | `vars/Rule/Derivation` 对象构建不合法 |
| Core 编译/执行层 | 例如 `RuleCompileError` | 规则语义约束（如 `RuleRef` 目标未 `expose=True`） |
| ingest 诊断层 | `result.diagnostics`（非异常） | item 级校验失败（collect-and-stop） |

说明（稳定合约）：
- `factpy_kernel.sdk` 顶层导出的 SDK 异常可直接 `except`。
- `sdk.ingest(...)` 存在“抛异常”和“返回 diagnostics”两条错误通道（见第 6 章）。

### 10.1 常见错误速查表

| 错误 / 现象 | 常见触发场景 | 处理建议 |
|------------|-------------|---------|
| `EntityNotFoundError` | `sdk.edit(...)` 目标不存在 | 核对 identity；新建请用 `sdk.batch()` |
| `FrozenSnapshotError` | 对 `EntitySnapshot` 或 `assertions` 赋值 | 改用 `sdk.edit(...)` / `sdk.ingest(...)` |
| `CardinalityError` | `edit` 中 `functional` 用 `.add` 或 `multi` 用 `.set`；或对不适用字段取 `.chosen` | 按字段 cardinality 选择正确 API |
| `EditorClosedError` | `commit/rollback` 后继续使用 editor | 重新打开一个 `sdk.edit(...)` 会话 |
| `SDKSchemaError` | `get` 传了非 identity 字段；`find` 过滤字段非法；`find` identity 不完整 | 对照 schema 修正查询参数 |
| `SDKStoreError` | 低层写入类型不匹配（如 entity_ref 不是 canonical ref）；`sdk.run/evaluate` 传字符串 DSL；`accept` 传未知参数 | 检查参数类型和接口边界 |
| `SDKDSLError` | `with vars() as (p,c)`；链式实体写法等对象 DSL 构造错误 | 改用支持语法（两步写法、named vars） |
| `RuleCompileError`（或上层包装错误） | `RuleRef` 目标规则未 `expose=True`、where 语义不安全 | 修正规则语义/依赖规则声明 |
| `IngestResult.diagnostics` 含 `severity="error"` | item 结构非法、item meta 非法、unknown retract asrt_id | 逐条按 `path` 修复；有 error 时整批不会写入 |

### 10.2 ingest 诊断的最短排查方式

```python
res = sdk.ingest(items, meta=meta)

for d in res.diagnostics:
    print(d["severity"], d["code"], d["path"], d["message"])

if any(d["severity"] == "error" for d in res.diagnostics):
    # collect-and-stop: 本批未写入
    ...
```

排查顺序建议：
1. 先看 `diagnostics`（结构错误、路径定位最快）  
2. 再看 `warnings`（语义敏感 key）  
3. 最后看 `written_assertion_ids / skipped_count / duplicate_count`

---

## 11. Registry 发布与读取：`SDKRegistry`

`SDKRegistry` 是 authoring registry 的 SDK 封装，负责 schema/rule/derivation 的注册、发布流水、以及版本读取。

### 11.1 初始化

```python
from factpy_kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
print(reg.root_dir)
```

说明（稳定合约）：
- 构造方式二选一：`SDKRegistry(root_dir=...)` 或 `SDKRegistry(registry=...)`。
- 若同时传 `root_dir` 和 `registry`，两者路径必须一致，否则抛 `SDKRegistryError`。

### 11.2 应用 schema：`apply_schema_classes(...)`

```python
res = reg.apply_schema_classes(
    [Person],
    apply_request_id="req-001",
    transaction_policy="best_effort_no_rollback_v1",
)

print(res["ok"])
print(res["apply_execute"]["status"])
print(res["apply_execute"]["idempotency"]["replayed"])
```

说明（当前行为）：
- `apply_schema_classes(...)` 先把 `Entity` 类编译为 authoring schema，再走 `apply_authoring_bundle(...)`。
- 同一个 `apply_request_id` 重放时会走幂等 replay，`idempotency.replayed=True`。
- `res["apply_execute"]["..."]` 这类细节字段属于当前行为，后续可能随 authoring 层演进而调整；业务侧建议优先使用顶层 `res["ok"]` 作为成功判断。

### 11.3 注册 / apply 入口（对象、spec、bundle）

既可注册“已编译 spec”，也可直接传 SDK 对象（内部会先 compile）：

```python
from factpy_kernel.sdk import Rule, Derivation, Pred, vars

with vars("e", "c") as (e, c):
    rule = Rule(
        id="rule.country_rows",
        version="1.0.0",
        select=[e, c],
        where=[Pred("person:country", e, c)],
        expose=True,
    )

reg.register_rule(rule)
```

```python
with vars("e", "c") as (e, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country_copy(person=e, country_copy=c),
        where=[Pred("person:country", e, c)],
    )

reg.register_derivation(drv)
```

也可以直接注册“已编译 spec”（跳过 SDK DSL compile）：

```python
reg.register_rule_spec(compiled_rule_spec_dict)
reg.register_derivation_spec(compiled_derivation_spec_dict)
```

更底层的统一入口是 `apply_authoring_bundle(...)`：

```python
res = reg.apply_authoring_bundle(
    authoring_schema=authoring_schema_dict,
    rule_request={"rule_spec_payload": compiled_rule_spec_dict},
    derivation_request={"derivation_id": "...", "version": "...", "target_pred_id": "...", "head_vars": [...], "where": [...]},
    apply_request_id="req-002",
)
```

说明（当前行为）：
- `register_rule(...)` / `register_derivation(...)` 接受 SDK 对象或 authoring payload dict。
- `register_rule_spec(...)` / `register_derivation_spec(...)` 适合“你已经拿到编译后 spec dict”的场景。
- `apply_authoring_bundle(...)` 是 `apply_schema_classes(...)` 的底层总入口，适合一次性组合 schema/rule/derivation 变更。
- `register_derivation(...)` 在未显式传 `schema_ir` 且首轮 compile 失败时，会尝试读取 registry 中已落盘的 schema_ir 重试一次（便于 head-only derivation 注册）。
- 对 head-only derivation，建议先 `apply_schema_classes(...)` 后再注册；或在注册时显式传 `schema_ir=...`，避免“首轮失败后 fallback 重试”带来的理解成本。

### 11.4 读取与列举

```python
print(reg.list_rule_ids())
print(reg.list_derivation_ids())
print(reg.list_rule_versions("rule.country_rows"))
print(reg.get_latest_rule_spec("rule.country_rows"))
print(reg.read_rule_spec("rule.country_rows", "1.0.0"))

print(reg.list_derivation_versions("drv.country_copy"))
print(reg.get_latest_derivation_spec("drv.country_copy"))
print(reg.read_derivation_spec("drv.country_copy", "1.0.0"))
```

说明（稳定合约）：
- `list_*` 系列返回有序列表。
- `get_latest_*` / `read_*` 在目标不存在时返回 `None`。
- rule 与 derivation 的读取命名是对称的：`*_rule_*` 对应 `*_derivation_*`。

### 11.5 发布流水查询（apply runs）

```python
print(reg.list_apply_run_ids())
print(reg.list_apply_runs())
print(reg.show_apply_run("req-001"))
```

说明（当前行为）：
- `show_apply_run(...)` 不存在时返回 `None`。
- `list_apply_runs()` 返回 apply execute run 记录列表（`list[dict]`）。

### 11.6 错误边界

说明（稳定合约）：
- 文件系统/authoring apply 层异常会统一包装为 `SDKRegistryError`。
- `register_rule/register_derivation` 输入既不是 SDK 对象也不是 dict 时，抛 `SDKRegistryError`。

### 11.7 Manifest / Schema 元数据方法

这三个方法容易和“真正 schema 内容”混淆，建议一起看：

```python
manifest = reg.read_manifest()
entry = reg.get_schema_entry()
res = reg.upsert_schema_ir(compiled_schema_ir)
```

`read_manifest()`（当前行为）：
- 返回 registry manifest 的 `dict`（含 `schema/rules/derivations` 索引信息）。
- 如果 manifest 文件尚不存在，会返回默认空结构（不是报错）。

`upsert_schema_ir(schema_ir)`（稳定合约）：
- 直接把一个已编译 `schema_ir` 写入 registry（绕过 `apply_schema_classes` 流程）。
- 返回写入结果 `dict`（典型字段：`kind/status/path/schema_digest`）。
- 传入非法 `schema_ir` 会抛 `SDKRegistryError`（来自底层校验包装）。

`get_schema_entry()`（稳定合约）：
- 返回 manifest 里的 schema entry 元数据（`dict | None`）。
- 常见字段是 `path`（registry 内相对路径），它描述“schema_ir 存放位置”，不是 schema_ir 内容本身。
- 若当前 registry 还没有 schema entry，返回 `None`。

---

## 12. API Surface 补充（高级）

本节补充第 1-10 章未展开、但在 `04_api_surface.md` 中已公开的方法。

### 12.1 低层直写：`ref / set / add / retract`

```python
alice_ref = sdk.ref(User, source_system="APP", source_id="u-001")
sdk.set(User.country, alice_ref, de_ref)
sdk.add(User.name, alice_ref, "Alice")
sdk.retract("asrt_xxx")
```

说明（稳定合约）：
- 这是“最少封装”的写入路径，直接落 ledger，不提供 batch 的 preview/wire 能力。

### 12.2 编译后直通：`evaluate_compiled / accept_compiled`

```python
cands = sdk.evaluate_compiled(...)
res = sdk.accept_compiled(...)
```

说明（当前行为）：
- 这两个 API 是到底层 `store` 的直通入口，适合你已经持有编译后参数并希望跳过 SDK 对象 compile 的场景。
- 常见场景：你拿到了外部流程（如 CLI/registry 发布流水）产出的 compiled 规格，想直接执行而不是再走一次 DSL compile。

### 12.3 包导出与执行：`export_package / run_package`

```python
# options 是 adapter-specific（当前常见为 Souffle 的 ExportOptions）
options = ...
sdk.export_package("./pkg", options)
sdk.run_package("./pkg", entrypoints=["__query__"], engine="souffle")
```

说明（当前行为）：
- 该能力依赖适配器实现（当前主要是 Souffle 适配器）；`options` 的具体类型和细节随适配器演进。
- 如果你的目标是常规 SDK 读写/推导链路，可先忽略这一层高级接口。

### 12.4 调试属性：`sdk.store / sdk.ledger / sdk.schema_ir`

```python
print(sdk.store)
print(sdk.ledger)
print(sdk.schema_ir)
```

说明（稳定合约）：
- 这些属性用于调试、审计和高级集成。
- `sdk.schema_ir` 是当前 store 实际使用的编译 schema。

### 12.5 审计查询：`explain_fact / conflicts`

这两个 API 适合排查 functional 冲突和 chosen 来源。

```python
audit = sdk.explain_fact("person:country", person_ref)      # 可选再追加值原子过滤
audit_de = sdk.explain_fact("person:country", person_ref, "de")
conf = sdk.conflicts("person:country", person_ref)
```

`explain_fact(...)` 返回（当前行为）：
- `pred_id`
- `e_ref`
- `active_claims`：`list[dict]`，每项包含 `asrt_id`、`args`、`meta`
- `chosen_asrt_id`

`conflicts(...)` 返回（当前行为）：
- `pred_id`
- `e_ref`
- `active_asrt_ids`
- `chosen_asrt_id`

参数约束（稳定合约）：
- `pred_id` 传谓词 ID（如 `"person:country"`）。
- `e_ref` 传 canonical `idref_v1` token（如 `snapshot.ref` 或 `sdk.ref(...)`）。
- `explain_fact(..., *val_atoms)` 会按“值原子精确匹配”过滤 `active_claims`。
