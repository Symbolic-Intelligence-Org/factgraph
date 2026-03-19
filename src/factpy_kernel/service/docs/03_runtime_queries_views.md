# Runtime Query, View And Derivation DTO（service v1）

范围：

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-support`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`
- `POST /v1/runtime/sessions/{session_id}/queries/explain`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-tree`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-summary`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-narrative`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-nl`
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
- 该 endpoint 继续作为 legacy compatibility wrapper 保留，供已直接持有 `support_digest` 的客户端使用。
- 默认情况下它仍是 session-scoped readback。
- 若打开 session 时配置了 `artifact_store_root`，则可从共享 sidecar root 回读旧 `support_digest`。
- 若当前 session 中不存在对应 artifact，返回 `runtime_explain_not_found`。
- 未配置 `artifact_store_root` 时，这不是 durable lookup；session 清理后 handle 可能失效。
- 为兼容旧客户端，响应顶层不新增 `kind` 字段。
- native `SupportArtifact` 当前可能同时包含：
  - legacy `rule_refs`
  - structured `rule_ref_edges`
- `rule_ref_edges` 是 per-occurrence child-proof edges：
  - `ruleref_atom_key`
  - `rule_ref_id`
  - `rule_ref_version`
  - `child_support_digest | None`
  - `unresolved_reason | None`
- first-round `unresolved_reason` 只使用 `child_support_unavailable`；artifact readback miss 与 recursion boundary 不写进这个字段。

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
        "non_fact_steps": [],
        "ruleref_links": []
      }
    ],
    "root_rows": [["idref_v1:Person:source_id=u1", "de"]]
  }
}
```

说明：

- 该 endpoint 内部直接调用 `Store.explain_rule_trace(...)`。
- 该 endpoint 继续作为 legacy compatibility wrapper 保留，供已直接持有 `rule_run_id` 的客户端使用。
- canonical public surface 是统一 `POST /queries/explain` + `{"kind":"rule_run","id":"..."}`。
- 本 endpoint 是 `rule_run` structured explain object 的 legacy alias。
- 默认情况下它仍是 session-scoped readback。
- 若打开 session 时配置了 `artifact_store_root`，则可从共享 sidecar root 回读旧 `rule_run_id`。
- `rule_run_id` 目前只会在 `/rules/run` 传 `capture_trace=true` 时返回。
- 若当前 session 中不存在对应 artifact，返回 `runtime_explain_not_found`。
- 为兼容旧客户端，响应顶层不新增 `kind` 字段。
- canonical endpoint 与 legacy alias 共享同一个 `explain` payload shape；两条路径唯一允许存在的 envelope 差异是 canonical 顶层多一个 `kind="rule_run"` discriminator。
- `rule_run` explain payload 的 stable contract 第一轮包括：
  - 顶层：`rule_run_id`、`root_rule`、`select_vars`、`root_rows`
  - `invocations[]`
    - `invocations` 本身是 stable flat list shape
    - consumer 通过 `parent_invocation_id` 与 `ruleref_links.child_invocation_id` 重建 tree
    - stable 字段：`invocation_id`、`parent_invocation_id`、`rule`、`memo_hit`、`memo_source_invocation_id`、`bindings`、`output_rows`
  - `pred_witnesses[]`：`binding_index`、`pred_atom_key`、`asrt_ids`
  - `ruleref_links[]`：`ruleref_atom_key`、`child_invocation_id`
  - `non_fact_steps[]`：`binding_index`、`step_key`、`kind`、`status`
- `non_fact_steps.details` 采用部分稳定边界：
  - `details.binding` 属于稳定 contract
  - `details.atom` 保持 opaque passthrough，不承诺 typed schema
- `T1` temporal checks 继续复用同一 explain contract：
  - fact-backed temporal anchors 出现在 `pred_witnesses`
  - 时间比较绑定值出现在 `details.binding`
  - 不新增 temporal 专用字段
- `Scenario A` 的 uncertainty threshold checks 也复用同一 explain contract：
  - fact-backed measurement / threshold predicates 出现在 `pred_witnesses`
  - 数值比较绑定值出现在 `details.binding`
  - 不新增 uncertainty 专用字段
- `original_where` 与 `rewritten_where` 也保持 opaque passthrough；客户端只能假定它们是 JSON-native payload，不能假定内部结构在 service v1 中稳定。
- 第一轮不引入 payload-internal discriminator 或 version tag：
  - 不新增 `explain.kind`
  - 不新增 `rule_run_v1`
  - object version boundary 继续留在 service/envelope 层处理

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 4. `POST /v1/runtime/sessions/{session_id}/queries/explain`

请求：

```json
{
  "kind": "candidate",
  "id": "cand_v2:abc123"
}
```

支持的 `kind`：

- `candidate`
- `assertion`
- `rule_run`

成功响应（`candidate`）：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "candidate_id": "cand_v2:abc123"
  },
  "kind": "candidate",
  "explain": {
    "candidate_id": "cand_v2:abc123",
    "support_digest": "sha256:6f3e4f9c2d1b8a7e6c5d4b3a291817161514131211100f0e0d0c0b0a09080706",
    "support": {
      "kind": "native_binding_v1"
    }
  }
}
```

