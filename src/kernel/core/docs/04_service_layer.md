# Service 层现状核验（kernel）

- 范围：`src/service`
- 核验日期：2026-03-10
- 结论：仓库内已具备可直接对接前端的 `FastAPI` 服务层，覆盖 rules、runtime session、view 管理、derivation、registry 读取与 package export。

## 1. 入口与依赖

- 服务入口：`service.app_v1`
- ASGI app：`service.app_v1:app`
- 可选依赖：`pip install -e '.[service]'`

建议启动：

```bash
python -m uvicorn service.app_v1:app --reload
```

## 2. 分层定位

service 负责：

- HTTP 路由与 JSON DTO
- runtime session 生命周期与编排
- 统一错误 envelope（`ok/errors/meta`）
- registry 文件读取 facade

service 不负责：

- core 语义定义（policy/chosen/where/evaluate/accept）
- authoring 写入工作流
- SDK 对象 API

## 3. 当前 v1 路由

### 3.1 rules

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`

### 3.2 runtime session + writes

- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`

### 3.3 runtime queries

- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`

### 3.4 runtime views

- `POST /v1/runtime/sessions/{session_id}/views/create`
- `POST /v1/runtime/sessions/{session_id}/views/update`
- `POST /v1/runtime/sessions/{session_id}/views/delete`
- `POST /v1/runtime/sessions/{session_id}/views/get`
- `GET /v1/runtime/sessions/{session_id}/views`

### 3.5 runtime rule/derivation/package

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/packages/export`

### 3.6 registry

- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/derivations/read`

## 4. 关键行为契约（当前实现）

### 4.1 `view-facts`

- `include_audit=true` 时，`view.audit` 返回 `ProjectorAudit`（来自 core projector）
- `temporal_view` 已移除；传入会返回 shape error
- `view_name` 与 `view` 二选一；都不传则用 session 默认视图

### 4.2 derivation 与 rule runtime

- 运行链路也不接受 `temporal_view`（显式 shape error）
- `derivations/evaluate` 返回 candidate，供 `derivations/accept` 回传
- `derivations/accept` 返回 `AcceptResult` 的序列化结果（含 `diagnostics_contract_version`）
- `rules/compile-preview` 与 registry 读接口会保留已编译资产中的 `description / tags` 等声明元数据；service 不解释这些字段的运行语义

### 4.3 全局异常包络

未捕获异常由 `app_v1` 全局 handler 统一包装（HTTP 200）：

- `ok=false`
- `errors[0].kind="runtime"`
- `errors[0].path="$"`
- `errors[0].details.message=str(exc)`

## 5. 说明

- service v1 已不是 rules-only 薄层，而是 runtime/BFF 第一批可用接口。
- service 与 core 契约应同步维护：core contract 见 `04_public_contract_v1.md`。
