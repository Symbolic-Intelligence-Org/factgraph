# Service 模块总览（kernel）

- 范围：`src/service`
- 最后更新：2026-05-06
- 目标读者：需要通过 HTTP 对接 runtime / registry 的前后端开发者

前端 / 机读 API 参考：[`06_frontend_integration.md`](./06_frontend_integration.md)（集成指南）+ [`../../../../docs/api/openapi.yaml`](../../../../docs/api/openapi.yaml)（OpenAPI 3.0 机读契约，48 个 operation 全覆盖；漂移守卫：`scripts/export_openapi.py`）。

## 1. 模块职责

`service` 是 **前端/BFF 层**。它把 runtime、rule authoring 校验和 registry 只读能力整理成前端可消费的 HTTP 接口。

它负责：

- FastAPI `app_v1`
- `/v1/...` API key 认证层（`X-FactPy-API-Key`）
- runtime session 管理
- facts 写入 / 查询
- rule validate / compile-preview
- runtime rule 执行
- derivation evaluate / accept
- explain/conflicts/view-facts 查询
- runtime views 管理
- package 导出
- registry manifest / schema / assets / rule / derivation 读取

它不负责：

- 直接实现 core 语义
- 保存 authoring 资产
- 替代 `SDKStore` / `SDKRegistry` 的 Python SDK 体验

### 1.1 v0.1 公开 surface 边界(per Batch 8 closure decision @ `6b32972`)

Round Story Completion routemap(Batch 3-7)新增的 application + audit-layer capabilities 在 v0.1 **不**通过本 service HTTP 路由暴露:

- Check / Diagnose / Fact Overlay / Why-not(`kernel.application` advanced importable)
- ProofFrame Rechecker(`kernel.application.proofframe_runtime`)
- Rule Disable / Literal Replace / Add Condition(`kernel.application.rule_*_runtime`)
- Round events 持久化 + 查询(`kernel.audit.round_events`)
- ProofFrame diff(`kernel.audit.proof_frame_diff`)

这些 capabilities 按 Batch 8 公开 surface 决议(见 [`docs/blueprints/archive/2026-05-06_public-surface.md`](../../../docs/blueprints/archive/2026-05-06_public-surface.md))保留为 **advanced importable surface**,通过 Python in-process 调用 `kernel.application` / `kernel.audit` 使用;v0.1 **不**新增对应 HTTP route 或 SDK shell。

如需通过 HTTP 暴露,reactivation 触发条件:explicit user-facing workflow demand + delivery / auth / session 单独 blueprint 设计。

## 2. 当前模块结构

- `app_v1.py`
  - FastAPI 路由入口
- `rules_v1.py`
  - rule validate / compile-preview / profile 列表
- `runtime_v1.py`
  - runtime session、facts 写入/查询、views、rule/derivation 执行、package 导出
- `registry_v1.py`
  - registry 只读接口
- `_common.py`
  - `ok/error` envelope 与错误转换
- `_certainty_service.py`
  - certainty derivation helper（condition_weights lookup / summary 计算 / batch 预计算）
  - 依赖 core（Store, _certainty_materializer）+ authoring（FileAuthoringRegistry）
  - 不反向依赖 runtime_v1
- `_registry_io.py`
  - 从 registry root 读取 schema 等底层辅助

## 3. 详细 DTO 文档

- `02_runtime_sessions.md`
  - runtime session 生命周期、writes、claims。
- `03_runtime_queries_views.md`
  - runtime query、views、rule/derivation 执行、package export。
- `04_rules_registry.md`
  - rules facade 与 registry 只读接口。
- `06_frontend_integration.md`
  - 前端/BFF 集成指南;envelope 解包模板、典型调用链路、HTTP 状态码速查表。
- extraction HTTP surface 已迁至 agent.service:见 [`src/agent/service/docs/05_extraction.md`](../../../agent/service/docs/05_extraction.md)。

## 4. 当前路由（v1）

### 4.0 认证边界

- 所有 `/v1/...` 路由默认都要求 `X-FactPy-API-Key`。
- 若 `FACTPY_KERNEL_AUTH_DISABLED=true`，本地开发可显式跳过认证。
- 认证失败会在 route handler 之前返回：
  - `HTTP 401`：缺失或错误 key
  - `HTTP 503`：认证启用但未配置 `FACTPY_KERNEL_API_KEYS`
