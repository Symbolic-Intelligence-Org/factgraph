# FactPy SDK 使用指南

> 本文描述已实现行为；未实现能力明确标注"当前边界"。  
> 文档中的行为按三类标签区分：**稳定合约**（建议写强断言测试）、**当前行为**（可能演进）、**规划中**（尚未实现）。

> **post-L SDK ergonomics redesign 教学说明：** v0.1 SDK 的顶层入口为 `FactGraph`(`SDKStore` 的字面别名)。新代码推荐使用 8 个 taxonomy namespace + 2 个 sub-namespace 的形式 (`fg.read.get(...)` / `fg.write.set(...)` / `fg.what_if.check(...)` / `fg.what_if.fact_overlay.check(...)` / `fg.what_if.rule.disable(...)` / `fg.audit.diff_proof_frames(...)` 等),清晰表达概念分层。本指南下文示例多以 flat `sdk.<method>(...)` 形式呈现 ——这是 **foundational API**,与 nested 形式同样受支持,既不被弃用也不会移除。完整 taxonomy 见 [04_api_surface.md §0](04_api_surface.md);redesign 详细 design 见 [post-L SDK ergonomics redesign blueprint](../../../../docs/blueprints/archive/2026-05-09_post-l-sdk-ergonomics-redesign.md) §5.2 / §5.4。

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
12. [迁移速记（v2 → v3）](#12-迁移速记v2--v3)

---

## 1. 安装与初始化

### 1.1 初始化 Store

```python
from kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

需要持久化时指定 `ledger_path`：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

如需把 explain artifact 也持久化到 sidecar root，以便后续 `SDKStore` 实例继续 `explain_support(...)` / `explain_rule_trace(...)`，可额外指定 `artifact_store_root`：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
    artifact_store_root="./data/artifacts",
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
- `ledger_path` 在打开/创建 ledger 时即记录 `schema_digest`；重新打开时校验，不一致抛 `SDKStoreError`。
- `artifact_store_root` 为可选 `str`；提供后会启用 sidecar-backed explain artifact 持久化读回，不提供则保持默认的进程内 explain registry 语义。
- `default_row_format` 仅作用于 `sdk.run(rule, ...)`，合法值为 `"tuple"` / `"dict"`，默认 `"dict"`。
- 解析结果为 `"tuple"` 时会触发 `DeprecationWarning`；推荐统一改为 `"dict"`。
- `FACTPY_ROW_FORMAT` 环境变量在 `SDKStore` 初始化时读取并缓存（非每次 `run()` 动态读取）。

### 1.2 Schema 预检

在不需要运行时 store 的场景（CI 校验、模块导入阶段），可单独做预检：

```python
from kernel.sdk import schema_preflight_from_classes

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
from kernel.sdk import Entity, Identity, Field

class User(Entity):
    """当未显式设置 description 时，docstring 会作为 fallback。"""

    class Meta:
        version = "v1"
        description = "用户实体"
        tags = ["user", "profile"]

    user_id: str = Identity(primary_key=True, default_factory="uuid4")
    lang: str = Identity()

    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
    country: Country = Field(cardinality="single")
```

`Identity` 定位一条事实，`Field` 承载这条事实的值。读取侧有限度的对称：快照的**值访问**（`snap.lang`、`snap.name`）对两者一致；但 `snap.assertions.lang` 不可用——`assertions` 命名空间只覆盖 `Field` 字段，不覆盖 `Identity` 字段。写入侧区别：对 `Identity` 字段调用 `.set()` / `.add()` 会抛异常。

**稳定合约**：每个 `Entity` 至少需要一个 `Identity(primary_key=True)`，否则类定义时报 `SDKSchemaError`。secondary `Identity()`（例如坐标维度 `locale`、`lang`）允许同时存在。

**当前行为**
- `entity_type` 直接由类名推导，不需要单独声明 `schema_id`。
- `Entity.Meta` 目前只支持 `version`、`description`、`tags`；出现其他键会在声明期报 `SDKSchemaError`。
- `description` 的解析优先级是 `Meta.description > 类 docstring`；只有没有显式 `description` 时才回退 docstring。
- `version`、`description`、`tags` 会进入 authoring / schema 编译输出，但不参与运行时求值语义。

### 2.2 Identity 参数

| 参数 | 含义 |
|------|------|
| `primary_key=True` | 标记为联结锚点；Rule 跨 Field 推理时隐式携带，head 里不出现 |
| `default` | 静态默认值 |
| `default_factory="uuid4"` | 缺省时自动生成 UUID |

`primary_key=True` 与 `default_factory` 是正交的——前者声明语义职责，后者声明生成策略，可以同时使用也可以分开。没有标记 `primary_key=True` 的 Entity，若 Rule 里出现跨 Field 联结，编译期报错。

**建议**：`Identity` 字段应指向实体的业务属性（如 `user_id`、`lang`），而非 `source`、`version` 等数据管理维度。后者属于 meta，不属于 Identity。这只是设计建议，引擎不强制。

### 2.2.1 声明元数据

`Entity` 的声明元数据统一通过 `Meta` 提供：

| 键 | 含义 |
|------|------|
| `version` | 声明版本 |
| `description` | 面向文档和 LLM 的实体说明 |
| `tags` | 轻量分类标签 |

```python
class EmploymentEvent(Entity):
    """如果 Meta.description 缺省，这里会被当作 description。"""

    class Meta:
        version = "v2"
        description = "雇佣事件"
        tags = ["employment", "event"]

    event_id: str = Identity(primary_key=True)
    company: str = Field(cardinality="single")
```

**当前边界**：`Meta` 不是开放字典；`owner`、`llm_hint`、`schema_id` 之类字段目前都不支持。

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

### 2.4.1 Relationship Schema 编译

当前也支持单独声明 `Relationship`，用于生成 `(from_ref, to_ref, value)` 形态的关系 predicate：

```python
from kernel.sdk import Entity, Identity, Field, Relationship, SDKStore
from kernel.sdk.compile import compile_schema_from_classes


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([User, Friends])
sdk = SDKStore([User], schema_ir=schema_ir)
```

**稳定合约**

- relationship field predicate 会同时带 `owner_type=<RelationshipType>` 和 `relationship_type=<RelationshipType>`。
- 不需要在示例或业务代码里手动篡改 `schema_ir["predicates"]` 来补 relationship metadata。
- 当需要 `SDKStore` 参与运行时，构造器仍应接收需要直接通过 SDK 操作的 `Entity` 类；relationship predicate 通过显式传入的 `schema_ir` 提供。

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
from kernel.sdk.batch import WireBatchPlan

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

**当前行为**
- `sdk.set(...)` / `sdk.add(...)` 仅在 `e_ref` 的 identity 值已被当前 `SDKStore` 记录时，才会补写对应 identity predicate；任意外部 canonical `idref_v1` 不保证可自动回填。
- `sdk.retract(...)` 返回 revoker assertion id；若目标断言已撤销，则返回已有 revoker id；若断言不存在则抛错。

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

**meta kind 体系**（v3 更新）

meta 数值字段按 kind 分类存储，kind 名称在 v3 中重命名并扩展：

| kind | 类型 | 说明 |
|------|------|------|
| `"str"` | `str` | 字符串 |
| `"int"` | `int` | 整数（原 `"num"`，v3 已重命名） |
| `"float"` | `float` | 浮点数（v3 新增，用于 `confidence` 等字段） |
| `"bool"` | `bool` | 布尔值 |
| `"time"` | `int` | epoch 纳秒时间戳 |
| `"json"` | `Any` | JSON 可序列化对象 |

`confidence` 字段的 kind 固定为 `"float"`，由写入协议自动推断，用户无需指定。

`kind` 对调用方不可见：写入协议会先按约定 key（`_KEY_KIND_MAP`）做强制映射，再对未知 key 按值类型推断。  
约定 key 覆盖检查在模块加载时执行（`convention + sensitive` key 必须都在映射表中）。

未知 key 的类型推断规则（约定 key 优先于此规则）：
- `bool` → `"bool"`
- `int` → `"int"`
- `float` → `"float"`
- `str` → `"str"`
- 其他类型不支持，抛 `WriteProtocolError`

**稳定合约（`confidence`）**
- `meta["confidence"]` 必须是 `float` 且值域在 `(0, 1]`。
- `int`（如 `1`）不会被自动提升为 `float`，会直接报错。
- `meta.confidence` 属于 source/display lane，不应用作 Scenario A 这类 requirement threshold probability。

### 4.1 常见写法示例（`confidence`）

```python
from kernel.core.store.types import ViewSpec

alice_ref = sdk.ref(User, user_id="u-001", lang="zh")

# ✅ 合法：float 且在 (0,1]
sdk.set(User.age, alice_ref, 30, meta={"source": "hr", "confidence": 0.82})
sdk.set(User.age, alice_ref, 30, meta={"source": "model_v2", "confidence": 0.64})

# ❌ 非法：int 不会自动提升为 float
sdk.set(User.age, alice_ref, 30, meta={"confidence": 1})      # WriteProtocolError

# ❌ 非法：越界
sdk.set(User.age, alice_ref, 30, meta={"confidence": 1.2})    # WriteProtocolError

# 读取时按视图聚合
row_max = sdk.find(User, user_id="u-001", lang="zh", view=ViewSpec(confidence_strategy="max"))[0]
row_mean = sdk.find(User, user_id="u-001", lang="zh", view=ViewSpec(confidence_strategy="mean"))[0]
print(row_max.confidence)   # 0.82
print(row_mean.confidence)  # 0.73
```

**去重依据**：`claim + source + source_loc + trace_id + valid_from + valid_to + version`

**边界说明（重要）**
- `confidence` 不参与 ingest 幂等键。
- 因此在同一 `trace_id`（accept 路径通常等于同一 `run_id`）下，若 claim 与其余去重字段相同，仅 `confidence` 不同不会形成新断言，而会被幂等折叠。
- “同事实不同 `confidence` 并存”通常发生在不同推理批次（`run_id/trace_id` 不同）或不同来源字段（`source/source_loc` 不同）时。

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

from kernel.core.store.types import ViewSpec
rows = sdk.find(User, lang="zh", view=ViewSpec(confidence_strategy="mean"))
```

**稳定合约**
- `limit` 必须是非负整数（`limit=0` 返回空列表）。
- 使用 Identity 过滤时必须提供该实体全部 Identity 字段。
- 不支持 `temporal_view` 参数。
- 传未知过滤字段抛 `SDKSchemaError`。

**当前边界**
- `view` 参数的 `confidence_strategy` 只影响返回结果中的 `confidence` 呈现值，不影响哪些断言被返回。

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
from kernel.sdk import vars

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
from kernel.sdk import Rule, Pred, Not, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_rule = Rule(
        id="q_speaks",
        version="1.0.0",
        description="查找用户可能会说的语言",
        tags=["demo", "query"],
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

rows = sdk.run(speaks_rule, view="default", row_format="dict")
# 默认返回 rows，不在行内注入 confidence 字段

rows, display_meta = sdk.run(
    speaks_rule,
    view="default",
    row_format="dict",
    return_display_meta=True,
)
# display_meta 与 rows 等长：每项至少包含 confidence / confidence_strategy / source_breakdown
```

**稳定合约**
- `LivesIn(li).user == u` 链式写法不支持；请使用两步写法。
- OR 使用 `where=[[...], [...]]`（OR-of-AND）。
- `row_format` 三层优先级：`run(..., row_format=...) > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`。
- 非法 `row_format` 值抛 `SDKStoreError(code="INVALID_ROW_FORMAT")`。
- `RuleRef` 目标规则需要 `expose=True`，否则报 `RuleCompileError`；不允许出现在 `Not(...)` 体内。
- `view` 可传具名视图名或 `ViewSpec`，仅影响结果呈现，不改变 Rule 求值范围。
- `sdk.run(rule, view=...)` 默认只返回 `rows`，不在行内注入 `confidence`。
- `return_display_meta=True` 时返回 `(rows, display_meta)`；且必须同时提供 `view`，否则抛 `SDKStoreError`。
- `Rule` 支持 `description`、`tags` 两个声明字段；它们会进入 compiler 输出，但不影响查询语义。

**当前行为**：支持线性算术 `+/-/常数倍`（如 `age == (2026 - by)`）；不支持 `x * y` 非线性乘法。

### 6.3 Body：带置信度的 OR 分支

概率推理场景下，OR 分支可用 `Body` 包装并附带分支置信度：

```python
from kernel.sdk import Body

with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            Body([User(u), Pred("user:lang_pref", u, lang)], confidence=0.9),
            Body([User(u), Pred("user:inferred_lang", u, lang)], confidence=0.6),
        ],
        head=Speaks(user=u, language=lang),
    )
