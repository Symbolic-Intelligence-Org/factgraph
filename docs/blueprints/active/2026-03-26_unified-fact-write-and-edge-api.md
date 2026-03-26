# Sub-Blueprint: Unified Fact Write + Edge Fact API

- Status: scoped
- Created: 2026-03-26
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- ADR Reference: [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) §ADR-14a, §ADR-14b, §ADR-14c

## 1. Problem

当前只有 Souffle 走了 `write_runtime_fact` → adapter 编译的完整路径。PyReason spike 直接调 `pr.add_fact()`，ProbLog adapter 用 subprocess 传文件。三个引擎的事实写入互不兼容，无法实现"用户写一次，三个引擎都能用"的框架承诺。

此外，PyReason 的图边（edge）是一等公民，当前 API 没有表达能力。

## 2. Goals

- 让 `write_runtime_fact` 的 meta schema 支持区间值和时间窗口
- 新增 `write_runtime_edge_fact` API
- 新增 `Relationship` schema 类型
- 为 PyReason adapter 提供 fact compilation 路径（graph node/edge attribute）
- 不改 Souffle 现有行为

## 3. Non-Goals

- 不做 Layer 2 Rule builder（Phase 2）
- 不做 Evaluate dispatch（Phase 3）
- 不做 ProbLog fact adapter compiler（本轮只做 PyReason，ProbLog 留到后续）
- 不改 audit pipeline
- 不改 provenance

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

### 5.1 Meta schema 扩展

```python
# 当前 meta（不改）：
meta = {"confidence": 0.85}

# 扩展后（additive）：
meta = {
    "confidence": 0.85,           # float: Souffle/ProbLog 单值
    # 或
    "confidence": [0.8, 0.9],    # [float, float]: PyReason 区间 [lower, upper]

    "valid_from": 0,              # int | None: PyReason 时间步起始
    "valid_to": 5,                # int | None: PyReason 时间步终止

    # 已有的其他 meta 字段不受影响：
    "source": "...",
    "analyst": "...",
}
```

### 5.2 Edge Fact API

```python
write_runtime_edge_fact(session_id, {
    "pred_id": "Friends",
    "from_ref": entity_ref_a,
    "to_ref": entity_ref_b,
    "rest_terms": [["string", "1"]],   # 边上的属性值（可选）
    "meta": {"confidence": 0.95},
}, kind="add")
```

Service 层新增 `write_runtime_edge_fact`。

**Edge 存储策略（冻结）**：edge fact 编码成普通 `claim`，不改 ledger schema：
- `pred_id` = relationship pred_id（例如 `"friends:strength"`）
- `e_ref` = `from_ref`（边的起点实体）
- `rest_terms[0]` = `to_ref`（边的终点实体，作为第一个 term）
- `rest_terms[1:]` = 边属性值

这样 Souffle adapter 自然编译成二元+ 谓词，PyReason adapter 解析 `rest_terms[0]` 为 `to_ref` 构建图边。

**本轮不升级**：generic `list_facts` / `explain` / read surface 不感知 edge 语义。Edge claim 在这些接口里表现为普通 claim（`e_ref` = from, 第一个 term = to）。这是刻意的——避免蔓延到通用读接口。

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

`Relationship` 在 `schema_ir` 里生成一个 predicate，arity = from_fields + to_fields + own_fields。

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
Step 1: Meta schema validation
  - runtime_v1.py: validate extended meta (confidence as float|list, valid_from/to)
  - 不改 Souffle 行为（Souffle 忽略 interval/temporal meta）

Step 2: Edge fact API
  - runtime_v1.py: write_runtime_edge_fact
  - Store: edge claim storage (minimal — can be a tagged claim)
  - 03_runtime_queries_views.md: document new endpoint

Step 3: Relationship SDK type
  - sdk/: Relationship class + schema_ir generation
  - tests: relationship schema compilation

Step 4: PyReason fact compiler
  - adapters/pyreason/fact_compiler.py
  - Convert node facts + edge facts to PyReason API calls
  - tests: synthetic compilation (no real PyReason dependency)

Step 5: Integration example
  - examples/pyreason_integration_demo.py
  - Uses write_runtime_fact + write_runtime_edge_fact + PyReason evaluate
```

## 7. Acceptance Criteria

- [ ] `write_runtime_fact` 接受 `meta.confidence` 为 float 或 `[float, float]`
- [ ] `write_runtime_fact` 接受 `meta.valid_from` / `meta.valid_to`
- [ ] 新增 `write_runtime_edge_fact` service endpoint
- [ ] 新增 `Relationship` SDK 类型，可编译为 `schema_ir`
- [ ] PyReason fact compiler 可将 node/edge facts 转换为 PyReason API 调用
- [ ] Souffle 现有路径不受影响（260 tests green）
- [ ] 至少一个集成 example 展示 fact write → PyReason evaluate 路径

## 8. File Scope

允许修改：
- `src/factpy_kernel/service/runtime_v1.py`（edge fact endpoint）
- `src/factpy_kernel/core/store/runtime.py`（edge claim）
- `src/factpy_kernel/core/store/ledger.py`（edge claim storage if needed）
- `src/factpy_kernel/sdk/`（Relationship type）
- `src/factpy_kernel/sdk/compile.py`（Relationship → schema_ir 编译）
- `src/factpy_kernel/authoring/schema_compile.py`（Relationship predicate 生成）
- `src/factpy_kernel/adapters/pyreason/`（fact compiler）
- `src/factpy_kernel/service/docs/`
- `src/factpy_kernel/tests/`
- `examples/`

不允许修改：
- Souffle adapter（不改现有编译路径）
- Audit pipeline
- Provenance modules
- Certainty modules
- Generic read/explain/list surface（不感知 edge 语义）

## 9. Outcome

任务完成后填写：

- Final result:
- Deviations:
- Archive notes:
