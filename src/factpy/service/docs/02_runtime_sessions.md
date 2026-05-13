# Runtime Session DTO（service v1）

范围：

- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `GET /v1/runtime/sessions/{session_id}/schema`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/ephemeral-rules`
- `GET /v1/runtime/sessions/{session_id}/ephemeral-rules`
- `DELETE /v1/runtime/sessions/{session_id}/ephemeral-rules`
- `GET /v1/runtime/sessions/{session_id}/rules`
- `GET /v1/runtime/sessions/{session_id}/candidates`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`

本文记录 service v1 的 runtime session / session-scoped ephemeral rule / session inventory / write / claims DTO 契约。rule、derivation、views、query、package、registry 端点不在本文范围内。

## 通用约定

- 所有 `/v1/...` runtime session 端点默认都要求 `X-FactPy-API-Key`。
- 缺失或错误 key 返回 `HTTP 401`，且不会进入 JSON envelope。
- 认证启用但未配置 `FACTPY_KERNEL_API_KEYS` 时返回 `HTTP 503`，且不会进入 JSON envelope。
- 只有通过认证后，应用层成功/失败才继续使用 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- `session_id` 一律走 path parameter。
- `entity_ref`（如 `idref_v1:...`）直接按普通字符串透传，不额外包装。
- `rest_terms` 使用类型化二元组 JSON：`[[type_domain, value], ...]`。
- 新 session 不再初始化内建视图 `default`；runtime read policy 通过 `03_runtime_queries_policy.md` 中的内联 `policy` 字段传入。

成功 envelope 示例：

```json
{
  "ok": true,
  "errors": [],
  "meta": {}
}
```

失败 envelope 示例：

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "shape",
      "path": "$.ledger_path",
      "details": {
        "message": "must be non-empty string when provided"
      }
    }
  ],
  "meta": {}
}
```

## 1. `POST /v1/runtime/sessions/open`

请求（直接提供 `schema_ir`）：

```json
{
  "schema_ir": {
    "schema_ir_version": "v1",
    "entities": [],
    "predicates": [],
    "projection": {
      "entities": [],
      "predicates": []
    },
    "protocol_version": {
      "idref_v1": "idref_v1",
      "tup_v1": "tup_v1",
      "export_v1": "export_v1"
    },
    "generated_at": "2026-01-01T00:00:00Z"
  },
  "ledger_path": "/tmp/runtime/ledger.db",
  "artifact_store_root": "/tmp/runtime/artifacts"
}
```

请求（从 registry 打开）：

```json
{
  "registry_root": "/tmp/registry",
  "ledger_path": "/tmp/runtime/ledger.db",
  "artifact_store_root": "/tmp/runtime/artifacts"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "session": {
    "session_id": "rt_123",
    "ledger_path": "/tmp/runtime/ledger.db",
    "registry_root": null,
    "schema_digest": "sha256:abc",
    "opened_at_ns": 1730000000000000000,
    "counts": {
      "claims": 0,
      "claim_args": 0,
      "meta_rows": 0,
      "revokes": 0
    }
  }
}
```

说明：

- `schema_ir` 与 `registry_root` 二选一，不能同时提供。
- 两者也不能同时缺失。
- `ledger_path` 可省略；省略时使用进程内临时 ledger。
- `artifact_store_root` 可省略；省略时 explain artifact 仍保持 session/process-local 语义。
- 提供 `artifact_store_root` 时，service 会为该 session 构造 sidecar carrier；目录在第一次 artifact durable write 时按需创建。
- 当 `ledger_path` 指向已有 ledger 时，service 会校验其中保存的 `schema_digest` 是否与本次 schema 一致。
- 若同一 `ledger_path` 下 `schema_digest` 不一致，返回 `schema_mismatch`，不会打开 session。

错误 kinds：

- `shape`
- `schema_mismatch`
- `registry_schema_missing`
- `registry_schema_manifest_entry_invalid`
- `registry_schema_read_failed`
- `registry_schema_invalid`
- `runtime`

## 2. `GET /v1/runtime/sessions/{session_id}`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "session": {
    "session_id": "rt_123",
    "ledger_path": "/tmp/runtime/ledger.db",
    "registry_root": "/tmp/registry",
    "schema_digest": "sha256:abc",
    "opened_at_ns": 1730000000000000000,
    "counts": {
      "claims": 2,
      "claim_args": 2,
      "meta_rows": 8,
      "revokes": 0
    }
  }
}
```

说明：

