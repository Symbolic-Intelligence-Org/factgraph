---
doc_type: reference
status: authoritative
source_of_truth: contract
implementation_state: implemented
owner: service/runtime
last_verified: 2026-03-14
---

# Runtime Queries DTO（service v1）

范围：

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`

本文是 service v1 的 runtime/query DTO 契约说明。session open/get/close、writes、claims 和 rules/registry 端点不在本文范围内。

## 通用约定

- 所有端点都返回 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- `session_id` 一律走 path parameter。
- tuple 在 JSON 中统一序列化为 list。
- `entity_ref`（如 `idref_v1:...`）直接按普通字符串透传，不额外包装。
- `view-facts.temporal_view` 的外部契约使用 `record | active`。
- 为兼容旧调用方，`view-facts` 仍接受 `current` 作为旧别名；响应 `meta.temporal_view` 会统一归一为 `active`。

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
      "path": "$.pred_id",
      "details": {
        "message": "must be non-empty string"
      }
    }
  ],
  "meta": {}
}
```

## 1. `POST /v1/runtime/sessions/{session_id}/rules/run`

请求：

```json
{
  "rule": {
    "rule_id": "q_country_rows",
    "version": "1.0.0",
    "select": ["e", "c"],
    "where": [["pred", "person:country", ["$e", "$c"]]],
    "expose": true
  },
  "temporal_view": "record",
  "override_registry_root": "/tmp/registry"
}
```

说明：

- `override_registry_root` 可选；未提供时默认复用 session 绑定的 `registry_root`。
- 为兼容旧客户端，`registry_root` 仍可作为 `override_registry_root` 的别名；新客户端应使用 `override_registry_root`。

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "rule_id": "q_country_rows",
    "version": "1.0.0",
    "rows": [
      ["idref_v1:Person:source_id=u1", "de"]
    ]
  }
}
```

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `where_ast_validate`
- `runtime`

## 2. `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`

请求：

```json
{
  "derivation": {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "target": "person:country_copy",
    "head_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]],
    "mode": "python",
    "temporal_view": "record"
  },
  "limit": 50
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "mode": "python",
    "temporal_view": "record",
    "candidate_count": 1,
    "returned_count": 1,
    "truncated": false
  },
  "evaluation": {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "target_pred_id": "person:country_copy",
    "candidates": [
      {
        "candidate_id": "cand_v2:...",
        "candidate_key": "candk_v2:...",
        "candidate_kind": "fact",
        "derivation_id": "drv.country_copy",
        "derivation_version": "1.0.0",
        "run_id": "run_123",
        "target": "person:country_copy",
        "key_tuple_digest": "sha256:abc",
        "tup_digest": "sha256:def",
        "payload": {
          "pred_id": "person:country_copy",
          "terms": [
            {"kind": "entity_ref", "value": "idref_v1:Person:source_id=u1"},
            {"kind": "literal", "tag": "string", "value": "de"}
          ]
        },
        "support_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "support_kind": "none",
        "generated_at": 1730000000000000000,
        "state": "generated"
      }
    ]
  }
}
```

说明：

- `evaluate` 返回完整 candidate 对象，供后续 `accept` 原样 round-trip。
- `meta` 不重复放 `derivation_id/version`；这些字段只保留在 `evaluation` 内。
- `limit` 只影响返回条数，不改变底层总候选数；总量体现在 `meta.candidate_count`。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `string_dsl_unsupported`
- `authoring_derivation_compile`
- `derivation_evaluate`

## 3. `POST /v1/runtime/sessions/{session_id}/derivations/accept`

请求：

```json
{
  "candidate": {
    "derivation_id": "drv.country_copy",
    "derivation_version": "1.0.0",
    "run_id": "run_123",
    "target": "person:country_copy",
    "key_tuple_digest": "sha256:abc",
    "tup_digest": "sha256:def",
    "payload": {
      "e_ref": "idref_v1:Person:source_id=u1",
      "rest_terms": [["string", "de"]]
    },
    "support_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "support_kind": "none",
    "generated_at": 1730000000000000000,
    "state": "generated"
  },
  "options": {
    "approved_by": "alice",
    "note": "ok",
    "dry_run": false
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "dry_run": false,
    "terminal": false
  },
  "accept": {
    "materialize_id": "mat_v1:country_copy",
    "run_id": "run_123",
    "accepted_count": 1,
    "skipped_count": 0,
    "written_assertions": [
      {
        "asrt_id": "A1",
        "pred_id": "person:country_copy",
        "key_tuple_digest": "sha256:abc"
      }
    ],
    "skipped_reason_counts": {},
    "diagnostics_contract_version": 1,
    "diagnostics": []
  }
}
```

说明：

- 客户端应原样回传 `evaluate` 返回的 candidate 对象，不要裁剪字段。
- fact candidate 必须保留完整 `terms`。
- entity candidate 必须保留 identity 相关字段（`entity_type` / `identity_fields` / `resolved_identity` / `missing_identity_fields`）。
- `meta.terminal=true` 表示已进入终止态；当前至少覆盖 `skipped_reason_counts.aborted > 0`，客户端不应自动重试。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `derivation_accept`

## 4. `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`

请求：

```json
{
  "pred_id": "person:country",
  "e_ref": "idref_v1:Person:source_id=u1",
  "val_atoms": ["de"]
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "pred_id": "person:country",
    "e_ref": "idref_v1:Person:source_id=u1"
  },
  "explain": {
    "pred_id": "person:country",
    "e_ref": "idref_v1:Person:source_id=u1",
    "active_claims": [
      {
        "asrt_id": "A1",
        "args": ["idref_v1:Person:source_id=u1", "de"],
        "meta": {
          "source": "seed"
        }
      }
    ],
    "chosen_asrt_id": "A1"
  }
}
```

说明：

- `val_atoms` 可选；提供时按值过滤 `args[1:]`。
- `val_atoms` 走 body，不走 query string。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `query_explain_fact`

## 5. `POST /v1/runtime/sessions/{session_id}/queries/conflicts`

请求：

```json
{
  "pred_id": "person:country",
  "e_ref": "idref_v1:Person:source_id=u1"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "pred_id": "person:country",
    "e_ref": "idref_v1:Person:source_id=u1"
  },
  "conflicts": {
    "pred_id": "person:country",
    "e_ref": "idref_v1:Person:source_id=u1",
    "active_asrt_ids": ["A1", "A2"],
    "chosen_asrt_id": "A2"
  }
}
```

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `query_conflicts`

## 6. `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`

请求：

```json
{
  "pred_id": "er:canon_of"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "pred_id": "er:canon_of"
  },
  "mapping": {
    "pred_id": "er:canon_of",
    "chosen_map": [
      {
        "key_tuple": ["idref_v1:Person:source_id=m1"],
        "value_tuple": ["idref_v1:Person:source_id=c1"]
      }
    ],
    "candidates": [
      {
        "asrt_id": "A1",
        "key_tuple": ["idref_v1:Person:source_id=m1"],
        "value_tuple": ["idref_v1:Person:source_id=c1"],
        "source": "seed",
        "confidence": null,
        "ingested_at": 1730000000000000000
      }
    ],
    "decisions": [
      {
        "key_tuple": ["idref_v1:Person:source_id=m1"],
        "chosen_asrt_id": "A1",
        "chosen_value_tuple": ["idref_v1:Person:source_id=c1"],
        "reason": "single_value",
        "candidate_asrt_ids": ["A1"]
      }
    ],
    "conflicts": []
  }
}
```

冲突响应：

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "mapping_conflict",
      "path": "$.pred_id",
      "details": {
        "message": "mapping conflict for er:canon_of: 1 key(s)",
        "conflicts": [
          {
            "key_tuple": ["idref_v1:Person:source_id=m2"],
            "candidate_values": [
              ["idref_v1:Person:source_id=ca"],
              ["idref_v1:Person:source_id=cb"]
            ],
            "candidate_asrt_ids": ["A1", "A2"]
          }
        ]
      }
    }
  ],
  "meta": {
    "pred_id": "er:canon_of"
  }
}
```

说明：

- service 只接受 `pred_id`，不要求客户端传 `schema_pred`。
- `pred_id` 不存在于 session schema 或者不是 `is_mapping=true` 的谓词时，返回 `shape`。
- `chosen_map` 不直接返回 tuple-key dict，而是序列化为 `[{key_tuple, value_tuple}]`。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `mapping_conflict`
- `query_resolve_mapping`

## 7. `POST /v1/runtime/sessions/{session_id}/queries/view-facts`

请求：

```json
{
  "temporal_view": "record",
  "legacy_record_visibility": "allow",
  "include_audit": true
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "temporal_view": "record",
    "legacy_record_visibility": "allow",
    "pred_count": 3,
    "total_tuple_count": 2
  },
  "view": {
    "facts": {
      "person:country": [["idref_v1:Person:source_id=u1", "de"]],
      "person:country_copy": [],
      "person:name": [["idref_v1:Person:source_id=u1", "Alice"]]
    },
    "audit": {
      "contract_version": 1,
      "legacy_record_total": 0,
      "legacy_record_by_pred": {},
      "legacy_exists_without_roles_total": 0,
      "legacy_exists_without_roles_by_pred": {},
      "marker_conflict_total": 0,
      "marker_conflict_by_reason": {},
      "committed_hidden_count_mismatch_total": 0,
      "committed_hidden_count_mismatch_by_pred": {}
    }
  }
}
```

说明：

- `temporal_view` 默认 `record`；外部契约推荐使用 `record | active`。
- `legacy_record_visibility` 默认 `allow`，可选值：`allow | audit | deny`。
- `include_audit` 默认 `false`；为 `false` 时响应中省略 `view.audit`。
- `meta.pred_count` 是 `facts` 中 predicate 数量；`meta.total_tuple_count` 是所有 predicate rows 总和。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `query_view_facts`

## 暂未提供的端点

当前没有独立的 `audit summary` service 端点。

原因：

- core 层尚无稳定的单一 `audit_summary(...)` 入口。
- summary 的聚合边界尚未收敛：按 session、按 package、按 registry，还是按 materialize/run 聚合，仍需要单独设计。
- 在聚合口径未稳定前，先把底层 DTO 契约写清楚更稳，避免上层 summary 端点反向绑死底层 shape。

后续如果补 `audit summary`，建议先单独定义：

- 聚合范围
- 输出字段
- 是否复用现有 `view-facts` / `resolve-mapping` / `accept` 结果
- 失败与部分成功语义

## 相关文档

- [`runtime-session.md`](./runtime-session.md)