```

**稳定合约**
- `Body.confidence` 值域：`(0, 1]`，`confidence=0` 编译期报错。
- `Body.confidence=None` 合法（表示无置信度约束）。
- 禁止在同一 `where` 里混用 `Body(...)` 与裸 list 分支；违反时编译失败。
- 裸 list 写法保留，编译后 `body_confidences=None`，行为与之前一致。

**支持范围**
- Rule：支持 `Body(...)`，当前仅用于 where 归一化；`Body.confidence` 不直接变成 Rule runtime 参数。
- Derivation：支持 `Body(...)`；编译阶段仍会提取兼容字段 `body_confidences`，但 `sdk.evaluate(..., mode="problog")` 会在执行前把它 bridge 成 `ProbLogRuleExt(branch_probabilities=...)`。
- Query：`Body.confidence` 不支持，构造期报错。
- `Body.confidence` 属于 probabilistic reasoning lane，不等同于 requirement threshold probability。

当前推荐语义 carrier：

- definition-time：`Derivation.engine_ext=ProbLogRuleExt(branch_probabilities=...)`
- compatibility authoring lane：`Body(confidence=...)` / authoring payload `body_confidences`
- SDK evaluate bridge：compat lane -> `ProbLogRuleExt`

compatibility bridge 链路：
`SDK Derivation/authoring payload -> compile_authoring_derivation_v1 -> compiled body_confidences -> sdk.evaluate bridge -> engine_ext -> engine(problog)`。

### 6.3.1 `Body` 的模式差异示例

```python
from kernel.sdk import Body, Derivation, Pred, vars

