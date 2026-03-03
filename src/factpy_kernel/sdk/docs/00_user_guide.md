# FactPy SDK 使用指南（当前代码基线）

> 基线：以 `src/factpy_kernel/sdk` 当前实现为准。  
> 本文仅描述已实现行为；未实现能力会明确标注“当前边界”。

---

## 1. 初始化

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

持久化 Ledger：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

稳定合约：
- `classes` 必须是非空 `list[Entity 子类]`。
- `ledger` 与 `ledger_path` 互斥。
- `ledger_path` 首次写入 `schema_digest`；重开时校验 digest，不一致抛 `SDKStoreError`。

---

## 2. Schema 定义

```python
from factpy_kernel.sdk import Entity, Identity, Field

class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
```

稳定合约：
- 每个 `Entity` 至少一个 `Identity`，否则类定义时报错。
- `Field.cardinality` 仅支持 `single | multi`。
- `Field` 公开参数只有 `cardinality` 与 `description`。
- `Identity` 支持 `default`、`default_factory`、`primary_key`。

当前边界：
- `dims` / `fact_key` / `pred_id` / `functional` / `temporal` 语义已移除。

---

## 3. 写入数据（`sdk.batch` / `sdk.set` / `sdk.add` / `sdk.retract`）

### 3.1 `sdk.batch(...)` 主流程

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "seed"}) as tx:
    u = tx.entity(User, user_id="u-001", locale="zh")
    u.name.add("Alice")
    u.age.set(30)

    plan = tx.preview()  # 只读预览
    res = tx.commit()    # 实际写入
```

稳定合约：
- `single` 字段用 `.set(...)`；`multi` 字段用 `.add(...)`。
- `.retract(asrt_id=...)` 按断言 ID 撤销。
- `preview()` 不落盘；`commit()` 才落盘。

### 3.2 Identity 不可写

稳定合约：
- `sdk.edit(...).<identity>.set/add/retract` 会抛错（Identity 不可变）。

### 3.3 低层写入口

```python
sdk.set(User.age, e_ref, 31, meta={"source": "hr"})
sdk.add(User.name, e_ref, "Alicia", meta={"source": "hr"})
sdk.retract(asrt_id, meta={"source": "hr"})
```

---

## 4. 读取数据（`sdk.get` / `sdk.find` / `EntitySnapshot`）

### 4.1 `sdk.get(...)`

```python
snap = sdk.get(User, user_id="u-001", locale="zh")
```

稳定合约：
- `get` 只接受 identity 参数。
- 返回 `EntitySnapshot | None`。

### 4.2 `sdk.find(...)`

```python
rows = sdk.find(User, age=30, limit=20)
```

稳定合约：
- `limit` 必须是非负整数。
- identity 过滤一旦使用，必须提供该实体全部 identity 字段。
- 不支持 `temporal_view` 参数。

### 4.3 `EntitySnapshot` 与断言视图

```python
snap.assertions.name.active
snap.assertions.name.history
snap.assertions.name.at("2024-03-01")
snap.assertions.name.version("v2")
```

稳定合约：
- `active`：当前未撤销断言。
- `history`：完整历史（含已撤销）。
- `at(t)`：在 active 集合上做业务时态过滤：`valid_from <= t` 且 `valid_to` 为空或 `valid_to > t`。
- `version(v)`：在 active 集合上做 `version == v` 过滤。

时态过滤边界：
- `valid_from` 缺失：不命中 `.at(t)`。
- `version` 缺失：不命中 `.version(v)`。
- `.at(t)` 会校验 ISO 8601（输入 `t` 与断言 `valid_from/valid_to` 都校验）；非法格式抛 `SDKStoreError`。
- `.version(v)` 仅接受 `str|int`（`bool` 非法）。

---

## 5. 编辑数据（`sdk.edit`）

```python
with sdk.edit(User, user_id="u-001", locale="zh") as editor:
    editor.name.add("Alicia")
    editor.age.set(31)
