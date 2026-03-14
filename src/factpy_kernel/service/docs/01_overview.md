# Service 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/service`
- 最后更新：2026-03-01
- 目标读者：需要通过 HTTP 对接 runtime / registry 的前后端开发者

## 1. 模块职责

`service` 是 **前端/BFF 层**。它把 runtime、rule authoring 校验和 registry 只读能力整理成前端可消费的 HTTP 接口。

它负责：

- FastAPI `app_v1`
- runtime session 管理
- facts 写入 / 查询
- rule validate / compile-preview
- runtime rule 执行
- derivation evaluate / accept
- explain/conflicts/view-facts 查询
- package 导出
- registry manifest / schema / assets / rule / derivation 读取

它不负责：

- 直接实现 core 语义
- 保存 authoring 资产
- 替代 `SDKStore` / `SDKRegistry` 的 Python SDK 体验

## 2. 当前模块结构

- `app_v1.py`
  - FastAPI 路由入口
- `rules_v1.py`
  - rule validate / compile-preview / profile 列表
- `runtime_v1.py`
  - runtime session、facts 写入/查询、rule/derivation 执行、package 导出
- `registry_v1.py`
  - registry 只读接口
- `_common.py`
  - `ok/error` envelope 与错误转换
- `_registry_io.py`
  - 从 registry root 读取 schema 等底层辅助

## 3. 当前路由（v1）

### 3.1 rules

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`

### 3.2 runtime

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
- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/packages/export`

### 3.3 registry

- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/derivations/read`

## 4. 典型运行链路

### 4.1 runtime session

1. 前端调用 `/v1/runtime/sessions/open`
2. service 打开或创建 `Ledger(path=ledger_path)`，并绑定 schema digest
3. 返回 `session_id`
4. 后续前端通过 `session_id` 调写入、查询、运行 rule/derivation、导出 package

### 4.2 derivation evaluate/accept（v2）

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

### 4.3 registry 读取

1. 前端提供 `root_dir`
2. service 使用 `FileAuthoringRegistry(root_dir)` 读取 schema / rule / derivation
3. 返回结构化 envelope

## 5. 与其他层的关系

- `core`
  - service 最终调用 `Store`、`Ledger`、`write_protocol`、`run_rule`
- `authoring`
  - service 通过 `compile_authoring_rule_v1(...)` 和 `FileAuthoringRegistry(...)` 复用 authoring 能力
- `sdk`
  - service 不是 `SDKStore` / `SDKRegistry` 的 HTTP 镜像，而是前端友好的 service facade

## 6. 当前限制

- 当前仅暴露单条 derivation `accept`，尚未暴露 `accept_many` HTTP 接口
- 错误 envelope 当前统一走 `{ok, errors, meta}`，但尚未完全收敛成单独的 service DTO 文档
