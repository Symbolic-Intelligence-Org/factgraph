# Rules DTO（service v1）

范围：

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`

本文记录 service v1 的 rules facade DTO 契约。runtime session /
writes / query / views / packages 不在本文范围内。A20(E) / Q6-A 后
`/v1/registry/*` routes 已从 `app_v1.py` 删除，不再返回 removed envelope。

## 通用约定

- 所有 `/v1/...` rules / registry 端点默认都要求 `X-FactPy-API-Key`。
- 缺失或错误 key 返回 `HTTP 401`，且不会进入 JSON envelope。
- 认证启用但未配置 `FACTPY_KERNEL_API_KEYS` 时返回 `HTTP 503`，且不会进入 JSON envelope。
- 只有通过认证后，应用层成功/失败才继续使用 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- rules 端点不依赖 runtime session。
- service 不再暴露 registry 文件系统读取端点；schema 通过 runtime session /
  workspace APIs 进入系统，rules/inferences 使用 in-memory DTO。

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

## 4. `/v1/registry/*`（A20(E) registry final-exit 已删除）

A20(E) registry final-exit 后，下列 registry read routes 已从 service v1
删除：

- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/inferences/read`

客户端不应继续调用这些 paths；FastAPI 不再注册对应 operation。

迁移方法：

- schema/workspace 读取走 `FactGraph.load(...)` / workspace APIs。
- 客户端构造 in-memory `Rule(...)` 并在 runtime session 内通过
  `/v1/runtime/sessions/{session_id}/ephemeral-rules` 注册 ephemeral rule，
  然后调用 `/rules/run`。
- 客户端构造 in-memory `Inference(...)` 并直接调用
  `/v1/runtime/sessions/{session_id}/inferences/evaluate`。
- authoring apply-log 写入路径已退役；audit readers 仍兼容历史
  `db/audit/authoring_apply_events.jsonl` 与
  `registry/authoring_apply_events.jsonl`。

## 相关文档

- `01_overview.md`
- `02_runtime_sessions.md`
- `03_runtime_queries_policy.md`
