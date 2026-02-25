# 15. SDK 快速开始（Python 直接定义）

本教程面向希望把 FactPy Kernel 当作 **Python SDK** 使用的开发者（而不是先写 DSL 文件再走 CLI）。

> 当前实现说明（以代码为准）：
> - `Entity / Field / Identity` 已提供 **runtime 声明类**（SDK facade）
> - `Rule / Derivation / RuleRef / vars / Pred / Not` 已提供 **runtime object DSL**
> - `SDKRegistry.apply_schema_classes(...)` 已可用（这是 `SDKRegistry` 实例方法，不是 `factpy_kernel.sdk` 顶层函数）
> - 底层核心（Store / write_protocol / derivation / export / runner）不变

---

## 目标

在一个 Python 脚本中完成：

1. 定义 `Entity` 类（`Person / Company`）
2. 编译 `SchemaIR` 并做 preflight
3. 用 `SDKStore` 写入事实（含 `meta`）
4. 导出推理包并运行 runner（`souffle` 或 `noop`）
5. 用 `SDKRegistry` 注册 schema / rule / derivation，并查看 apply runs

---

## 1) 定义实体（Python SDK 方式）

```python
from factpy_kernel.sdk import Entity, Field, Identity


class Company(Entity):
    source_id: str = Identity()
    sector: str = Field(cardinality="functional", pred_id="company:sector")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    country_copy: str = Field(cardinality="functional", pred_id="person:country_copy")
    works_at: Company = Field(cardinality="multi", pred_id="person:works_at")
    name_by_lang: str = Field(
        cardinality="functional",
        pred_id="person:name_by_lang",
        dims=[("lang", "string")],
        fact_key=["lang"],
    )
```

说明：

- `Identity()` 定义实体身份字段（用于生成 `EntityRef`）
- `Field(...)` 定义 GNF 事实字段（会编译成 `SchemaIR` predicate）
- `dims + fact_key` 用于表达按维度唯一（如 `(person, lang) -> name`）

---

## 2) 编译 SchemaIR / preflight（不经过 CLI）

```python
from factpy_kernel.sdk import (
    build_authoring_schema_from_classes,
    compile_schema_from_classes,
    schema_preflight_from_classes,
)

authoring_schema = build_authoring_schema_from_classes([Person, Company])
schema_ir = compile_schema_from_classes([Person, Company])
preflight = schema_preflight_from_classes([Person, Company])

print(preflight["ok"], preflight["schema_digest"])
```

你会得到：

- `authoring_schema`：authoring payload（可用于 registry/apply）
- `schema_ir`：可直接喂给 `Store`
- `preflight`：结构化诊断结果（含 `diagnostics/warnings`）

---

## 3) 用 SDKStore 写入事实（含 dims / meta）

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([Person, Company])

# 生成实体引用（EntityRef）
p_ref = sdk.ref(Person, source_id="u-001")
c_ref = sdk.ref(Company, source_id="c-001")

# functional field
asrt_country = sdk.set(
    Person.country,
    p_ref,
    "de",
    meta={"source": "sdk.demo", "source_loc": "demo.py:1", "trace_id": "t-001"},
)

# multi edge
asrt_works = sdk.add(
    Person.works_at,
    p_ref,
    c_ref,
    meta={"source": "sdk.demo", "source_loc": "demo.py:2", "trace_id": "t-002"},
)

# functional + dims（按 lang 分组）
asrt_name_en = sdk.set(
    Person.name_by_lang,
    p_ref,
    "Alice",
    dims={"lang": "en"},
    meta={"source": "sdk.demo", "source_loc": "demo.py:3", "trace_id": "t-003"},
)
asrt_name_de = sdk.set(
    Person.name_by_lang,
    p_ref,
    "Alicia",
    dims=["de"],   # 也支持 positional dims
    meta={"source": "sdk.demo", "source_loc": "demo.py:4", "trace_id": "t-004"},
)