- `schema_digest` 在 session 生命周期内保持稳定。
- `counts` 是当前 ledger 快照计数，不是累计历史统计。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 3. `DELETE /v1/runtime/sessions/{session_id}`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "closed": {
    "session_id": "rt_123"
  }
}
```

说明：

- 关闭 session 会从进程内 session manager 中移除该 session，并关闭对应 ledger 句柄。
- session-scoped `ephemeral_rules` 只存在于进程内 `RuntimeSession`；关闭 session 时也一并丢弃，不写入 ledger / sidecar / audit package。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 3A. `GET /v1/runtime/sessions/{session_id}/schema`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "schema_digest": "sha256:abc",
    "schema_ir": {
      "schema_ir_version": "v1",
      "entities": [],
      "predicates": []
    }
  }
}
```

说明：

- 该 endpoint 返回当前 session 绑定的完整 `schema_ir`，用于 readback / agentic schema discovery。
- `schema_digest` 与 `GET /sessions/{session_id}` 返回的 digest 相同；`schema_ir` 是其完整内容。
- 返回的是 session 打开时绑定的 schema 快照，不会单独做过滤、裁剪或 predicate 查询。
- `GET /sessions/{session_id}` 继续保持轻量 summary，不追加 `schema_ir`。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 4. `POST /v1/runtime/sessions/{session_id}/writes/set`

请求：

```json
{
  "pred_id": "person:country",
  "e_ref": "idref_v1:Person:source_id=u1",
  "rest_terms": [["string", "de"]],
  "meta": {
    "source": "seed",
    "source_loc": "row-1"
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "write": {
    "kind": "set",
    "assertion_id": "A1"
  }
}
```

说明：

- `pred_id / e_ref / rest_terms` 必填。
- `writes/set` 走单值字段写协议；相同 ingest-key 的重复写入会命中幂等键并返回既有 assertion。
- 系统保留 meta（如 `ingested_at / ingest_key`）由底层写协议自动补齐，不要求客户端提供。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 5. `POST /v1/runtime/sessions/{session_id}/writes/add`

请求：

```json
{
  "pred_id": "person:tag",
  "e_ref": "idref_v1:Person:source_id=u1",
  "rest_terms": [["string", "vip"]],
  "meta": {
    "source": "seed",
    "source_loc": "row-2"
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "write": {
    "kind": "add",
    "assertion_id": "A2"
  }
}
```

说明：

- `writes/add` 适用于多值事实追加。
- 其余字段约定与 `writes/set` 一致。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 6. `POST /v1/runtime/sessions/{session_id}/writes/retract`

请求：

```json
{
  "asrt_id": "A2",
  "meta": {
    "reason": "duplicate"
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "write": {
    "kind": "retract",
    "assertion_id": "R1"
  }
}
```

说明：

- `writes/retract` 只接受 `asrt_id`，按 assertion 撤销。
- 返回的 `assertion_id` 是 revoker assertion id，不是被撤销的原 assertion id。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 7. `GET /v1/runtime/sessions/{session_id}/claims`

Query 参数：

- `pred_id`：可选
- `e_ref`：可选
- `include_meta`：可选，默认 `false`
- `include_args`：可选，默认 `false`
- `limit`：可选，非负整数

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "claims": [
    {
      "asrt_id": "A1",
      "pred_id": "person:country",
      "e_ref": "idref_v1:Person:source_id=u1",
      "rest_terms": [["string", "de"]],
      "is_revoked": false,
      "revoker_asrt_id": null,
      "claim_args": [
        {
          "asrt_id": "A1",
          "idx": 0,
          "val_atom": "de",
          "tag": "string"
        }
      ],
      "meta_rows": [
        {
          "asrt_id": "A1",
          "key": "ingest_key",
          "kind": "str",
          "value": "sha256:abc"
        }
      ]
    }
  ]
}
```

说明：

- `rest_terms` 是类型化事实载荷，保留 tag：`[[type_domain, value], ...]`。
- `claim_args` 是把 `rest_terms` 拆成 position-aware row 的读模型，只有 `include_args=true` 时返回。
- `meta_rows` 只有 `include_meta=true` 时返回。
- `view-facts.view.facts` 返回投影后的扁平 tuple/list；`claims.rest_terms` 则保留原始类型标签，更适合调试写入协议和原始断言。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 8. `POST /v1/runtime/sessions/{session_id}/ephemeral-rules`

请求：

```json
{
  "rule": {
    "rule_id": "q_country_rows",
    "version": "1.0.0",
    "select": ["$e", "$c"],
    "where": [["pred", "person:country", ["$e", "$c"]]],
    "expose": true
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "rule_id": "q_country_rows",
    "version": "1.0.0",
    "status": "registered",
    "total_ephemeral": 1
  }
}
```

说明：

- `rule` 必须是结构化 authored rule object；DTO 规范化、`where` JSON→IR 转换与 `rules/run` 共用同一编译链。
- 返回 `result.status`：
  - 首次注册：`"registered"`
  - 同一 session 内相同 `(rule_id, version)` 再注册：`"replaced"`；新 rule body 会替换旧条目，`total_ephemeral` 不增长
- 注册成功后，rule 只挂在当前 `RuntimeSession.ephemeral_rules`，不会写入 filesystem registry、ledger、sidecar 或 audit package。
- session 内 duplicate 语义固定为 **upsert replace**；filesystem collision 语义固定为 **FS rule 优先**：
  - 评估时先加载 filesystem registry（若有）
  - 再 merge `ephemeral_rules`
  - 若 `(rule_id, version)` 冲突，ephemeral rule 被静默忽略，不覆盖 FS rule，也不返回 500
- 注册时会对 compiled `where` 中的 `pred` atoms 做 schema 存在性校验：
  - 若 `pred_id` 不在当前 session schema 中，注册直接失败
  - 错误返回 `kind="rule_ast_validate"`，并在 `details` 中补：
    - `error_code="unknown_predicate"`
    - `missing_pred_id`
    - `remediation_hint="verify_pred_id_via_GET_sessions_schema"`
- 当前只承诺 native rule evaluation 使用这组 rules；Souffle / ProbLog / PyReason 不消费 session-scoped ephemeral registry。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`
- `rule_ast_validate`

