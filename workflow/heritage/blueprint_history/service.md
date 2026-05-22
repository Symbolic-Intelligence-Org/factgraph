> 状态：已实现（service v1）  
> 类型：服务蓝图  
> 说明：本文档保留为历史 service v1 蓝图；相关能力已进入当前主线，但当前对外契约与实现细节仍以模块 docs 为准。

# FactPy Kernel Service (v1)

最小 HTTP 服务层（FastAPI），用于把 `factpy_kernel.service.rules_v1` 和 runtime/registry service facade 暴露给前端/产品团队使用。

当前 `service v1` 的定位不是 rules-only thin proxy，而是前端/BFF 第一批接口；session 编排、DTO 规范化和统一 envelope 返回由 service 自身负责，`core` 继续只承载领域语义。

## 安装

Core-only（不含服务依赖）：

```bash
pip install -e .
```

Service（含 FastAPI/uvicorn/httpx）：

```bash
pip install -e ".[service]"
```

## 启动

```bash
uvicorn factpy_kernel.service.app_v1:app --host 0.0.0.0 --port 8000
```

## 边界

`service v1` 的角色是 HTTP/BFF 层，不是领域语义层。

它负责：

- 对外 HTTP/JSON API 与路由暴露
- request DTO 校验、JSON 归一化、协议兼容别名处理
- runtime session 生命周期编排
- 统一 envelope：`HTTP 200` + `ok/errors/meta`
- runtime query / derivation / package export 的远程访问壳
- registry 只读访问

它不负责：

- core 规则/accept/store/view/mapping 的领域语义本身
- authoring / registry 写入 workflow
- SDK 对象式本地 API
- audit summary 之类尚未收敛的更高层聚合查询

## 依赖与存储

依赖分层（按当前实现）：

- route 层：`app_v1` 只依赖 service facade，不直接依赖 `core` / `authoring`
- rules facade：依赖 `authoring.rules` 与 `core.rules.*`
- runtime facade：依赖 `authoring.*`、`core.*`，并在 package export 场景直接依赖 `adapters.souffle.package`
- registry facade：依赖 `authoring.FileAuthoringRegistry` 与 registry 文件系统读取

存储整合：

- runtime session 底层使用 `core.store.ledger.Ledger`
- 未提供 `ledger_path` 时使用内存 ledger
- 提供 `ledger_path` 时使用 file-backed SQLite ledger，并在打开时绑定 `schema_digest`
- registry 读取走文件系统目录（`root_dir`），不是数据库
- 当前 service 不直接接入外部业务数据库、ORM 或连接池

## API 分组

建议从四组理解 service API：

- rules facade：`/v1/rules/*` + `/v1/profiles`
- runtime session：`/v1/runtime/sessions/open`、`/{session_id}`、`/writes/*`、`/claims`
- runtime queries：`/rules/run`、`/derivations/*`、`/queries/*`、`/views/*`、`/packages/export`
- registry read-only：`/v1/registry/*`

## API（v1）

详细 DTO 文档：

- `runtime-session`：[`service/docs/02_runtime_sessions.md`](../../src/factpy_kernel/service/docs/02_runtime_sessions.md)
- `runtime-queries`：[`service/docs/03_runtime_queries_views.md`](../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- `rules-registry`：[`service/docs/04_rules_registry.md`](../../src/factpy_kernel/service/docs/04_rules_registry.md)

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`
- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`
- `POST /v1/runtime/sessions/{session_id}/views/create`
- `POST /v1/runtime/sessions/{session_id}/views/update`
- `POST /v1/runtime/sessions/{session_id}/views/delete`
- `POST /v1/runtime/sessions/{session_id}/views/get`
- `GET /v1/runtime/sessions/{session_id}/views`
- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/packages/export`
- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/derivations/read`

说明：

- 当前 service 已是前端可用的第一批 BFF 接口，不再是 rules-only 薄层
- `POST /v1/runtime/sessions/open` 会把 `schema_digest` 和可选 `registry_root` 绑定到 session
- `POST /v1/runtime/sessions/{session_id}/rules/run` 默认复用 session 绑定的 `registry_root`
- 如需按请求覆盖 registry，请显式传 `override_registry_root`
- 为兼容旧客户端，`rules/run` 仍接受旧字段 `registry_root` 作为别名；新客户端应使用 `override_registry_root`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact` 和 `POST /v1/runtime/sessions/{session_id}/queries/conflicts` 统一使用 `POST` body；`explain-fact` 的 `val_atoms` 走 body，不走 query string
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping` 只接受 `pred_id`；service 从 session 绑定 schema 中解析 mapping predicate，不要求客户端传 `schema_pred`
- `resolve-mapping` 的 `chosen_map` 会序列化为 `[{key_tuple, value_tuple}]`，避免把 tuple-key dict 直接暴露成 JSON
- 当 `resolve-mapping` 遇到多值冲突时，service 返回 `ok=false` 和 `errors[].kind="mapping_conflict"`；`errors[].details.conflicts` 保留冲突细节
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts` 统一返回 `view.facts: dict[pred_id, rows[]]`；tuple 会序列化为 JSON list，`entity_ref` 仍按普通字符串透传
- `view-facts` 支持 `include_audit=true|false`；默认 `false`，开启后在 `view.audit` 中直接返回 `ProjectorAudit` 字段
- `view-facts.temporal_view` 的外部契约使用 `record | active`；service 会把 `active` 归一到 core 的 `current` 视图语义
- `view-facts.meta` 额外返回 `pred_count` 和 `total_tuple_count`，便于客户端快速判断结果规模
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate` 返回完整 candidate 对象，供后续 `accept` 原样 round-trip
- `POST /v1/runtime/sessions/{session_id}/derivations/accept` 要求客户端原样回传 `evaluate` 返回的 candidate；不要裁剪 `payload` 字段，尤其是 fact candidate 的 `terms` 与 entity candidate 的 identity 字段
- 当 `accept.meta.terminal=true` 时，表示结果已进入终止态；当前 v1 至少包括 `skipped_reason_counts.aborted > 0` 的情况，客户端不应自动重试

## 响应约定

- v1 在应用层内统一返回 `HTTP 200` JSON envelope，包括 facade 校验错误和进入 FastAPI 之后的未捕获 service 异常
- 使用 JSON envelope 表达结果：
  - 成功：`ok=true`
  - 失败：`ok=false` + `errors[]`
- 这个约定只覆盖请求进入 service 进程之后的应用级错误；进程崩溃、代理超时、网络中断等传输/基础设施故障不在该契约内

## Strict/Profile

- 可在请求 DTO 中使用 `strict=true` 或显式 `profile`
- 当前 strict 预设：`PROFILE_SOUFFLE_STRICT`
- 具体 strict/profile 语义与示例请见 `docs/语法.md`（Strict/profile 校验段落）
