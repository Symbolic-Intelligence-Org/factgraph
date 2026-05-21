# Runtime Query, Policy And Inference DTO（service v1）

范围：

- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/inferences/evaluate`
- `POST /v1/runtime/sessions/{session_id}/inferences/accept`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-support`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`
- `POST /v1/runtime/sessions/{session_id}/queries/explain`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-tree`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-summary`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-narrative`
- `POST /v1/runtime/sessions/{session_id}/queries/explain-nl`
- `GET /v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}`
- `GET /v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`
- `POST /v1/runtime/sessions/{session_id}/packages/export`

本文记录 service v1 的 runtime query、rule/inference 执行与 package export DTO 契约。session open/get/close、writes、claims 和 rules/registry 端点不在本文范围内。

## 通用约定

- 所有 `/v1/...` runtime query/policy/inference 端点默认都要求 `X-FactPy-API-Key`。
- 缺失或错误 key 返回 `HTTP 401`，且不会进入 JSON envelope。
- 认证启用但未配置 `FACTPY_KERNEL_API_KEYS` 时返回 `HTTP 503`，且不会进入 JSON envelope。
- 只有通过认证后，应用层成功/失败才继续使用 `HTTP 200` JSON envelope。
- 成功：`ok=true`，失败：`ok=false` 且 `errors[]` 非空。
- `session_id` 一律走 path parameter。
- tuple 在 JSON 中统一序列化为 list。
- `entity_ref`（如 `idref_v1:...`）直接按普通字符串透传，不额外包装。
- runtime query/rule/inference 链路不再接受 `temporal_view`；传入时返回 `shape` error。
- `view-facts` 不再有命名 view registry，也不接受 inline read policy。
  `policy`、`view_name` 和旧的 `view` 字段都会返回 `shape` error。

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
- `registry_root` / `override_registry_root` 已被 A20(E) / Q6-A 移除；
  传入任一字段都会返回 `registry_root_removed`。
- `run` 使用的 active `RuleRegistry` 只由当前 session 的
  `ephemeral_rules` 组成。
- 因此只要 session 已注册了匹配的 ephemeral rule，`ruleref(...)` 仍可在
  native rule path 上解析成功；filesystem registry 不再参与。
- `capture_trace` 可选，默认 `false`；当为 `true` 时 service 会调用 traced sibling helper，并在 `result.trace.rule_run_id` 返回 trace handle。
- 若 session 没有配置 `artifact_store_root`，该 handle 仍是 session-scoped。
- 若 session 配置了共享的 `artifact_store_root`，后续 session 可继续用该 handle 做 explain readback。
- `capture_trace=false` 时响应保持旧 shape，不返回 `trace`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。
- 其他 rule 编译或执行失败默认仍落入统一 `runtime` error；但常见 agent-facing 失败现在会在 `errors[0].details` 中追加稳定字段：
  - unknown predicate：`error_code="unknown_predicate"` + `missing_pred_id` + `remediation_hint`
  - unknown RuleRef：`error_code="unknown_rule_ref"` + `missing_rule_ref` + `remediation_hint`
  - RuleRef target not exposed：`error_code="rule_not_expose"` + `rule_ref_id` + `remediation_hint`

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
  - 第二跳按 `support_kind` 分流：
    - native / Souffle tree-bearing kind：`support_digest -> SupportArtifact`
    - engine provenance kind：`support_digest -> ProvenanceEnvelope`
  - 若 `support_kind in {"native_binding_v1", "souffle_witness_v1"}`，service 会继续回放 `Store.explain_support(...)`：
    - 响应仍为 `ok=true`
    - `explain.support` 携带 flat support payload
    - 当前不额外写 `witness_status`
  - 若 `support_kind="pyreason_provenance_v1"`，service 会回放 `Store.explain_provenance(...)`：
    - 响应仍为 `ok=true`
    - `explain.support_kind` 保留当前 kind
    - `explain.provenance` 携带 engine-native `ProvenanceEnvelope`
    - 当前不把 envelope 强制转成 `SupportArtifact` 或 candidate evidence tree
  - 若 `support_kind="problog_provenance_v1"`，service 也会回放 `Store.explain_provenance(...)`：
    - 响应仍为 `ok=true`
    - `explain.support_kind` 保留当前 kind
    - `explain.provenance` 携带 engine-native `ProvenanceEnvelope`
    - 这不替代后续 `explain-tree` / summary / narrative / NL 的 ProbLog 投影路径；flat `explain` 仍是 canonical raw provenance surface
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
- `runtime_explain_not_supported`

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
  - witness-bearing
    - `support_kind in {"native_binding_v1", "souffle_witness_v1"}`
  - engine degraded
    - `support_kind in {"engine_no_witness_v1", "none"}`
- runtime 现在还支持第三类 candidate tree：
  - projected ProbLog proof
    - `support_kind="problog_provenance_v1"`
    - 仅当 candidate payload 可从 accepted claim / ledger 回溯时可用
    - 同一支持矩阵适用于：
      - `explain-tree`
      - `explain-summary`
      - `explain-narrative`
      - `explain-nl`
      - `GET /evidence/candidate/{candidate_id}`
    - pre-accept candidate 或 payload 不可回溯时，tree family 返回 `explain_not_supported`
