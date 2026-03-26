# Sub-Blueprint: Shared Schema Extension + Engine Session Write Path

- Status: scoped
- Created: 2026-03-26
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- ADR Reference: [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) §ADR-14a, §ADR-14b, §ADR-14c

## 1. Problem

当前只有 Souffle 走了 schema 校验 + 事实写入 + 审计记录的完整路径。PyReason spike 直接调 `pr.add_fact()` 绕过了框架。各引擎的事实写入互不兼容。

按修正后的 ADR-14a："Schema 是统一边界，审计是统一出口。写入路径是引擎适配层的事。" 不需要强行统一写入 API，但需要：
1. 共享 schema 能表达图关系（Relationship）
2. 通用 meta（belief 区间）有定义
3. PyReason 有自己的写入 session，校验同一份 schema

## 2. Goals

- 新增 `Relationship` schema 类型（与 Entity 平行）
- 定义 `belief` 通用真值区间（`confidence` 向后兼容 alias）
- 为 PyReason 实现引擎特定写入 session（校验 schema，记录审计）
- 不改 Souffle 现有行为

## 3. Non-Goals

- 不强行统一写入 API（ADR-14a 已明确：各引擎独立写入路径）
- 不做 Layer 2 Rule builder（Phase 2）
- 不做 Evaluate dispatch（Phase 3）
- 不做 ProbLog 写入 session（本轮只做 PyReason）
- 不改 audit pipeline
- 不改 provenance
- 不给共享 meta 加引擎特有参数

## 4. Current Context

### 4.1 现有 write_runtime_fact 签名

```python
write_runtime_fact(session_id, {
    "pred_id": "ict_incident:affected_clients",
    "e_ref": entity_ref,
    "rest_terms": [["string", "15000"]],
    "meta": {"confidence": 0.85},
}, kind="add")
```

### 4.2 PyReason 需要什么

```python
# Node fact:
pr.add_fact(pr.Fact("affected_clients(entity)", "fact_name", 0, 5))
# 对应 write_runtime_fact + meta.valid_from/valid_to

# Edge fact:
g.add_edge("John", "Mary", Friends=1)
# 对应 write_runtime_edge_fact（当前不存在）

# Interval bound:
pr.add_fact(pr.Fact("confidence(entity)", "fact", 0, 5, bound=[0.8, 0.9]))
# 对应 meta.confidence = [0.8, 0.9]
```

## 5. Design

### 5.1 通用 Meta：`belief` 区间

```python
# 通用 meta（所有引擎共用，不因新引擎膨胀）：
meta = {
    "belief": 0.8,            # float → 框架内部当作 [0.8, 0.8]
    # 或
    "belief": [0.6, 0.9],    # [float, float] → PyReason 直接用

    "source": "...",
    "analyst": "...",
    # confidence 保留为 alias（certainty v1 向后兼容）
}
```

引擎特有参数（`active_from`、`probability` 等）不进 meta，留在引擎自己的写入 API。

### 5.2 PyReason 写入 Session

PyReason 有自己的写入路径，不走 `write_runtime_fact`：

```python
# PyReason 写入 session（引擎特定 API）
pyreason_session = open_pyreason_session(schema_ir=schema_ir)

# 写节点事实（引擎特有参数在 API 里，不在 meta 里）
pyreason_session.write_node_fact(
    pred_id="ict_incident:affected_clients",
    node_ref=entity_ref,
    value="15000",
    bound=[0.8, 0.9],       # PyReason 特有：区间值
    active_from=0,           # PyReason 特有：时间步
    active_to=5,
    meta={"source": "..."},  # 通用 meta（belief 从 bound 自动派生）
)

# 写边事实（图关系，PyReason 一等概念）
pyreason_session.write_edge_fact(
    pred_id="friends:strength",
    from_ref=entity_ref_a,
    to_ref=entity_ref_b,
    value="0.9",
    bound=[0.9, 0.9],
    meta={"source": "survey"},
)
```

**共同约束**：
1. `pred_id` 必须在 `schema_ir` 里（校验 Relationship / Entity schema）
2. 通用 `meta`（belief, source, analyst）被记录到审计层
3. 引擎特有参数（bound, active_from）只在 PyReason session 里，不进共享 meta

