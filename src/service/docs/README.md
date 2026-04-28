# FactPy Service 文档

本目录记录 `src/service` 的当前实现口径,面向需要通过 HTTP 对接 kernel runtime 与 registry 的开发者。

注:extraction HTTP surface(`POST /v1/extraction/documents`)在 namespace split 后已迁至 `agent.service`,文档见 [`src/agent/service/docs/`](../../agent/service/docs/)。

当前 `app_v1` 的 `/v1/...` 路由都经过 API key 认证层保护:

- 请求头:`X-FactPy-API-Key`
- 若 `FACTPY_KERNEL_AUTH_DISABLED=true`,本地开发可显式跳过认证
- 缺失或错误 key 返回 `HTTP 401`
- 认证启用但未配置 `FACTPY_KERNEL_API_KEYS` 时返回 `HTTP 503`
- 只有通过认证后,service 才继续返回既有的 `HTTP 200` JSON envelope

## 当前文档

- `src/service/docs/01_overview.md`
  - service 模块职责、路由分组、关键行为约束、与 SDK/core/authoring 的关系。
- `src/service/docs/02_runtime_sessions.md`
  - runtime session 生命周期、writes、claims 的 DTO 契约。
- `src/service/docs/03_runtime_queries_views.md`
  - runtime query、views、rule/derivation 执行、package export 的 DTO 契约。
- `src/service/docs/04_rules_registry.md`
  - rules facade 与 registry 只读接口的 DTO 契约。
- `src/service/docs/05_audit_static_site_contract.md`
  - audit static site renderer 的交付 contract；`site_manifest.json` / `ui_index.json` 与 rendered page layout 的稳定边界。
- `src/service/docs/06_frontend_integration.md`
  - 前端/BFF 集成指南;envelope 解包模板、典型调用链路、HTTP 状态码速查表。

extraction HTTP 文档已随 owner 迁出:见 [`src/agent/service/docs/05_extraction.md`](../../agent/service/docs/05_extraction.md)。

## 使用约定

- 本目录文档以当前 `service.app_v1` 行为为准。
- 新增、删除或修改 route / DTO / rendered static site contract 时,应同步更新本目录文档与相关回归测试。
- service 层对前端提供稳定 envelope,但不等价于直接暴露 SDK Python 对象。