- `support_kind="pyreason_provenance_v1"` 当前仍不会自动渲染成 tree：
  - `explain-tree`
  - `explain-summary`
  - `explain-narrative`
  - `explain-nl`
  - `GET /evidence/candidate/{candidate_id}`
  都会返回 `runtime_explain_not_supported`
- `tree` DTO 是 recursive schema，并在当前版本采用 sectioned shape：
  - root：`candidate_result`
  - section layer：
    - `support_section`
    - optional `rule_ref_section`
  - support section children：
    - `proof_goal`
    - `proof_leaf`
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
- `souffle_witness_v1` 当前复用既有 witness-bearing tree shape：
  - envelope 仍是 `candidate_evidence_tree`
  - root 仍是 `candidate_result`
  - `support_section` 下仍使用：
    - `predicate_witness_group`
    - minimal `non_fact_check`
  - `rule_ref_section` / recursive child proof 当前不适用于此 kind
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
- `node_kind` 是 carrier-level provenance-role taxonomy（冻结 contract），consumer 可直接基于 `node_kind` 做渲染/分类决策：
  - **structural**：`candidate_result`, `support_section`, `rule_ref_section` — 纯结构容器
  - **proof**：`proof_goal`, `proof_leaf` — engine-native logical proof frame / terminal，不等价于 ledger assertion witness
  - **witness**：`predicate_witness_group`, `assertion_fact` — 直接见证 ledger 事实
  - **constraint**：`non_fact_check` — 非事实约束检查
  - **rule_chain**：`rule_ref`, `referenced_support` — 规则引用及递归证明
  - **terminal**：`unresolved_support`, `recursion_boundary` — 遍历终止或证据不可用
  - **degraded**：`degraded_support` — Engine 路径无 witness artifact
- 当 projected ProbLog tree 可用时：
  - root `candidate_result` 还可附加 `engine_meta.probability`
  - `proof_goal` 暴露 goal-level predicate / args / child subgoal 数
  - `proof_leaf` 只表示 logical terminal，不携带 `asrt_id`，也不链接 assertion detail page
