# Runtime Session DTO（service v1）

范围：

- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`

本文是 service v1 的 runtime session / write / claims DTO 契约说明。rule/derivation/query/registry 端点不在本文范围内。

## 通用约定

- 所有端点都返回 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- `session_id` 一律走 path parameter。
- `entity_ref`（如 `idref_v1:...`）直接按普通字符串透传，不额外包装。
- `rest_terms` 统一使用类型化二元组的 JSON 形态：`[[type_domain, value], ...]`。

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
    "entities": [
      {
        "entity_type": "Person",
        "identity_fields": [
          {"name": "source_id", "type_domain": "string"}
        ]
      }
    ],
    "predicates": [
      {
        "pred_id": "person:country",
        "arg_specs": [
          {"name": "person", "type_domain": "entity_ref"},
          {"name": "country", "type_domain": "string"}
        ],
        "group_key_indexes": [0],
        "cardinality": "functional"
      }
    ],
    "projection": {
      "entities": [],
      "predicates": ["person:country"]
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

- `schema_digest` 在 session 生命周期内应保持稳定。
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

- 关闭 session 会从 service 进程内 session manager 中移除该 session，并关闭对应 ledger 句柄。

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
- `rest_terms` 走类型化格式 `[[type_domain, value], ...]`。
- 当前 service v1 中，`writes/set` 走 ingest-key 写协议，重复写入相同事实会命中幂等键并返回既有 assertion。
- 系统保留 meta（如 `ingested_at / ingest_key`）由底层写协议自动补齐，不要求客户端提供。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 5. `POST /v1/runtime/sessions/{session_id}/writes/add`

请求：

```json
{
  "pred_id": "person:name",
  "e_ref": "idref_v1:Person:source_id=u1",
  "rest_terms": [["string", "Alice"]],
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

- 当前实现里，`writes/add` 与 `writes/set` 复用同一底层写协议，因此也具有 ingest-key 幂等行为。
- 也就是说，`add` 与 `set` 在 service v1 的差异主要是客户端语义意图，而不是重复写入时的冲突处理。
- 当前实现通过 ingest-key 去重，相同内容的重复调用不会产生额外断言。若未来需要“无条件追加”语义，需要协议层变更。
- 如果未来写协议收敛出更强的 `set/add` 语义分离，应以实现和回归测试更新本文。

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
    "source": "seed",
    "note": "cleanup"
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

- `retract` 的目标是已有 assertion，因此请求参数是 `asrt_id`，不是 `pred_id + e_ref + rest_terms`。
- 若目标 assertion 已经被撤销，底层写协议会幂等返回既有 revoker assertion。

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
- `claims.rest_terms` 与 `view-facts.view.facts` 的用途不同：
  - `claims.rest_terms` 保留类型标签，适合调试写入协议和原始断言。
  - `view-facts.view.facts` 返回投影后的扁平 tuple/list，适合前端直接消费视图结果。

错误 kinds：

- `shape`
- `runtime_session_not_found`

## 相关文档

- [`runtime-queries.md`](./runtime-queries.md)
- [`rules-registry.md`](./rules-registry.md)
