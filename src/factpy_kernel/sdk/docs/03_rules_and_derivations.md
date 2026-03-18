# SDK Rule / Query / Derivation DSL（当前实现）

范围：`src/factpy_kernel/sdk/dsl` + `SDKStore.run/evaluate/accept`

## 1. `vars(...)`

支持：

```python
with vars("p", "c") as (p, c):
    ...
```

```python
with vars() as V:
    p, c = V("p", "c")
```

不支持：
- `with vars() as (p, c)`（Python 运行时限制，SDK 会抛 `SDKDSLError`）

## 2. Rule DSL

```python
with vars("li", "u", "c") as (li, u, c):
    rule = Rule(
        id="q_user_country",
        version="1.0.0",
        select=[u, c],
        where=[
            LivesIn(li),
            li.user == u,
            li.country == c,
        ],
        expose=True,
    )

rows = sdk.run(rule, row_format="dict")
```

稳定合约：
- `Rule.id/version` 必须是非空字符串。
- `Rule.select/where` 必须是非空列表。
- `sdk.run(rule, row_format=...)` 仅 Rule 路径支持 `row_format`。
- `row_format` 优先级：调用参数 > `SDKStore(default_row_format=...)` > `FACTPY_ROW_FORMAT` > `"dict"`。
- 当解析结果为 `"tuple"` 时会触发 `DeprecationWarning`（建议统一 `"dict"`）。

## 3. where 支持语法与限制

支持：
- 实体存在 sugar：`LivesIn(li)`
- 路径等值 sugar：`li.user == u`、`li.country == c`
- 属性间比较：`u1.user_id == u2.user_id`
- 显式谓词：`Pred("user:tag", u, "vip")`
- 规则引用：`RuleRef(...)(...)`
- 否定：`Not([...])`
- 比较：`== != > >= < <=`
- OR 体：`where=[[...], [...]]`
- `Body` 分支：`where=[Body([...], confidence=0.9), Body([...], confidence=0.6)]`（Rule/Derivation）
- 比较表达式中的线性算术（如 `age == (2026 - by)`、`x * 2`）

`Body` 示例：

```python
from factpy_kernel.sdk import Body

where = [
    Body([User(u), Pred("user:lang_pref", u, lang)], confidence=0.9),
    Body([User(u), Pred("user:inferred_lang", u, lang)], confidence=0.6),
]
```

限制：
- 路径 sugar 仅支持 `==`。
- 属性间比较只支持 `==`，且必须在 schema-aware 编译上下文。
- 非线性乘法（`x * y`）不支持。
- `where` 中不允许混用 `Body(...)` 与裸分支（如 `[Body([...]), [...]]`）。
- `Body.confidence` 取值必须在 `(0,1]`；且只要任一分支设置 confidence，所有 `Body` 分支都必须设置。
- Query 不支持 `Body.confidence`（`confidence!=None` 会报错）。
- 字符串 DSL 不支持（`sdk.run("...")` / `sdk.evaluate("...")` 均不支持）。

## 4. RuleRef 与依赖注册

构造方式：

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

规则：
- RuleRef 目标规则必须 `expose=True`，否则运行时报 `RuleCompileError`。
- `RuleRef` 不允许出现在 `Not(...)` 体内（编译期错误）。
- `sdk.run(..., registry=None)` 时会自动注册 `RuleRef(RuleObj)` 依赖。
- 显式传 `registry` 时不自动补依赖。

## 5. Query DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    q = Query(
        head=[User(u), User.name(locale=loc, name=nm)],
        where=[User(u), u.locale == loc, u.name == nm],
        on_missing="error",
        on_type_mismatch="error",
    )

rows = sdk.run(q)  # list[dict]
```

稳定合约：
- Query head 仅支持 `Entity(var)` 与 `Entity.field(...)`。
- Query 支持 `row_format="dict"|"instance"`；默认 `"dict"`。
- `row_format="instance"` 仅允许 head 为单个 `Entity(var)`，返回实例列表（`list[EntitySnapshot|None]`）。
- 字段投影必须匹配 schema 中的 `single` 字段。
- where 未绑定变量会在构造期报 `SDKDSLError(code="QUERY_UNBOUND_VAR")`。
- `on_missing` / `on_type_mismatch` 仅支持 `error|skip|null`。
- Query 使用非法 `row_format`、或 instance 形态与 head 不匹配，会抛 `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`。

## 6. Derivation DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    d = Derivation(
        id="drv.copy_name",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

cands = sdk.evaluate(d, mode="native")
res = sdk.accept(cands[0], approved_by="alice")
```

字段：
- 必填：`id`、`version`、`where`
- 可选：`head`、`target`、`head_vars`、`mode`、`status`

稳定合约：
- `head` 形态自动决定 candidate kind（fact/entity）。
- 支持 `head=[H1, H2, ...]`；`evaluate` 返回展平后的 `list[CandidateSet]`，共享同一 `run_id`。
- `Rule/Derivation.where` 都支持 `Body(...)`；Rule 路径仅展开 atoms，不消费 `confidence`。
- `sdk.run(derivation)` 不支持，必须走 `sdk.evaluate(...)`。
- `sdk.run(derivation)` 报错码为 `QUERY_INVALID_ROW_FORMAT`（语义上提示改用 `evaluate()`）。

## 7. 编译期硬约束（v2）

### 7.1 head + primary_key

- `head` 中出现任何 `primary_key` 字段：编译失败。
- `where` 未绑定对应实体变量：编译失败。
- `where` 中同类型实体变量多绑定且无法消歧：编译失败。

### 7.2 跨坐标属性比较

`u1.user_id == u2.user_id` 仅在以下条件成立时合法：
- 两侧是同一实体类型
- 两侧字段相同
- 字段是该实体的 `primary_key`

否则编译失败（不做自动猜测）。

### 7.3 lowering 形态

合法的跨坐标主键比较会改写为共享系统变量（`$__pk_N`）：

```python
("pred", "user:user_id", ["$u1", "$__pk_0"])
("pred", "user:user_id", ["$u2", "$__pk_0"])
```

系统前缀变量由 DSL 层保留，用户变量名不允许冲突。

## 8. `evaluate/accept` 运行语义

### 8.1 `sdk.evaluate(...)`

```python
cands = sdk.evaluate(drv, mode="native")
```

- `mode`：`native`（默认）/ `souffle` / `problog`。
- 旧名 `python` / `engine` 会明确报错，并提示新名称。
- `souffle` / `problog` 路径依赖已注册后端（例如 `import factpy_kernel.adapters.souffle`、`import factpy_kernel.adapters.problog`）。
- `sdk.evaluate(..., view=...)` 不支持；推理始终基于完整 active 断言集。

### 8.2 `CandidateSet` 关键字段

- `candidate_id`：本次 run 句柄
- `candidate_key`：跨 run 稳定键
- `candidate_kind`：`fact` / `entity`
- `confidence`：`float | None`（`problog` 为概率值；`native/souffle` 为 `None`）
- 该字段当前属于 probabilistic engine lane，不应用作 Scenario A 的 requirement threshold probability；后者应通过 fact-backed uncertainty predicates + 现有比较语法表达。
- `payload`：
  - fact：`{"pred_id": ..., "terms": [...]}`
  - entity：`{"entity_type": ..., "resolved_identity": ..., ...}`

### 8.3 `sdk.accept(...)`

```python
sdk.accept(candidate, approved_by="alice", note="ok", dry_run=False)
```

accept sugar：
- `approved_by`
- `note`
- `dry_run`
- `identity_override`（用于 entity candidate 缺失 identity 场景）
- `meta_overrides`（可包含以上 sugar 键）

参数边界：
- `accept(CandidateSet, ...)` 只接受一个位置参数；多位置参数会抛 `SDKStoreError`。
- `meta_overrides` 仅允许 `approved_by` / `note` / `dry_run` / `identity_override`；其余键会报错。
- sugar 键同时出现在 `meta_overrides` 与顶层关键字参数时会报重复参数错误。
- 重复 accept 同一 candidate 会走幂等 no-op（`duplicate`）。
- 同 claim 但业务语义 meta 不同（如 `confidence`、`source`）可并存，不会误判 duplicate。
- 同一 `run_id` 批次通常不会出现“同 claim 不同 confidence”的候选；该并存场景主要发生在跨批次/跨来源写回。

## 9. 时态语义边界（当前状态）

已实现：
- 读路径：`snapshot.assertions.<field>.at(t)` 与 `.version(v)`。
- `T1` temporal checks 可通过显式 temporal predicates + 现有比较语法表达：
  - deadline：时间 anchor predicate + `<=` / `<`
  - window：时间 anchor predicate + `>=` / `<=`
  - interval relation：helper rule + 现有比较语法
- 这条路径要求 temporal predicate 参数使用 schema tag `"time"`（Python `int` / epoch 纳秒），不复用 `.at(t)` 的 ISO 8601 读侧口径。
- 若 temporal anchor 需要 explain drill-down，应优先建模为 predicate assertion 或至少绑定到变量；这样它会进入 `pred_witnesses` 或 `non_fact_steps.details.binding`。

未开放：
- derivation/runtime 侧 `temporal_view` 参数。
- dedicated temporal where atom / temporal builtin tag。
- Rule/Derivation head 直接产出时态写语义。

显式行为：
- authoring derivation payload 含 `temporal_view` 会编译失败。
- `sdk.evaluate(..., temporal_view=...)` 会抛 `SDKStoreError`。

## 10. 最小闭环示例

### 10.1 fact candidate

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    drv = Derivation(
        id="drv.alias",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

fact = next(c for c in sdk.evaluate(drv) if c.candidate_kind == "fact")
sdk.accept(fact, approved_by="alice")
```

### 10.2 entity candidate + 依赖事实

```python
with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[User(u), Pred("user:lang_pref", u, lang)],
        head=Speaks(user=u, language=lang),
    )

rows = sdk.accept_many(sdk.evaluate(drv), mode="atomic")
```