成功响应（`assertion`）：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "asrt_id": "A1"
  },
  "kind": "assertion",
  "explain": {
    "asrt_id": "A1",
    "pred_id": "person:country",
    "e_ref": "idref_v1:Person:source_id=u1",
    "is_active": true
  }
}
```

成功响应（`rule_run`）：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "rule_run_id": "rt_trace_123"
  },
  "kind": "rule_run",
  "explain": {
    "rule_run_id": "rt_trace_123",
    "root_rule": {
      "rule_id": "q_country_rows",
      "version": "1.0.0"
    }
  }
}
```

说明：

- 这是 service v1 的统一 `explain_ref` 入口，第一轮只接受 `{kind, id}`。
- `kind` 是 load-bearing discriminator；service 不会仅凭 `id` 形状推断 handle 类型。
- `candidate` 是 weak-durable convenience kind：
  - 第一跳 `candidate_id -> (support_digest, support_kind)` 只存在于当前 session 的 `_candidate_support_index` / `_candidate_support_kind_index`
  - 第一跳 miss 时直接返回 `runtime_explain_not_found`
  - 第二跳 `support_digest -> SupportArtifact` 可受 sidecar durability 覆盖
  - 若 `support_kind="engine_no_witness_v1"`（legacy `"none"` 读回也按同类处理），则该 candidate 表示 engine no-witness 降级路径：
    - 响应仍为 `ok=true`
    - `explain.support_kind="engine_no_witness_v1"`（或 legacy `"none"`）
    - `explain.witness_status="degraded"`
    - `explain.support` 会缺失；这不是 artifact miss 错误，而是结构上无 witness
- `assertion` 返回 narrow single-`asrt_id` explain payload，不等价于 pair-level `explain-fact` 查询。
- `rule_run` 直接桥接既有 `rule_run_id -> RuleTraceArtifact` explain 路径。
- `kind="rule_run"` 的 `explain` payload 与 `explain-rule-trace` 使用同一底层 `RuleTraceArtifact` dict 形态：
  - `explain` payload 本身与 legacy alias identical
  - 稳定字段、部分稳定字段、opaque 边界与上一节保持一致
  - 统一 endpoint 只是在 envelope 顶层增加 `kind="rule_run"` discriminator
- 统一成功响应总是包含顶层 `kind` 与 `explain`。
- `kind` 缺失或值不在 `{candidate, assertion, rule_run}` 内时，返回 `HTTP 200` + `ok=false` + `errors[0].kind="shape"`。
- `kind="fact"` 不受支持；`explain-fact` 仍是独立 endpoint。
- 旧 `explain-support` / `explain-rule-trace` 继续保留，但其响应 shape 不会新增顶层 `kind`。
- 第一轮不在 `explain` payload 内部重复放置 object-level discriminator 或 version tag；统一入口的顶层 `kind` 已足够区分 `rule_run` object。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 4.1 `POST /v1/runtime/sessions/{session_id}/queries/explain-tree`

请求：

```json
{
  "kind": "candidate",
  "id": "cand_v2:abc123"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "candidate_id": "cand_v2:abc123"
  },
  "kind": "candidate_evidence_tree",
  "tree": {
    "kind": "candidate_evidence_tree",
    "candidate_id": "cand_v2:abc123",
    "support_digest": "sha256:6f3e4f9c2d1b8a7e6c5d4b3a291817161514131211100f0e0d0c0b0a09080706",
    "support_kind": "native_binding_v1",
    "root": {
      "node_kind": "candidate_result",
      "children": []
    }
  }
}
```

说明：

- 这是 candidate explain 的独立 tree surface，不会修改既有 `POST /queries/explain` 的 flat DTO。
- 第一轮只接受 `{kind:"candidate", id}`。
- 第一轮支持两类 candidate tree：
  - native
    - `support_kind="native_binding_v1"`
  - engine degraded
    - `support_kind in {"engine_no_witness_v1", "none"}`