- first-round 不新增 `source_kind` / `provenance_kind` 字段；`node_kind` 本身即为 provenance-role carrier
- `rule_ref` node_kind 同时用于 legacy flat 和 structured edge；consumer 通过 `ruleref_atom_key` 字段有无区分
- deeper assertion-origin taxonomy（direct write / inference accept / import）deferred

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`
- `explain_not_supported`

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

- 这是 service v1 的 consumer-facing derived DTO endpoint，当前支持：
  - `{kind:"rule_run", id}`
  - `{kind:"candidate", id}`
- 它不会修改或替代 raw `rule_run` / `candidate_evidence_tree` explain contract。
- `rule_run` summary 继续直接复用 canonical raw explain path：`POST /queries/explain` + `kind="rule_run"`。
- `candidate` summary 则复用 canonical tree path：`POST /queries/explain-tree` + `kind="candidate"`。
- summary 是 pure derivation：
  - 每个 summary 字段都直接从 canonical raw carrier 派生
  - summary 不会要求 raw carrier 改 shape
- `rule_run_summary` 继续只包含 7 个字段：
  - `rule_run_id`
  - `root_rule`
  - `root_row_count`
  - `invocation_count`
  - `witness_assertion_ids`
  - `predicate_witness_groups`
  - `non_fact_step_groups`
- `candidate_evidence_tree_summary` 则采用 provenance-role-first 的 12 字段 core set：
  - `candidate_id`
  - `support_kind`
  - `is_degraded`
  - `root_result_kind`
  - `node_count_by_role`
  - `witness_assertion_count`
  - `rule_ref_count`
  - `recursive_depth`
  - `has_unresolved`
  - `has_boundary`
  - `unresolved_reasons`
  - `boundary_reasons`
- 当 candidate tree 含 proof nodes（或 `support_kind="problog_provenance_v1"`）时，summary 还允许附加：
  - `node_count_by_role.proof`
  - `proof_goal_count`
  - `proof_leaf_count`
- 当 projected ProbLog tree root 暴露 `engine_meta.probability` 时，summary 还允许附加：
  - `problog_probability`
- `candidate` summary 响应当前还允许附加 response-level sibling `certainty_summary`（**certainty v1 contract frozen** — 语义改动必须经 blueprint）：
  - 不嵌入 `summary` dict
  - 不改变上述基础 12 字段 core set
  - 当 store 内部 candidate carrier 不是 `confidence_kind="certainty"` 时固定为 `null`
  - 当 store 内部 candidate carrier 是 `confidence_kind="certainty"` 时，service 会尝试：
    - 从 `candidate_id` 回取内部 `confidence_kind`
    - 从 `support.rule_ref_edges` 定位单条 structured child rule edge
    - 解析该 edge 的 `rule_ref_id@version` 对应的 in-memory rule metadata
    - 在唯一 `referenced_support` subtree 上调用 annotation prototype `derive_certainty_summary(...)`
  - `condition_weights` 在这里是 certainty/explain projection input，
    不是 engine adapter 参数，也不进入 `where` / adapter rule syntax；
    未来运行时配置归 `SemanticsProfile.certainty_projection`
  - 若出现多 rule_ref_edges、nested referenced_support、unresolved child support、rule payload 缺失等情况，则 graceful degrade 为 `certainty_summary=null`
  - 若 rule payload 存在但未声明 `condition_weights`，则 `certainty_summary` 仍可返回；此时所有 condition 都是 unweighted
  - 对 runtime native inference 而言，eligible candidate 的 `confidence_kind="certainty"` 现在由 evaluate create-time routing 自动写入；不再依赖调用侧 patch
- `certainty_summary` 的 stable shape 为：
  - internal `confidence_kind`
  - `condition_count`
  - `weighted_condition_count`
  - `conditions[]`
    - `atom_key`
    - `node_kind`
    - `weight`
    - `impact`（bottleneck: 绝对 `weight × condition_confidence`；additive: 归一化 contribution `(weight/Σweights) × condition_confidence`；缺少 certainty 输入时使用 `1.0`）
  - `aggregate_certainty`（bottleneck: `min(impacts)`；additive: `sum(impacts)`）
  - `aggregation`（`"bottleneck"` 或 `"additive"`）
- candidate explain 端点（summary/narrative/NL）接受可选 `certainty_aggregation` 参数：
  - `"bottleneck"`（默认）— 最弱环节决定整体强度
  - `"additive"` — 按归一化权重加和各条件贡献
  - 不传时使用默认 `"bottleneck"`，完全向后兼容
- `candidate` summary 不新增 `node_count_by_kind`、`witness_predicate_ids`、`constraint_check_kinds`；这些仍属于 deferred enhancement。
- `problog_probability` 属于 summary dict 内的 engine-derived scalar，不走 response-level sibling。
- `witness_assertion_ids` 是跨全部 invocations 的 `pred_witnesses.asrt_ids` flat 去重结果。
- `predicate_witness_groups` 采用 flat semantic-key grouping：
  - grouping key = 从 raw `pred_atom_key` 派生出的 `pred_id`
  - group fields = `pred_id`、`asrt_ids`、`invocation_ids`
- `non_fact_step_groups` 也采用 flat semantic-key grouping：
  - grouping key = raw `non_fact_steps.kind`
  - group fields = `kind`、`count`、`invocation_ids`
- `queries/explain-summary` 不接受 `registry_root` /
  `override_registry_root`。certainty projection 只使用运行时已经持有的
  in-memory rule metadata；缺失 metadata 时 `certainty_summary` 降级为
  `null`。
- 第一轮不把 `binding_index`、`step_key`、`details.atom` 提升进 `rule_run_summary` DTO；这些仍属于 raw payload 的消费层级。
- `rule_run_id` 本身就是回跳 raw explain 的充分 handle。
- `candidate_id` 本身就是回跳 raw tree explain 的充分 handle。
- 第一轮不支持 `assertion` summary；`kind` 取其他值时返回 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`
- `explain_not_supported`

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

- 这是 service v1 的 narrative DTO endpoint，当前支持：
  - `{kind:"rule_run", id}`
  - `{kind:"candidate", id}`
- narrative 不是 raw explain 或 summary 的替代物；它是建立在 summary 之上的 deterministic presentation layer。
- `rule_run` narrative 调用链为：
  - canonical raw explain
  - `rule_run_summary`
  - `render_rule_run_narrative(..., locale="en")`
- `candidate` narrative 调用链为：
  - canonical raw tree
  - `candidate_evidence_tree_summary`
  - `render_candidate_evidence_tree_narrative(summary, tree=tree, locale="en")`
  - **Contract Fork D-EED1**：`tree` 参数可选，传入时额外扫描 `assertion_fact` 节点的 `fact_meta.source`；不传时行为与之前完全一致
- `rule_run_narrative` 继续固定为 5 个字段：
  - `headline`
  - `overview_lines`
  - `predicate_lines`
  - `non_fact_check_lines`
  - `drilldown_lines`
- `candidate_evidence_tree_narrative` 基础 6 字段：
  - `headline`
  - `overview_lines`
  - `evidence_lines`
  - `rule_chain_lines`
  - `terminal_lines`
  - `drilldown_lines`
- projected ProbLog tree narrative 还可附加可选 `probability_lines`：
  - 不改变上述 6 个基础字段
  - 用于显式传递概率信息到 NL
- 当 candidate certainty lane 可派生时，runtime narrative 还可附加 additive `certainty_lines`：
  - 不改变上述 6 个基础字段
  - 首行显式标注 scope：`Certainty (eligible child-proof subtree): ...`
  - 后续每行对应一个 condition，保持 atom position order，不做排序
  - 无 certainty_summary 时不返回该 key
- 当 `assertion_fact` 节点含 `fact_meta.source` 时，runtime narrative 还可附加 `source_lines`：
  - 不改变上述 6 个基础字段
  - 每行格式：`{pred_id}({e_ref}) — from '{source}'[ (approved by {approved_by})]`
  - 无 source meta 时不返回该 key