# 撤销（append-only + revokes）
revoker = sdk.retract(
    asrt_works,
    meta={"source": "sdk.demo", "source_loc": "demo.py:5", "trace_id": "t-005"},
)
```

### 可选：使用 `sdk.batch`（staging + flush，对象图写法）

如果你的场景是 ETL / 导入 / notebook / 测试构造，`sdk.batch` 通常比逐条 `ref/set/add` 更顺手。

先强调一个常见误区：

- `Person(...)` / `Company(...)` 创建的是**普通内存对象**，字段写法是 `obj.field = value`
- `tx.entity(Person, ...)` 创建的是 **batch 托管对象**，字段写法才支持 `.set/.add/.retract`

```python
# 普通 Entity（内存对象）
alice_obj = Person(source_id="u-001")
alice_obj.country = "de"  # 用普通赋值

# batch staging（托管对象）
with sdk.batch(meta={"trace_id": "t-batch-001", "source": "sdk.demo"}) as tx:
    alice = tx.entity(Person, source_id="u-001")
    company = tx.entity(Company, source_id="c-001")

    alice.country.set("de")
    alice.works_at.add(company)

    plan = tx.preview()           # 纯函数：不写入
    wire_json = plan.to_json(sdk) # 稳定 JSON（可存盘/回放）
    tx.commit()                   # 执行与 preview 等价的 Core 调用序列
```

如果误写成 `Person(...).country.set(...)`，当前 SDK 会抛出带提示的 `SDKSchemaError`，说明应改用普通赋值或 `tx.entity(...)`。

补充两个常见点（batch v0）：

- `tx.save(...)` 当前只接受 `tx.entity(...)` 返回的托管对象，并且会立即提交（等价 `commit(objects=[handle], ...)`）
- 字段基数规则是严格的：`functional -> set(...)`，`multi -> add(...)`

例如，如果 `Language.name` 在 schema 中是 `multi`，应写成：

```python
language = tx.entity(Language, code="de", language_id="114514")
language.name.add("German")
```

常见错误：

- `dims` 缺少必需维度、或多传未知维度 → `SDKStoreError`
- 传错值类型（如 `int` 字段传 `str`）→ `SDKStoreError`
- 用户传入系统管理 meta key（如 `ingested_at`）→ 底层写入协议拒绝

常见 SDK 异常类型（建议按层捕获）：

- `SDKSchemaError`：`Entity / Field / Identity` 声明、schema 编译/preflight 相关错误
- `SDKStoreError`：`SDKStore` 写入/运行/evaluate/accept 输入不合法
- `SDKRegistryError`：`SDKRegistry` apply / registry IO / 注册包装错误
- `SDKDSLError`：对象式 `Rule / Derivation / Pred / Not / vars` DSL 构造或 lowering 错误

### 可选：读取 / 编辑 Facade（`sdk.get / sdk.find / sdk.edit`）

除底层 `ref/set/add/retract` 和 `sdk.batch` 外，当前 SDK 还提供一层更适合 notebook / 调试 / 轻量人工修正的读写 facade：

- `sdk.get(...)`：按 identity 读取单个只读快照（`EntitySnapshot | None`）
- `sdk.find(...)`：按字段过滤当前视图（返回快照列表）
- `sdk.edit(...)`：按 identity 打开编辑会话（context manager；无异常自动 commit）

```python
from factpy_kernel.sdk import (
    CardinalityError,
    EntityNotFoundError,
    FrozenSnapshotError,
)

# 读取单个实体（按 identity）
alice = sdk.get(Person, source_id="u-001")
if alice is None:
    raise RuntimeError("person not found")

print(alice.ref)          # canonical EntityRef token
print(alice.country)      # functional -> 单值（当前视图）
print(alice.works_at)     # multi -> tuple（当前 active 值）

# 断言级信息（含 asrt_id / meta / active/history）
for asrt in alice.assertions.country.history:
    print(asrt.asrt_id, asrt.value, asrt.is_active, asrt.meta.source)

# multi 字段用 .active / .history；functional 字段可用 .chosen
for asrt in alice.assertions.works_at.active:
    print("works_at:", asrt.value)

# 查询（按当前视图过滤；AND 语义）
rows = sdk.find(Person, country="de")
rows = sdk.find(Person, works_at=c_ref)     # multi 字段：按“包含该值”匹配
rows = sdk.find(Person, source_id="u-001")  # identity 全量过滤也支持