- `tree` DTO 是 recursive schema，并在当前版本采用 sectioned shape：
  - root：`candidate_result`
  - section layer：
    - `support_section`
    - optional `rule_ref_section`
  - support section children：
    - `predicate_witness_group`
    - `non_fact_check`
    - `degraded_support`
  - leaf / recursive nodes：
    - `assertion_fact`
    - `rule_ref`
    - `referenced_support`
    - `unresolved_support`
    - `recursion_boundary`
- `support_section` 当前始终存在。
- `rule_ref_section` 在 `SupportArtifact.rule_ref_edges` 非空时优先按 structured edge emit；若只有 legacy `rule_refs`，则回退到 minimal `rule_ref` 节点。
- `rule_ref` 节点当前会显式暴露：
  - `ruleref_atom_key`
  - `rule_ref_id`
  - `rule_ref_version`
  - `child_support_digest`
  - `unresolved_reason`
- 当 `child_support_digest` 可解引用时，tree 会继续展开 `referenced_support`；否则会落到 `unresolved_support`。
- `artifact_missing`、`cycle`、`depth_limit` 是 tree terminal reason，不属于 capture-side `unresolved_reason`。
- 这些 terminal reason 现在属于正式的 shared taxonomy contract，不再只是实现细节：
  - `unresolved_support`
    - `child_support_unavailable`
      - capture / substrate-owned
    - `artifact_missing`
      - lookup / readback-owned
  - `recursion_boundary`
    - `cycle`
    - `depth_limit`
      - traversal-owned
- runtime / audit / static 三侧共享同一组 raw reason enum；service 不在 transport 层再翻译成另一套状态名。
- richer taxonomy 只适用于 structured `rule_ref_edges` path；只有 legacy `rule_refs` 的旧 artifact 仍只展示 flat `rule_ref` 节点，不进入 recursive terminal taxonomy。
- engine degraded candidate 则走单独的 tree contract：
  - envelope 仍是 `candidate_evidence_tree`
  - first-round shape 固定为：
    - `candidate_result`
    - `support_section`
    - `degraded_support`
  - `degraded_support` 最小字段为：
    - `support_kind`
    - `witness_status="degraded"`
    - `children=[]`
  - `degraded_support` 不复用 `unresolved_support` / `recursion_boundary`
  - node 本体不暴露 `support_digest`；若需要 raw digest，只从顶层 envelope 兼容字段读取
  - legacy `"none"` 与 `engine_no_witness_v1` 在 tree surface 上同构
- native candidate proof 现在会在 support capture 时做 winning-branch narrowing：
  - `support_section` / `rule_ref_section` 只反映 adopted branch
  - 若多个 branch 都满足同一 final binding，则采用 `source-order wins`
  - selected branch identity 继续通过现有 atom keys recoverable
- `assertion_fact` leaf 只携带：
  - `asrt_id`
  - `pred_id`
  - `e_ref`
  - `claim_args`
- `assertion_fact` leaf 不携带：
  - `meta`
  - `revoked_by`
  - `revokes`
  - `is_revoked`
- 若 consumer 需要 revocation / meta / full assertion state，继续按 `asrt_id` 回跳：
  - `POST /queries/explain` + `kind="assertion"`
  - 或 audit assertion detail surface
- 第一轮 `candidate_evidence_tree` 只表达 “why this candidate holds”：
  - 不表达 non-witnessed alternatives
  - 不表达 conflict-resolution
  - 不表达 source-linkage graph
- 当前 tree 相比最初 v1 引入了 section layer；这是已接受的、范围受控的 shape change，而不是纯 additive enrichment。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 5. `POST /v1/runtime/sessions/{session_id}/queries/explain-summary`

请求：

```json
{
  "kind": "rule_run",
  "id": "rt_trace_123"
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
  "kind": "rule_run_summary",
  "summary": {
    "rule_run_id": "rt_trace_123",
    "root_rule": {
      "rule_id": "q_country_rows",
      "version": "1.0.0"
    },
    "root_row_count": 1,
    "invocation_count": 1,
    "witness_assertion_ids": ["A1"],
    "predicate_witness_groups": [
      {
        "pred_id": "person:country",
        "asrt_ids": ["A1"],
        "invocation_ids": ["rt_trace_123:i1"]
      }
    ],
    "non_fact_step_groups": []
  }
}
```