- narrative 的字段来自 summary（聚合层）及可选的 tree 下探（fact_meta 层）；不直接下探 raw engine carrier。
- 对 degraded candidate，narrative 也必须生成非空降级说明，而不是返回空段。
- 第一轮故意不把 narrative 打包进 `explain-summary`；bundled delivery 若需要，后续另行评估。
- `queries/explain-narrative` 不接受 `registry_root` /
  `override_registry_root`；基础 narrative output 与可选 certainty lines 均从
  session/runtime 内存数据派生。
- 第一轮不支持 `assertion` narrative；`kind` 取其他值时返回 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`
- `explain_not_supported`

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

- 这是 service v1 的 deterministic prose endpoint，当前支持：
  - `{kind:"rule_run", id}`
  - `{kind:"candidate", id}`
- 它不是 raw / summary / narrative 的替代物，而是建立在这两层 structured DTO 之上的 runtime-first prose view。
- `rule_run` 调用链为：
  - canonical raw explain
  - `rule_run_summary`
  - `rule_run_narrative`
  - `render_rule_run_nl_explain(..., locale="en")`
- `candidate` 调用链为：
  - PyReason candidate：
    - `explain-timeline`
    - `candidate_provenance_timeline_summary`
    - `candidate_provenance_timeline_narrative`
    - `render_candidate_provenance_timeline_nl_explain(..., locale="en")`
  - 其余 candidate：
    - canonical raw tree
    - `candidate_evidence_tree_summary`
    - optional additive `certainty_summary`
    - `candidate_evidence_tree_narrative`
    - `render_candidate_evidence_tree_nl_explain(..., locale="en")`
- candidate NL 默认仍是 4 段：
  - overview
  - evidence
  - rule-chain
  - terminal + drill-down
- 当 candidate narrative 含 `probability_lines` 时，NL 追加 probability paragraph：
  - `Probability assessment: ...`
  - 该段只复述 narrative 的 probability lines，不新增计算语义
- 当 candidate narrative 含 `certainty_lines` 时，NL 再追加 certainty paragraph：
  - `Certainty summary: ...`
  - 该段只复述 narrative 的 certainty lines，不新增计算语义
- `queries/explain-nl` 不接受 `registry_root` / `override_registry_root`；
  certainty paragraph 只在 runtime 内存数据足够时派生。
- `candidate` 调用链为：
  - canonical raw tree
  - `candidate_evidence_tree_summary`
  - `candidate_evidence_tree_narrative`
  - `render_candidate_evidence_tree_nl_explain(..., locale="en")`
- `rule_run_nl_explain` 与 `candidate_evidence_tree_nl_explain` 都只包含 2 个字段：
  - `headline`
  - `paragraphs`
- `paragraphs` 是 deterministic prose composition：
  - 会吸收 narrative 中的 section lines
  - 但不会继续暴露 narrative 的结构化 section 字段
- 若 consumer 需要结构化 drill-down affordance，应继续使用 `explain-narrative`。
- audit/static 第一轮不单独交付 candidate NL；candidate NL 当前是 runtime-only surface。
- 第一轮不支持 `assertion` NL explain；`kind` 取其他值时返回 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`
- `explain_not_supported`

## 7A. `POST /v1/runtime/sessions/{session_id}/queries/explain-steps`

请求：

```json
{
  "kind": "candidate",
  "id": "cand_v2:123"
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "candidate_id": "cand_v2:123"
  },
  "kind": "candidate_evidence_steps",
  "candidate_id": "cand_v2:123",
  "engine": "native_binding_v1",
  "steps": [
    {
      "step_num": 1,
      "step_kind": "fact_check",
      "description": "Fact expert:publication(entity:alice) = 12 ✓",
      "node_ref": "asrt_123",
      "detail": {
        "depth": 2,
        "parent_node_ref": "support:cand_v2:123",
        "pred_id": "expert:publication",
        "e_ref": "entity:alice",
        "claim_args": [{"idx": 0, "tag": "int", "val": "12"}]
      }
    },
    {
      "step_num": 2,
      "step_kind": "rule_apply",
      "description": "Rule q.expert_has_recent_pub@v1: 1 condition(s) met",
      "node_ref": "support:cand_v2:123",
      "detail": {
        "depth": 1,
        "parent_node_ref": "cand:cand_v2:123",
        "witness_count": 1,
        "rule_ref_ids": ["q.expert_has_recent_pub@v1"]
      }
    }
  ]
}
```

说明：

- 当前只支持 `{kind:"candidate", id}`
- `engine` 当前直通 `support_kind`，例如：
  - `native_binding_v1`
  - `souffle_witness_v1`
  - `problog_provenance_v1`
  - `pyreason_provenance_v1`
- dispatch：
  - `native / souffle / problog`：从 `candidate_evidence_tree` 生成 DFS post-order flat steps
  - `pyreason`：从 `candidate_provenance_timeline` 生成按时间排序的 flat steps