## 9. `GET /v1/runtime/sessions/{session_id}/ephemeral-rules`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "ephemeral_rules": [
      {
        "rule_id": "q_country_rows",
        "version": "1.0.0"
      }
    ],
    "total": 1
  }
}
```

说明：

- 只返回当前 session 内存中的 ephemeral rule inventory。
- 不回读 filesystem registry，也不返回完整 rule body。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 10. `DELETE /v1/runtime/sessions/{session_id}/ephemeral-rules`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "cleared": 1
  }
}
```

说明：

- 该操作只清空当前 session 的 `ephemeral_rules` 列表。
- 清空后，后续 `rules/run` / native `inferences/evaluate` 不再看到这些临时规则。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 10A. `GET /v1/runtime/sessions/{session_id}/rules`

Query 参数：

- `include_spec`：可选，默认 `false`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "rules": [
      {
        "rule_id": "q_country_rows",
        "version": "1.0.0",
        "source": "fs"
      },
      {
        "rule_id": "q_runtime_probe",
        "version": "1.0.0",
        "source": "ephemeral"
      }
    ],
    "total": 2,
    "fs_count": 1,
    "ephemeral_count": 1
  }
}
```

`include_spec=true` 时每条 rule 还会补：

```json
{
  "select_vars": ["$e", "$c"],
  "where": [["pred", "person:country", ["$e", "$c"]]],
  "expose": true
}
```

说明：

- 返回的是当前 session 的 effective rule inventory：
  - filesystem registry rules（若 `registry_root` 非空）
  - `RuntimeSession.ephemeral_rules`
- `source` 取值：
  - `"fs"`：来自 filesystem registry
  - `"ephemeral"`：来自当前 session 的临时规则
  - `"ephemeral_shadowed_by_fs"`：相同 `(rule_id, version)` 同时存在于 session ephemeral 与 filesystem registry；effective 行为仍以 FS rule 为准，因此列表中只出现一次，并显式标记 shadowed 状态
- `include_spec=false` 只返回 inventory summary，适合 agent/session readback。
- `include_spec=true` 额外返回规则 body；FS rule body 来自 `FileAuthoringRegistry.read_rule_spec(...)`，ephemeral body 来自当前 session 内存中的 `RuleSpec`。
- 该 endpoint 不改变 `GET /ephemeral-rules` 的响应结构；后者仍只返回最小 `{rule_id, version}` 列表。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 10B. `GET /v1/runtime/sessions/{session_id}/candidates`

Query 参数：

- `pred_id`：可选；提供时只返回 `pred_id` 精确匹配的 candidates

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "candidates": [
      {
        "candidate_id": "cand_v2:abc",
        "pred_id": "person:country",
        "support_kind": "native_binding_v1"
      }
    ],
    "total": 1
  }
}
```

说明：

- 返回的是当前 session store 中已登记的 candidate handles，适合长循环 / 中断恢复后的 candidate rediscovery。
- 每条只返回 v1 可稳定读取的 store-level metadata：
  - `candidate_id`
  - `pred_id`
  - `support_kind`
- `pred_id` 来自 store 在 candidate remember 路径上维护的 `_candidate_pred_index`。
- Legacy candidate `confidence` / `confidence_kind` carriers are internal
  compatibility fields and are not returned by the inventory DTO.
- v1 **不返回 accepted 状态**：
  - accepted / revoked 等状态目前属于 ledger 层信息
  - 该 endpoint 刻意保持 store-scoped inventory，不做跨层查询

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 相关文档

- `01_overview.md`
- `03_runtime_queries_policy.md`
- `04_rules_registry.md`
