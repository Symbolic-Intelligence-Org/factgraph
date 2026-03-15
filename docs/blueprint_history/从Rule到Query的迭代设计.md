> 状态：部分实现  
> 类型：架构蓝图  
> 说明：本文档保留为历史 Rule / Query / Derivation 演进蓝图；其中部分结论已被当前实现吸收，但整体路线并未完全按本文落地。

# Rule / Derivation / Query 设计蓝图

> 核心判定句：**"看结果契约，不看语法长相。"**

---

## 1. 三者定位

Rule 面向**信息**；Query 和 Derivation 面向实际**实体和事实**，是特化的 Rule。区别仅在方向：Query 读，Derivation 写。

| | 面向 | head / select | 结果 | store 存在性 |
|---|---|---|---|---|
| `Rule` | 信息 / 关系 | `select=[vars]`，变量投影 | `list[tuple]` → `list[dict]` | ❌ 不承诺 |
| `Query` | 已有实体 / 事实 | `head=Entity(vars)`，读出目标 | `list[dict]` | ✅ 必须 store-backed |
| `Derivation` | 新实体 / 事实 | `head=Entity(vars)`，写入目标 | `list[CandidateSet]` | ❌ accept 前不存在 |

---

## 2. 三者定义与语法

### 2.1 Rule（已实现）

```python
Rule(
    id="q_active_persons",
    version="1.0.0",
    select=[p, c],
    where=[Person(p), p.country == c, p.active == True],
)
```

- **输出：** `list[tuple[Any, ...]]`（当前），迁移目标为 `list[dict[str, Any]]`
- **身份：** 版本化资产（`id + version`），进 registry，可被 `RuleRef` 引用
- **注册：** `SDKRegistry.register_rule(rule)`
- **执行：** `sdk.run(rule, temporal_view="active")`

---

### 2.2 Derivation（已实现）

```python
Derivation(
    id="drv.speaks",
    version="1.0.0",
    head=Speaks(person=p, language=l),
    where=[LivesIn(li), li.person == p, li.country == c,
           HasLanguage(hl), hl.country == c, hl.language == l],
)
```

- **输出：** `list[CandidateSet]`（已锁定）
- **身份：** 版本化资产（`id + version`），进 registry
- **执行：** `sdk.evaluate(drv, temporal_view="active")` → `sdk.accept(candidate_set)`
- **多候选原子接收：** 使用现有 `sdk.accept_many(candidates, mode="atomic")`，不依赖外层 batch

**多 head（独立里程碑，Query 完成后再做）：**

当前编译与执行以单 `target_pred_id + head_vars` 为核心（`derivation_compile.py`、`runtime.py`、`engine_eval.py`），多 head 是链路级改造，不是小扩展。第一版实现方案：将多 head 编译为多个共享 `run_id` 的单 head 计划，避免一次性穿透全栈。DSL 语法预留如下，实现推迟：

```python
# 预留语法，暂不实现
Derivation(
    id="drv.speaks_with_count",
    version="1.0.0",
    head=[
        Speaks(person=p, language=l),
        Person.lang_count(person=p, value=n),
    ],
    where=[...],
)
```

---

### 2.3 Query（待实现）

**单 head：**
```python
Query(
    head=Person(p),
    where=[p.country == "DE", p.active == True],
)
# → [{"p": <EntitySnapshot: Person>}, ...]
```

**多 head（join）：**
```python
Query(
    head=[Person(p), Company(c)],
    where=[Person(p), Company(c), p.works_at == c],
)
# → [{"p": <EntitySnapshot: Person>, "c": <EntitySnapshot: Company>}, ...]
```

**字段投影：**
```python
Query(
    head=Person.name(person=p, value=name),
    where=[Person(p), p.active == True],
)
# → [{"person": <EntitySnapshot: Person>, "name": "Alice"}, ...]
```

- **输出：** `list[dict[str, Any]]`，固定 dict，不支持 `row_format`
- **身份：** 请求对象，不进 registry，不可被引用
- **执行：** `sdk.run(query, temporal_view="active")`
- **配置参数（定义时传入）：** `on_missing`、`on_type_mismatch`

---

## 3. 引用关系

```
Rule  ←── RuleRef ───  Rule / Derivation / Query

Query      ✗  不可被任何人引用（终端消费者）
Derivation ✗  不可被 Query 或 Derivation 引用
```

- Query `head` 端禁止聚合 / 计算 / 构造新对象；需要 `count/sum/derived` 时转 Rule
- 只要结果要进 `accept()`，就用 Derivation；只要是读已有对象，就用 Query

---

## 4. SDK 接口

### 4.1 错误模型（实现 Query 前先做）

当前 `SDKStoreError` 不接受 `code` 参数（`errors.py:12`），直接传 `code=` 会 `TypeError`。在引入 `QUERY_*` 错误码前，需先扩展错误基类：