- `native / souffle` 路径中的 `rule_apply` step 可带 `detail.rule_ref_ids`
  - 来源于同一 `support_section` 对应 support artifact 的 rule refs
  - 单规则：`Rule <id>: N condition(s) met`
  - 多规则：`Rules [a, b]: N condition(s) met`
  - 无规则：降级为 `Support group satisfied: N condition(s) met`
- ProbLog / PyReason 不生成 `rule_apply.detail.rule_ref_ids`
- 第一轮不单独交付 audit/static steps DTO；runtime 返回是当前唯一 canonical delivery

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`
- `explain_not_supported`

## 7B. `GET /v1/runtime/sessions/{session_id}/evidence/...`

当前 runtime 也提供 session-bound live proof-entry permalink：

- `GET /v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}`
- `GET /v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}`

约束：

- 第一轮只覆盖 `candidate_id` 与 `rule_run_id`
- route 直接返回 `text/html`
- permalink 是 **session-bound ephemeral URL**
- 不承诺 durable live URL；长期分享仍以 audit/static export 为主

复用边界：

- candidate page 复用既有 candidate tree renderer：
  - runtime 直接组出 `tree + narrative`
  - accepted ProbLog candidate 现在也走这条路径；proof nodes 由同一 renderer 渲染
  - `proof_leaf` 不链接 assertion detail page
  - PyReason candidate page 仍不支持
- rule-trace page 复用既有 rule-trace detail renderer：
  - runtime 直接组出 `detail payload + narrative`
  - assertion detail lookup 继续从当前 session ledger 读取
- service 不新建第二套 HTML 模板

错误：

- 成功时返回 HTML
- 失败时仍复用 service 的统一异常处理

## 8. `POST /v1/runtime/sessions/{session_id}/inferences/evaluate`

请求：

```json
{
  "inference": {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "target": "person:country_copy",
    "head_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]]
  },
  "engine": "native",
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
    "inference_id": "drv.country_copy",
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
        "state": "generated"
      }
    ]
  }
}
```

说明：

- 请求顶层使用 public `inference` vocabulary；嵌套的 `derivation_id`
  是 compiler-facing authoring payload 的 substrate key。
- `evaluate` 返回完整 candidate 对象，供后续 `accept` 原样 round-trip。
- candidate DTO 中的 `derivation_id` / `derivation_version` 也是
  candidate/internal substrate 字段，不是 public `Derivation` value object。
- candidate DTO 不再默认暴露 legacy `confidence` / `confidence_kind`
  字段；这些值只保留为 store 内部/session carrier。
- Souffle deterministic 路径内部仍可保留 `confidence_kind="none"`；
  ProbLog / PyReason 路径可在 `CandidateSet` 上保留 adapter summary。
- runtime native inference 当前会在 create-time 注入 certainty resolver：
  - 只有 single resolved child-rule edge 且 child rule payload 含非空 `condition_weights` 时，store 内部 candidate carrier 才会自动标记 `confidence_kind="certainty"`
  - 其余 native 场景继续回落到 `none`
  - SDK parity 当前 deferred；未注入 resolver 的路径保持 `none`
- native inference evaluate 当前会填充 `support_kind="native_binding_v1"`。
- `souffle` evaluate 现在可在 runtime live path 上填充 `support_kind="souffle_witness_v1"`：
  - 前提是 adapter 能通过 `_w` witness 变体为当前 where 产出 assertion witness
  - 此时 `support_digest` 为真实 digest，不再是 zero placeholder
  - runtime `explain` / `explain-tree` 会把它视为 witness-bearing support
- `registry_root` / `override_registry_root` 已被 A20(E) / Q6-A 移除；
  传入任一字段都会返回 `registry_root_removed`。
- runtime inference evaluation 使用 top-level `engine` 选择后端；
  `inference.mode` 和 top-level `mode` 都会被拒绝。
- Track 3 / B 已引入 core `SemanticsProfile` scaffolding，Track 3 / C
  已让 core `Store.evaluate(..., mode="problog", semantics_profile=...)`
  消费 `rule_projection.problog`。Track 3 / D 也已让 core
  `Store.evaluate(..., mode="pyreason", semantics_profile=...)` 消费
  `rule_projection.pyreason` 与 `temporal_projection`。Track 3 / E 让
  service runtime 消费 top-level `semantics` inline dict，并通过
  `SemanticsProfile(**semantics)` 校验；`semantics_profile` 和
  `inference.semantics` / `inference.semantics_profile` 继续返回
  `shape` error。
- Track 2 的 `ProbLogSemantics` / `PyReasonSemantics` 是 SDK-only wrapper：
  SDK 会在持有 SDK `Rule` / `Inference` 对象时解析 branch id 并 lower 成
  canonical `SemanticsProfile`。Service runtime 不接受 wrapper-style JSON
  keys，例如 `branch_probabilities` / `timestep_delay` / `head_bound` /
  `branch_bounds`；
  service 仍只接受 top-level canonical `SemanticsProfile` shape。
- native `engine="native"` inference 会在 evaluate-time 使用当前 session 的
  `ephemeral_rules` 构造 in-memory `RuleRegistry`。
- 该 registry 只对 native + `ruleref(...)` 路径承诺生效；Souffle /
  ProbLog / PyReason 模式不消费 session-scoped ephemeral rules。
- native inference where 若使用字符串 `RuleRef("rule_id", version)`，必须在
  当前 session 注册 matching ephemeral rule；否则运行时会 fail fast。
- native inference support 当前可记录 direct `rule_refs`，因此后续 `explain-support` / `explain-tree` 可能看到 minimal `rule_ref` 节点；这还不是递归 child proof。
- native inference support 现在会优先记录 structured `rule_ref_edges`，因此后续 `explain-support` / `explain-tree` 已可沿 `child_support_digest` 继续展开 first-round recursive proof。
- direct `rule_refs` 继续保留为兼容摘要字段；child row proof 复用既有 native `SupportArtifact` readback，而不是发明第二套 handle。
- evaluate 失败时，常见 agent-facing恢复分支会在 `errors[0].details` 中追加稳定字段：
  - unknown RuleRef：`error_code="unknown_rule_ref"` + `missing_rule_ref` + `remediation_hint="register_referenced_rule_first_or_check_fs_registry"`
  - RuleRef target not exposed：`error_code="rule_not_expose"` + `rule_ref_id` + `remediation_hint="add_expose_true_to_rule_definition"`
  - unknown predicate：`error_code="unknown_predicate"` + `missing_pred_id` + `remediation_hint="verify_pred_id_via_GET_sessions_schema"`
- native inference support 现已在 capture 阶段应用 winning-branch narrowing：
  - `pred_witnesses`
  - `non_fact_steps`
  - `rule_ref_edges`
  只反映 selected branch
- 若多个 OR branch 都满足同一 final binding，则采用 `source-order wins`；若没有任何 branch 满足该 binding，则视为 capture contract violation 并 fail fast。
- engine evaluate 当前分三种 explainability surface：
  - partial tree witness
    - 目前覆盖 `souffle`
    - `support_kind="souffle_witness_v1"`
    - 仍是 engine path，不伪装成 `native_binding_v1`
  - engine provenance envelope
    - `pyreason`：`support_kind="pyreason_provenance_v1"`
    - `problog`：`support_kind="problog_provenance_v1"`
    - 统一 `explain_ref(kind="candidate")` 可返回 engine-native `ProvenanceEnvelope`
    - runtime tree/summary/narrative/NL surface 当前不支持这两类 support kind
  - degraded
    - `support_kind="engine_no_witness_v1"`
    - 这表示 candidate 本身有效，但当前 engine path 不产出可解引用的 witness artifact
    - 统一 `explain_ref(kind="candidate")` 会返回 `witness_status="degraded"`，而不是 `runtime_explain_not_found`
- audit/static 现在也接受 `souffle_witness_v1`：
  - `AuditQuery.get_candidate_evidence_tree(...)` 与 DTO/static 页面继续复用既有 witness-bearing tree shape
  - 不新增专用 engine DTO 或 static 分支
- `pyreason_provenance_v1` / `problog_provenance_v1` 现在有第二条离线交付链：
  - runtime export 会物化 `audit/evidence_graphs.jsonl`
  - `AuditQuery.get_candidate_evidence_graph(...)` 可直接读取 durable `EvidenceGraph`
  - candidate static page 会在 degraded tree 之外追加统一 `EvidenceGraph` section
  - 这仍不等于 runtime live tree/summary/narrative/NL 支持
- legacy `support_kind="none"` 只作为兼容读回值保留；新 writer 不再产生它。
- `limit` 只影响返回条数，不改变底层总候选数；总量体现在 `meta.candidate_count`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `string_dsl_unsupported`
- `authoring_derivation_compile`
- `inference_evaluate`

## 9. `POST /v1/runtime/sessions/{session_id}/inferences/accept`

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
- candidate DTO 的 `derivation_id` / `derivation_version` 是
  accept/proof/audit round-trip substrate 字段。
- 为兼容旧客户端，accept 仍会解析 echoed `candidate.confidence` /
  `candidate.confidence_kind` 字段；这些字段只 hydrate 内部 carrier，
  不会写入 assertion meta 或 adapter semantic lanes。
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

请求（返回 active projection facts）：

```json
{
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
    "audit": {
      "contract_version": 1
    }
  }
}
```

说明：

- `policy` 已移除；传入时返回 `$.policy` 的 `shape` error。
- `view_name` 已移除；传入时返回 `$.view_name` 的 `shape` error。
- 旧字段 `view` 已移除；传入时返回 `$.view` 的 `shape` error。
- `include_audit` 默认 `false`；为 `true` 时响应中返回 `view.audit`。
- `temporal_view` 已移除；传入会返回 `$.temporal_view` 的 `shape` error。
- `meta.pred_count` 是投影结果中的 predicate 数量；`meta.total_tuple_count` 是所有 predicate rows 总和。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `query_view_facts`

## 14. `POST /v1/runtime/sessions/{session_id}/queries/explain-timeline`

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
  "kind": "candidate_provenance_timeline",
  "timeline": {
    "kind": "candidate_provenance_timeline",
    "candidate_id": "cand_v2:abc123",
    "engine": "pyreason",
    "timesteps": 3,
    "chains": [
      {
        "component_type": "node",
        "component": "PAYMENTS_GATEWAY",
        "label": "at_risk_signal",
        "events": [
          {
            "time": 1,
            "fixpoint_op": 2,
            "old_bound": [0.0, 1.0],
            "new_bound": [1.0, 1.0],
            "occurred_due_to": "vendor_risk_propagation",
            "groundings": ["[ACME_CLOUD]", "[(PAYMENTS_GATEWAY, ACME_CLOUD)]"]
          }
        ]
      }
    ],
    "root_chain_key": ["node", "PAYMENTS_GATEWAY", "at_risk_signal"]
  }
}
```

说明：

- 这是 PyReason candidate 的 runtime timeline explain surface。只接受 `{kind:"candidate", id}`。
- 只对 `support_kind="pyreason_provenance_v1"` 的 candidate 返回 timeline。
- 对 native/souffle/problog candidate 调这个端点返回 `runtime_explain_not_supported`。
- 这个端点 **不改、不替代** 现有 `explain-tree` / `explain-summary` / `explain-narrative` / `explain-nl` 的行为：
  - `explain-tree` 对 pyreason 仍返回 `runtime_explain_not_supported`
  - `explain-summary` / `explain-narrative` / `explain-nl` 现在会在候选分支 early dispatch 到 timeline family
- `timeline` DTO shape：
  - `kind`: 固定为 `"candidate_provenance_timeline"`
  - `candidate_id`: candidate identifier
  - `engine`: 固定为 `"pyreason"`
  - `timesteps`: 推理总步数
  - `chains`: 按 `(component_type, component, label)` 字典序排列的 propagation chain 列表
  - `root_chain_key`: `[component_type, component, label]` 三元组，标识 candidate payload 对应的 root chain
- 每个 chain 包含：
  - `component_type`: `"node"` 或 `"edge"`
  - `component`: 实体标识
  - `label`: predicate label
  - `events`: 按 `(time, fixpoint_op)` 排序的 bound 更新事件列表
