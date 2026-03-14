# FactPy Service 文档

本目录记录 `src/factpy_kernel/service` 的当前实现口径，面向需要通过 HTTP 对接 runtime 与 registry 的开发者。

## 当前文档

- `src/factpy_kernel/service/docs/01_overview.md`
  - service 模块职责、当前路由、请求边界、与 SDK/core/authoring 的关系。

## 使用约定

- 本目录文档以当前 `app_v1` 行为为准。
- 新增或删除 route 时，应同步更新本目录文档与 `test_service_*` 回归测试。
- service 层对前端提供稳定 envelope，但不等价于直接暴露 SDK Python 对象。
