# SDK Rule / Derivation 对象 DSL（v1）

范围：`src/factpy_kernel/sdk/dsl` + `SDKStore.run/evaluate/accept`

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

## 4. `RuleRef` 与依赖注册

构造方式：

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

调用方式：

```python
RuleRef(...)(p, c)
```

`sdk.run(...)` 依赖注册语义：
- 未传 `registry` 时：SDK 会构造本地 `RuleRegistry` 并自动注册依赖。
- 显式传了 `registry` 时：SDK 不自动补依赖，调用方自己管理 registry 内容。

## 5. Derivation DSL

```python
with vars("p", "c") as (p, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        where=[Pred("person:country", p, c)],
        head=Person.country(person=p, value=c),
        materialize_as="fact",   # "fact" | "record"
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

## 6. Derivation head 语法

Field head（常见于 `materialize_as="fact"`）：

```python
head = Person.country(person=p, value=c)
```

Entity head（常见于 `materialize_as="record"`）：

```python
head = Speaks(person=p, language=l)
```

当前规则：
- Field head 不支持位置参数，仅支持 kwargs。
- kwargs 里至少要有一个 DSL 值（例如 `vars()` 变量）。
- 其余 kwargs 可以是字面量（例如字符串常量）。

## 7. `run / evaluate / accept`

### 7.1 `sdk.run(rule, temporal_view=..., registry=...)`

输入支持：
- `Rule` 对象
- `RuleSpec`
- authoring rule payload dict
- compiled rule dict

不支持字符串 DSL。

### 7.2 `sdk.evaluate(...)`

输入支持：
- `Derivation` 对象
- authoring derivation payload dict
- compiled derivation dict
- 直接透传到底层 `store.evaluate(...)`

不支持字符串 DSL。

### 7.3 `sdk.accept(...)`

主路径：

```python
res = sdk.accept(candidate_set, approved_by="alice")
```

SDK facade 对 `CandidateSet` 路径支持：
- `approved_by`
- `note`
- `dry_run`
- `meta_overrides={...}`（仅支持同名键）

其他输入形态会透传到底层 `store.accept(...)`。

## 8. 记录路径 sugar 与 schema 映射

对象 DSL 里 `li.person == p` 先 lower 为 predicate 形式，再进入 authoring compile。

在 `SDKStore` 的 compile 路径中，`schema_ir` 总是可用，编译阶段会做 schema-aware rewrite：
- 根据 record 变量绑定与字段名映射到 schema 中实际 predicate。
- 因此通常不要求 predicate id 必须符合固定命名约定。

如果你在 schema 外场景单独 lower/compile 且缺少 `schema_ir`，建议显式使用 `Pred(...)` 避免歧义。

