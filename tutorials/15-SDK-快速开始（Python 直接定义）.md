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
  - `SDKStore`（ref / set / add / retract / evaluate / accept / export / run）
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