- 每个 event 包含：
  - `time`: 时间步
  - `fixpoint_op`: 定点运算序号
  - `old_bound`: `[lower, upper]` 旧区间
  - `new_bound`: `[lower, upper]` 新区间
  - `occurred_due_to`: 触发规则或 `"seed_fact"`
  - `groundings`: 子句 grounding 的原始文本列表（不透明调试信息，不稳定锚点）
- `groundings` 是从 PyReason carrier 原样回显的文本；不应解释为稳定的 body-atom dependency edge。跨 chain 因果关系不在 v1 scope 内。
- 已 accept 的 pyreason candidate 可返回 timeline；未 accept 的 candidate 因当前 store 没有持久化 candidate payload 索引，可能落到 `runtime_explain_not_found`。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`

## 15. `POST /v1/runtime/sessions/{session_id}/queries/explain-timeline-summary`

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
  "kind": "candidate_provenance_timeline_summary",
  "summary": {
    "explain_kind": "timeline",
    "timesteps": 3,
    "chain_count": 2,
    "total_event_count": 5,
    "root_chain_key": ["node", "PAYMENTS_GATEWAY", "at_risk_signal"],
    "root_chain_final_bound": [1.0, 1.0]
  }
}
```

说明：

- 这是 PyReason candidate 的 timeline summary surface，建立在 `explain-timeline` 之上。
- 只对 `support_kind="pyreason_provenance_v1"` 的 candidate 返回；其余返回 `runtime_explain_not_supported`。
- summary 是纯派生：所有字段都从 timeline DTO 计算得出，不直接下探 raw carrier。
- `summary` DTO shape 固定为 6 个字段：
  - `explain_kind`: 固定为 `"timeline"`
  - `timesteps`: 推理总步数
  - `chain_count`: chain 总数
  - `total_event_count`: 所有 chain 的事件总数
  - `root_chain_key`: root chain 的 `[component_type, component, label]`
  - `root_chain_final_bound`: root chain 最后一个事件的 `new_bound`

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`

## 16. `POST /v1/runtime/sessions/{session_id}/queries/explain-timeline-narrative`

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
  "kind": "candidate_provenance_timeline_narrative",
  "narrative": {
    "headline": "PyReason timeline: 2 propagation chains across 3 timesteps.",
    "propagation_lines": [
      "at_risk_signal on PAYMENTS_GATEWAY: [0.0,1.0] → [1.0,1.0] at t=1 (vendor_risk_propagation)"
    ],
    "root_line": "Root chain: at_risk_signal on PAYMENTS_GATEWAY final bound [1.0, 1.0]."
  }
}
```

说明：

- 这是 PyReason candidate 的 timeline narrative surface，建立在 `explain-timeline` 之上。
- 只对 `support_kind="pyreason_provenance_v1"` 的 candidate 返回；其余返回 `runtime_explain_not_supported`。
- narrative 是纯派生：所有字段都从 timeline DTO 计算得出，不直接下探 raw carrier。
- `narrative` DTO shape 固定为 3 个字段：
  - `headline`: 概要行，包含 chain 数和 timestep 数
  - `propagation_lines`: 每条描述一个 chain 内的事件（chain-local，不推断跨 chain 因果）
  - `root_line`: 描述 root chain 的最终 bound 状态
