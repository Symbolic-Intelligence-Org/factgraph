# PyReason Adapter（factpy_kernel）

- 范围：`src/factpy_kernel/adapters/pyreason`
- 最后更新：2026-03-27
- 状态：execution-surface V1（engine_options: timesteps）+ bounded materialization L3b

## 1. 概述

PyReason adapter 是 factpy 对 [PyReason](https://github.com/lab-v2/pyreason) 图推理引擎的接入。当前已经接上 shared evaluate surface：`Store.evaluate(mode="pyreason")` / `SDKStore.evaluate(Derivation(..., mode="pyreason"))` 会走 adapter 的 EDB materialization、WhereIR 编译、runner 和 CandidateSet 输出。adapter-local 的 provenance、session、rule ext、runner、accept helper 仍然保留，作为引擎内部实现与独立 helper 层。

PyReason 使用 Generalized Annotated Logic Programs (GAPs) 在 NetworkX 图上做区间值时序推理，与 Souffle（确定性 Datalog）和 ProbLog（概率逻辑）都有本质差异。

## 2. 环境要求

- `pyreason==3.0.0`（或更新版本；3.4.0 依赖矩阵相同）
- Python 3.10
- 手动安装：`pip install 'pyreason==3.0.0'`（不在 `pyproject.toml` 中，spike-only dependency）
- 当前已验证环境（2026-03-27）：`numba==0.64.0`、`llvmlite==0.46.0`
- **重要**：如果 `import pyreason` 报 numba cache 错误（`RuntimeError: cannot cache function ... no locator available`），清除过期 cache：`rm -rf $(python -c "import pyreason, pathlib; print(pathlib.Path(pyreason.__file__).parent / 'cache')")`
- 首次运行时 numba JIT 编译约 `~170s`，后续运行使用 cache 约 `~8s`

## 3. 当前模块内容

| 文件 | 角色 |
|------|------|
| `provenance.py` | `PyReasonTraceEventV0` / `PyReasonTraceV0` / `parse_pyreason_trace` / `pyreason_trace_to_dict` |
| `session.py` | `PyReasonSession` — 引擎特定写入 session，校验 shared schema_ir，处理 batch API / bound / active_from / active_to / annotation templates |
| `rule_ext.py` | `PyReasonRuleExt` / `PyReasonRuleDef` / `PyReasonFactDef` / `compile_pyreason_rule(...)` |
| `where_compile.py` | `compile_where_ir_to_pyreason(...)` — lowered WhereIR → PyReason rule syntax（execution surface compiler） |
| `runner.py` | `run_pyreason(...)` / `build_pyreason_graph(...)` / `PyReasonRunConfig` / `PyReasonRunResult`；接受 legacy tuple 或 typed defs |
| `engine_eval.py` | `pyreason_engine_eval(...)` / `_materialize_edb_session(...)` — shared evaluate dispatch 入口，输出 `CandidateSet` 并缓存 pending annotations |
| `accept.py` | `accept_pyreason_session(...)` + `persist_pyreason_annotations(...)` — adapter-local accept helper and shared-surface post-accept annotation binder |
| `__init__.py` | import 时注册 `register_engine_evaluator(pyreason_engine_eval, "pyreason")` |

## 4. PyReason 推理模型

```text
输入：NetworkX DiGraph + 规则 + 初始事实
规则语法：head(x) <-T body(y), edge(x,y)   （T = 时间步延迟）
值域：[lower, upper] 区间，不是 true/false 或概率
世界假设：开放世界（缺失事实 = [0,1] 未知，不是 false）
输出：Interpretation（每时间步每节点的谓词区间值）+ Rule Trace（事件日志）
```

## 5. Trace 数据形态

PyReason 的 `pr.get_rule_trace(interpretation)` 返回两个 pandas DataFrame。

**nodes_trace 列：**

| 列 | 含义 |
|----|------|
| Time | 时间步 |
| Fixed-Point-Operation / Fixed-Point-Op | 固定点迭代编号 |
| Node | 图节点标识 |
| Label | 谓词名 |
| Old Bound | 变化前的区间 `[lo, hi]` |
| New Bound | 变化后的区间 `[lo, hi]` |
| Occurred Due To | 规则名或 `fact` |
| Clause-1, Clause-2, ... | 具体的 clause grounding（哪些节点/边匹配了规则体原子） |

**这是事件日志（event log），不是证明树（proof tree）。**

## 5A. Session 写入模型

当前写入路径不是 `runtime_v1` 的统一写入 API，而是 adapter-local 的 `PyReasonSession`：

```python
session = PyReasonSession(schema_ir)
with session.batch() as tx:
    alice = tx.entity(User, user_id="Alice")
    alice.name.set("Alice", bound=[1.0, 1.0], meta={"source": "profile"})
    tx.relationship(Friends, from_entity=alice, to_entity=bob,
                    strength="0.9", bound=[0.9, 0.9])
    tx.commit()
```

### 5A.1 当前 session API

| API | 角色 |
|-----|------|
| `session.batch()` | entity-level batch transaction 入口 |
| `tx.entity(EntityCls, **identity)` | 创建/复用 entity handle |
| `handle.field.set(value, *, bound, active_from, active_to, meta)` | 写 node fact |
| `tx.relationship(RelCls, *, from_entity, to_entity, **fields)` | 写 edge fact |
| `session.node_facts` / `session.edge_facts` | engine consumption buffer |
| `session.annotation_templates` | assertion annotation 模板（待 Ledger consumer 填充 `asrt_id`） |
| `session.all_facts_meta` | audit-facing shared metadata |

### 5A.2 Annotation 模板

每条 buffered fact 同时生成 annotation-ready dict（`asrt_id=""` 占位）：

| namespace | category | key | 说明 |
|-----------|----------|-----|------|
| `pyreason` | `semantic` | `bound_lower` | 区间下界 |
| `pyreason` | `semantic` | `bound_upper` | 区间上界 |
| `pyreason` | `semantic` | `active_from` | 非默认时写入 |
| `pyreason` | `semantic` | `active_to` | 非 `None` 时写入 |
| `shared` | `derived` | `confidence` | 派生摘要 = lower bound |
| `shared` | `derived` | `confidence_source` | 当前固定为 `pyreason:lower_bound` |
| `shared` | `source` | `source` / `analyst` / `method` | 从 shared meta 转发 |

### 5A.3 Accept Helper

当前已经有一条最小的 adapter-local accept 路径：

```python
from factpy_kernel.adapters.pyreason.accept import accept_pyreason_session

result = accept_pyreason_session(ledger, session)
```

它做两件事：

1. 对每条 buffered fact 走 shared `set_field()`，拿到真正的 `asrt_id`
2. 只把 `session.annotation_templates` 中的 `pyreason/*` 条目 materialize 成 `AnnotationRow` 并写入 `ledger.append_annotations()`

`shared/*` annotation 不在这里重复写入，因为 `set_field()` 已经会通过 shared whitelist 自动写入。

### 5A.4 当前 accept 约束

PyReason session 内部的 graph node id 仍然是裸字符串（如 `Alice` / `Dog`），而 shared write path 的 ingest key 计算要求 `entity_ref` 走 canonical token。

因此 `accept_pyreason_session(...)` 在写入 Ledger 前会做一个最小的 adapter-local materialization：

- node fact: `Alice` → `idref_v1:User:Alice`
- edge `to_ref`: `Bob` → `idref_v1:User:Bob`

这不是完整的 factpy entity identity 对齐，只是为了让 PyReason 的 raw graph ids 能进入当前 shared write path。更完整的 identity/encoding 方案留待后续蓝图。

## 5B. Runner 模型

当前仍有一条 reusable 的底层执行路径；shared evaluate surface 会在 `engine_eval.py` 里复用它：

```python
from factpy_kernel.adapters.pyreason.rule_ext import (
    PyReasonFactDef,
    PyReasonRuleDef,
    PyReasonRuleExt,
)
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from factpy_kernel.sdk.dsl.expr import LogicVar, Pred
from factpy_kernel.sdk.dsl.rule import Rule

x = LogicVar("x")
y = LogicVar("y")

result = run_pyreason(
    session,
    rule_defs=[
        PyReasonRuleDef(
            rule=Rule(
                id="friend_popularity",
                version="1.0",
                select=[Pred("user:popular", x)],
                where=[
                    Pred("user:popular", y),
                    Pred("friends:strength", x, y),
                ],
            ),
            ext=PyReasonRuleExt(timestep_delay=1),
        )
    ],
    fact_defs=[PyReasonFactDef(atom="popular(Alice)", name="alice_popular", start=0, end=3)],
    config=PyReasonRunConfig(timesteps=2, atom_trace=True),
)
```

### 5B.1 Runner 输出

| 字段 | 含义 |
|------|------|
| `interpretation` | 原始 PyReason `Interpretation` 对象 |
| `trace` | `PyReasonTraceV0` |
| `trace_dict` | 可序列化 trace dict |
| `derived_session` | 只包含引擎推导出的新 facts 的 `PyReasonSession` |
| `config` | 本次运行配置 |
| `elapsed_seconds` | 运行耗时 |

### 5B.2 Runner 边界

- `run_pyreason(...)` 同时接受 legacy tuple 形式的 `rules` / `facts`，以及 typed `rule_defs` / `fact_defs`
- `PyReasonRuleDef` 是 adapter-local wrapper：`Rule + PyReasonRuleExt`，不修改 shared `Rule`
- `compile_pyreason_rule(...)` 当前只支持 `PredAtom` + `LogicVar` + 字面量；`CompareExpr` / `NotExpr` / `RuleRefAtom` 会报明确错误
- `run_pyreason(...)` 本身仍是底层 helper；`Store.evaluate(mode="pyreason")` 通过 `engine_eval.py` 在外层完成 WHERE→PyReason 编译和 CandidateSet 组装
- `derived_session` 可以直接接到 `accept_pyreason_session(...)`

## 5C. Shared Execution Surface

当前共享执行链路如下：

```python
import factpy_kernel.adapters.pyreason

candidates = sdk.evaluate(
    Derivation(
        id="drv.pyreason_popular",
        version="v1",
        where=[Pred("user:name", u, name)],
        target="user:popular",
        head_vars=[u],
        mode="pyreason",
        engine_ext=PyReasonRuleExt(timestep_delay=2),
    ),
    engine_options={"timesteps": 5},
)
```

执行顺序：

1. `SDKStore.evaluate(...)` 从 `Derivation` 单独提取 `engine_ext`，同时把 call-time `engine_options` 保持在 evaluate 调用层；两者都不写入 `to_authoring_payload()`
2. `evaluate_store(...)` / `Store.evaluate_engine(...)` 把 `mode="pyreason"`、`engine_ext` 与 `engine_options` 转发到 adapter
3. `pyreason_engine_eval(...)`：
   - 用 `project_view_facts(...)` 把 Ledger active facts materialize 成 `PyReasonSession`
   - 用 `compile_where_ir_to_pyreason(...)` 把 lowered WhereIR 编译成 PyReason rule strings
   - 用 `resolve_pyreason_run_config(engine_options)` 归一化运行配置
   - 调用 `run_pyreason(...)`
   - 把 derived session facts 转成 `CandidateSet`
   - 把 annotation templates 缓存在 `store._engine_pending_annotations[run_id]`
4. core `accept()` 负责把 candidate payload 写回 Ledger
5. caller 在 post-accept 阶段调用 `persist_pyreason_annotations(ledger, run_id, store, accept_result)`，把 pending `pyreason/*` templates 绑定到真实 `asrt_id` 后写入 `annotation_rows`

### 5C.0 Runtime options

shared evaluate surface 当前对 PyReason 公开的 run-time 选项只有一个：

- `timesteps: int`

约束：

- `sdk.evaluate(..., mode="pyreason", engine_options={"timesteps": 5})` 会生效
- 缺省时使用 adapter 默认值 `timesteps=2`
- unknown keys 直接报 `ValueError`
- `atom_trace` / `convergence_*` 仍保持 adapter-internal，不通过 shared evaluate surface 暴露

### 5C.1 Bounded numeric extension (L3b)

PyReason adapter 当前支持一个收窄的 value-carrying 路径：**bounded numeric predicates**。

触发条件必须同时满足：

1. predicate spec 显式声明 `pyreason_bounded: true`
2. value `type_domain` 是 numeric（当前实际覆盖 `int` / `float64`）
3. 事实值可解析为 `[0, 1]` 内的数值

这是 adapter-local 语义扩展，不是 shared schema contract。没有 `pyreason_bounded: true` 的 predicate，即使值长得像 `0.85`，也继续走 v0 existence materialization。

当前实现行为：

- **EDB materialization**：`engine_eval.py` 把 bounded predicate 的 Ledger value 解析成 point interval `bound=(v, v)`；非 bounded predicate 仍用 `bound=(1.0, 1.0)`
- **Graph build**：`runner.build_pyreason_graph(...)` 对 bounded predicate 写入 `graph.nodes[...] = v` / `graph.edges[...] = v`；非 bounded predicate 仍写 `= 1`
- **Derived extraction**：`runner._extract_derived_facts(...)` 对 bounded predicate 返回 `value=str(lower_bound)`；非 bounded node 仍是 `"true"/"false"`，非 bounded edge 仍是空字符串
- **Canonical float64**：通过 `project_view_facts(...)` 进入 adapter 的 `float64` 值会是 canonical `0x...` bit-pattern；bounded parser 已显式支持这种形态

v0 / v1 约束：

- WhereIR compiler 只支持 lowered `("pred", pred_id, terms)` atoms；`eq` / `not` / `ruleref` 直接报错
- 采用 attribute-existence model：node predicates 只编译实体变量，不带 value variable
- bounded numeric 只影响 materialization / extraction，不引入 rule syntax value variable
- `engine_ext` 只支持 `Derivation.engine_ext`，不进入持久化 payload
- `engine_options` 是 call-time only，不进入 `Derivation`、`to_authoring_payload()` 或 audit artifacts
- `Store.accept()` 当前不会自动 materialize / clear pending annotations；v0 通过 `persist_pyreason_annotations(...)` 完成这一步

## 6. Souffle vs PyReason Provenance 对比

### 6.1 形态

| 维度 | Souffle | PyReason |
|------|---------|----------|
| **数据结构** | JSON proof tree（per-conclusion） | pandas DataFrame event log（per-change） |
| **粒度** | 一棵树解释一个结论 | 所有变化的扁平日志 |
| **时间维度** | 无 | 内建 timestep，可追踪传播 |
| **值域** | Boolean（true/false） | 区间 `[lower, upper]` |
| **世界假设** | 封闭（CWA） | 开放（OWA，缺失 = `[0,1]`） |
| **获取方式** | `-t explain` + stdin pipe（subprocess） | `pr.get_rule_trace()`（in-process Python） |
| **序列化** | JSON（天然） | DataFrame → 需转换为 JSON |

### 6.2 可统一字段

| 字段 | Souffle | PyReason | 可统一？ |
|------|---------|----------|---------|
| 结论标识 | `relation(args)` | `Node + Label` | ✅ 映射 |
| 规则标识 | `rule-number (R1)` | `Occurred Due To`（rule name） | ✅ 语义一致 |
| 叶子事实 | `axiom` nodes | `Occurred Due To = "fact"` rows | ✅ 语义一致 |
| 时间 | 无 | `Time` 列 | ❌ Souffle 无此维度 |
| 区间值 | 无 | `Old Bound / New Bound` | ❌ Souffle 无此维度 |
| 否定 | `!relation` negation leaf | 不适用（OWA 下无显式否定） | ❌ 语义不同 |
| 子证明截断 | `subproof` marker | 不适用 | ❌ Souffle 特有 |
| Clause grounding | 无（隐含在树结构中） | `Clause-1, Clause-2, ...` 显式列 | ⚠️ 形态不同但语义可桥接 |

### 6.3 ProofNode v1 更新建议

基于 Souffle + PyReason 两个真实样本的结论：

1. **不能假设所有引擎产出 tree。** Souffle 是 tree，PyReason 是 event log。统一抽象不能是 `ProofTree`。
2. **候选方案 A：per-candidate payload with engine-specific shape。** 每个 candidate 携带一个 `provenance_payload`，其 `engine` 字段指示形态（`souffle_proof_tree` / `pyreason_event_log`），consumer 按 engine 分发渲染。
3. **候选方案 B：统一为 event sequence。** 把 Souffle proof tree 展平为事件序列（DFS），再与 PyReason 的 event log 对齐。代价是丢失 Souffle 的树结构。
4. **当前建议：选 A。** 保留引擎原生形态更诚实，也更符合 ADR 的 adapter-local before core 原则。
5. **ProofNode v1 开启门槛**：至少有 2 个引擎的真实 provenance 通过 adapter → audit → static 完整管道验证后，再冻结统一抽象。当前 Souffle 已完整，PyReason 仍是 spike，不足以冻结。

## 7. 当前限制

- shared evaluate surface 已实现，但 rule registry / rule builder integration 仍未做
- `session.annotation_templates` 已可通过 `accept_pyreason_session(...)` 落到 Ledger；但当前 accept 仍依赖 adapter-local synthetic `entity_ref` materialization
- pending `pyreason/*` annotations 仍需在 accept 后显式 bind/persist；core `Store.accept()` 不会自动完成这一步，但 adapter 已提供 `persist_pyreason_annotations(...)`
- 依赖 `pyreason==3.0.0`（非 repo-managed dependency）
- 真实 execution-surface operator path 仍受外部 `pyreason` / `numba` / `llvmlite` 环境兼容性限制；当前本机组合 `numba==0.64.0`、`llvmlite==0.46.0` 未通过验证
- `PyReasonTraceEventV0` 字段未冻结
