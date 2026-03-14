---
doc_type: reference
status: authoritative
source_of_truth: contract
implementation_state: implemented
owner: service/api
last_verified: 2026-03-14
---

# Service API DTO Index

`docs/api/` 用于承载 service v1 的对外 DTO 契约文档。

所有端点均返回 `HTTP 200` + `ok/errors` envelope。具体错误语义请见各文档的 `error kinds` 小节。

service 的边界、依赖分层与 API 总览见 [`../blueprint/service.md`](../blueprint/service.md)。

| 端点范围 | 文档 | 简述 |
| --- | --- | --- |
| `POST /v1/runtime/sessions/open` | [`runtime-session.md`](./runtime-session.md) | session 打开、读取、关闭 |
| `GET /v1/runtime/sessions/{session_id}` | [`runtime-session.md`](./runtime-session.md) | session 状态与计数 |
| `DELETE /v1/runtime/sessions/{session_id}` | [`runtime-session.md`](./runtime-session.md) | session 关闭 |
| `POST /v1/runtime/sessions/{session_id}/writes/*` | [`runtime-session.md`](./runtime-session.md) | facts 写入与撤销 |
| `GET /v1/runtime/sessions/{session_id}/claims` | [`runtime-session.md`](./runtime-session.md) | 原始 claims 查询 |
| `POST /v1/runtime/sessions/{session_id}/rules/run` | [`runtime-queries.md`](./runtime-queries.md) | runtime rule 执行 |
| `POST /v1/runtime/sessions/{session_id}/derivations/*` | [`runtime-queries.md`](./runtime-queries.md) | derivation evaluate / accept |
| `POST /v1/runtime/sessions/{session_id}/queries/*` | [`runtime-queries.md`](./runtime-queries.md) | explain / conflicts / mapping / view-facts |
| `POST /v1/rules/validate` | [`rules-registry.md`](./rules-registry.md) | rule 校验 |
| `POST /v1/rules/compile-preview` | [`rules-registry.md`](./rules-registry.md) | rule 编译预览 |
| `GET /v1/profiles` | [`rules-registry.md`](./rules-registry.md) | backend profiles 列表 |
| `POST /v1/registry/*` | [`rules-registry.md`](./rules-registry.md) | registry 只读访问 |
