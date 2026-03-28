# Task Blueprint: Examples SDK Schema Cleanup

- Status: scoped
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/authoring`
  - `src/factpy_kernel/domains/ecss`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/sdk/docs/README.md](../../../src/factpy_kernel/sdk/docs/README.md)
  - [src/factpy_kernel/domains/ecss/docs/README.md](../../../src/factpy_kernel/domains/ecss/docs/README.md)
- Audit Log:
  - [2026-03-28_examples-sdk-schema-cleanup.audit.md](./2026-03-28_examples-sdk-schema-cleanup.audit.md)

## 1. Problem

`examples/` 目录里混入了两类旧式示例写法：

- 直接篡改 `schema_ir["predicates"]` 注入 ECSS raw predicate dict，绕过 `Entity`/`Field` 声明模型。
- 针对 relationship predicate 手动补 `owner_type`，掩盖 `compile_schema_from_classes()` 与 runtime schema index 之间的不一致。

这些写法让示例偏离当前 SDK 语义，也让 notebook / script 出现“能演示但不是推荐路径”的错误示范。

## 2. Goals

- 清理 `examples/` 中的 schema-level hack，示例默认走当前 SDK 声明路径。
- 为 relationship predicate 提供最小兼容修复，消除示例中的 `owner_type` 手补逻辑。
- 给 `examples/` 增加一份面向维护者的索引和现状说明，明确每个示例的定位与状态。
- 同步受影响模块 docs，记录当前推荐口径和兼容边界。

## 3. Non-goals

- 不重写 ECSS domain preset helper 的对外 API。
- 不统一重跑所有 notebook 输出，也不追求把所有示例都改成同一种风格。
- 不扩展 PyReason / Souffle 能力边界，只做示例与当前实现的对齐。

## 4. Current Context

- 当前实现入口：`examples/esa_demo.py`、`examples/ecss_compliance_demo.ipynb`、`examples/multi_engine_evaluate_demo.py`
- 当前已知约束：
  - `SDKStore` 仍要求 `classes` 为 `Entity` 子类列表。
  - runtime schema index 要求 predicate 带 `owner_type`。
  - ECSS preset helper 仍保留于 domain 模块，兼容旧调用。
- 当前相关历史蓝图：
  - `docs/blueprints/archive/2026-03-23_esa-demo-packaging.md`
  - `docs/blueprints/archive/2026-03-27_multi-engine-execution-surface-impl.md`
  - `docs/blueprints/archive/2026-03-27_pyreason-execution-surface-closeout.md`

## 5. Proposed Shape

- 在 schema 编译层为 relationship field predicate 补齐 `owner_type`，让 `compile_schema_from_classes()` 产物直接可供 SDK/runtime 使用。
- 把 ECSS demo 中仅用于 schema 承载的 raw predicate 注入改成显式 `Entity` 声明，保留现有 rule / runtime / audit 行为不变。
- 清理 example 脚本和 notebook 中不再需要的 `schema_ir` 篡改逻辑。
- 新增 `examples/README.md`，逐个说明示例用途、当前状态、重构/保留原因。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 示例的用户可见主题和引擎分工不变。
  - ECSS demo 现有 pred_id、规则 ID、导出产物结构不变。
  - relationship predicate 的新增 `owner_type` 只能是兼容增强，不能破坏既有字段。
- 明确不做的内容：
  - 不删除 `extend_schema_ir_with_ecss_*` helper。
  - 不把 notebook 迁移成脚本或反向。
- 兼容性约束：
  - 既有测试中依赖 relationship metadata 的路径需要继续通过。
  - 示例在无 `pyreason` 或 PyReason 运行失败时仍应保留 graceful fallback。

## 7. Acceptance

- [ ] 代码行为满足任务目标
- [ ] 没有越过 blueprint 明示的边界
- [ ] 受影响模块 docs 已同步
- [ ] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. [schema compile/tests] 补齐 relationship predicate 的 `owner_type`，并更新相关测试以覆盖当前口径。
2. [examples/ECSS] 把 ESA/ECSS compliance demo 的 raw `schema_ir` 注入替换为显式 `Entity` 声明，保持规则和导出行为稳定。
3. [examples/PyReason + docs] 清理多引擎示例中的 schema patch，补 `examples/README.md` 与受影响模块 docs 说明。
4. [validation] 运行针对性测试和示例脚本，确认例子与文档对齐。

## 9. Docs To Update

- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/domains/ecss/docs/README.md`
- `examples/README.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
