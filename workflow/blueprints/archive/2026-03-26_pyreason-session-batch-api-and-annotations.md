# Task Blueprint: PyReason Session Batch API And Annotations

- Status: implemented
- Created: 2026-03-26
- Last Updated: 2026-03-26
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/session.py`
  - `src/factpy_kernel/tests/test_pyreason_session.py`
  - `examples/pyreason_integration_demo.py`
- Related Docs:
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) (ADR-14a, ADR-14d)
  - [memory/session_handoffs/2026-03-26.md](../../../memory/session_handoffs/2026-03-26.md) (§8.1)
- Audit Log:
  - [2026-03-26_pyreason-session-batch-api-and-annotations.audit.md](./2026-03-26_pyreason-session-batch-api-and-annotations.audit.md)

## 1. Problem

PyReasonSession 当前暴露 `write_node_fact(pred_id, ...)` / `write_edge_fact(pred_id, ...)`，存在两个问题：

1. **API 粒度错位**：用户必须知道 pred_id 和 node/edge 区分，而 SDK 共享路径在 entity level 操作（`tx.entity(User, ...).name.set(...)`）。schema 的抽象被穿透。
2. **Annotation Store 未接入**：PyReason 的 engine-native 语义（bound, active_from/to）没有生成 `pyreason/semantic/*` annotation 模板，无法零损失持久化到 Annotation Store。

## 2. Goals

- 新增 entity-level batch API：`session.batch()` → `tx.entity()` → `field.set()` + `tx.relationship()`
- 系统根据 schema 自动路由到 node/edge fact，用户不感知区分
- `write_node_fact`/`write_edge_fact` 降为内部方法（`_write_node_fact_internal`/`_write_edge_fact_internal`）
- 每条 fact 写入时生成 annotation 模板（`pyreason/semantic/*` + `shared/derived/confidence`）
- 更新现有测试 + 新增 batch API 测试
- 更新 integration demo

## 3. Non-goals

- 不做 Ledger 集成（accept flow for PyReason）
- 不做 evaluate dispatch（`mode="pyreason"`）
- 不做 rule builder（`PyReasonRuleExt`）
- 不做 `engine_ext` 实现
- 不碰 provenance carrier

## 4. Current Context

- Annotation Store 已落地（`annotation_rows` in Ledger）
- `write_protocol` 共享路径已双写（`shared/*` annotations）
- PyReasonSession 是纯内存 buffer，不写 Ledger
- SDK batch pattern 在 `sdk/batch.py` 已有成熟实现，可参考但不需要完整复制

## 5. Proposed Shape

### 5.1 Target API

```python
session = PyReasonSession(schema_ir)
with session.batch() as tx:
    alice = tx.entity(User, user_id="Alice")
    alice.name.set("Alice", bound=[1.0, 1.0])
    alice.popular.set("true", bound=[1.0, 1.0])

    bob = tx.entity(User, user_id="Bob")
    bob.name.set("Bob", bound=[1.0, 1.0])

    tx.relationship(Friends, from_entity=alice, to_entity=bob,
                    strength="0.9", bound=[0.9, 0.9])
    tx.commit()

# Engine consumption (unchanged)
session.node_facts   # → same format as before
session.edge_facts   # → same format as before

# Annotation templates (new)
session.annotation_templates  # → list of annotation-ready dicts
```

### 5.2 New Classes

**`PyReasonFieldHandle`**：field proxy，`set(value, *, bound, active_from, active_to, meta)` 通过 `_write_node_fact_internal` 暂存事实。

**`PyReasonEntityHandle`**：entity proxy，`__getattr__(name)` 返回 `PyReasonFieldHandle`。`_node_ref` 从 identity 值派生。

**`PyReasonBatchTx`**：batch 事务，`entity(cls, **identity)` 创建/复用 handle，`relationship(cls, *, from_entity, to_entity, **fields)` 暂存 edge facts。

### 5.3 Entity/Relationship Resolution

`tx.entity(User, user_id="Alice")`：
1. 从 `User.__sdk_entity_spec__` 获取 `entity_type` → `"User"`
2. `_owner_prefix("User")` → `"user"`
3. `node_ref = identity_values["user_id"]` → `"Alice"`（v1: 单 identity = node_ref）
4. 验证 `"user:name"` 等 pred_id 存在于 `session._pred_ids`

`tx.relationship(Friends, ..., strength="0.9", bound=[0.9, 0.9])`：
1. 从 `Friends.__sdk_relationship_spec__` 获取 `relationship_type` → `"Friends"`
2. `_owner_prefix("Friends")` → `"friends"`
3. 对每个 field kwarg 调用 `_write_edge_fact_internal("friends:strength", ...)`

### 5.4 Annotation Template Generation

每条 fact 写入时生成模板（`asrt_id=""` 占位，附 `fact_index` 关联源 fact）：

| namespace | category | key | kind | origin | derivation |
|-----------|----------|-----|------|--------|------------|
| `pyreason` | `semantic` | `bound_lower` | `float` | `observed` | None |
| `pyreason` | `semantic` | `bound_upper` | `float` | `observed` | None |
| `pyreason` | `semantic` | `active_from` | `int` | `observed` | None（仅 !=0 时） |
| `pyreason` | `semantic` | `active_to` | `int` | `observed` | None（仅非 None 时） |
| `shared` | `derived` | `confidence` | `float` | `derived` | `"pyreason:lower_bound"` |
| `shared` | `derived` | `confidence_source` | `str` | `derived` | `"pyreason:lower_bound"` |

`shared/source/*` 从 meta 中的 `source`/`analyst`/`method` 转发。

### 5.5 `_owner_prefix()` 来源

从 `authoring/schema_compile.py:480` 复制 12 行 CamelCase→snake_case 函数到 session.py，避免 adapter 到 authoring 的跨层 import。

## 6. Boundaries And Invariants

- PyReasonSession 仍是纯内存 buffer，不写 Ledger
- annotation 模板不含 `asrt_id`（Ledger 消费者后续填充）
- `_write_node_fact_internal`/`_write_edge_fact_internal` 保留完整验证逻辑
- `node_facts`/`edge_facts`/`all_facts_meta` 输出格式不变
- v1 只支持单 identity entity（多 identity 拼接为 node_ref）

## 7. Acceptance

- [x] batch API（`tx.entity().field.set()` + `tx.relationship()`）可用
- [x] 系统自动路由 node/edge，用户不需要区分
- [x] annotation 模板正确生成
- [x] canonical 实现已迁到内部方法；公开 `write_node_fact`/`write_edge_fact` 保留兼容包装层
- [x] 现有测试迁移通过
- [x] 新增 batch API + annotation 模板测试
- [x] integration demo 已更新

## 8. Implementation Plan

1. session.py: 添加 `_owner_prefix()` + 重命名 public methods + annotation 模板生成
2. session.py: 添加 `PyReasonFieldHandle` + `PyReasonEntityHandle` + `PyReasonBatchTx` + `batch()`
3. test_pyreason_session.py: 迁移现有测试 + 新增 batch API 测试
4. pyreason_integration_demo.py: 更新为 batch API

## 9. Docs To Update

- 本蓝图 audit log
- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `PyReasonSession` 新增 `batch()` entity-level API，支持 `tx.entity(...).field.set(...)` 与 `tx.relationship(...)`
  - session 在暂存 node/edge facts 的同时生成 `annotation_templates`
  - `examples/pyreason_integration_demo.py` 已切到 batch API
  - adapter docs 已同步到 batch API + annotation template 现状
- 与 blueprint 不同的地方：
  - `write_node_fact` / `write_edge_fact` 没有完全移除，保留为对内部方法的兼容包装层
  - integration demo 在当前环境下对 `pyreason` 导入失败做了优雅降级，而不是硬失败
- 为什么会有这些调整：
  - 兼容包装层避免打断现有 example / 外部调用点，同时保持 canonical 实现在内部方法
  - 本机 `pyreason==3.0.0` 仍可能触发 numba cache `RuntimeError`，demo 需要能在 session/batch/annotation 段成功展示
- 归档说明：
  - 代码、测试、示例、模块 docs 对齐后归档