```python
class SDKError(Exception):
    def __init__(self, message: str, *, code: str | None = None, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.path = path
```

所有 `QUERY_*` 错误码统一通过 `code=` 字段承载，不新增子类。

### 4.2 `sdk.run()` 分发（实现时一次写入完整骨架）

```python
def run(self, obj, *, row_format=None, temporal_view="active", registry=None):
    if isinstance(obj, Query):
        if row_format is not None:
            raise SDKStoreError(
                "row_format is not supported for Query; Query always returns dict",
                code="QUERY_INVALID_ROW_FORMAT",
            )
        return self._run_query(obj, temporal_view=temporal_view)

    if isinstance(obj, Derivation):
        raise SDKStoreError(
            "Derivation is not supported by run(); use sdk.evaluate() instead",
            code="QUERY_INVALID_ROW_FORMAT",
        )

    # Rule 路径（现有）
    return self._run_rule(obj, row_format=row_format,
                          temporal_view=temporal_view, registry=registry)
```

### 4.3 `temporal_view` 合法值

全栈统一：`"active"`（默认）| `"current"`

> `"active"` 是业务视图（全量活跃断言）；`"current"` 是时态字段的最新值视图。

### 4.4 `row_format`（Rule 专属，三层控制）

| 层级 | 写法 |
|---|---|
| 调用参数（最高） | `sdk.run(rule, row_format="dict")` |
| store 级默认（中） | `SDKStore.from_schema_classes([...], default_row_format="dict")` |
| 环境变量（最低） | `FACTPY_ROW_FORMAT=dict` |

迁移路径：当前默认 `tuple`（现有测试依赖，`store.py:188`、`test_sdk_store_v1.py:149`）→ 加显式 `row_format` 参数，默认仍 `tuple` → 下一版切默认为 `dict`，`tuple` 打 deprecation warning → 最终移除 `tuple`。

### 4.5 Rule 注册

```python
registry = SDKRegistry(root_dir="./registry")
registry.register_rule(rule)      # 持久注册，使 Rule 可被 RuleRef 引用
```

`sdk.run(rule)` 在 `registry=None`（默认）时自动注册 `RuleRef(RuleObj)` 依赖（含递归）；显式传入 `registry` 时不做自动补全。

### 4.6 完整接口速览

```python
# 读（无副作用）
sdk.get(Person, source_id="u1")          # → EntitySnapshot | None
sdk.find(Person, country="DE")           # → list[EntitySnapshot]
sdk.run(rule, temporal_view="active")    # → list[tuple] 当前 / list[dict] 目标
sdk.run(query, temporal_view="active")   # → list[dict]（store-backed）

# 推理 + 写（有副作用）
sdk.evaluate(drv, temporal_view="active")         # → list[CandidateSet]
sdk.accept(candidate_set)                          # → AcceptResult，单个写入
sdk.accept_many(candidates, mode="atomic")         # → 多候选原子写入

# 实体写入
sdk.batch() / sdk.edit(...) / sdk.set(...) / sdk.add(...) / sdk.retract(...)
sdk.ingest(data)
```

---

## 5. Query 边界条款

### 5.1 `query_id`（内部身份，用于缓存和错误定位）

```python
canonical_payload = {
    "head_ir":          head_ir,          # 保留声明顺序，不排序
    "where_ir":         where_ir,
    "temporal_view":    temporal_view,
    "return_mode":      return_mode,
    "on_missing":       on_missing,
    "on_type_mismatch": on_type_mismatch,
    "schema_digest":    schema_digest,
}
query_id = f"__query__:{sha256(canonical_json(canonical_payload))[:16]}"
# canonical_json: sort_keys=True, separators=(',', ':')
```

错误信息显示为 `query@<16hex>`，用户不感知内部结构。

### 5.2 `where` 变量绑定约束

`head` 中的变量视为初始已绑定集合（`initial_bound_vars`），传入现有 `where_ast_validate` 验证器，不绕过验证逻辑，不做特殊 case。

`where` 可使用这些变量，也可引入新的中间变量（用于 join，不出现在输出中）。`where` 中出现既不在初始绑定集合也未被前序原子绑定的变量，parse 阶段报错（`QUERY_UNBOUND_VAR`）。

```python
# 合法
Query(head=Person(p), where=[p.active == True])
Query(head=[Person(p), Company(c)], where=[p.works_at == c])

# 非法：q 未绑定
Query(head=Person(p), where=[p.friend == q])  # QUERY_UNBOUND_VAR
```

### 5.3 缺失与类型不匹配

| 参数 | 触发条件 | 默认 | 可降级 |
|---|---|---|---|
| `on_missing` | 合法 entity_ref 但 store 中不存在 | `"error"` | ✅ 可降级 |
| `on_type_mismatch` | 值不是 entity_ref 或类型不符 | `"error"` | ⚠️ 不建议 |

两者均支持 `"error"` / `"skip"` / `"null"`。`"null"` 为列级置空，行保留；多列缺失时每列独立处理。

### 5.4 store-backed 语义边界（三项协议）

**① 实体存在性判定：** 实体存在 = store 中有至少一条活跃断言（exists 断言或任意活跃字段均算）。仅有已撤销断言 → 视为不存在，触发 `on_missing`。

**② 字段投影遇到 multi / dims 字段：** parse 阶段报错，不支持展开或聚合。调用方应通过 Rule 处理 multi / dims 字段，Query 只做 functional 字段投影。

**③ `null` / `skip` 与去重、排序：**
- 行顺序与 where_eval 输出顺序一致，不做额外排序，结果顺序稳定但不保证特定语义顺序
- `on_missing="null"` 置空后，行仍参与去重（基于其余列）
- `on_missing="skip"` 丢行发生在去重之前

### 5.5 alias 命名规则（按优先级）

```
1. 显式 alias：p.alias("person_ref")       → "person_ref"
2. 变量名去 $：$p                          → "p"
3. head entity 变量：head=Person(p)        → "p"（同变量名去 $）
4. 字段投影 kwarg：value=name              → "name"
5. 无法推断                                → parse 阶段报错，强制显式 alias
```

同一 Query / Rule 内输出键重复，parse 阶段报错（`QUERY_ALIAS_CONFLICT`）。

### 5.6 store lookup 实现约束

执行后处理流程：
1. where_eval 输出 bindings（每行为变量绑定 dict）
2. 按 `return_contract` 中的 `entity_type` 分桶，收集各类型所有 ref
3. 每个 entity_type 一次批量查询（预索引 predicate rows，不走逐行 `sdk.get`）
4. 按 ref 回填 snapshot 到各行

禁止逐行单次 lookup（N+1 查询）。当前 `facade.py:539` 的 snapshot 构建路径会退化为 N+1，Query 后处理不得复用该路径，需独立实现批量 hydrate。

### 5.7 错误码

| 错误码 | 触发条件 |
|---|---|
| `QUERY_MISSING_REF` | `on_missing="error"` 时实体不存在 |
| `QUERY_TYPE_MISMATCH` | `on_type_mismatch="error"` 时类型不符 |
| `QUERY_ALIAS_CONFLICT` | parse 阶段输出键重复 |
| `QUERY_UNBOUND_VAR` | parse 阶段 where 中有未绑定变量 |
| `QUERY_INVALID_ROW_FORMAT` | Query 传入 `row_format`，或 `sdk.run()` 传入 Derivation |

---

## 6. 内核 IR

```
Rule(DSL)       → QueryRuleAst(rule_id, version, select_vars, where)
                → where_eval → list[tuple]（当前）/ list[dict]（目标）

Query(DSL)      → QueryRuleAst(query_id=__query__:<digest>, version="runtime",
                               head_vars, where,
                               initial_bound_vars=head_vars)   ← 传入验证器
                + return_contract（由 head 推导）
                → where_eval → 批量 hydrate → list[dict]

Derivation(DSL) → DerivationSpec（独立 IR，单 head）
                → evaluate_store → list[CandidateSet]
```

**`return_contract` 由 head 推导：**

| head 形态 | 推导结果 |
|---|---|
| `Person(p)` | `{var: "$p", entity_type: "Person", field_path: None}` |
| `[Person(p), Company(c)]` | 两条 contract，顺序与 head 一致 |
| `Person.name(person=p, value=name)` | `{var: "$name", entity_type: None, field_path: "Person.name"}` |

Rule / Query 共用 `QueryRuleAst`；Derivation 走独立 `DerivationSpec`，两路在内核层完全分离。

---

## 7. 落代码顺序

1. **扩展错误基类**，支持 `code` / `path` 参数，引入 `QUERY_*` 错误码
2. **`sdk.run()` 写入完整分发骨架**（Rule / Query / Derivation 三路），同步加入 `row_format` 参数（默认仍 `tuple`）和三层全局开关
3. **定义 `Query` DSL 类**（`head / where / on_missing / on_type_mismatch`），head → return_contract 推导，alias 静态校验；扩展 `where_ast_validate` 支持 `initial_bound_vars`
4. **实现 Query lowering** → `QueryRuleAst + return_contract`，含 `query_id` digest 生成
5. **实现执行后处理**：批量 hydrate，`on_missing / on_type_mismatch` 策略，5.4 三项协议
6. **接入 `_run_query`** 真实实现（步骤 3-5 完成后）
7. **`row_format` 迁移**：切默认为 `dict`，`tuple` 打 deprecation warning（独立 PR，观察期后）
8. **Derivation 多 head**（独立里程碑）：编译为多个共享 `run_id` 的单 head 计划，复用现有执行路径
