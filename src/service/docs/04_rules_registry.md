# Rules And Registry DTO（service v1）

范围：

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`
- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/inferences/read`

本文记录 service v1 的 rules facade 与 registry 只读接口 DTO 契约。runtime session / writes / query / views / packages 不在本文范围内。

## 通用约定

- 所有 `/v1/...` rules / registry 端点默认都要求 `X-FactPy-API-Key`。
- 缺失或错误 key 返回 `HTTP 401`，且不会进入 JSON envelope。
- 认证启用但未配置 `FACTPY_KERNEL_API_KEYS` 时返回 `HTTP 503`，且不会进入 JSON envelope。
- 只有通过认证后，应用层成功/失败才继续使用 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- rules 端点不依赖 runtime session。
- registry 端点也不依赖 runtime session；它们直接访问 `root_dir` 指向的 registry 文件系统。
- registry 端点是只读 contract，不应触发任何 registry 写操作。

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
      "kind": "string_dsl_unsupported",
      "path": "$.rule",
      "details": {
        "message": "string rule DSL is not supported in service v1; send structured rule object",
        "strategy": "object_rule_only",
        "input_kind": "string"
      }
    }
  ],
  "meta": {
    "profile_effective": "default",
    "mode": "souffle"
  }
}
```

## 1. `POST /v1/rules/validate`

请求：

```json
{
  "api_version": "v1",
  "mode": "souffle",
  "strict": false,
  "rule": {
    "rule_id": "rules.country_rows",
    "version": "v1",
    "select_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]],
    "description": "Country row helper",
    "tags": ["demo", "query"],
    "condition_weights": {"b0.a0": 0.75},
    "expose": true
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "profile_effective": "default",
    "mode": "souffle"
  }
}
```

说明：

- `validate` 只做 request 规范化、AST 校验和 profile 约束校验，不返回编译产物。
- `description`、`tags`、`condition_weights` 可随请求一起出现，但 `validate` 只校验 rule 逻辑 IR / profile 约束；这些字段不进入 core rule AST。
- `condition_weights` 是 certainty/explain projection input，keyed
  by `b{branch}.a{atom}`；它不是 engine adapter 参数，未来运行时配置归
  `SemanticsProfile.certainty_projection`。Track 3 / B 已提供 core
  `SemanticsProfile` validation / inspection scaffolding，但 rules
  registry 仍保留现有 `condition_weights` payload，不消费 profile。
- string rule DSL 不被接受，客户端必须传结构化 rule object。
- string `where` DSL 同样不被接受，客户端必须传结构化 where IR。
- `strict=true` 且未显式提供 `profile` 时，`profile_effective` 会收敛为 `souffle_strict`。
- 显式 `profile={"name":"default"}` 可覆盖 `strict=true` 的默认 profile 选择。

错误 kinds：

- `shape`
- `profile_unknown`
- `string_dsl_unsupported`
- `rule_ast_validate`
- `runtime`

## 2. `POST /v1/rules/compile-preview`

请求：

```json
{
  "api_version": "v1",
  "mode": "souffle",
  "rule": {
    "rule_id": "rules.country_rows",
    "version": "v1",
    "select_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]],
    "description": "Country row helper",
    "tags": ["demo", "query"],
    "condition_weights": {"b0.a0": 0.75},
    "expose": true
  }
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "profile_effective": "default",
    "mode": "souffle"
  },
  "preview": {
    "compiled_payload": {
      "rule_id": "rules.country_rows",
      "version": "v1",
      "select_vars": ["$E", "$C"],
      "where": [["pred", "person:country", ["$E", "$C"]]],
      "description": "Country row helper",
      "tags": ["demo", "query"],
      "condition_weights": {"b0.a0": 0.75},
      "expose": true
    }
  }
}
```

说明：

- `compile-preview` 在通过 validate 阶段后，继续返回 authoring compile 产物。
- `compile-preview` 会保留 rule asset metadata：`description`、`tags`、`condition_weights`。
- `condition_weights` 的语义仍是 certainty/explain projection input；
  它只随 rule asset 持久化，供 certainty summary 链路读取。
- 因为 `compile-preview` 复用 validate 的 request 规范化逻辑，所以 string DSL 的拒绝策略完全一致。

错误 kinds：

- `shape`
- `profile_unknown`
- `string_dsl_unsupported`
- `rule_ast_validate`
- `authoring_rule_compile`
- `runtime`

## 3. `GET /v1/profiles`

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "profiles": [
    {
      "name": "default",
      "description": "No additional restrictions; matches current behavior.",
      "capabilities": {}
    },
    {
      "name": "souffle_strict",
      "description": "Soufflé strict validation: requires resolved ruleref and forbids not-body OR.",
      "capabilities": {
        "ruleref_policy": "require_resolved",
        "not_body_policy": "forbid_or"
      }
    }
  ]
}
```