# 编辑（显式进入写会话；无异常自动 commit）
try:
    with sdk.edit(Person, source_id="u-001") as user:
        user.country.set("fr", meta={"source": "manual_fix"})
        user.works_at.add(c_ref, meta={"source": "manual_fix"})
        plan = user.preview()  # 可选：先看 staged ops
        print("staged ops:", len(plan.ops))
except EntityNotFoundError:
    print("entity not found")
```

record（reified relation）也用同一个 `edit(...)` 入口，identity 由 schema 决定：

```python
with sdk.edit(LivesIn, uid="li_u001") as rec:
    rec.country.set("idref_v1:Country:...")  # 或传 sdk.ref(...) 结果
```

### `EntitySnapshot` 怎么看 / 怎么用（重要）

`sdk.get(...)` / `sdk.find(...)` 返回的是 `EntitySnapshot`（只读快照），不是普通 `Entity(...)` 实例，也不是 ORM 对象。

在 notebook 里你通常这样用：

```python
rows = sdk.find(Person, country="de")
print(rows)       # 会显示可读 repr（entity_type/ref/字段预览）

alice = rows[0]
print(alice)      # EntitySnapshot(...)
print(alice.ref)  # canonical EntityRef
```

#### 1) 读当前值：直接访问字段

- `functional` 字段 -> 单值（或 `None`）
- `multi` 字段 -> `tuple[...]`（当前 active 值）
- `entity-ref` 字段 -> 返回 `ref` 字符串（如 `idref_v1:...`）

```python
print(alice.country)     # "de"
print(alice.works_at)    # ("idref_v1:Company:...", ...)
```

#### 2) 看断言级细节：`snapshot.assertions.<field>`

如果你需要 `asrt_id`、`meta`、历史版本（含已撤销），使用 `assertions` 命名空间：

```python
# functional 字段：可看 chosen / active / history
print(alice.assertions.country.chosen)   # 当前 chosen 断言（AssertionRecord | None）
print(alice.assertions.country.active)   # 当前 active 断言元组
print(alice.assertions.country.history)  # 全部历史（含 revoked）

# multi 字段：用 active / history（没有 chosen）
print(alice.assertions.works_at.active)
print(alice.assertions.works_at.history)
```

`AssertionRecord` 常用字段：

- `asrt_id`
- `value`
- `dims`
- `is_active` / `is_revoked`
- `meta`（如 `meta.source / meta.trace_id / meta.ingested_at / meta.raw`）

示例：

```python
for asrt in alice.assertions.country.history:
    print(
        asrt.asrt_id,
        asrt.value,
        asrt.is_active,
        asrt.meta.source,
        asrt.meta.trace_id,
    )
```

#### 3) 快照是只读；修改请用 `sdk.edit(...)`

```python
# 错误：快照不可写
# alice.country = "fr"

with sdk.edit(Person, source_id="u-001") as user:
    user.country.set("fr")
```

#### 4) 常见误解（尤其 notebook）

- `sdk.ledger.find_claims(...)` 返回的是历史账本（含后续可能被 revoke 的 claim）
- `EntitySnapshot` 的字段值来自当前视图（`project_view_facts`），更接近你在规则里看到的结果
- 所以“账本里还在”与“快照里看不到”并不矛盾（通常是被 revoke / 未 chosen）

### 读写对象对照表（避免混淆）

同样看起来像 “对象”，在 SDK 里其实有 4 种常见类型，语义完全不同：

| 对象类型 | 典型来源 | 主要用途 | 字段读取 | 字段写入 | 备注 |
|---|---|---|---|---|---|
| `EntitySnapshot`（只读快照） | `sdk.get(...)` / `sdk.find(...)` | 看当前视图值、看断言历史 | `snap.field` / `snap.assertions.field...` | ❌ 不可写 | notebook 调试最常用 |
| `EntityEditor`（编辑会话） | `with sdk.edit(...) as obj:` | 显式修改已存在实体 | `obj.identity_field`（可读） | `obj.field.set/add/retract` | 无异常自动 commit |
| batch handle（托管对象） | `tx.entity(...)` | 构造对象图、批量写入、preview/wire | `obj.identity_field`（可读） | `obj.field.set/add/retract` | 用于 `sdk.batch(...)` |
| DSL 符号变量 | `with vars(...) as (...)` | `Rule/Derivation` 查询表达式 | `li.country == c`（DSL） | ❌ 不写入 | 不是 store 中实体 |

最常见的误用是把它们混起来：

```python
# 1) Snapshot 不是可编辑对象（错误）
alice = sdk.get(Person, source_id="u-001")
# alice.country.set("fr")   # ❌

