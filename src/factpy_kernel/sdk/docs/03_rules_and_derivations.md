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
- entity exists sugar：`LivesIn(li)`
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
    )
```

字段：
- `id`、`version`、`where`（必需）
- `head`
- `target`
- `head_vars`
- `mode`
- `temporal_view`
- `status`

方法：
- `drv.to_authoring_payload()`

`head` 写法：
- Field head（fact 路径）：`Entity.field(...)`
- Entity head（entity 路径）：`EntityType(...)`

Field head 约束：
- 不支持位置参数，仅支持 kwargs。
- kwargs 至少要包含一个 DSL 值（如 `vars()` 变量）。

补充：
- `status` 可在 DSL 层携带到 authoring payload。
- 当前 `sdk.run/evaluate` 编译路径不会对 `status` 做运行时语义判断或强校验。

---

## 6. `head` 判定 candidate kind（v2）

### 6.1 默认判定规则（推荐路径）

编译器按 `head` 结构自动判定：

| `head` 结构 | 默认路径 | evaluate 输出 |
|---|---|---|
| `EntityType(...)` | entity 路径 | 1 个 entity candidate + 若干依赖 fact candidates |
| `EntityType.field(...)` | fact 路径 | fact candidates |

兼容写法：
- 无 `head` 时，仍可用 `target + head_vars` 走 fact-only 路径（兼容 no-head）。

### 6.2 从旧写法迁移到 v2（速查）

| 旧写法 | 新写法 | 说明 |
|---|---|---|
| `materialize_as="fact"` | `head=Entity.field(...)` | candidate_kind 自动推断为 fact |
| `legacy entity 路径` | `head=EntityType(...)` | candidate_kind 自动推断为 entity（并生成依赖 fact） |
| `id_policy=...` | 移除 | identity 在 entity candidate 中解析；缺失字段由 accept 时 `identity_override` 补齐 |
| fact payload: `e_ref/rest_terms` | fact payload: `terms` | `terms[0]` 固定是 subject（arg0） |

---

## 7. `sdk.evaluate(...)` 返回的 `CandidateSet`

返回：`list[CandidateSet]`

`CandidateSet` 核心字段：
- `candidate_id`（per-run 句柄）
- `candidate_key`（跨 run 稳定键）
- `candidate_kind`（`"fact"` / `"entity"`）
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
- `target`：fact candidate 下通常是 `pred_id`；entity candidate 下是 `entity_type`。
- `key_tuple_digest`：候选幂等键摘要。
- `support_*`：支撑证据摘要信息（`accept` meta 与 provenance 校验会使用）。

`payload` 形态：
- entity 候选（v2）：
  - `{"entity_type": ..., "identity_fields": [...], "resolved_identity": {...}, "missing_identity_fields": [...], "proposed_entity_ref": ...}`
- fact 候选（v2）：
  - `{"pred_id": ..., "terms": [{"kind": "entity_ref" | "candidate_ref" | "literal", ...}, ...]}`
  - `terms[0]` 固定是 subject 槽位（arg0）。

补充：
- 对 Entity head derivation，evaluate 常见会返回一个小图：`1` 个 entity candidate + `N` 个依赖 fact candidates（通过 `candidate_ref` 关联）。

### 7.1 读取 fact candidate 的推荐方式

```python
fact = next(c for c in cands if c.candidate_kind == "fact")
subject = fact.payload["terms"][0]                 # {"kind":"entity_ref"| "candidate_ref", ...}
value_terms = fact.payload["terms"][1:]            # literal / entity_ref / candidate_ref
```

不要再按 `payload["e_ref"]` / `payload["rest_terms"]` 读取。

---

## 8. `sdk.accept(...)`：结果结构与幂等语义

主路径：

```python
res = sdk.accept(candidate_set, approved_by="alice")
```

批量路径（有依赖关系时推荐）：

```python
rows = sdk.accept_many(cands_list, mode="atomic")
```

SDK facade 的 sugar：
- `approved_by=...`
- `note=...`
- `dry_run=True`
- `meta_overrides={...}`（仅支持同名键）

### 9.1 `AcceptResult` 字段

- `candidate_id`
- `candidate_key`
- `run_id`
- `candidate_kind`（可选，返回时与候选一致）
- `accepted_count`
- `skipped_count`
- `written_assertions`
- `skipped_reason_counts`
- `diagnostics`
- `diagnostics_contract_version`
- `entity_ref`（entity candidate 成功时返回）

### 9.2 幂等行为

同一候选重复 `accept` 时会走 no-op：
- 不追加写入
- 返回 `accepted_count=0`
- `skipped_count=1`
- `skipped_reason_counts={"duplicate": 1}`

### 9.3 `dry_run`

`dry_run=True` 不写 ledger，仅返回将写入的 `written_assertions` 预览。

### 9.4 `accept_many(...)` 状态

`accept_many` 返回逐候选状态，核心包括：
- `ACCEPTED`
- `DUPLICATE`
- `BLOCKED_DEPENDENCY`
- `FAILED_VALIDATION`
- `FAILED_RUNTIME`

默认 `mode="atomic"`；可选 `mode="best_effort"`。

---

## 10. `mode` / `temporal_view` 参数

### 10.1 `sdk.run(...)`

```python
rows = sdk.run(rule, temporal_view="active")
```

- `temporal_view`：`"active"` | `"current"`

### 10.2 `sdk.evaluate(...)`

```python
cands = sdk.evaluate(drv, mode="python", temporal_view="active")
```

- `mode`：`"python"` | `"engine"`
- `temporal_view`：`"active"` | `"current"`

说明：
- `mode="python"` 为默认实现路径。
- `mode="engine"` 依赖已注册 engine evaluator（Souffle 适配通常通过导入 `factpy_kernel.adapters.souffle` 完成注册）。

---

## 11. Schema-aware 说明（路径 sugar 与自定义 pred_id）

SDK 路径下，对象 DSL 会先 lower，再经过 schema-aware compile：
- `LivesIn(li)` 等 exists sugar 会映射到 schema 中实际 exists predicate
- `li.user == p` 等路径 sugar 在有 schema_ir 时会重写到对应角色谓词

因此在 `SDKStore.run/evaluate` 常见路径中，entity sugar 通常可以跟随 schema 自定义 `pred_id` 正确工作。  
在 schema 外独立 lower/compile 场景，建议优先使用 `Pred(...)` 显式谓词写法。

---

## 12. 最小闭环示例（推荐照抄）

### 12.1 fact 路径：evaluate -> accept

```python
with vars("p", "c") as (p, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country_copy(person=p, country_copy=c),
        where=[Pred("person:country", p, c)],
    )

cands = sdk.evaluate(drv, mode="python")
fact = next(c for c in cands if c.candidate_kind == "fact")
res = sdk.accept(fact, approved_by="alice")
```

### 12.2 entity 路径：先接受实体，再接受依赖 fact（推荐 `accept_many`）

```python
with vars("u", "l") as (u, l):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        head=Speaks(user=u, language=l),
        where=[Pred("person:country", u, "de"), Pred("user:lang_pref", u, l)],
    )

cands = sdk.evaluate(drv, mode="python")
rows = sdk.accept_many(cands, mode="atomic")
```

### 12.3 identity 不完整时补齐

```python
entity = next(c for c in cands if c.candidate_kind == "entity")
res = sdk.accept(entity, identity_override={"source_id": "u-001"})
```

若不传 `identity_override`，会得到 `IDENTITY_INCOMPLETE`（或等价 validation 错误）。