说明：

- 这是 service v1 的 consumer-facing derived DTO endpoint，第一轮只接受 `{kind:"rule_run", id}`。
- 它不会修改或替代 raw `rule_run` explain contract。
- 它内部直接复用 canonical raw explain path：`POST /queries/explain` + `kind="rule_run"`。
- summary 是 pure derivation：
  - 每个 summary 字段都直接从 canonical raw `rule_run` payload 派生
  - summary 不会要求 raw carrier 改 shape
- 第一轮 `rule_run_summary` 只包含 7 个字段：
  - `rule_run_id`
  - `root_rule`
  - `root_row_count`
  - `invocation_count`
  - `witness_assertion_ids`
  - `predicate_witness_groups`
  - `non_fact_step_groups`
- `witness_assertion_ids` 是跨全部 invocations 的 `pred_witnesses.asrt_ids` flat 去重结果。
- `predicate_witness_groups` 采用 flat semantic-key grouping：
  - grouping key = 从 raw `pred_atom_key` 派生出的 `pred_id`
  - group fields = `pred_id`、`asrt_ids`、`invocation_ids`
- `non_fact_step_groups` 也采用 flat semantic-key grouping：
  - grouping key = raw `non_fact_steps.kind`
  - group fields = `kind`、`count`、`invocation_ids`
- 第一轮不把 `binding_index`、`step_key`、`details.atom` 提升进 summary DTO；这些仍属于 raw payload 的消费层级。
- `rule_run_id` 本身就是回跳 raw explain 的充分 handle。
- `witness_assertion_ids` 本身就是回跳 `explain_ref(kind="assertion")` 的充分 handle。
- 第一轮不支持 `candidate` / `assertion` summary；`kind` 取其他值时返回 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 6. `POST /v1/runtime/sessions/{session_id}/queries/explain-narrative`

请求：

```json
{
  "kind": "rule_run",
  "id": "rt_trace_123"
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
  "kind": "rule_run_narrative",
  "narrative": {
    "headline": "Rule q_country_rows@1.0.0 produced 1 root row(s) across 1 invocation(s).",
    "overview_lines": [
      "Witness assertions: 1 unique assertion(s).",
      "Predicate witness groups: 1.",
      "Non-fact check groups: 0."
    ],
    "predicate_lines": [
      "Predicate person:country was witnessed by 1 assertion(s) across 1 invocation(s)."
    ],
    "non_fact_check_lines": [
      "No non-fact check groups were captured."
    ],
    "drilldown_lines": [
      "Open the linked assertion detail page(s) for 1 witness assertion(s) to inspect supporting facts.",
      "Continue below for invocation-level detail and the full raw trace payload."
    ]
  }
}
```

说明：

- 这是 service v1 的 narrative DTO endpoint，第一轮只接受 `{kind:"rule_run", id}`。
- narrative 不是 raw explain 或 summary 的替代物；它是建立在 `rule_run_summary` 之上的 deterministic presentation layer。
- 它内部调用链为：
  - canonical raw explain
  - `rule_run_summary`
  - `render_rule_run_narrative(..., locale="en")`
- 第一轮 narrative DTO 固定为 5 个字段：
  - `headline`
  - `overview_lines`
  - `predicate_lines`
  - `non_fact_check_lines`
  - `drilldown_lines`
- 这些字段都只从 `rule_run_summary` 纯派生，不直接下探 raw trace carrier。
- 第一轮故意不把 narrative 打包进 `explain-summary`；bundled delivery 若需要，后续另行评估。
- 第一轮不支持 `candidate` / `assertion` narrative；`kind` 取其他值时返回 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 7. `POST /v1/runtime/sessions/{session_id}/queries/explain-nl`

请求：

```json
{
  "kind": "rule_run",
  "id": "rt_trace_123"
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
  "kind": "rule_run_nl_explain",
  "explain_nl": {
    "headline": "Rule q_country_rows@1.0.0 matched 1 root row(s) across 1 invocation(s).",
    "paragraphs": [
      "Rule q_country_rows@1.0.0 produced 1 root row(s) across 1 invocation(s). This run identified 1 unique witness assertion(s), 1 predicate witness group(s), and 0 non-fact check group(s). Witness assertions: 1 unique assertion(s). Predicate witness groups: 1. Non-fact check groups: 0.",
      "Evidence summary: Predicate person:country was witnessed by 1 assertion(s) across 1 invocation(s).",
      "Check summary: No non-fact check groups were captured.",
      "Drill-down guidance: Open the linked assertion detail page(s) for 1 witness assertion(s) to inspect supporting facts. Continue below for invocation-level detail and the full raw trace payload."
    ]
  }
}
```

