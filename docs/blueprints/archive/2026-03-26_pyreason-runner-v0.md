# Task Blueprint: PyReason Runner v0

- Status: implemented
- Created: 2026-03-26
- Last Updated: 2026-03-26
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/runner.py` (new)
  - `src/factpy_kernel/adapters/pyreason/session.py`
  - `src/factpy_kernel/adapters/pyreason/accept.py`
  - `src/factpy_kernel/adapters/pyreason/provenance.py`
- Audit Log:
  - [2026-03-26_pyreason-runner-v0.audit.md](./2026-03-26_pyreason-runner-v0.audit.md)

## 1. Problem

Integration demo 里 session→graph→reason→trace 是手动步骤。没有 reusable helper 把它们串成一条正式路径。下游 accept helper 已经存在，但没有上游 runner 喂数据给它。

## 2. Goals

- `PyReasonRunConfig` — 引擎运行配置（timesteps, atom_trace 等）
- `build_pyreason_graph(session)` — 从 session facts 构建 NetworkX graph
- `run_pyreason(session, rules, facts, config)` — 完整执行路径
- `PyReasonRunResult` — 封装 interpretation + trace + derived facts
- 与现有 `accept_pyreason_session()` 可直接接线

## 3. Non-goals

- 不注册到 `Store.evaluate()`（那需要 WHERE→rule 编译）
- 不做 rule builder / `PyReasonRuleExt`
- 不做 CandidateSet 输出（那是 Store 系统的概念）
- 不碰 provenance audit pipeline
- 不碰 core/ 下任何文件

## 4. Current Context

- `PyReasonSession` 已有 batch API + annotation templates
- `accept_pyreason_session()` 已能持久化到 Ledger
- `parse_pyreason_trace()` + `pyreason_trace_to_dict()` 已存在
- Integration demo 已跑通完整路径（手动）

## 5. Proposed Shape

### 5.1 Target API

```python
from factpy_kernel.adapters.pyreason.runner import (
    PyReasonRunConfig,
    PyReasonRunResult,
    build_pyreason_graph,
    run_pyreason,
)

# 1. Config
config = PyReasonRunConfig(timesteps=2, atom_trace=True)

# 2. Run
result = run_pyreason(
    session=session,
    rules=[
        ("popular(x) <-1 popular(y), Friends(x,y)", "friend_popularity"),
        ("outdoorsy(x) <-0 Owns(x,y), dog_breed(y)", "dog_owner_outdoorsy"),
    ],
    facts=[
        ("popular(Alice)", "alice_popular", 0, 3),
    ],
    config=config,
)

# 3. Access results
result.interpretation   # Raw PyReason Interpretation object
result.trace            # PyReasonTraceV0
result.derived_session  # PyReasonSession with derived facts (for accept)

# 4. Accept to Ledger
accept_result = accept_pyreason_session(ledger, result.derived_session)
```

### 5.2 `PyReasonRunConfig`

```python
@dataclass
class PyReasonRunConfig:
    timesteps: int = 1
    atom_trace: bool = True
    convergence_threshold: float | None = None  # future
    convergence_bound_threshold: float | None = None  # future
```

只暴露 PyReason 当前支持的 `pr.reason()` 参数。其余留 `None` 不传。

### 5.3 `build_pyreason_graph(session)`

从 `session.node_facts` + `session.edge_facts` 构建 `nx.DiGraph`：
- Node facts: `graph.nodes[node_ref][attr_name] = 1`
- Edge facts: `graph.edges[from_ref, to_ref][attr_name] = 1`
- `attr_name` = `pred_id.split(":")[1]`（field name）

这是 demo 里 lines 152-176 的提取。

### 5.4 `run_pyreason(session, rules, facts, config)`

完整执行路径：
1. `build_pyreason_graph(session)` → graph
2. `pr.reset()` + `pr.load_graph(graph)`
3. 添加 rules：`pr.add_rule(pr.Rule(body, name))`
4. 添加 initial facts：`pr.add_fact(pr.Fact(atom, name, start, end))`
5. `pr.settings.atom_trace = config.atom_trace`
6. `interpretation = pr.reason(timesteps=config.timesteps)`
7. `nodes_trace, edges_trace = pr.get_rule_trace(interpretation)`
8. `trace = parse_pyreason_trace(nodes_trace, edges_trace, timesteps=config.timesteps)`
9. Extract derived facts → `derived_session`
10. `pr.reset()`（cleanup）

### 5.5 Derived Fact Extraction

从 `interpretation.get_dict()` 提取非初始状态的 fact 变化：
- 遍历 timestep > 0 的条目
- 对于新出现或 bound 变化的 facts，写入 `derived_session`
- 使用原 session 的 schema_ir 构建 derived_session

### 5.6 `PyReasonRunResult`

```python
@dataclass
class PyReasonRunResult:
    interpretation: Any          # pyreason.Interpretation
    trace: PyReasonTraceV0       # Parsed provenance
    trace_dict: dict             # Serializable trace
    derived_session: PyReasonSession  # Derived facts for accept
    config: PyReasonRunConfig
    elapsed_seconds: float
```

### 5.7 Rules/Facts 输入格式

Rules 和 facts 使用简单 tuple 格式，不引入 `PyReasonRule` 类型（那是 rule builder 的范围）：
- Rule: `(body_str, name_str)` → `pr.Rule(body_str, name_str)`
- Fact: `(atom_str, name_str, start_time, end_time)` → `pr.Fact(atom_str, name_str, start_time, end_time)`

## 6. Boundaries And Invariants

- runner 在 `adapters/pyreason/` 下，不在 core/
- `import pyreason` 可能失败（JIT/numba 问题），runner 不做 fallback——调用方负责 try/except
- `derived_session` 只包含引擎推导出的新 facts，不包含原始输入 facts
- `pr.reset()` 在 run 结束后必须调用（cleanup PyReason global state）
- rules/facts 以 tuple 传入，不引入新 DSL 类型

## 7. Acceptance

- [x] `build_pyreason_graph()` 从 session 构建正确的 NetworkX graph
- [x] `run_pyreason()` helper 已实现并返回 `PyReasonRunResult`
- [x] derived_session 提取逻辑已实现并有 mock 覆盖
- [x] trace 解析路径已在 helper 中接到 `PyReasonTraceV0`
- [x] `accept_pyreason_session(ledger, result.derived_session)` 可直接接线
- [x] Integration demo 已简化为使用 runner helper

## 8. Implementation Plan

1. 新建 `adapters/pyreason/runner.py`：`PyReasonRunConfig` + `build_pyreason_graph()` + `run_pyreason()` + `PyReasonRunResult`
2. 新建 `tests/test_pyreason_runner.py`：graph builder 测试 + mock runner 测试
3. 更新 `examples/pyreason_integration_demo.py`：使用 runner helper
4. 更新 `adapters/docs/03_pyreason_adapter.md`

## 9. Docs To Update

- 本蓝图 audit log
- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `adapters/pyreason/runner.py`，提供 `PyReasonRunConfig` / `build_pyreason_graph()` / `run_pyreason()` / `PyReasonRunResult`
  - Integration demo 已从手写 graph/load/rule/trace 步骤切到 runner helper
  - adapter docs 已同步 runner + accept 的当前形态
- 与 blueprint 不同的地方：
  - 本轮没有拿到一次真实 PyReason 运行的绿灯；本机 `pyreason` 导入仍会触发 numba cache runtime error
- 为什么会有这些调整：
  - `run_pyreason()` 的结构、graph builder、derived extraction、accept 接线都可以本地验证，但真实 engine import 问题仍是环境前置，不是 helper 逻辑错误
- 归档说明：
  - 代码、tests、demo、module docs 对齐后归档
