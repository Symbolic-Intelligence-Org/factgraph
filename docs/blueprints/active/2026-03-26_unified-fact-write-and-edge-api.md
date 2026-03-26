# Sub-Blueprint: Shared Schema Extension + Engine Session Write Path

- Status: scoped
- Created: 2026-03-26
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- ADR Reference: [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) §ADR-14a, §ADR-14b, §ADR-14c

## 1. Problem

当前只有 Souffle 走了 schema 校验 + 事实写入 + 审计记录的完整路径。PyReason spike 直接调 `pr.add_fact()` 绕过了框架。各引擎的事实写入互不兼容。

按修正后的 ADR-14a："Schema 是统一边界，审计是统一出口。写入路径是引擎适配层的事。" 不需要强行统一写入 API，但需要：
1. 共享 schema 能表达图关系（Relationship）
2. `confidence` 值域扩展为 `float | [float, float]`
3. PyReason 有自己的写入 session，校验同一份 schema

## 2. Goals

- 新增 `Relationship` schema 类型（与 Entity 平行）
- 扩展 `confidence` 值域为 `float | [float, float]`（dual-write 向后兼容）
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

### 4.1 Souffle 写入路径（已有，不改）

```python
write_runtime_fact(session_id, {
    "pred_id": "ict_incident:affected_clients",
    "e_ref": entity_ref,
    "rest_terms": [["string", "15000"]],
    "meta": {"confidence": 0.85},
}, kind="add")
```

### 4.2 PyReason 需要什么（引擎特定 session）

```python
# Node fact — 引擎特有参数在 session API 里：
pyreason_session.write_node_fact(
    pred_id="affected_clients", node_ref=entity_ref,
    value="15000", bound=[0.8, 0.9], active_from=0, active_to=5,
    meta={"confidence": [0.8, 0.9], "source": "..."},
)

# Edge fact — 图关系，PyReason 一等概念：
pyreason_session.write_edge_fact(
    pred_id="friends:strength", from_ref=ref_a, to_ref=ref_b,
    value="0.9", bound=[0.9, 0.9],
    meta={"source": "survey"},
)
```

## 5. Design

### 5.1 通用 Meta：`confidence` 值域扩展

**决策：不引入 `belief`。继续用 `confidence`，扩展值域为 `float | [float, float]`。**

```python
# 通用 meta（所有引擎共用，不因新引擎膨胀）：
meta = {
    "confidence": 0.8,            # float → 框架内部当作 [0.8, 0.8]（已有，不改）
    # 或
    "confidence": [0.6, 0.9],    # [float, float] → 区间值（新增）

    "source": "...",
    "analyst": "...",
}
```

**原因**：`confidence` 已在 16 条冻结 contract + runtime/certainty/mapping/sdk 多个 surface 使用。引入 `belief` 会造成全系统双轨不兼容。区间 `[0.6, 0.9]` 作为 confidence 的扩展值域语义自洽："置信度在 0.6 到 0.9 之间"。

**规范化规则**：
- `write_protocol` 接受 `confidence: float | [float, float]`
- 内部 canonical 存储为 `[lower, upper]`
- 单值 `0.8` 存储为 `[0.8, 0.8]`
- 旧 surface 读 `confidence` 时：如果是区间，取 `lower`（向后兼容）
- PyReason adapter 读 confidence 时：直接用 `[lower, upper]`

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
    meta={"confidence": [0.8, 0.9], "source": "..."},  # 通用 meta
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
2. 通用 `meta`（confidence, source, analyst）被记录到审计层
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

def compile_confidence_to_bound(meta) -> tuple[float, float]:
    """Convert meta.confidence (float | [float, float]) to PyReason bound."""
    confidence = meta.get("confidence")
    if isinstance(confidence, (list, tuple)) and len(confidence) == 2:
        return (float(confidence[0]), float(confidence[1]))
    if isinstance(confidence, (int, float)):
        return (float(confidence), float(confidence))
    return (0.0, 1.0)  # no confidence → open world default
```

## 6. Implementation Plan

```
Step 1: Relationship SDK type + schema_ir 编译
  - sdk/: Relationship class
  - sdk/compile.py: Relationship → schema_ir predicate 生成
  - authoring/schema_compile.py: 扩展 _compile 路径支持 Relationship
  - predicate 形态: (e_ref_from, e_ref_to, ...field_args)
  - tests: relationship schema compilation

Step 2: (CANCELLED — violates ADR-14a)
  原计划：扩展 write_protocol 接受 confidence interval
  取消原因：区间值是 PyReason 引擎特有概念，不应进共享 write_protocol
  替代方案：PyReason session (Step 3) 内部处理区间值，
            向审计层写入时自动取 lower bound 作为 compat confidence

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
- [ ] ~~confidence 值域扩展~~ (CANCELLED — violates ADR-14a)
- [ ] PyReason session 内部处理 bound → confidence 映射（在 Step 3 实现）
- [ ] PyReason session 可写入 node/edge facts（校验 schema）
- [ ] 引擎特有参数只在 PyReason session API 里，不进共享 meta
- [ ] Souffle 现有路径不受影响（260 tests green）
- [ ] 至少一个集成 example 展示 schema → PyReason session → write → reason

## 8. File Scope

允许修改：
- `src/factpy_kernel/sdk/`（Relationship type）
- `src/factpy_kernel/sdk/compile.py`（Relationship → schema_ir）
- `src/factpy_kernel/authoring/schema_compile.py`（Relationship predicate 生成）
- ~~`src/factpy_kernel/core/evidence/write_protocol.py`~~ (removed — Step 2 cancelled)
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
