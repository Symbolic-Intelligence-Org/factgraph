# Application 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/application`
- 最后更新：2026-03-10
- 目标读者：需要理解 entity-centric runtime 中层、SDK 委托边界与后续 service 集成入口的开发者

## 1. 模块职责

`application` 是 **core 之上的中性运行层**。

它负责把原本散落在 SDK facade 中的 entity-centric runtime 机制抽取成一组可共享能力，让：

- `sdk` 继续提供 Python authoring / facade 体验
- `service` 直接依赖中性 read/write/query/projection 能力

它当前负责：

- protocol DTO
- schema runtime 索引与 selector/ref 解析
- entity hydration / read request
- entity write planning / apply
- SDK facade 的读写委托承接点

它当前不负责：

- 替代 `SDKStore` / `SDKBatchTx` 的 Python facade 外观
- HTTP / session / registry 路由
- graph projection / relationship family / binding 的完整实现
- query lowering/runtime hydration 的中层统一

## 2. 当前模块结构

- `protocol/`
  - application 层 canonical DTO
- `schema_runtime.py`
  - `SchemaIndex`、field type、selector/ref 解析
- `entity_view.py`
  - entity hydration、`execute_read_request(...)`
- `entity_write.py`
  - write planning、`apply_write_plan(...)`
- `__init__.py`
  - 当前对外导出的中层入口

## 3. 当前已落地能力

### 3.1 protocol

当前已定义：

- common DTO
- schema runtime DTO
- entity read DTO
- entity write DTO

边界：

- 使用 `dataclass(frozen=True)`
- 协议层只接受 JSON-safe 值与结构化 `EntityRef` / `EntitySelector`
- 不把 SDK descriptor / metaclass 语义带入中层

### 3.2 schema runtime

当前已落地：

- `build_schema_index(...)`
- `resolve_selector(...)`
- `materialize_identity(...)`
- `field_predicate(...)`
- `field_value_type(...)`
- `encode_entity_ref(...)`
- `entity_type_from_ref(...)`

它为 read/write path 提供统一的 schema 运行时索引，而不再依赖 `SDKStore` 内部索引。

### 3.3 entity view

当前已落地：

- `hydrate_entity(...)`
- `hydrate_entities(...)`
- `execute_read_request(...)`

实现方式：

- 基于 `Store + Ledger + project_view_facts(...)`
- 从 identity predicates 恢复 canonical identity
- 输出 `EntitySnapshotDTO`、字段当前值与 assertions/history

### 3.4 entity write

当前已落地：

- `plan_write_command(...)`
- `apply_write_plan(...)`

当前能力包括：

- target selector 解析
- dependency entity ref 解析
- `set/add/retract` planning
- `record_exists` / identity materialization
- 单目标 application-level apply

## 4. 与其他层的关系

- `core`
  - `application` 直接依赖 `Store`、`Ledger`、`projector`、write protocol 等底层原语
- `sdk`
  - SDK facade 已开始委托 `application`
  - SDK 负责外观兼容与 Python ergonomics
- `service`
  - 未来应直接依赖 `application`，而不是依赖 `SDKStore`
- `frontend`
  - 不直接依赖 `application`
  - 应通过 `service` DTO 获取能力

## 5. 当前 SDK 委托状态

### 5.1 读侧

SDK 当前已把以下读能力委托到 `application`：

- `sdk_get(...)`
- `sdk_find(...)`
- `_build_snapshot(...)`

兼容策略：

- SDK outward shape 保持不变
- `entity_ref` 字段仍表现为 encoded ref 字符串
- `FieldAssertions` / `AssertionRecord` 仍保持 SDK facade 类型
- 过滤语义仍保守保留在 SDK 适配层

### 5.2 写侧

SDK 当前已把以下批写主路径委托到 `application`：

- `SDKBatchTx.preview()`
- `BatchPlan.apply()`

当前策略是保守委托：

- 当整批 staged writes 都可表达为 application protocol 时，走 application planner/apply
- 否则整批回退到 legacy batch 路径

## 6. 当前保守边界

以下边界仍然保留，属于当前实现刻意不跨越的部分：

- SDK batch 只有在整批 staged writes 都能被 application 协议表达时才委托 application
- 如果批中存在 raw `entity_ref` token、`bytes`、非 JSON-safe meta，或 application planner 无法稳定表示的值，整批回退到 legacy
- `BatchPlan.ops` / `export()` / `to_json()` / `WireBatchPlan.apply()` 保持 legacy 语义
- `entity_write.py` 当前以单目标 `EntityWriteCommand` 为 canonical planner，不直接表达 multi-root atomic batch
- temporal read/write 还没有在 application 层统一收口

## 7. 当前未完成部分

以下能力仍未在 `application` 层落地：

- `query_view.py`
- `authoring_normalize.py`
- `graph_projection.py`
- `binding.py`

这意味着当前“核心迁移目标”已验证完成，但 Blueprint 的后续阶段仍未实施完成。

## 8. 当前测试入口

核心回归可用以下命令：

```bash
PYTHONPATH=src python -m unittest \
  factpy_kernel.tests.test_application_protocol \
  factpy_kernel.tests.test_application_schema_runtime \
  factpy_kernel.tests.test_application_entity_view \
  factpy_kernel.tests.test_application_entity_write \
  factpy_kernel.tests.test_sdk_facade_application_delegate \
  factpy_kernel.tests.test_sdk_batch_application_delegate \
  factpy_kernel.tests.test_phase3_contracts_v1
```

这些测试覆盖：

- application protocol / schema runtime / read / write
- SDK read delegation
- SDK batch write delegation
- 迁移后的 facade compatibility

## 9. 相关文档

- [application_projection_blueprint.md](/Users/zhenzhili/symbolic_agent/docs/architecture/blueprints/application/application_projection_blueprint.md)
  - 架构蓝图、迁移阶段、后续规划
- [application_protocol_spec.md](/Users/zhenzhili/symbolic_agent/docs/reference/application/application_protocol_spec.md)
  - application protocol DTO 规范
- [frontend_entity_ui_design.md](/Users/zhenzhili/symbolic_agent/docs/architecture/blueprints/frontend/frontend_entity_ui_design.md)
  - 实体/规则 UI、graph projection 目标表达