# 2) 普通修改请用 edit（正确）
with sdk.edit(Person, source_id="u-001") as user:
    user.country.set("fr")

# 3) batch handle 用于“构造 + 预览 + 批量提交”（正确）
with sdk.batch() as tx:
    user = tx.entity(Person, source_id="u-001")
    user.country.set("fr")
    plan = tx.preview()
    tx.commit()

# 4) vars(...) 是查询符号，不是实体实例（正确用法）
from factpy_kernel.sdk import vars
with vars("u", "c") as (u, c):
    expr = (u == c)  # 只是 DSL 表达式示意
```

说明（v1 语义）：

- `Snapshot` 是只读对象；`alice.country = "fr"` 会抛 `FrozenSnapshotError`
- `Editor` 的字段基数规则仍是严格的：
  - `functional -> .set(...)`
  - `multi -> .add(...)`
  - 调错会抛 `CardinalityError`
- `sdk.edit(...)` 不会隐式创建实体；找不到会抛 `EntityNotFoundError`
- `sdk.find(...)` 过滤基于当前投影视图（而不是原始 ledger 历史）
- `sdk.find(...)` 暂不支持对带 `dims` 的字段做过滤（会显式报错）

实践建议：

- 新建对象/对象图导入：优先 `sdk.batch(...)`
- 精确底层写入：`sdk.ref/set/add/retract`
- Notebook 检视 / 轻量修正：`sdk.get/find/edit`

一个实现边界（重要）：

- `sdk.get(...)` 因为调用者提供了 identity，所以快照通常可直接访问 identity 字段（如 `alice.source_id`）
- `sdk.find(...)` 返回的通用快照总是保证 `.ref` 可用；但某些实体的 identity（例如 `uid`）不一定能从 `ref` 反解，因此不承诺所有 `find` 结果都能访问 `.uid`

---

## 4) 导出推理包并运行（SDK passthrough）

```python
from pathlib import Path
from factpy_kernel.adapters.souffle.package import ExportOptions

pkg_dir = Path("./out/inference_pkg")
manifest_path = sdk.export_package(pkg_dir, ExportOptions(package_kind="inference"))
print("manifest:", manifest_path)

# 若本机没有 souffle，会 fallback noop（见 run_manifest.engine_mode）
run_manifest_path = sdk.run_package(pkg_dir, entrypoints=["person:country"], engine="souffle")
print("run_manifest:", run_manifest_path)
```

说明：

- `SDKStore.export_package(...)` / `run_package(...)` 只是高层 passthrough，底层仍复用现有 `export/runner`
- 适合在同一个 Python 脚本里完成“写入 → 导出 → 执行 → 检查输出”

---

## 5) 用 SDKRegistry 注册 authoring 资产（schema/rule/derivation）

当前 `SDKRegistry` 重点是包装 **authoring apply + file registry**，便于 Python 内直接调用。

```python
from pathlib import Path
from factpy_kernel.sdk import SDKRegistry

sdk_registry = SDKRegistry(Path("./out/registry"))

# 直接从 schema classes 执行 apply（会走 authoring workflow + apply_execute）
bundle = sdk_registry.apply_schema_classes(
    [Person, Company],
    apply_request_id="sdk-apply-001",
    transaction_policy="best_effort_no_rollback_v1",
)
print(bundle["apply_execute"]["status"])
print(bundle["apply_execute"]["idempotency"])