- 只有通过认证后，service 才继续沿用各 DTO 文档里的 `HTTP 200` envelope 合同。

### 4.1 rules

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`

### 4.2 runtime session + writes

- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`

### 4.3 runtime queries

- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`

### 4.4 runtime views

- `POST /v1/runtime/sessions/{session_id}/views/create`
- `POST /v1/runtime/sessions/{session_id}/views/update`
- `POST /v1/runtime/sessions/{session_id}/views/delete`
- `POST /v1/runtime/sessions/{session_id}/views/get`
- `GET /v1/runtime/sessions/{session_id}/views`

### 4.5 runtime rule/derivation/package

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/packages/export`

### 4.6 registry

- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/derivations/read`

注:`POST /v1/extraction/documents` 已不在本 service 内,迁至 `agent.service.app`,见 [`src/agent/service/docs/05_extraction.md`](../../../agent/service/docs/05_extraction.md)。

## 5. 典型运行链路

### 5.1 runtime session

1. 前端调用 `/v1/runtime/sessions/open`
2. service 打开或创建 `Ledger(path=ledger_path)`，并绑定 schema digest
3. 返回 `session_id`
4. 后续前端通过 `session_id` 调写入、查询、运行 rule/derivation、导出 package

### 5.2 derivation evaluate/accept（v2）

- `derivations/evaluate` 返回 `CandidateSet` v2 结构（含 `candidate_id/candidate_key/candidate_kind`）。
- fact candidate 主 payload 形态为 `terms`；entity candidate 主 payload 形态为 identity 解析字段。
- `derivations/accept` 要求客户端回传完整 candidate payload；不要裁剪 `terms`/identity 字段。

最小请求示例（evaluate）：

```json
{
  "derivation": {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "target": "person:country_copy",
    "head_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]]
  }
}
```

最小请求示例（accept）：

```json
{
  "candidate": {
    "candidate_id": "cand_v2:...",
    "candidate_key": "candk_v2:...",
    "candidate_kind": "fact",
    "derivation_id": "drv.country_copy",
    "derivation_version": "1.0.0",
    "run_id": "run_...",
    "target": "person:country_copy",
    "key_tuple_digest": "sha256:...",
    "support_digest": "sha256:...",
    "support_kind": "none",
    "generated_at": 0,
    "state": "generated",
    "confidence": null,
    "confidence_kind": "none",
    "payload": {
      "pred_id": "person:country_copy",
      "terms": [
        {"kind": "entity_ref", "value": "idref_v1:Person:..."},
        {"kind": "literal", "tag": "string", "value": "de"}
      ]
    }
  }
}
```

常见错误：
- `$.candidate.payload`：payload 不是 v2 形态（例如客户端裁剪了 `terms`）。
- `$.candidate.candidate_kind`：缺少或非法（必须是 `fact` / `entity`）。

### 5.3 runtime views / view-facts

- 每个 session 会内建 `default` 视图。
- `view-facts` 支持 `view_name` 或内联 `view`，并可选返回 projector audit。
- `temporal_view` 已从 runtime view / rule / derivation 链路移除；传入会返回 shape error。

### 5.4 registry 读取

1. 前端提供 `root_dir`
2. service 使用 `FileAuthoringRegistry(root_dir)` 读取 schema / rule / derivation
3. 返回结构化 envelope

## 6. 与其他层的关系

- `core`
  - service 最终调用 `Store`、`Ledger`、`write_protocol`、`run_rule`
- `authoring`
  - service 通过 `compile_authoring_rule_v1(...)`、`compile_authoring_derivation_v1(...)` 和 `FileAuthoringRegistry(...)` 复用 authoring 能力
- `sdk`
  - service 不是 `SDKStore` / `SDKRegistry` 的 HTTP 镜像，而是前端友好的 service facade

## 7. 当前限制

- 当前仅暴露单条 derivation `accept`，尚未暴露 `accept_many` HTTP 接口
- 错误 envelope 当前统一走 `{ok, errors, meta}`；未捕获异常由 `app_v1` 全局 exception handler 统一包装
- `HttpRuntimeAPI` 这类 HTTP 调用方若访问启用认证的 kernel，需要自行提供 API key header；`LocalRuntimeAPI` 不经过 HTTP 认证层