### 5.3 Relationship Schema

```python
from factpy_kernel.sdk import Relationship, Entity, Identity, Field

class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")

class Friends(Relationship):
    from_entity: User
    to_entity: User
    strength: str = Field(cardinality="single")
```

`Relationship` 在 `schema_ir` 里生成一个 predicate，形态为 `(e_ref_from, e_ref_to, ...field_args)`。

**和 edge claim 编码对齐**：`e_ref` = from, `rest_terms[0]` = to, `rest_terms[1:]` = field values。schema_ir predicate 的 `arg_specs[0]` 是 from entity ref，`arg_specs[1]` 是 to entity ref，后续是 Relationship 自身的 Field args。不展开 identity fields——from/to 都用 entity ref（和现有 Entity predicate 的 `e_ref` 约定一致）。

### 5.4 PyReason Fact Adapter Compiler

新增 `adapters/pyreason/fact_compiler.py`：

```python
def compile_node_fact(pred_id, e_ref, rest_terms, meta) -> pr.Fact:
    """Convert write_runtime_fact input to PyReason Fact."""

def compile_edge_fact(pred_id, from_ref, to_ref, rest_terms, meta) -> tuple:
    """Convert write_runtime_edge_fact input to NetworkX edge + pr.Fact."""

def compile_meta_to_bound(meta) -> tuple[float, float]:
    """Convert meta.confidence to PyReason interval bound."""
    confidence = meta.get("confidence")
    if isinstance(confidence, list):
        return tuple(confidence)  # [lower, upper]
    if isinstance(confidence, (int, float)):
        return (confidence, confidence)  # single value → point interval
    return (0.0, 1.0)  # unknown → open world default
```

## 6. Implementation Plan

```
Step 1: Relationship SDK type + schema_ir 编译
  - sdk/: Relationship class
  - sdk/compile.py: Relationship → schema_ir predicate 生成
  - authoring/schema_compile.py: 扩展 _compile 路径支持 Relationship
  - predicate 形态: (e_ref_from, e_ref_to, ...field_args)
  - tests: relationship schema compilation

Step 2: belief meta 定义
  - write_protocol.py: 放宽 meta 校验，接受 belief (float | [float, float])
  - confidence 保留为向后兼容 alias
  - 不改 Souffle 行为

Step 3: PyReason 写入 session
  - adapters/pyreason/session.py: PyReasonSession class
  - write_node_fact: 校验 schema + 记录 meta + 调 pr.add_fact
  - write_edge_fact: 校验 Relationship schema + 调 g.add_edge
  - 引擎特有参数（bound, active_from/to）在 session API 里
  - tests: synthetic (no real PyReason JIT)

Step 4: Integration example
  - examples/pyreason_integration_demo.py
  - Schema → Relationship → PyReason session → write → reason → trace
```

## 7. Acceptance Criteria

- [ ] 新增 `Relationship` SDK 类型，可编译为 `schema_ir`
- [ ] `belief` meta 字段定义并校验（float | [float, float]）
- [ ] `confidence` 保留为向后兼容 alias
- [ ] PyReason session 可写入 node/edge facts（校验 schema）
- [ ] 引擎特有参数只在 PyReason session API 里，不进共享 meta
- [ ] Souffle 现有路径不受影响（260 tests green）
- [ ] 至少一个集成 example 展示 schema → PyReason session → write → reason

## 8. File Scope

允许修改：
- `src/factpy_kernel/sdk/`（Relationship type）
- `src/factpy_kernel/sdk/compile.py`（Relationship → schema_ir）
- `src/factpy_kernel/authoring/schema_compile.py`（Relationship predicate 生成）
- `src/factpy_kernel/core/evidence/write_protocol.py`（belief meta 校验）
- `src/factpy_kernel/adapters/pyreason/`（session + fact writer）
- `src/factpy_kernel/tests/`
- `examples/`

不允许修改：
- `src/factpy_kernel/service/runtime_v1.py`（不加 edge fact endpoint——PyReason 走自己的 session）
- Souffle adapter（不改现有路径）
- Audit pipeline
- Provenance modules
- Certainty modules

## 9. Outcome

任务完成后填写：

- Final result:
- Deviations:
- Archive notes:
