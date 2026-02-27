# SDK Rule / Derivation 对象 DSL（v1）

范围：`src/factpy_kernel/sdk/dsl` + `SDKStore.run/evaluate/accept`

---

## 1. `vars(...)`

支持两种写法：

```python
with vars("p", "c") as (p, c):
    ...
```

```python
with vars() as V:
    p, c = V("p", "c")
```

限制：
- 不支持 `with vars() as (p, c)`。

---

## 2. Rule DSL

```python
with vars("li", "p", "c") as (li, p, c):
    rule = Rule(
        id="q_country_rows",
        version="1.0.0",
        select=[p, c],
        where=[
            LivesIn(li),                 # exists sugar
            li.person == p,              # path eq sugar
            li.country == c,
            RuleRef("q_other", version="1.0.0")(p, c),
            Not([Pred("person:blacklist", p, "x")]),
        ],
        expose=True,
    )
rows = sdk.run(rule)
```

`Rule(...)` 约束：
- `id` / `version` 非空字符串
- `select` / `where` 非空 list

方法：
- `rule.to_authoring_payload()`
- `rule.dependency_rules()`
  - 返回当前 rule where 中可见的直接 `RuleRef(RuleObj)` 依赖。
  - 不是“单次调用返回全传递依赖”。

---

## 3. `where` 支持语法

支持：
- record exists sugar：`LivesIn(li)`
- path equality sugar：`li.person == p`
- 谓词：`Pred("person:country", p, c)`
- rule 引用：`RuleRef(...)(...)`
- 否定：`Not([...])`
- 比较：`== != > >= < <=`
- OR：`where=[[...], [...]]`
- 线性算术：`age == (2026 - by)`、`x * 2` / `2 * x`

限制：
- 路径比较 sugar 仅支持 `==`。
- 属性对属性比较 sugar 不支持：`a.country == b.country`。
- 非线性乘法不支持：`x * y`。
- 字符串 DSL 不支持。
- 链式写法不支持：`LivesIn(li).person == p`。

---

## 4. `RuleRef`、`expose=True` 与依赖注册

构造方式：

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

调用方式：

```python
RuleRef(...)(p, c)
```

规则：
- `RuleRef` 目标规则必须是 `expose=True`，否则运行时会报 `RuleCompileError`。
- `sdk.run(..., registry=None)` 时，SDK 会自动注册 `RuleRef(RuleObj)` 依赖（含递归对象依赖）。
- 显式传 `registry` 时，SDK 不做自动补依赖，由调用方保证 registry 完整。
- 自动注册只解决“依赖是否已注册”，不会绕过 `expose=True` 约束；`expose=False` 的被引用规则仍会在运行时报错。

---

## 5. Derivation DSL

```python
with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            LivesIn(li), li.user == u, li.country == c,
            HasLanguage(hl), hl.country == c, hl.language == l,
        ],
        head=Speaks(user=u, language=l),
        materialize_as="record",
    )
```

字段：
- `id`、`version`、`where`（必需）
- `head`
- `materialize_as`
- `target`
- `head_vars`
- `mode`
- `temporal_view`
- `status`
- `id_policy`

方法：
- `drv.to_authoring_payload()`

`head` 写法：
- Field head（常见于 fact）：`Entity.field(...)`
- Entity head（常见于 record）：`RecordType(...)`

Field head 约束：
- 不支持位置参数，仅支持 kwargs。
- kwargs 至少要包含一个 DSL 值（如 `vars()` 变量）。

补充：
- `status` 可在 DSL 层携带到 authoring payload。
- 当前 `sdk.run/evaluate` 编译路径不会对 `status` 做运行时语义判断或强校验。

---

## 6. `materialize_as` 语义（核心）

`materialize_as` 决定 `accept` 时写入形态：

| 取值 | 写入语义 |
|---|---|
| `"fact"` | 写入目标业务谓词断言（不创建新实体） |
| `"record"` | 物化 reified record：写 `<RecordType>:exists` + role facts |

### 6.1 `materialize_as="record"`

硬约束：
- 需要 `head`
- `head` 必须是 Entity head（`RecordType(...)`）
- 在 schema-aware 编译路径中，`head` kwargs 必须匹配 record role 字段名

例如：

```python
head = Speaks(user=u, language=l)  # kwargs 是 role 字段名
```

`uid=` 这类 identity 字段不属于 role kwargs，会在编译/运行时报错。

### 6.2 `materialize_as="fact"`

常见写法是 Field head：

```python
head = Person.country(person=p, value=c)
```

