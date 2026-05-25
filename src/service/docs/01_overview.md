# Service 模块总览（kernel）

- 范围：`src/service`
- 最后更新：2026-05-12
- 目标读者：需要通过 HTTP 对接 runtime / rules 的前后端开发者

前端 / 机读 API 参考：[`06_frontend_integration.md`](./06_frontend_integration.md)（集成指南）+ [`../../../docs/api/openapi.yaml`](../../../docs/api/openapi.yaml)（OpenAPI 3.0 机读契约，37 个 operation 全覆盖；漂移守卫：`scripts/export_openapi.py`，需 `PYTHONPATH=src` 执行）。

## 1. 模块职责

`service` 是 **前端/BFF 层**。它把 runtime 与 rule authoring 校验整理成前端可消费的 HTTP 接口。

它负责：

- FastAPI `app_v1`
- `/v1/...` API key 认证层（`X-FactPy-API-Key`）
- runtime session 管理
- facts 写入 / 查询
- rule validate / compile-preview
- runtime rule 执行
- inference evaluate / accept
- explain/conflicts/view-facts 查询
- package 导出

它不负责：

- 直接实现 core 语义
- 保存 authoring 资产
- 替代 `SDKStore` 的 Python SDK 体验

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
- runtime session、facts 写入/查询、rule/inference 执行、package 导出
- `_common.py`
  - `ok/error` envelope 与错误转换
- `_certainty_service.py`
  - certainty derivation helper（condition_weights lookup / summary 计算 / batch 预计算）
  - 依赖 core（Store, _certainty_materializer）
  - 不反向依赖 runtime_v1
  - `condition_weights` 在该链路中是 certainty/explain projection input，
    不是 engine adapter 参数；未来运行时配置归
    `SemanticsProfile.certainty_projection`

## 3. 详细 DTO 文档

- `02_runtime_sessions.md`
  - runtime session 生命周期、writes、claims。
- `03_runtime_queries_policy.md`
  - runtime query、rule/inference 执行、package export。
- `04_rules_registry.md`
  - rules facade 与已删除 registry routes 的迁移说明。
- `06_frontend_integration.md`
  - 前端/BFF 集成指南;envelope 解包模板、典型调用链路、HTTP 状态码速查表。
- 文档抽取 HTTP surface 已迁至 agent service；本模块不再维护对应 route。

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

### 4.4 runtime rule/inference/package

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/inferences/evaluate`
- `POST /v1/runtime/sessions/{session_id}/inferences/accept`
- `POST /v1/runtime/sessions/{session_id}/packages/export`

### 4.5 registry

`/v1/registry/*` routes 已在 A20(E) / Q6-A 中从 `app_v1.py` 删除。
Q8 Phase 2 先移除了 SavedRule/SavedInference 持久化;A20(E) registry
final-exit 进一步移除了 schema/manifest/assets 的 service registry
read surface。

注:文档抽取 HTTP surface 已不在本 service 内,迁至 `agent.service.app`。

## 5. 典型运行链路

### 5.1 runtime session

1. 前端调用 `/v1/runtime/sessions/open`
2. service 打开或创建 `Ledger(path=ledger_path)`，并绑定 schema digest
3. 返回 `session_id`
4. 后续前端通过 `session_id` 调写入、查询、运行 rule/inference、导出 package

### 5.2 inference evaluate（T5）

- `inferences/evaluate` 返回 `EvaluateResult` 表示：result/run id、digest anchors、head Rule 摘要、以及 `rows[]`。
- 每个 row 暴露 `row_id`、`bindings`、`claim`、`raw_kind` / `bound` 和 `evidence_ref`。
- `CandidateSet` 是 runtime 内部 artifact，不再作为 service evaluate 响应或 accept round-trip payload 暴露。
- `inferences/accept` CandidateSet echo workflow 已移除；旧客户端会得到 `kind="removed"` error envelope。

最小请求示例（evaluate）：

```json
{
  "inference": {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "target": "person:country_copy",
    "head_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]]
  }
}
```

注：请求与 route 使用 public `inference` vocabulary；candidate payload
仍保留 `derivation_id` / `derivation_version` substrate 字段，供
accept/proof/audit 链路 round-trip。

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
- 为兼容旧客户端，accept 仍可解析 echoed legacy `confidence` /
  `confidence_kind` 字段；这些字段只 hydrate 内部 carrier，不会默认写入
  assertion meta、service DTO 或 evidence tree。

### 5.3 runtime policy / view-facts

- runtime service 不保存命名 policy registry，也不初始化 `default` 视图。
- `view-facts` 只返回 active projection facts，并可选返回 projector audit。
- `policy`、`view_name` 与 `view` 字段会返回 shape error。
- `temporal_view` 已从 runtime view / rule / derivation 链路移除；传入会返回 shape error。

### 5.4 registry 读取

registry 读取 routes 已删除。前端应通过 runtime session、in-memory
ephemeral rules / inferences、以及 workspace APIs 工作。

## 6. 与其他层的关系

- `core`
  - service 最终调用 `Store`、`Ledger`、`write_protocol`、`run_rule`
- `authoring`
  - service 通过 `compile_authoring_rule_v1(...)` 和
    `compile_authoring_derivation_v1(...)` 复用 authoring 编译能力
- `sdk`
  - service 不是 `SDKStore` 的 HTTP 镜像，而是前端友好的 service facade

## 7. 当前限制

- Candidate accept HTTP workflow 已移除；持久化事实应通过写入接口表达。
- 错误 envelope 当前统一走 `{ok, errors, meta}`；未捕获异常由 `app_v1` 全局 exception handler 统一包装
- `HttpRuntimeAPI` 这类 HTTP 调用方若访问启用认证的 kernel，需要自行提供 API key header；`LocalRuntimeAPI` 不经过 HTTP 认证层