说明：

- 当前 service v1 只暴露 `default` 和 `souffle_strict` 两个 profile。
- 该端点不返回 `meta` 字段；结构与 rules validate/preview 略有不同，客户端应按端点 contract 处理。

## 4. `POST /v1/registry/manifest`

请求：

```json
{
  "root_dir": "/tmp/registry"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "manifest": {
    "authoring_registry_fs_version": "authoring_registry_fs_v1",
    "schema": {
      "path": "schema/schema_ir.json",
      "schema_digest": "sha256:abc",
      "bytes_digest": "sha256:def"
    },
    "rules": [
      {
        "rule_id": "q_country_rows",
        "version": "1.0.0",
        "path": "rules/q_country_rows/1.0.0.json",
        "digest": "sha256:aaa"
      }
    ],
    "inferences": [
      {
        "inference_id": "drv.country_copy",
        "version": "1.0.0",
        "path": "inferences/drv.country_copy/1.0.0.json",
        "digest": "sha256:bbb",
        "target_pred_id": "person:country"
      }
    ]
  }
}
```

说明：

- 该端点直接返回 registry manifest 文件内容。
- 如果 manifest 文件不存在，底层 registry 会返回默认空 manifest，而不是报错。

错误 kinds：

- `shape`
- `runtime`

## 5. `POST /v1/registry/schema/read`

请求：

```json
{
  "root_dir": "/tmp/registry"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
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
  }
}
```

说明：

- `schema/read` 不经过 runtime session；它只根据 `root_dir` 读取 registry manifest 中登记的 schema 文件。
- 这也是 runtime session `open` 在传 `registry_root` 时复用的 schema 加载路径。

错误 kinds：

- `shape`
- `registry_schema_missing`
- `registry_schema_manifest_entry_invalid`
- `registry_schema_read_failed`
- `registry_schema_invalid`

## 6. `POST /v1/registry/assets/list`

请求：

```json
{
  "root_dir": "/tmp/registry"
}
```

成功响应（Q8 Phase 2 schema-only 形态）：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "registry": {
    "schema_entry": {"schema_id": "demo", "version": "1.0.0", "digest": "..."},
    "apply_run_ids": ["apply-1"]
  }
}
```

说明：

- `assets/list` 现在只返回 schema entry 与 apply-log run id 列表。
- `rule_ids` / `inference_ids` 字段在 Q8 Phase 2（Slice 6）随 SavedRule
  持久化层一同移除，并未保留为永久空列表的兼容字段。
- `apply_run_ids` 来自 `authoring_apply_execute_run` 事件日志的
  latest-by-request 视图。

错误 kinds：

- `shape`
- `runtime`

## 7. `POST /v1/registry/rules/read`（Q8 Phase 2 已移除）

Q8 Phase 2（Slice 6）移除了 SavedRule 持久化层。该路由依旧存在，但永远返回
removed envelope：

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "removed",
      "path": "$",
      "details": {
        "message": "registry-backed SavedRule/SavedInference persistence was removed by Q8 Phase 2; use in-memory Rule(...) / Inference(...) instead of registry-backed reads"
      }
    }
  ],
  "meta": {}
}
```

迁移方法：客户端构造 in-memory `Rule(...)` 并在 runtime session 内通过
`/v1/runtime/sessions/{session_id}/ephemeral-rules` 注册 ephemeral rule，
然后调用 `/rules/run`。

## 8. `POST /v1/registry/inferences/read`（Q8 Phase 2 已移除）

Q8 Phase 2（Slice 6）移除了 SavedInference 持久化层。该路由依旧存在，但永远
返回 removed envelope：

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "removed",
      "path": "$",
      "details": {
        "message": "registry-backed SavedRule/SavedInference persistence was removed by Q8 Phase 2; use in-memory Rule(...) / Inference(...) instead of registry-backed reads"
      }
    }
  ],
  "meta": {}
}
```

迁移方法：客户端构造 in-memory `Inference(...)` 并直接调用
`/v1/runtime/sessions/{session_id}/inferences/evaluate`（请求 body 中携带
`inference` payload）。registry 文件布局在 Q8 Phase 2 之后是 schema-only。
旧工作区的 `registry/rules/` / `registry/inferences/` / `registry/derivations/`
目录会被忽略，不再被读取。

## 相关文档

- `01_overview.md`
- `02_runtime_sessions.md`
- `03_runtime_queries_policy.md`
