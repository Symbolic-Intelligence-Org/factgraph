# 16) SDK Batch staging（`sdk.batch`）

本页是当前 `sdk.batch()` 的教程式入口，语义以当前实现为准。

权威参考仍在代码同目录文档：

- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/sdk/docs/01_alignment_matrix.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
- `src/factpy_kernel/sdk/docs/04_api_surface.md`

历史上的 v0 契约草案已归档到：

- `docs/history/design-evolution/sdk_batch_v0_contract.md`

## 1. 什么时候用 `sdk.batch()`

适合这些场景：

- 一次构造多个相互引用的实体
- 提交前先 `preview()` 看计划
- 需要导出/回放 wire plan
- ETL、测试数据构造、notebook demo

不适合这些场景：

- 只改一个已存在实体的少数字段
  - 这时更适合 `sdk.edit(...)`
- 需要最低层逐条控制写入
  - 这时更适合 `sdk.ref/set/add/retract`

当前边界：

- `with sdk.batch() as tx:` 的 context manager 不会自动 `commit()`，也不会自动 `rollback()`
- `single` 字段只能 `.set(...)`
- `multi` 字段只能 `.add(...)`
- 撤销只支持 `.retract(assertion_id=...)`
- 旧的 `functional` / `dims` / `fact_key` 口径已经不适用

## 2. 最小可运行示例

```python
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="zh")
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")
    lives_in: Country = Field(cardinality="single")


sdk = SDKStore.from_schema_classes([Country, User])
```

这里的关键点只有两个：

- `Field.cardinality` 只用 `single|multi`
- 实体引用字段直接写 handle 或 canonical `idref_v1`，不再引入 `dims`

## 3. 构造对象图 -> preview -> commit

```python
with sdk.batch(meta={"trace_id": "seed", "source": "demo"}) as tx:
    country = tx.entity(Country, code="DE")
    country.name.set("Germany")

    user = tx.entity(User, user_id="u-1")
    user.name.set("Alice")
    user.tag.add("vip")
    user.lives_in.set(country)   # 直接引用同 tx 内的 handle

    plan = tx.preview(objects=[user])
    result = tx.commit(objects=[user])
```

这段示例体现的是当前稳定语义：

- `preview()` 只生成计划，不落盘
- `commit()` 执行与 `preview()` 等价的写入序列
- `objects=[user]` 默认会带上依赖闭包，所以 `country` 会一起进入计划

写完后可以直接验证：

```python
snap = sdk.get(User, user_id="u-1", locale="zh")
assert snap is not None
assert snap.name == "Alice"
assert snap.tag == ("vip",)
assert snap.lives_in == country.e_ref
```

## 4. 普通内存对象 vs batch 托管对象

普通 `Entity(...)` 是内存对象，不支持 `.set/.add/.retract`：

```python
user = User(user_id="u-plain")
user.name = "Alice"   # 普通 Python 赋值
```

只有 `tx.entity(...)` 返回的托管对象才支持 batch 写 API：

```python
with sdk.batch(meta={"trace_id": "seed"}) as tx:
    user = tx.entity(User, user_id="u-2")
    user.name.set("Alice")
    tx.commit()
```

如果你误把普通对象当成 handle 来调用 `.set(...)`，当前 SDK 会明确报错并提示应该使用普通赋值或 `tx.entity(...)`。

## 5. identity、`bind(...)` 与字段约束

identity 不完整时，batch 写入会直接报错；需要先补齐：

```python
with sdk.batch() as tx:
    user = tx.entity(User, user_id="u-3")
    user = user.bind(locale="en")
    user.name.set("Alicia")
    tx.commit()
```

当前约束：

- identity 字段是只读 guard，不能 `.set/.add/.retract`
- `single` 字段只能 `.set(...)`
- `multi` 字段只能 `.add(...)`

例子：

```python
with sdk.batch() as tx:
    user = tx.entity(User, user_id="u-4")

    user.name.set("Alice")   # single: OK
    user.tag.add("vip")      # multi: OK

    # user.name.add("Alice")   -> SDKStoreError
    # user.tag.set("vip")      -> SDKStoreError
```

## 6. Wire plan：导出与回放

如果你需要把 batch 计划存盘或跨进程回放，用 `WireBatchPlan`：

```python
from factpy_kernel.sdk.batch import WireBatchPlan

with sdk.batch(meta={"trace_id": "seed"}) as tx:
    country = tx.entity(Country, code="DE")
    country.name.set("Germany")

    user = tx.entity(User, user_id="u-5")
    user.lives_in.set(country)

    wire_json = tx.preview(objects=[user]).to_json(sdk)

plan = WireBatchPlan.from_json(wire_json)
plan.apply(sdk, strict_schema=True)
```

当前行为要点：

- wire plan 协议版本是 `sdk_batch_plan_v1`
- `strict_schema=True` 会校验 `schema_digest`
- wire 导出不接受 raw `idref_v1` 字符串值作为 `entity_ref` 写入值
- 想保持可回放，优先在同一 tx 里用 handle 表达实体关系

## 7. 撤销历史断言

batch 路径的撤销 API 是：

```python
with sdk.batch(meta={"trace_id": "fix-1"}) as tx:
    user = tx.entity(User, user_id="u-1")
    user.tag.retract(assertion_id="asrt_123")
    tx.commit()
```

这里的边界是明确的：

- 只能按 `assertion_id` 撤销
- 不支持按值撤销
- 同一 tx 内重复撤销同一 `assertion_id` 会被去重

如果你走 `sdk.edit(...)`，对应的接口是 `FieldEditor.retract(asrt_id=...)`，参数名不一样。

## 8. `tx.save(...)` 的当前定位

`tx.save(handle, ...)` 仍然存在，但它只是便捷提交入口：

- 只接受 `tx.entity(...)` 返回的 handle
- 语义上等价于 `tx.commit(objects=[handle], ...)`
- 会立即执行写入，不是“登记后稍后统一提交”

如果你在写教程、脚本或 notebook，默认还是优先用：

- `tx.preview(...)`
- `tx.commit(...)`

这样更符合 batch 的可审计和可回放心智。

## 9. 当前最重要的 4 条记忆点

1. `sdk.batch()` 是当前实现的活跃能力，但语义已经是 `single|multi`，不是 `functional/multi`。
2. `preview()` 和 `commit()` 是主流程；context manager 不会自动提交。
3. batch handle 撤销按 `assertion_id`，不支持按值撤销。
4. 权威口径优先看 `src/factpy_kernel/sdk/docs/`，不要再把 v0 设计稿当当前契约。

## 10. 下一跳

如果你接下来要继续查当前实现，建议按这个顺序：

1. `src/factpy_kernel/sdk/docs/00_user_guide.md`
2. `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
3. `src/factpy_kernel/sdk/docs/04_api_surface.md`
4. `src/factpy_kernel/tests/test_sdk_batch_application_delegate.py`
