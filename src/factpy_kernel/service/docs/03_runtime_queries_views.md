# Runtime Query, View And Derivation DTO（service v1）

范围：

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-support`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`
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
  "override_registry_root": "/tmp/registry",
  "capture_trace": true
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
    ],
    "trace": {
      "rule_run_id": "rt_trace_123"
    }
  }
}
```

说明：

- `rule` 必须是结构化对象；传 string 或其他非 object 值时返回 `shape` error。
- `override_registry_root` 可选；未提供时默认复用 session 绑定的 `registry_root`。
- 为兼容旧客户端，`registry_root` 仍可作为 `override_registry_root` 的别名；两者不能同时提供。
- `capture_trace` 可选，默认 `false`；当为 `true` 时 service 会调用 traced sibling helper，并在 `result.trace.rule_run_id` 返回 trace handle。
- 若 session 没有配置 `artifact_store_root`，该 handle 仍是 session-scoped。
- 若 session 配置了共享的 `artifact_store_root`，后续 session 可继续用该 handle 做 explain readback。
- `capture_trace=false` 时响应保持旧 shape，不返回 `trace`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。
- 其他 rule 编译或执行失败会落入统一 `runtime` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 2. `POST /v1/runtime/sessions/{session_id}/queries/explain-support`

请求：

```json
{
  "support_digest": "sha256:6f3e4f9c2d1b8a7e6c5d4b3a291817161514131211100f0e0d0c0b0a09080706"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "support_digest": "sha256:6f3e4f9c2d1b8a7e6c5d4b3a291817161514131211100f0e0d0c0b0a09080706"
  },
  "explain": {
    "kind": "native_binding_v1",
    "root_result_kind": "fact",
    "binding": [
      ["$E", "idref_v1:Person:source_id=u1"],
      ["$C", "de"]
    ],
    "pred_witnesses": [
      {
        "pred_atom_key": "b0.a0:person:country",
        "asrt_ids": ["A1"]
      }
    ],
    "non_fact_steps": []
  }
}
```

说明：

- 该 endpoint 内部直接调用 `Store.explain_support(...)`。
- 默认情况下它仍是 session-scoped readback。
- 若打开 session 时配置了 `artifact_store_root`，则可从共享 sidecar root 回读旧 `support_digest`。
- 若当前 session 中不存在对应 artifact，返回 `runtime_explain_not_found`。
- 未配置 `artifact_store_root` 时，这不是 durable lookup；session 清理后 handle 可能失效。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 3. `POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`

请求：

```json
{
  "rule_run_id": "rt_trace_123"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "rule_run_id": "rt_trace_123"
  },
  "explain": {
    "rule_run_id": "rt_trace_123",
    "root_rule": {
      "rule_id": "q_country_rows",
      "version": "1.0.0"
    },
    "select_vars": ["$e", "$c"],
    "invocations": [
      {
        "invocation_id": "rt_trace_123:i1",
        "parent_invocation_id": null,
        "rule": {
          "rule_id": "q_country_rows",
          "version": "1.0.0"
        },
        "memo_hit": false,
        "memo_source_invocation_id": null,
        "original_where": [["pred", "person:country", ["$e", "$c"]]],
        "rewritten_where": [["pred", "person:country", ["$e", "$c"]]],
        "bindings": [[["$c", "de"], ["$e", "idref_v1:Person:source_id=u1"]]],
        "output_rows": [["idref_v1:Person:source_id=u1", "de"]],
        "pred_witnesses": [
          {
            "binding_index": 0,
            "pred_atom_key": "b0.a0:person:country",
            "asrt_ids": ["A1"]
          }
        ],
        "non_fact_steps": []
      }
    ],
    "root_rows": [["idref_v1:Person:source_id=u1", "de"]]
  }
}
```

说明：

- 该 endpoint 内部直接调用 `Store.explain_rule_trace(...)`。
- 默认情况下它仍是 session-scoped readback。
- 若打开 session 时配置了 `artifact_store_root`，则可从共享 sidecar root 回读旧 `rule_run_id`。
- `rule_run_id` 目前只会在 `/rules/run` 传 `capture_trace=true` 时返回。
- 若当前 session 中不存在对应 artifact，返回 `runtime_explain_not_found`。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 4. `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`

请求：

```json
{
  "derivation": {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "target": "person:country_copy",
    "head_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]],
    "mode": "native"
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
    "mode": "native",
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
        "support_digest": "sha256:6f3e4f9c2d1b8a7e6c5d4b3a291817161514131211100f0e0d0c0b0a09080706",
        "support_kind": "native_binding_v1",
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
- native derivation evaluate 当前会填充 `support_kind="native_binding_v1"`；其他兼容路径仍可能返回 `support_kind="none"`。
- `limit` 只影响返回条数，不改变底层总候选数；总量体现在 `meta.candidate_count`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `string_dsl_unsupported`
- `authoring_derivation_compile`
- `derivation_evaluate`

## 5. `POST /v1/runtime/sessions/{session_id}/derivations/accept`

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
    "support_digest": "sha256:6f3e4f9c2d1b8a7e6c5d4b3a291817161514131211100f0e0d0c0b0a09080706",
    "support_kind": "native_binding_v1",
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

## 6. `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`

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

## 7. `POST /v1/runtime/sessions/{session_id}/queries/conflicts`

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

## 8. `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`

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

## 9. `POST /v1/runtime/sessions/{session_id}/queries/view-facts`

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

## 10. `POST /v1/runtime/sessions/{session_id}/views/create`

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

## 11. `POST /v1/runtime/sessions/{session_id}/views/update`

请求与成功响应结构同 `views/create`，但要求 `name` 已存在。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_update`

## 12. `POST /v1/runtime/sessions/{session_id}/views/delete`

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

## 13. `POST /v1/runtime/sessions/{session_id}/views/get`

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

## 14. `GET /v1/runtime/sessions/{session_id}/views`

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

## 15. `POST /v1/runtime/sessions/{session_id}/packages/export`

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
- 当 `package_kind="audit"` 时，当前 package 还会额外包含：
  - `audit/support_artifacts.jsonl`
  - `audit/rule_trace_artifacts.jsonl`
  这两个文件分别导出 `SupportArtifact` 与 `RuleTraceArtifact` 的 flat JSONL rows，用于离线 audit / explain 消费。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 相关文档

- `01_overview.md`
- `02_runtime_sessions.md`
- `04_rules_registry.md`
