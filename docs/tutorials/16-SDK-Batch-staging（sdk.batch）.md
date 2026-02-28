# 16) SDK Batch staging（`sdk.batch`）

`SDKStore.batch()` 提供一个“staging + flush”的编译前端，适合导入脚本、ETL、测试数据构造、notebook/demo 等场景。

它不是第二套写入模型：所有写入最终都会展开为 Core Contract 的 `ref/set/add/retract` 调用，并保持可预览、可导出、可回放、可等价测试。

如需查看完整的 v0 语义约束、排序规则、wire plan 边界与 retract 强制约束，继续阅读
`17-SDK-Batch-staging（语义与契约-v0）.md`。

## 1. 为什么需要 batch（不是 ORM）

- `sdk.batch` 适合“先搭对象图，再一次性落盘”的心智模型。
- `sdk.batch` 不是 ORM：不会引入另一套持久化语义；`preview()` / wire plan 是它的核心能力。
- 低层写入语义仍以 `sdk.ref / sdk.set / sdk.add / sdk.retract` 为准。
- 读取/轻量编辑场景可使用 `sdk.get / sdk.find / sdk.edit`（只读快照 + 显式编辑会话）；创建对象图仍建议 `sdk.batch`。

## 2. 最小例子：构造对象图 -> preview -> commit

```python
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore
from factpy_kernel.sdk.batch import WireBatchPlan


class Company(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    sector: str = Field(cardinality="functional", pred_id="company:sector")


class Person(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    works_at: Company = Field(cardinality="multi", pred_id="person:works_at")


sdk = SDKStore.from_schema_classes([Person, Company])

with sdk.batch(meta={"trace_id": "t1", "source": "demo"}) as tx:
    alice = tx.entity(Person, source_system="HR", source_id="u1")
    google = tx.entity(Company, source_system="HR", source_id="c1")

    alice.country.set("de")
    alice.works_at.add(google)

    plan = tx.preview()            # 纯函数：不写入
    wire_json = plan.to_json(sdk)  # 稳定 JSON（可存盘/可回放）

    # 强制建议：至少看一眼 preview 摘要（避免 ORM 心智）
    wire_obj = plan.export(sdk).to_dict()
    print("ops:", len(wire_obj["ops"]))
    for op in wire_obj["ops"][:3]:
        print(op["kind"], op.get("path"), op.get("pred_id"))

    res = tx.commit()              # 执行与 preview 等价的写入序列
```

建议在 demo/ETL 中始终保留 `preview()`：它是 batch 的“编译输出”，用于审计、调试与回放。

## 2.1 普通 `Entity` 实例 vs `tx.entity(...)` 托管对象（常见误用）

普通 `Entity(...)` 是内存对象；字段操作用普通赋值，不支持 `.set/.add/.retract`。

```python
germany = Language(code="de", language_id="114514")
alice = Person(source_id="u-001")

alice.native_language = germany   # 正确：普通内存对象赋值
```

如果你要使用 `.set/.add/.retract`，必须在 `sdk.batch()` 里通过 `tx.entity(...)` 获取托管对象：

```python
with sdk.batch(meta={"trace_id": "t3"}) as tx:
    germany = tx.entity(Language, code="de", language_id="114514")
    alice = tx.entity(Person, source_id="u-001")
    alice.native_language.set(germany)  # 正确：batch handle
    tx.commit()
```

如果误写成 `Person(...).field.set(...)`，当前 SDK 会抛出带提示的 `SDKSchemaError`，明确说明应使用普通赋值或 `tx.entity(...)`。

### `tx.save(...)` 的当前语义（v0）

当前 `tx.save(...)` 是一个便捷入口，但它的语义是：

- 只接受 `tx.entity(...)` 返回的托管对象（`ManagedEntityHandle`）
- 等价于 `tx.commit(objects=[handle], include_deps=...)`
- 会立即执行写入，不是“先登记到 tx、稍后统一 commit”

因此，下面这种写法在 v0 中**不支持**（`alice/language` 是普通 `Entity`）：

```python
with sdk.batch(meta={"trace_id": "t4"}) as tx:
    alice = Person(source_id="u-001")       # plain Entity
    language = Language(code="de", language_id="114514")
    alice.native_language = language

    tx.save(alice)   # 不支持：tx.save 只接受 tx.entity(...) handle
```

如果你要走“预览计划 -> 统一提交”的流程，建议始终使用 `tx.entity(...)`，然后调用 `tx.preview()` / `tx.commit()`。

## 2.2 字段基数与 `set/add`（严格模式）

batch staging v0 对字段基数是严格的：

- `functional` 字段只能用 `.set(...)`
- `multi` 字段只能用 `.add(...)`

例如，如果 `Language.name` 在 schema 中是 `multi`，下面会报错：

```python
language = tx.entity(Language, code="de", language_id="114514")
language.name.set("German")  # 错误：multi 字段不能 set
```

应改为：

```python
language.name.add("German")
```

这条规则是有意设计的，用来避免“多值字段 set 到底是覆盖还是追加”的语义歧义。

## 3. Wire plan：导出与回放（可序列化契约）

Wire plan 是 `commit` 的等价计划，可序列化、可跨进程回放。默认严格校验 schema digest，防止 schema 漂移导致误写。

```python
wire = tx.preview().to_json(sdk)

plan2 = WireBatchPlan.from_json(wire)
plan2.apply(sdk, strict_schema=True)  # 等价于 commit 的调用序列回放
```

注意：

- wire 中引用值统一使用 `ref_identity`（`entity_type + identity`）形式
- 不接受 raw `EntityRef` token 作为 wire value（避免两套引用语义）

## 4. 依赖闭包（`include_deps`）

默认 `include_deps=True`：当字段引用了其他 staging entity，`preview/commit` 会自动包含被引用对象的写入（按拓扑顺序展开）。

如需高级模式，可关闭依赖闭包：

```python
plan = tx.preview(include_deps=False)
# 若存在未满足依赖，将在 preview/commit 报错并带 path
```

## 5. Retract（v1）：仅支持显式 `assertion_id`

v1 retract 只支持显式撤销某条历史断言，不支持按值撤销（避免引入查询与策略歧义）。

```python
with sdk.batch(meta={"trace_id": "t2"}) as tx:
    alice = tx.entity(Person, source_system="HR", source_id="u1")
    alice.works_at.retract(assertion_id="asrt_...")

    tx.preview()
    tx.commit()
```

说明：

- 同一 tx 内重复 retract 同一 `assertion_id` 会去重
- 后一次 meta 会覆盖前一次 meta

## 6. 什么时候用 batch，什么时候用 core

- 用 `sdk.ref/set/add/retract`：需要精确控制、底层工具/adapter、生成器输出、或要直接操作 assertion log
- 用 `sdk.get/find/edit`：notebook 调试、只读检视、轻量人工修正（按 identity 显式编辑）
- 用 `sdk.batch`：ETL/导入、人工录入、测试构造、demo/notebook；需要共享 meta、可预览计划、可导出回放

## 7. 保证与边界（速记）

- `preview()` 生成的是可审计、可导出的编译计划
- `commit()` 必须执行与 `preview()` 等价的 Core 调用序列
- wire plan 默认受 `schema_digest` 严格校验
- `sdk.batch` 不承诺跨进程/跨存储 ACID

更完整的契约口径（identity、meta merge、顺序确定性、wire/retract 规则）见
`17-SDK-Batch-staging（语义与契约-v0）.md`。

关于 `tx.save` 的当前限制（仅 handle、立即提交）与未来易用层方向，也见 `17` 中的“实现现状与下一步优化方向”。

## 8. 当前持久化状态

截至 2026-02，Core Ledger 已支持 SQLite 持久化；`sdk.batch()` 最终仍会写入同一个 Core Ledger。

如果你当前需要文件持久化，可以显式传入 file-backed Ledger：

```python
from factpy_kernel.core.store.ledger import Ledger
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes(
    [Person, Company],
    ledger=Ledger(path="./data/ledger.db"),
)
```

说明：

- `Ledger(path=...)` 已可用，重启后可恢复 ledger 数据。
- `SDKStore` 的“恢复工厂方法”目前尚未实现；也就是说，SDK 层还没有正式的
  `from_path(...)` / `from_ledger_path(...)` 风格入口来同时恢复 ledger 并校验 schema digest。
- 在该工厂方法落地前，推荐把 schema 定义与 `ledger_path` 放在同一个应用初始化位置，显式构造 `SDKStore`。
