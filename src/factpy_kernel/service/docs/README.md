# FactPy Service 文档

本目录记录 `src/factpy_kernel/service` 的当前实现口径，面向需要通过 HTTP 对接 runtime 与 registry 的开发者。

## 当前文档

- `src/factpy_kernel/service/docs/01_overview.md`
  - service 模块职责、路由分组、关键行为约束、与 SDK/core/authoring 的关系。
- `src/factpy_kernel/service/docs/02_runtime_sessions.md`
  - runtime session 生命周期、writes、claims 的 DTO 契约。
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - runtime query、views、rule/derivation 执行、package export 的 DTO 契约。
- `src/factpy_kernel/service/docs/04_rules_registry.md`
  - rules facade 与 registry 只读接口的 DTO 契约。

## 使用约定

- 本目录文档以当前 `factpy_kernel.service.app_v1` 行为为准。
- 新增、删除或修改 route / DTO 时，应同步更新本目录文档与相关回归测试。
- service 层对前端提供稳定 envelope，但不等价于直接暴露 SDK Python 对象。