```

稳定合约：
- 找不到实体抛 `EntityNotFoundError`。
- editor 关闭后复用抛 `EditorClosedError`。
- 字段基数用错抛 `CardinalityError`。

---

## 6. 外部导入（`sdk.ingest`）

```python
res = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": user_ref, "value": "Alias"},
        {"kind": "set", "field": User.age, "e_ref": user_ref, "value": 31},
        {"kind": "retract", "asrt_id": old_asrt_id},
    ],
    meta={"source": "hr", "trace_id": "hr-001"},
)
```

稳定合约：
- `kind=set` 对应 `single` 字段；`kind=add` 对应 `multi` 字段。
- 顶层 `meta` 与 item `meta` 合并时，item 同名键覆盖顶层。
- 只要出现 `diagnostics` 错误，整批不写（collect-and-stop）。

meta 关键点：
- 系统保留：`ingested_at` / `ingest_key` / `revoked_asrt_id`（用户不可写）。
- 业务时态：`valid_from` / `valid_to` / `version`。
- `ingest_key` 去重物料：
  `claim + source + source_loc + trace_id + valid_from + valid_to + version`。

---

## 7. Rule / Query / Derivation

### 7.1 Rule

```python
from factpy_kernel.sdk import Rule, Pred, Not, vars

with vars("u") as (u,):
    r = Rule(
        id="q.vip",
        version="1.0.0",
        select=[u],
        where=[
            Pred("user:tag", u, "vip"),
            Not([Pred("user:tag", u, "blocked")]),
        ],
    )

rows = sdk.run(r, row_format="dict")
```

稳定合约：
- `row_format` 仅 Rule 路径支持（`tuple|dict`）。
- `RuleRef` 目标必须 `expose=True`。
- `RuleRef` 不允许出现在 `Not(...)` 体内（编译期错误）。

### 7.2 Query

```python
from factpy_kernel.sdk import Query, vars

with vars("u", "loc", "nm") as (u, loc, nm):
    q = Query(
        head=[User(u), User.name(locale=loc, name=nm)],
        where=[User(u), u.locale == loc, u.name == nm],
    )

rows = sdk.run(q)  # 始终返回 list[dict]
```

稳定合约：
- Query 仅返回 dict 行；不支持 `row_format`。
- Query head 只支持 `Entity(var)` 与 `Entity.field(...)`。

### 7.3 Derivation

```python
from factpy_kernel.sdk import Derivation, vars

with vars("u", "loc", "nm") as (u, loc, nm):
    d = Derivation(
        id="drv.copy_name",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

cands = sdk.evaluate(d, mode="python")
res = sdk.accept(cands[0], approved_by="alice")
```

稳定合约：
- `head` 自动决定 candidate kind（fact/entity）。
- 支持 `head=[H1, H2, ...]` 多 head；`evaluate` 返回展平结果并共享同一个 `run_id`。
- `materialize_as` / `id_policy` 已移除。

当前边界：
- `sdk.evaluate(..., temporal_view=...)` 被显式拒绝。
- derivation/runtime 侧时态写语义（head 直接产出带 `valid_from/valid_to/version`）尚未开放。

---

## 8. 时态语义现状

已实现：
- 写入：`valid_from/valid_to/version` 可持久化，并进入 `ingest_key` 去重。
- 读取：`snapshot.assertions.<field>.at(t)` / `.version(v)`。

未实现：
- Rule/Derivation head 的时态写语义。

---

## 9. 审计与排错

```python
sdk.explain_fact(pred_id, e_ref, *val_atoms)
sdk.conflicts(pred_id, e_ref)
```

说明：
- 两者都基于当前 active 断言集合计算。
- `single` 字段会返回 `chosen_asrt_id` 辅助定位冲突与决策结果。

---

## 10. Registry（`SDKRegistry`）

常见入口：
- `apply_schema_classes(...)`
- `register_rule(...)` / `register_derivation(...)`
- `list_rule_ids()` / `list_derivation_ids()`
- `get_latest_rule_spec(...)` / `get_latest_derivation_spec(...)`

当前边界：
- Registry 管理 authoring 资产；运行执行仍由 `SDKStore` 路径负责。
- 多 head Derivation 的 registry 发布建议先在调用侧展开为多个单 head。

---

## 11. 迁移速记（v2）

- `Field.cardinality`：`functional|temporal` -> `single`。
- 删除 `dims` / `fact_key` / `chosen`。
- `temporal_view` 从 evaluate/runtime 入口移除（显式报错）。
- 跨坐标联结仅允许 primary_key 比较，非法写法编译期报错。
