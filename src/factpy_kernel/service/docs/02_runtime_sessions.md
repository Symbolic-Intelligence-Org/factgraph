# Runtime Session DTO（service v1）

范围：

- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`

本文记录 service v1 的 runtime session / write / claims DTO 契约。rule、derivation、views、query、package、registry 端点不在本文范围内。

## 通用约定

- 所有端点都返回 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- `session_id` 一律走 path parameter。
- `entity_ref`（如 `idref_v1:...`）直接按普通字符串透传，不额外包装。
- `rest_terms` 使用类型化二元组 JSON：`[[type_domain, value], ...]`。
- 新 session 会自动初始化内建视图 `default`；视图管理端点见 `03_runtime_queries_views.md`。

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
  "ledger_path": "/tmp/runtime/ledger.db"
}
```

请求（从 registry 打开）：

```json
{
  "registry_root": "/tmp/registry",
  "ledger_path": "/tmp/runtime/ledger.db"
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

## 相关文档

- `01_overview.md`
- `03_runtime_queries_views.md`
- `04_rules_registry.md`