# replay（同 request_id + 同 plan_digest）会走幂等回放
bundle_replay = sdk_registry.apply_schema_classes(
    [Person, Company],
    apply_request_id="sdk-apply-001",
    transaction_policy="best_effort_no_rollback_v1",
)
print(bundle_replay["apply_execute"]["idempotency"]["replayed"])  # True
```

### 注册 Rule / Derivation（对象 DSL 或 payload dict）

```python
from factpy_kernel.sdk import Derivation, Not, Pred, Rule, vars

with vars("e", "c") as (e, c):
    rule = Rule(
        id="rule.country_rows",
        version="1.0.0",
        select=[e, c],
        where=[
            Pred("person:country", e, c),
            Not([Pred("person:blacklist", e, "x")]),
        ],
        expose=True,
    )
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country_copy(person=e, country_copy=c),
        materialize_as="fact",
        where=[Pred("person:country", e, c)],
        mode="python",
        temporal_view="record",
    )

sdk_registry.register_rule(rule)
sdk_registry.register_derivation(drv)
```

说明：

- 上面的 `sdk_registry.apply_schema_classes([Person, Company], ...)` 已把 schema 写入 registry；当前实现里 `register_derivation(drv)` 会在未显式传 `schema_ir` 时自动读取 registry 中的 `schema_ir` 来完成 `head=...` 的 schema-aware lowering（推导 `target_pred_id + head_vars`）。
- 如果 registry 里还没有 schema，请先 `apply_schema_classes(...)` / `upsert_schema_ir(...)`，或改为显式传 `target=...` + `head_vars=[...]`。
- 排查提示（record head 常见误解）：
  - `SDKRegistry.register_derivation(...)` 会先尝试一次“无 schema 编译”，因此 traceback 第一条常见错误可能是 `materialize_as='record' requires id_policy ...`；若随后 fallback 到 registry schema 又报 `record exists predicate not found for X`，通常表示 registry 中保存的 schema 仍是旧版本（尚未包含 `X:exists`）。
  - 遇到这种情况，请先重新 `apply_schema_classes(...)` 更新 registry schema，或在 `register_derivation(..., schema_ir=...)` 中显式传入当前 schema。

显式传 `schema_ir`（推荐用于排障/Notebook 迭代）：

```python
from factpy_kernel.sdk import compile_schema_from_classes

schema_ir = compile_schema_from_classes([Person, Company])  # 用当前类定义现编译

sdk_registry.register_rule(rule)  # rule 一般不需要 schema-aware lowering
sdk_registry.register_derivation(drv, schema_ir=schema_ir)
```

如果你已经有 `SDKStore`，也可以直接复用 store 内的 schema：

```python
sdk_registry.register_derivation(drv, schema_ir=sdk.store.schema_ir)
```

### `materialize_as="record"` 常见坑（重要）

1. `head=RecordType(...)` 的关键字参数必须是 **record role 字段名**

- 不是 identity 字段名（如 `uid` / `source_id`）
- 也不存在隐式 `person=<owner>` 参数，除非该 record 真的定义了 `person` 字段

例如：若 `Person` 被标记为 record，且只有一个字段 `native_language`，则合法写法是：

```python
with vars("n") as (n,):
    drv = Derivation(
        id="drv.person_lang_record",
        version="1.0.0",
        head=Person(native_language=n),  # 只有 role 字段 native_language
        materialize_as="record",
        where=[n == "de"],
        mode="python",
        temporal_view="record",
    )
```

如果写成 `Person(person=e, native_language=n)`，会报类似：
- `head kwargs includes unknown record roles: person`

2. `where` 必须绑定 `head` 中出现的变量

- 例如 `head=Speaks(person=p, language=l)` 时，`where` 必须能导出/绑定 `p`、`l`
- 仅写 `l == "de"` 而不绑定 `p`，后续编译/执行会失败

3. 建模建议：如果你要表达 `(person, language)` 这种 reified 关系，优先定义单独 record 类型

```python
class Speaks(Entity):
    uid: str = Identity(default_factory="uuid4")
    person: Person = Field(cardinality="functional")
    language: Language = Field(cardinality="functional")
    class Meta:
        is_record = True
