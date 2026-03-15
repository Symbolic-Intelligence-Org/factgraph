# Runtime Query, View And Derivation DTO（service v1）

范围：

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`
- `POST /v1/runtime/sessions/{session_id}/views/create`
- `POST /v1/runtime/sessions/{session_id}/views/update`
- `POST /v1/runtime/sessions/{session_id}/views/delete`
- `POST /v1/runtime/sessions/{session_id}/views/get`
- `GET /v1/runtime/sessions/{session_id}/views`
- `POST /v1/runtime/sessions/{session_id}/packages/export`

本文记录 service v1 的 runtime query、view 管理、rule/derivation 执行与 package export DTO 契约。session open/get/close、writes、claims 和 rules/registry 端点不在本文范围内。

## 通用约定

- 所有端点都返回 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- `session_id` 一律走 path parameter。
- tuple 在 JSON 中统一序列化为 list。
- `entity_ref`（如 `idref_v1:...`）直接按普通字符串透传，不额外包装。
- runtime query/rule/derivation 链路不再接受 `temporal_view`；传入时返回 `shape` error。
- `view-facts` 通过 `view_name` 或内联 `view` 指定视图，两者不能同时提供。

成功 envelope 示例：

```json
{
  "ok": true,
  "errors": [],
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
    "select": ["$e", "$c"],
    "where": [["pred", "person:country", ["$e", "$c"]]],
    "expose": true
  },
  "override_registry_root": "/tmp/registry"
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
    "rows": [
      ["idref_v1:Person:source_id=u1", "de"]
    ]
  }
}
```

说明：

- `rule` 必须是结构化对象；传 string 或其他非 object 值时返回 `shape` error。
- `override_registry_root` 可选；未提供时默认复用 session 绑定的 `registry_root`。
- 为兼容旧客户端，`registry_root` 仍可作为 `override_registry_root` 的别名；两者不能同时提供。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。
- 其他 rule 编译或执行失败会落入统一 `runtime` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
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
    "mode": "python"
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
        "state": "generated",
        "confidence": null
      }
    ]
  }
}
```

说明：

- `evaluate` 返回完整 candidate 对象，供后续 `accept` 原样 round-trip。
- `limit` 只影响返回条数，不改变底层总候选数；总量体现在 `meta.candidate_count`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。

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
    "state": "generated",
    "confidence": null
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
    "candidate_id": "cand_v2:...",
    "candidate_key": "candk_v2:...",
    "run_id": "run_123",
    "accepted_count": 1,
    "skipped_count": 0,
    "written_assertions": [
      {
        "asrt_id": "A1",
        "pred_id": "person:country_copy"
      }
    ],
    "skipped_reason_counts": {},
    "diagnostics_contract_version": 1,
    "diagnostics": [],
    "entity_ref": null
  }
}
```

说明：

- 客户端应原样回传 `evaluate` 返回的 candidate 对象，不要裁剪字段。
- fact candidate 必须保留完整 `payload.terms`。
- entity candidate 必须保留 identity 相关字段（如 `entity_type / identity_fields / resolved_identity / missing_identity_fields / proposed_entity_ref`）。
- `options.identity_override` 可选，用于 entity candidate 的 identity 覆盖。
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

请求（使用内联 view）：

```json
{
  "view": {
    "active": true,
    "confidence_strategy": "max",
    "prefer_source": null
  },
  "include_audit": true
}
```

请求（使用命名 view）：

```json
{
  "view_name": "default",
  "include_audit": false
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "pred_count": 3,
    "total_tuple_count": 2
  },
  "view": {
    "facts": {
      "person:country": [["idref_v1:Person:source_id=u1", "de"]],
      "person:name": [["idref_v1:Person:source_id=u1", "Alice"]]
    },
    "view_spec": {
      "active": true,
      "confidence_strategy": "max",
      "prefer_source": null
    },
    "audit": {
      "contract_version": 1
    }
  }
}
```

说明：

- `view_name` 与 `view` 二选一；都不传时使用 session 默认视图 `default`。
- `include_audit` 默认 `false`；为 `true` 时响应中返回 `view.audit`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。
- `meta.pred_count` 是投影结果中的 predicate 数量；`meta.total_tuple_count` 是所有 predicate rows 总和。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `query_view_facts`

## 8. `POST /v1/runtime/sessions/{session_id}/views/create`

请求：

```json
{
  "name": "prefer_seed",
  "view": {
    "active": true,
    "confidence_strategy": "prefer_source",
    "prefer_source": "seed"
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "view": {
    "name": "prefer_seed",
    "spec": {
      "active": true,
      "confidence_strategy": "prefer_source",
      "prefer_source": "seed"
    }
  }
}
```

说明：

- `view.active` 必须是 `bool`。
- `view.confidence_strategy` 目前只接受 `max | mean | median | prefer_source`。
- `view.prefer_source` 只能是非空字符串或 `null`。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_create`

## 9. `POST /v1/runtime/sessions/{session_id}/views/update`

请求与成功响应结构同 `views/create`，但要求 `name` 已存在。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_update`

## 10. `POST /v1/runtime/sessions/{session_id}/views/delete`

请求：

```json
{
  "name": "prefer_seed"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "deleted": {
    "name": "prefer_seed"
  }
}
```

说明：

- 内建视图 `default` 不能删除。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_delete`

## 11. `POST /v1/runtime/sessions/{session_id}/views/get`

请求：

```json
{
  "name": "default"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "view": {
    "name": "default",
    "spec": {
      "active": true,
      "confidence_strategy": "max",
      "prefer_source": null
    }
  }
}
```

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_get`

## 12. `GET /v1/runtime/sessions/{session_id}/views`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "views": {
    "default": {
      "active": true,
      "confidence_strategy": "max",
      "prefer_source": null
    },
    "prefer_seed": {
      "active": true,
      "confidence_strategy": "prefer_source",
      "prefer_source": "seed"
    }
  }
}
```

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_list`

## 13. `POST /v1/runtime/sessions/{session_id}/packages/export`

请求：

```json
{
  "out_dir": "/tmp/pkg",
  "package_kind": "audit",
  "query": {
    "predicates": ["person:country"]
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "package": {
    "out_dir": "/tmp/pkg",
    "package_kind": "audit",
    "manifest_path": "/tmp/pkg/manifest.json"
  }
}
```

说明：

- `package_kind` 只接受 `inference` 或 `audit`。
- `query` 为可选透传字段，由底层 exporter 解释。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 相关文档

- `01_overview.md`
- `02_runtime_sessions.md`
- `04_rules_registry.md`