但这不是唯一形态。当前实现还支持兼容路径：
- 直接给 `target + head_vars`
- schema-aware 条件下，Entity head 可被重写到 record projection fact（要求 schema 中有 projection 定义）

因此文档里应将 Field head描述为“常见/推荐形态”，而不是“唯一硬约束”。

---

## 7. `id_policy`（record 物化幂等键）

`id_policy` 仅在 `materialize_as="record"` 时生效，用于确定 record 的 e_ref（从而控制幂等与去重）。

v1 支持：
- `key_tuple_digest_v1`
- `identity_fields_v1`

### 7.1 `key_tuple_digest_v1`

最简策略，基于候选 key 摘要派生 record identity。适合快速落地。

### 7.2 `identity_fields_v1`

显式指定由哪些 role 字段组成 record identity，语义更稳定，适合生产。

```python
id_policy={
  "kind": "identity_fields_v1",
  "fields": [
    {"name": "person", "role": "person", "type_domain": "entity_ref"},
    {"name": "language", "role": "language", "type_domain": "entity_ref"},
  ],
}
```

schema-aware 编译路径下，record derivation 在省略 `id_policy` 时可自动推导默认 `identity_fields_v1`；生产仍建议显式声明。

---

## 8. `sdk.evaluate(...)` 返回的 `CandidateSet`

返回：`list[CandidateSet]`

`CandidateSet` 核心字段：
- `derivation_id`
- `derivation_version`
- `run_id`
- `target`
- `key_tuple_digest`
- `tup_digest`
- `payload`
- `support_digest`
- `support_kind`
- `generated_at`
- `state`

说明：
- `run_id`：同一轮 evaluate 的运行标识。
- `target`：fact 路径下通常是目标 `pred_id`；record 路径下是 `record_type`。
- `key_tuple_digest`：候选幂等键摘要。
- `support_*`：支撑证据摘要信息（`accept` meta 与 provenance 校验会使用）。

`payload` 形态：
- fact 候选：`{"e_ref": ..., "rest_terms": ...}`
- record 候选：`{"materialize_as": "record", "record_type": ..., "record_exists_pred_id": ..., "id_policy": ..., "roles": ...}`

---

## 9. `sdk.accept(...)`：结果结构与幂等语义

主路径：

```python
res = sdk.accept(candidate_set, approved_by="alice")
```

SDK facade 的 sugar：
- `approved_by=...`
- `note=...`
- `dry_run=True`
- `meta_overrides={...}`（仅支持同名键）

### 9.1 `AcceptResult` 字段

- `materialize_id`
- `run_id`
- `accepted_count`
- `skipped_count`
- `written_assertions`
- `skipped_reason_counts`
- `diagnostics`
- `diagnostics_contract_version`

### 9.2 幂等行为

同一候选重复 `accept` 时会走 no-op：
- 不追加写入
- 返回 `accepted_count=0`
- `skipped_count=1`
- `skipped_reason_counts={"duplicate": 1}`

### 9.3 `dry_run`

`dry_run=True` 不写 ledger，仅返回将写入的 `written_assertions` 预览。

### 9.4 conflict / aborted

record 物化在冲突或中断恢复场景可能返回：
- `skipped_reason_counts={"conflict": 1}` 或 `{"aborted": 1}`
- 并携带 `diagnostics`

其中 `aborted` 语义是“当前物化流程已终止，不能按同一路径自动重试”。

---

## 10. `mode` / `temporal_view` 参数

### 10.1 `sdk.run(...)`

```python
rows = sdk.run(rule, temporal_view="record")
```

- `temporal_view`：`"record"` | `"current"`

### 10.2 `sdk.evaluate(...)`

```python
cands = sdk.evaluate(drv, mode="python", temporal_view="record")
```

- `mode`：`"python"` | `"engine"`
- `temporal_view`：`"record"` | `"current"`

说明：
- `mode="python"` 为默认实现路径。
- `mode="engine"` 依赖已注册 engine evaluator（Souffle 适配通常通过导入 `factpy_kernel.adapters.souffle` 完成注册）。

---

## 11. Schema-aware 说明（路径 sugar 与自定义 pred_id）

SDK 路径下，对象 DSL 会先 lower，再经过 schema-aware compile：
- `LivesIn(li)` 等 exists sugar 会映射到 schema 中实际 exists predicate
- `li.user == p` 等路径 sugar 在有 schema_ir 时会重写到对应角色谓词

因此在 `SDKStore.run/evaluate` 常见路径中，record sugar 通常可以跟随 schema 自定义 `pred_id` 正确工作。  
在 schema 外独立 lower/compile 场景，建议优先使用 `Pred(...)` 显式谓词写法。