```

然后使用：

```python
with vars("p", "l") as (p, l):
    drv = Derivation(
        id="drv.speaks_from_rule",
        version="1.0.0",
        head=Speaks(person=p, language=l),
        materialize_as="record",
        where=[
            # 这里用 Pred(...) / RuleRef(...) 绑定 p, l
        ],
        mode="python",
        temporal_view="record",
    )
```

也支持直接传 authoring payload dict（兼容/高级用法）：

```python
rule_payload = {
    "rule_id": "rule.country_rows",
    "version": "1.0.0",
    "select_vars": ["$E", "$C"],
    "where": [("pred", "person:country", ["$E", "$C"])],
    "expose": True,
}

drv_payload = {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "head": {
        "kind": "head_call",
        "callee_kind": "pred_ref",
        "entity_type": "Person",
        "field": "country_copy",
        "kwargs": {"person": "$E", "country_copy": "$C"},
    },
    "materialize_as": "fact",
    "where": [("pred", "person:country", ["$E", "$C"])],
    "mode": "python",
    "temporal_view": "record",
}

sdk_registry.register_rule_spec(rule_payload)
sdk_registry.register_derivation_spec(drv_payload)
```

> 说明：对象 DSL 与 payload dict 都可用；如果对签名或行为有疑问，建议用 `help(SDKStore)` / `inspect.signature(...)` 以代码为准。

---

## 6) Registry 只读查看（Python API）

```python
print(sdk_registry.read_manifest())
print(sdk_registry.get_schema_entry())
print(sdk_registry.list_rule_ids())
print(sdk_registry.list_derivation_ids())
print(sdk_registry.list_apply_run_ids())

print(sdk_registry.show_apply_run("sdk-apply-001"))
print(sdk_registry.get_latest_rule_spec("rule.country_rows"))
print(sdk_registry.get_latest_derivation_spec("drv.country_copy"))
```

这和 CLI 的以下命令对应：

- `registry-list --kind rule_ids`
- `registry-list --kind derivation_ids`
- `registry-list --kind apply_run_ids`
- `registry-show --kind apply-run --id <apply_request_id>`

---

## 7) 当前边界（重要）

当前 SDK v1 目标是 **“不改核心引擎的 facade 层”**，所以有这些边界：

- ✅ 已有
  - `Entity / Field / Identity` runtime 声明
  - `Rule / Derivation / RuleRef / vars / Pred / Not` 对象式 DSL
  - schema compile / preflight bridge
  - `SDKStore`（ref / set / add / retract / get / find / edit / evaluate / accept / export / run）
  - `SDKRegistry`（`apply_schema_classes(...)`、registry 只读、注册 rule/derivation SDK 对象或 payload）
- ❌ 还没有
  - `factpy_kernel.sdk` 顶层 `apply_schema_classes(...)` 便捷函数（请使用 `SDKRegistry.apply_schema_classes(...)`）
  - 部分 where 语法糖（如 attr-to-attr compare）在 SDK object DSL v1 仍有限制
  - `store.save(Person(...))` 这类 ORM 风格批量实例保存
  - 完整前端 UI（当前仍是 audit static UI）

补充：

- 已提供 `sdk.batch`（staging + flush）作为 `SDKStore` 上层易用层，但它不是 ORM，也不替代 Core Contract（`ref/set/add/retract`）

---

## 8) 推荐实践

- **本地/应用内开发**：优先用 SDK（本教程）
- **CLI/CI/安全模式**：继续用 AST-safe 的 DSL 文件 + `authoring.cli`
- 两条路径都会落到同一套 canonical `SchemaIR / RuleSpec / DerivationSpec / apply_execute` 契约

相关教程：

- 教程 09：CLI 速查（CLI 路径）
- 教程 03 / 04：apply 与 registry 运维
- 教程 05：导出审计包与静态审计站点
- `docs/tutorials/16-SDK-Batch-staging（sdk.batch）.md`：`sdk.batch` 快速上手（含 preview / wire plan）
- `docs/tutorials/17-SDK-Batch-staging（语义与契约-v0）.md`：`sdk.batch` 语义/契约边界