说明：

- 这是 service v1 的 deterministic prose endpoint，第一轮只接受 `{kind:\"rule_run\", id}`。
- 它不是 raw / summary / narrative 的替代物，而是建立在这两层 structured DTO 之上的 runtime-first prose view。
- 它内部调用链为：
  - canonical raw explain
  - `rule_run_summary`
  - `rule_run_narrative`
  - `render_rule_run_nl_explain(..., locale=\"en\")`
- 第一轮 `rule_run_nl_explain` 只包含 2 个字段：
  - `headline`
  - `paragraphs`
- `paragraphs` 是 deterministic prose composition：
  - 会吸收 narrative 中的 overview、predicate evidence、non-fact checks 与 drill-down guidance
  - 但不会继续暴露 narrative 的结构化 section 字段
- 若 consumer 需要结构化 drill-down affordance，应继续使用 `explain-narrative`。
- 第一轮不支持 `candidate` / `assertion` NL explain；`kind` 取其他值时返回 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`

## 8. `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`

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
  "override_registry_root": "/tmp/registry",
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
- native derivation evaluate 当前会填充 `support_kind="native_binding_v1"`。
- `override_registry_root` 可选；未提供时默认复用 session 绑定的 `registry_root`。
- 为兼容旧客户端，`registry_root` 仍可作为 `override_registry_root` 的别名；两者不能同时提供。
- native derivation where 若使用字符串 `RuleRef("rule_id", version)`，必须通过：
  - `override_registry_root`
  - legacy `registry_root`
  - 或 session-level `registry_root`
  提供显式 registry context；否则运行时会 fail fast。
- native derivation support 当前可记录 direct `rule_refs`，因此后续 `explain-support` / `explain-tree` 可能看到 minimal `rule_ref` 节点；这还不是递归 child proof。
- native derivation support 现在会优先记录 structured `rule_ref_edges`，因此后续 `explain-support` / `explain-tree` 已可沿 `child_support_digest` 继续展开 first-round recursive proof。
- direct `rule_refs` 继续保留为兼容摘要字段；child row proof 复用既有 native `SupportArtifact` readback，而不是发明第二套 handle。
- native derivation support 现已在 capture 阶段应用 winning-branch narrowing：
  - `pred_witnesses`
  - `non_fact_steps`
  - `rule_ref_edges`
  只反映 selected branch
- 若多个 OR branch 都满足同一 final binding，则采用 `source-order wins`；若没有任何 branch 满足该 binding，则视为 capture contract violation 并 fail fast。
- engine evaluate（`souffle` / `problog`）第一轮显式返回 `support_kind="engine_no_witness_v1"`：
  - 这表示 candidate 本身有效，但当前 engine path 不产出可解引用的 witness artifact
  - 统一 `explain_ref(kind="candidate")` 会返回 `witness_status="degraded"`，而不是 `runtime_explain_not_found`
- legacy `support_kind="none"` 只作为兼容读回值保留；新 writer 不再产生它。
- `limit` 只影响返回条数，不改变底层总候选数；总量体现在 `meta.candidate_count`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `string_dsl_unsupported`
- `authoring_derivation_compile`
- `derivation_evaluate`

## 9. `POST /v1/runtime/sessions/{session_id}/derivations/accept`

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

## 10. `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`

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
- 该 endpoint 不属于统一 `explain_ref` kind 集合；它继续表示 `(pred_id, e_ref, optional val_atoms)` 的 predicate/entity 查询语义。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `query_explain_fact`

## 11. `POST /v1/runtime/sessions/{session_id}/queries/conflicts`

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

## 12. `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`

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

## 13. `POST /v1/runtime/sessions/{session_id}/queries/view-facts`

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

## 14. `POST /v1/runtime/sessions/{session_id}/views/create`

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

## 15. `POST /v1/runtime/sessions/{session_id}/views/update`

请求与成功响应结构同 `views/create`，但要求 `name` 已存在。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `view_update`

## 16. `POST /v1/runtime/sessions/{session_id}/views/delete`

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

## 17. `POST /v1/runtime/sessions/{session_id}/views/get`

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

## 18. `GET /v1/runtime/sessions/{session_id}/views`

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

## 19. `POST /v1/runtime/sessions/{session_id}/packages/export`

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