with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.lang",
        version="1.0.0",
        where=[
            Body([Pred("user:lang_pref", u, lang)], confidence=0.9),
            Body([Pred("user:lang_model", u, lang)], confidence=0.6),
        ],
        head=User.name(lang="zh", name=lang),
    )

# native：不会消费 branch probabilities（与裸 list 行为一致）
cands_native = sdk.evaluate(drv, mode="native")
print(cands_native[0].confidence)  # None

# problog：SDK 会先把 Body.confidence bridge 成 ProbLogRuleExt，再返回概率
import kernel.adapters.problog
cands_prob = sdk.evaluate(drv, mode="problog")
print(cands_prob[0].confidence)    # float，例如 0.86
```

```python
# ❌ 混用 Body 和裸 list（编译期报错）
with vars("u") as (u,):
    Rule(
        id="r.bad",
        version="1.0.0",
        select=[u],
        where=[Body([Pred("p", u)], confidence=0.9), [Pred("q", u)]],
    )
```

### 6.4 Query DSL

Identity 和 Field 字段在 where 子句里访问语法完全一致：

```python
from kernel.sdk import Query, vars

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
- where 中推荐使用字段 sugar 表达 schema field 条件，例如 `u.name == name`、`u.tag == "admin"`。这会 lowering 到对应 predicate（`user:name` / `user:tag`），`single` 与 `multi` 字段都支持。`Pred("...")` 是低层显式 predicate escape hatch，用于非 schema field predicate、temporal / uncertainty predicate 或调试迁移场景。
- entity head 列返回 `EntitySnapshot`；field 投影列返回标量值。
- `Query.where` 不支持 `Body.confidence`；传入时编译报错。
- `sdk.run(query, view=...)` 不支持（抛 `SDKStoreError`）。
- `sdk.run(query, return_display_meta=True)` 不支持（抛 `SDKStoreError`）。

**当前行为**：`on_missing` / `on_type_mismatch` 策略：
- `error`：抛 `SDKStoreError`（`QUERY_MISSING_REF` / `QUERY_TYPE_MISMATCH`）
- `skip`：丢弃该行
- `null`：该列置 `None`，行保留（仍参与去重）

### 6.5 Derivation

```python
from kernel.sdk import Derivation, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        description="根据居住地和官方语言推导用户语言能力",
        tags=["demo", "derivation"],
        where=[
            LivesIn(li), li.user == u, li.country == c,
            HasLanguage(hl), hl.country == c, hl.language == l,
        ],
        head=Speaks(user=u, language=l),
    )

cands = sdk.evaluate(speaks_drv, mode="native")   # list[CandidateSet]
res = sdk.accept(cands[0], approved_by="alice")

# 多候选集原子提交
res = sdk.accept_many(cands, mode="atomic")
```

**`mode` 合法值**（稳定合约，v3 更新）

| mode | 说明 |
|------|------|
| `"native"` | Python 内置求值器（原 `"python"`，已重命名） |
| `"souffle"` | Souffle 引擎（原 `"engine"`，已重命名） |
| `"problog"` | ProbLog 概率推理引擎 |
| `"pyreason"` | PyReason 图上模糊推理引擎 |

旧名 `"python"` / `"engine"` 传入时明确报错，并提示新名称。

引擎采用名称注册表（非单例）：`register_engine_evaluator(name -> fn)`。
适配器模块导入时自动注册：
- `import kernel.adapters.souffle` 注册 `"souffle"`
- `import kernel.adapters.problog` 注册 `"problog"`
- `import kernel.adapters.pyreason` 注册 `"pyreason"`

### 6.4.1 PyReason 使用示例

```python
import kernel.adapters.pyreason  # 注册 "pyreason"
from kernel.adapters.pyreason.rule_ext import PyReasonRuleExt
from kernel.adapters.pyreason.accept import persist_pyreason_annotations

# engine_ext 携带引擎特有规则语义（definition-time）
drv = Derivation(
    id="drv.popular",
    version="v1",
    where=[Pred("user:name", u, name)],
    target="user:popular",
    head_vars=[u],
    mode="pyreason",
    engine_ext=PyReasonRuleExt(timestep_delay=1),
)

# engine_options 携带运行时配置（call-time only，不进入 Derivation）
cands = sdk.evaluate(drv, engine_options={"timesteps": 5})

# accept 后持久化语义 annotation
result = sdk.accept(cands[0])
persist_pyreason_annotations(sdk.ledger, cands[0].run_id, sdk.store, result)
# → pyreason/semantic/bound_lower, bound_upper 等写入 Annotation Store
```

### 6.4.2 ProbLog 使用示例

```python
import kernel.adapters.problog  # 注册 "problog"
from kernel.adapters.problog.rule_ext import ProbLogRuleExt

drv = Derivation(
    id="drv.speaks",
    version="v1",
    where=[
        [Pred("user:lang_pref", u, lang)],
        [Pred("user:lang_model", u, lang)],
    ],
    target="user:speaks",
    head_vars=[u, lang],
    mode="problog",
    engine_ext=ProbLogRuleExt(branch_probabilities=(0.9, 0.6)),
)

cands = sdk.evaluate(drv, engine_options={"timeout": 15})
print(cands[0].confidence)  # float probability
```

**关键区分**：
- `engine_ext`：定义期引擎语义 carrier；共享类型上可挂在 `Rule.engine_ext` 或 `Derivation.engine_ext`，编译时伴随但不序列化
- `engine_options`：运行时参数，call-time only，`mode="native"` 拒绝非空 options
- 语义 annotation：accept 后需显式调用 `persist_pyreason_annotations()` 或 `persist_problog_annotations()` 完成持久化
- ProbLog 的 definition-time contract 当前是 `ProbLogRuleExt.branch_probabilities`
  - `Body(confidence=...)` / `body_confidences` 仍可用，但只是 bridge 输入，不再是 shared evaluate 参数

**稳定合约**
- `sdk.evaluate(...)` 产出候选，不写 ledger；`sdk.accept(...)` 才写 ledger。
- 支持 `head=[H1, H2, ...]` 多 head；`evaluate` 返回展平结果，共享同一个 `run_id`。
- `sdk.accept(CandidateSet, ...)` 只接受一个位置参数；允许覆盖键：`approved_by`、`note`、`dry_run`、`identity_override`（也可通过 `meta_overrides` 传入）；未识别参数抛 `SDKStoreError`。
- `sdk.run(Derivation(...))` 不支持；应使用 `sdk.evaluate(...)`。
- `sdk.evaluate(..., view=...)` 不支持；传入时抛 `SDKStoreError`（推理路径始终基于完整 active 断言集）。
- 存在依赖图时，优先使用 `sdk.accept_many(..., mode="atomic")` 保证原子性。
- `Derivation` 支持 `description`、`tags` 两个声明字段；它们会进入 compiler 输出，但不影响候选生成语义。

### 6.5.1 `accept` 幂等与并存示例

```python
from dataclasses import replace
import kernel.adapters.problog

cands = sdk.evaluate(speaks_drv, mode="problog")
cand = cands[0]

# 第一次写入
r1 = sdk.accept(cand, approved_by="alice")
print(r1.accepted_count, r1.skipped_count)  # 1, 0

# 完全相同候选再次写入：幂等跳过
r2 = sdk.accept(cand, approved_by="alice")
print(r2.accepted_count, r2.skipped_count)  # 0, 1
print(r2.skipped_reason_counts)             # {"duplicate": 1}

# 同一 claim，不同 confidence：并存（不是 duplicate）
cand_v2 = replace(cand, confidence=0.61)
r3 = sdk.accept(cand_v2, approved_by="alice")
print(r3.accepted_count, r3.skipped_count)  # 1, 0
```

**当前边界**
- Derivation head 的时态写语义（head 直接产出带 `valid_from`/`valid_to`/`version` 的断言）尚未开放。时态信息目前只能在写入路径（`sdk.batch`/`sdk.ingest`）通过 meta 携带。

### 6.6 head 的 Identity 规则

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

### 6.7 跨坐标联结

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

### 6.8 Rule / Derivation 当前限制速查

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
from kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
```

**稳定合约**：至少提供 `root_dir` 或 `registry` 之一；两者也可同时传入，但路径必须一致，否则抛 `SDKRegistryError`。

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

导出包格式为 v2，`manifest.json` 包含 `"export_version": "v2"`，facts 目录结构：

```text
facts/
  claim.facts
  claim_arg.facts
  meta_str.facts
  meta_int.facts
  meta_float.facts
  meta_bool.facts
  meta_time.facts
  revokes.facts
```

浮点 meta 采用可逆序列化：导出写 `repr(value)`，导入读 `float(raw)`；科学计数法是合法格式。

**稳定合约**：v1 格式的包（含 `meta_num.facts`，无 `export_version`）喂给新 reader 时明确报错 `unsupported export_version`。

### 11.3 可配置视图（`sdk.views`）

视图定义了"用哪个视角读数据"，影响 `sdk.find()` 和 `sdk.run()` 的结果呈现：

```python
from kernel.core.store.types import ViewSpec

sdk.views.create("conservative", ViewSpec(confidence_strategy="max"))
sdk.views.create("hr_only", ViewSpec(
    confidence_strategy="prefer_source",
    prefer_source="HR系统",
))
sdk.views.update("conservative", ViewSpec(confidence_strategy="mean"))
sdk.views.delete("hr_only")
sdk.views.get("conservative")
sdk.views.list()
```

`sdk.views` 是进程内管理器（非持久化）；重启进程后会回到内置 `"default"` 视图。

**`ViewSpec` 参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `active` | `bool` | `True` | 是否只看 active 断言 |
| `confidence_strategy` | `str` | `"max"` | 置信度聚合策略 |
| `prefer_source` | `str \| None` | `None` | 仅 `prefer_source` 策略时有效 |

**置信度聚合策略**

| 策略 | 语义 |
|------|------|
| `"max"` | 取最高置信度（默认） |
| `"mean"` | 算术平均 |
| `"median"` | 中位数 |
| `"prefer_source"` | 优先取 `prefer_source` 来源，未命中降级为 `max` |

**作用范围**：`confidence_strategy` 仅影响 `sdk.find()` / `sdk.run()` 结果呈现，不影响推理过程。`sdk.evaluate()` 不接受 `view` 参数。

**`sdk.run(..., view=...)` 输出契约**（稳定合约）
- 默认：返回 `rows`（`list[dict]` 或 `list[tuple]`），不在行内注入 `confidence` 字段。
- `return_display_meta=True`：返回 `(rows, display_meta)`。
- `display_meta` 与 `rows` 等长，每项至少包含 `confidence`、`confidence_strategy`、`source_breakdown`。
- `return_display_meta=True` 必须配合 `view` 使用，否则抛 `SDKStoreError`。

### 11.3.1 端到端示例：`find` 与 `run` 如何拿到 confidence

```python
from kernel.core.store.types import ViewSpec

# 1) 注册视图（均值策略）
sdk.views.create("risk_mean", ViewSpec(confidence_strategy="mean"))

# 2) find：直接在快照对象上拿聚合值
users = sdk.find(User, lang="zh", view="risk_mean")
print(users[0].confidence)  # 例如 0.73

# 3) run：默认不注入 confidence
rows = sdk.run(speaks_rule, view="risk_mean", row_format="dict")
print(rows[0])  # {"u": "...", "l": "..."}

# 4) run + return_display_meta：拿展示元信息
rows, display_meta = sdk.run(
    speaks_rule,
    view="risk_mean",
    row_format="dict",
    return_display_meta=True,
)
print(display_meta[0]["confidence"])           # 例如 0.73
print(display_meta[0]["confidence_strategy"])  # "mean"
print(display_meta[0]["source_breakdown"])     # 按 source 的聚合拆分
```

**内置视图**：`"default"`（`active=True, confidence_strategy="max"`），不可删除。

**内联视图**（临时，不存储）：

```python
sdk.find(User, view=ViewSpec(confidence_strategy="mean"))
sdk.run(rule, view="conservative", row_format="dict")
sdk.run(rule, view=ViewSpec(confidence_strategy="max"), row_format="dict")

rows, display_meta = sdk.run(
    rule,
    view="conservative",
    row_format="dict",
    return_display_meta=True,
)
```

service `runtime_v1` 的视图管理端点（当前实现）：

| 方法 | 端点 |
|------|------|
| `POST` | `/v1/runtime/sessions/{session_id}/views/create` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/update` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/delete` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/get` |
| `GET` | `/v1/runtime/sessions/{session_id}/views` |

### 11.4 ProbLog 概率推理

```python
from kernel.sdk import Body
import kernel.adapters.problog

with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.infer_speaks",
        version="1.0.0",
        where=[
            Body([User(u), Pred("user:lang_pref", u, lang)], confidence=0.9),
            Body([User(u), Pred("user:inferred_lang", u, lang)], confidence=0.6),
        ],
        head=Speaks(user=u, language=lang),
    )

cands = sdk.evaluate(drv, mode="problog")
res = sdk.accept(cands[0], approved_by="alice")
```

**`CandidateSet.confidence` 字段**（v3 新增）
- 类型：`float | None`
- ProbLog 路径下为边际概率值，native/souffle 路径下为 `None`
- 序列化/反序列化全链路透传，跨进程不丢失
- 该字段当前属于 probabilistic engine lane；Scenario A 的阈值判断应使用 fact-backed `ecss.uncertainty` predicates，而不是复用该字段。

**accept 语义**（v3 更新）
- duplicate 判定为：claim 相同，且业务语义 meta（排除时间戳/run/candidate 标识字段后）相同
- 同一事实来自不同 `confidence`、不同 `source` 的断言可并存，不会被误判为 duplicate

**当前边界**
- ProbLog CLI 不可用或超时时抛 `ProbLogEngineError`。
- 导出阶段结构不支持/参数不合法时抛 `ProbLogExportError`。
- 结果解析失败时抛 `ProbLogImportError`。
- 同一推理批次（同 `run_id/trace_id`）重复写入同一 claim 时，`confidence` 变化本身不会强制产生并存；是否并存仍受 ingest 幂等键约束。

### 11.5 调试属性

```python
sdk.store        # 底层 Store 对象
sdk.ledger       # 底层 Ledger 对象
sdk.schema_ir    # 当前 store 实际使用的编译 schema
```

plain `Entity` 实例的 `repr(...)` 会按声明顺序预览 identity 与 field 值，未赋值 `Field` 显示为 `None`，例如 `User(user_id='u-1', name='Alice', age=None)`。

### 11.6 审计查询

```python
audit = sdk.explain_fact("user:age", alice_ref)
conf = sdk.conflicts("user:age", alice_ref)
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

## 12. 迁移速记（v2 → v3）

### EvaluateMode 重命名

| 旧 | 新 | 传旧值时行为 |
|----|----|----|
| `"python"` | `"native"` | 明确报错，提示新名 |
| `"engine"` | `"souffle"` | 明确报错，提示新名 |
| —— | `"problog"` | v3 新增 |

默认值也同步更新为 `"native"`（包括 authoring DTO/session 和 SDK derivation evaluate 路径）。

### meta kind 重命名 + 新增

| 旧 | 新 | 说明 |
|----|----|----|
| `"num"` | `"int"` | 整数，写入校验更新 |
| —— | `"float"` | v3 新增，`confidence` 字段使用 |

`Ledger.META_KINDS` 已从 `{"str","num","bool","time","json"}` 更新为 `{"str","int","float","bool","time","json"}`。写入 `kind="num"` 的代码需改为 `kind="int"`（系统会在写入校验时明确报错）。

### export 包格式升级（v1 → v2）

| v1 | v2 |
|----|----|
| `meta_num.facts` | `meta_int.facts` |
| —— | `meta_float.facts`（新增） |
| 无 `export_version` | `manifest.json` 含 `"export_version": "v2"` |

v1 格式的包喂给 v2 reader 时明确报错 `unsupported export_version: 'v1'; expected 'v2'`。

### accept 语义变更

| 旧 | 新 |
|----|----|
| duplicate 判定只看 claim（`pred_id + e_ref + rest_terms`） | 还要比较业务语义 meta（排除时间戳/run 标识后） |
| 同事实不同 confidence 会被误判为 duplicate | 自然并存，不再误判 |

### Body DSL（新增）

```python
# v2 写法（仍支持）
where=[[atom1, atom2], [atom3]]