- narrative 保持 chain-local 描述原则：每条 propagation line 只描述一个 chain 内部的 bound 变化，不从 groundings 推断跨 chain 的因果关系。
- `explain_runtime_nl(kind="candidate")` 现在对 PyReason candidate 做 early dispatch：
  - 检测 `support_kind == "pyreason_provenance_v1"`
  - 走 timeline → summary → narrative → NL 管线
  - 返回 `kind="candidate_provenance_timeline_nl_explain"`

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime_explain_not_found`
- `runtime_explain_not_supported`

## 17. `POST /v1/runtime/sessions/{session_id}/packages/export`

请求：

```json
{
  "out_dir": "/tmp/pkg",
  "package_kind": "audit",
  "query": {
    "where": [["pred", "person:country", ["$e", "$country"]]],
    "query_rel": "country_query"
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
- 当 `query.where` 含 `ruleref` 时，当前 exporter 使用 session/runtime 已持有的
  in-memory rule resolver；不接受 filesystem registry root：

```json
{
  "query": {
    "where": [["ruleref", "q.example_rule", "1.0.0", ["$e", "$status"]]],
    "query_rel": "example_query",
    "engine": "souffle"
  }
}
```

  这不会改变 outer DTO；exporter 在编译 `rules/idb.dl` 时使用调用方提供的
  in-memory rule resolver 展开 composed query。
- 当 `package_kind="audit"` 时，当前 package 还会额外包含：
  - `audit/support_artifacts.jsonl`
  - `audit/rule_trace_artifacts.jsonl`
  - `audit/certainty_summaries.jsonl`（可选 — 当 candidate certainty 可由 runtime 内存数据派生时写入）
  - `audit/provenance_trees.jsonl`（可选 — 当 accepted candidate 仍可通过当前 session 的 `run_id`-keyed derivation recipe replay 成 query-bearing Souffle package，并能匹配到具体 output row 时写入）
  - `audit/provenance_statuses.jsonl`（可选 — 当 `package_kind="audit"` 时与 provenance materialization 同步写入，按 candidate 记录 `present | missing_recipe | export_failed | no_matching_row | explain_failed` 等状态）
  - `audit/evidence_graphs.jsonl`（可选 — 当 accepted candidate 的 engine provenance / proof tree 可在 export-time 确定性转换为 `EvidenceGraph` 时写入）
  前两个文件分别导出 `SupportArtifact` 与 `RuleTraceArtifact` 的 flat JSONL rows，用于离线 audit / explain 消费。
  `certainty_summaries.jsonl` 导出 export-time 预计算的 `certainty_summary` dict（每行 `{candidate_id, certainty_summary}`），因为 `condition_weights` 只在 registry filesystem 可用、离线 audit 无法 query-time 派生。
  `condition_weights` 不作为 engine adapter 参数导出；它是 runtime
  certainty/explain projection input，未来运行时配置归
  `SemanticsProfile.certainty_projection`。
  routing 与 delivery 分开：candidate 必须先在 evaluate 时被内部标成 `confidence_kind="certainty"`，export 才会继续物化 certainty summary。
  `provenance_trees.jsonl` 导出 runtime export-time replay 的 Souffle proof tree dict（每行 `{candidate_id, provenance_tree}`）；缺少 recipe、query export 失败、Souffle explain 失败或无法匹配 output row 的 candidate 会被静默跳过，不影响整个 package export。
  `provenance_statuses.jsonl` 导出同一轮 replay 的 per-candidate status rows（含 `engine`、`truncated`、可选 `reason`）；它让离线 audit consumer 能区分“有 provenance”、“没有 provenance”以及“为什么没有”，而不是把所有缺失都折叠成静默空白。
  `evidence_graphs.jsonl` 导出统一 explain DTO（每行 `{candidate_id, evidence_graph}`）；当前来源包括 Souffle proof tree replay、PyReason provenance envelope event log、以及 ProbLog provenance envelope proof trace。旧 package 没有这个文件时，static UI 仍会对 Souffle 保留基于 `provenance_trees.jsonl` 的 fallback。
  - `audit/provenance_timelines.jsonl`（可选 — 当 accepted candidate 的 `support_kind="pyreason_provenance_v1"` 且 provenance envelope 可在 export-time 转换为 `CandidateProvenanceTimeline` 时写入）
  `provenance_timelines.jsonl` 导出 PyReason candidate 的高保真 timeline DTO（每行 `{candidate_id, provenance_timeline}`）；这是 `AuditQuery.get_candidate_provenance_timeline()` 的 durable 数据源。non-pyreason candidate 不写入此文件。

错误 kinds：

- `shape`
- `runtime_session_not_found`
- `runtime`

## 相关文档

- `01_overview.md`
- `02_runtime_sessions.md`
- `04_rules_registry.md`