# v3 新写法（需要 confidence 时）
from kernel.sdk import Body
where=[
    Body([atom1, atom2], confidence=0.9),
    Body([atom3], confidence=0.6),
]
# 禁止混用两种写法
```

### `run(view)` 结果契约收紧

| 旧认知 | v3 实际行为 |
|----|----|
| `sdk.run(rule, view=...)` 可能在行内带 `confidence` | 默认不注入行内字段，返回类型与 `row_format` 保持一致 |
| —— | 需要聚合置信度时使用 `return_display_meta=True`，返回 `(rows, display_meta)` |

### Schema 层（v1 → v2，历史遗留）

- `Field.cardinality`：`"functional"` / `"temporal"` → `"single"`
- `Field.dims`、`Field.fact_key`、`Field.pred_id` 已移除
- `Identity(primary_key=True)` 是跨坐标 join 的必要条件
- `sdk_batch_plan_v1` wire payload 不再携带 `dims` / `fact_key`

---

## 13. 可选 domain bundle helper 模式

v0.1 kernel-only wheel 不直接发布 domain bundle。ECSS 合规、行业评分、团队内部审查模型等 domain 层应作为独立包或 monorepo companion 提供。它们可以复用同一个 helper 模式：domain 包拥有自己的 schema preset 或实体定义,对外暴露小函数,内部只调用 `kernel.sdk` 的公开 API。

一个最小 helper 可以这样写：

```python
from kernel.sdk import Entity, Field, Identity, SDKStore


class ReviewNote(Entity):
    note_id: str = Identity(primary_key=True)
    target_ref: str = Field(cardinality="single")
    reviewer: str = Field(cardinality="single")
    decision: str = Field(cardinality="single")


def write_review_note(
    sdk: SDKStore,
    *,
    note_id: str,
    target_ref: str,
    reviewer: str,
    decision: str,
) -> str:
    note_ref = sdk.ref(ReviewNote, note_id=note_id)
    sdk.set(ReviewNote.target_ref, note_ref, target_ref)
    sdk.set(ReviewNote.reviewer, note_ref, reviewer)
    return sdk.set(ReviewNote.decision, note_ref, decision)


sdk = SDKStore([ReviewNote])
write_review_note(
    sdk,
    note_id="review-001",
    target_ref="idref_v1:User:example",
    reviewer="alice",
    decision="approved",
)
```

说明：

- domain 包可以提供 `apply_<domain>_schema(...)` 这类 preset 函数,但该函数属于 domain 包,不是 `kernel.sdk` 的顶层 API。
- helper 应封装 `sdk.ref` / `sdk.set` / `sdk.add` 等公开入口,不要直接写 ledger。
- 如果 helper 依赖 v0.1 wheel 之外的 package,主用户文档必须把它标为 optional-domain 能力,而不是 kernel-only 默认能力。

---

## 14. 何时下探到 Layer 2(`kernel.application`)

绝大多数 Python 用户应停留在 `kernel.sdk`:它提供 `Entity` / `Field` descriptors、DSL sugar、snapshot、batch、editor 与 SDK 异常体系。

当调用方不是人手写 Python schema / DSL,而是 automation 或 wire bridge 时,可以下探到 `kernel.application`:

| 场景 | 为什么不用 SDK facade |
|----|----|
| LLM / agent 产出 JSON-like ingest payload | 调用方没有 SDK `Field` descriptor,只有 `entity_type` / `field_name` / identity 值 |
| HTTP / RPC server 接收跨进程 request | 需要稳定 DTO 和 error shape,而不是 Python DSL object |
| 批量 ingest 需要 `collect_mode="collect"` | application `IngestRequest` 可以把多项错误收集成 DTO |
| 迁移 / replay / bridge adapter | 输入已经是 string-keyed contract,不需要再构造 `Entity` class |

最小形态如下;实际 host 进程负责持有 `store` 与 `SchemaIndex`:

```python
from kernel.application import apply_ingest_request
from kernel.application.protocol import (
    EntitySelector,
    FieldPath,
    IngestRequest,
    IngestSetItem,
)

request = IngestRequest(
    items=(
        IngestSetItem(
            target=EntitySelector(entity_type="User", identity={"user_id": "u-1"}),
            field=FieldPath(entity_type="User", field_name="name"),
            value="Alice",
        ),
    ),
    collect_mode="collect",
)

result = apply_ingest_request(request, store=store, index=schema_index)
```

Layer 2 的 contract 是 SDK-independent:不要传 SDK `Field` descriptor、`EntitySnapshot`、`Query` 或 `Derivation` object。SDK 的职责正是把这些 ergonomic outward objects lower / adapter 成 application DTO。
