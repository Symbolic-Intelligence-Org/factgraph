# Task Blueprint: Runtime Service Explain Readback

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_support-artifact-readback.md](./2026-03-17_support-artifact-readback.md)
  - [2026-03-17_run-rule-trace-capture.md](./2026-03-17_run-rule-trace-capture.md)
- Audit Log:
  - [2026-03-17_runtime-service-explain-readback.audit.md](./2026-03-17_runtime-service-explain-readback.audit.md)

## 1. Problem

core 层的 explainability 基座现在已经有两条闭环：

- native derivation:
  - `Store.evaluate(...)`
  - `CandidateSet.support_digest`
  - `Store.explain_support(support_digest)`
- rule runtime:
  - `run_rule_with_trace(...)`
  - `rule_run_id`
  - `Store.explain_rule_trace(rule_run_id)`

但 service v1 仍然无法暴露这些能力。

当前 runtime service 的现状是：

- `/derivations/evaluate` 已返回 `support_digest`，但没有 explain-support endpoint
- `/rules/run` 只返回 rows，没有任何方式请求或返回 `rule_run_id`
- 没有 query endpoint 能读取 rule trace
- runtime explain 仍只覆盖 `explain_fact / conflicts / resolve_mapping / view-facts`

因此，在 HTTP/runtime session 这一层，explainability 仍然是断开的。

## 2. Goals

- 在 runtime service 中新增 session-scoped explain-support endpoint。
- 在 runtime service 中为 `/rules/run` 增加可选 `capture_trace` 开关，并在需要时返回 `rule_run_id`。
- 在 runtime service 中新增 session-scoped explain-rule-trace endpoint。
- 保持现有 service v1 风格一致：
  - `POST /v1/runtime/sessions/{session_id}/queries/...`
  - `HTTP 200` envelope
  - `ok_response(...)` / `error_response(...)`
  - DTO shape 校验通过 `facade_error(..., kind="shape", path=...)`
- 保持旧调用面兼容：
  - `capture_trace=false` 时 `/rules/run` 响应 shape 不变
  - 不强制旧客户端升级

## 3. Non-goals

- 不实现统一的 generic `explain_ref` 或 `/queries/explain` 总入口。
- 不实现 `candidate_id -> support_digest` 反查。
- 不实现 `row -> rule_run_id` 反查。
- 不处理 durable / cross-process artifact storage。
- 不处理 cross-session / cross-instance explain lookup。
- 不改 SDK 返回面或 SDK public API。

## 4. Current Context

- 当前 runtime query 风格集中在 [`src/factpy_kernel/service/runtime_v1.py`](../../../src/factpy_kernel/service/runtime_v1.py)：
  - `explain_runtime_fact(...)`
  - `list_runtime_conflicts(...)`
  - `resolve_runtime_mapping(...)`
  - `project_runtime_view_facts(...)`
- 对应的 `app_v1.py` 路由采用：
  - `POST /v1/runtime/sessions/{session_id}/queries/...`
  - `POST /v1/runtime/sessions/{session_id}/rules/run`
- 现有 handler 风格要点：
  - `dto` 必须是 object，否则报 `shape`
  - 成功时通常返回 `ok_response(meta=..., <payload>=...)`
  - query-style 响应 payload key 常用 `explain / conflicts / mapping / view`
  - session 不存在时统一走 `runtime_session_not_found`
- 当前 explain readback 基座：
  - `Store.explain_support(support_digest) -> dict | None`
  - `Store.explain_rule_trace(rule_run_id) -> dict | None`
- 当前 `/rules/run` 只调用 `run_rule(...)`，成功响应为：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "rule_id": "...",
    "version": "...",
    "rows": [...]
  }
}
```

## 5. Proposed Shape

### 5.1 New Query Endpoint: `explain-support`

新增：

```text
POST /v1/runtime/sessions/{session_id}/queries/explain-support
```

请求：

```json
{
  "support_digest": "sha256:..."
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "support_digest": "sha256:..."
  },
  "explain": {
    "kind": "native_binding_v1",
    "root_result_kind": "fact",
    "binding": [["$E", "idref_v1:Person:source_id=u1"], ["$C", "de"]],
    "pred_witnesses": [
      {"pred_atom_key": "b0.a0:person:country", "asrt_ids": ["A1"]}
    ],
    "non_fact_steps": []
  }
}
```

行为：

- 内部直接调用 `session.store.explain_support(support_digest)`
- 若 artifact 存在，返回 `meta + explain`
- 若 artifact 不存在，返回 explain-specific not-found error

### 5.2 Extend `/rules/run` With Optional `capture_trace`

在现有请求 DTO 上新增可选字段：

```json
{
  "rule": { "...": "existing shape" },
  "capture_trace": true
}
```

兼容约束：

- `capture_trace` 默认 `false`
- `false` 时响应保持当前形状，不返回 `trace`
- `true` 时内部改为调用 `run_rule_with_trace(...)`

成功响应扩展采用附属块，而不是平铺字段：

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "rule_id": "...",
    "version": "...",
    "rows": [...],
    "trace": {
      "rule_run_id": "..."
    }
  }
}
```

第一轮不做：

- `capture_trace=false` 时返回 `trace: null`
- 单独的 `trace_available` 布尔位
- rows 内嵌 row-level trace handle

### 5.3 New Query Endpoint: `explain-rule-trace`

新增：

```text
POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace
```

请求：

```json
{
  "rule_run_id": "..."
}
```

成功响应：

```json
{
  "ok": true,
  "errors": [],
  "meta": {
    "rule_run_id": "..."
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
        "rule": {"rule_id": "q_country_rows", "version": "1.0.0"},
        "memo_hit": false,
        "memo_source_invocation_id": null,
        "original_where": [["pred", "person:country", ["$e", "$c"]]],
        "rewritten_where": [["pred", "person:country", ["$e", "$c"]]],
        "bindings": [[["$c", "de"], ["$e", "idref_v1:Person:source_id=u1"]]],
        "output_rows": [["idref_v1:Person:source_id=u1", "de"]],
        "pred_witnesses": [
          {"binding_index": 0, "pred_atom_key": "b0.a0:person:country", "asrt_ids": ["A1"]}
        ],
        "non_fact_steps": []
      }
    ],
    "root_rows": [["idref_v1:Person:source_id=u1", "de"]]
  }
}
```

行为：

- 内部直接调用 `session.store.explain_rule_trace(rule_run_id)`
- 若 artifact 不存在，返回 explain-specific not-found error

### 5.4 Error Semantics

这一轮应显式区分两类 not-found：

- session 不存在：
  - 继续使用现有 `runtime_session_not_found`
- session 存在，但 explain artifact 不存在：
  - 使用新的 explain-specific error kind

当前建议：

- `runtime_explain_not_found`

典型细分场景：

- `support_digest` 格式合法，但当前 session 中不存在对应 support artifact
- `rule_run_id` 格式合法，但当前 session 中不存在对应 rule trace artifact

### 5.5 Session-Scoped Limitation

本轮 service explain 必须明确继承当前 core registry 的限制：

- explain readback 仅对**当前 session、当前进程内** artifact 有效
- session 被清理后，旧 handle 可能失效
- 横向扩展 / 多实例部署下，不保证另一个实例能解引用同一 handle

这不是 bug，而是当前 non-goal。

蓝图应明确写成：

- session-scoped
- in-process
- non-durable

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 新 explain 入口沿用当前 runtime query 风格：`POST /queries/...`
  - 不引入新的全局 explain route family
  - `/rules/run` 默认调用路径保持兼容
  - service 只消费 core 已有 readback，不重新解释 artifact schema
- 明确不做的内容：
  - 不做跨 session/cross-instance explain
  - 不做 artifact persistence
  - 不做 `GET` 版本 explain route
  - 不做 generic explain multiplexing
- 兼容性约束：
  - 现有 `/rules/run` 客户端在不传 `capture_trace` 时必须行为不变
  - 新 explain endpoints 只增加能力，不要求旧端点改 contract

## 7. Acceptance

- [x] `POST /queries/explain-support` 已接到 `Store.explain_support(...)`
- [x] `POST /queries/explain-rule-trace` 已接到 `Store.explain_rule_trace(...)`
- [x] `/rules/run` 支持可选 `capture_trace`
- [x] `capture_trace=false` 时 `/rules/run` 响应 shape 保持兼容
- [x] `capture_trace=true` 时返回 `result.trace.rule_run_id`
- [x] explain artifact miss 有明确的 explain-specific error kind
- [x] `service/docs/03_runtime_queries_views.md` 已同步

## 8. Implementation Plan

1. 在 `runtime_v1.py` 中新增两个 query handler：
   - `explain_runtime_support(...)`
   - `explain_runtime_rule_trace(...)`
2. 在 `app_v1.py` 中新增对应 POST routes。
3. 在 `runtime_v1.py` 中扩展 `run_runtime_rule(...)`：
   - 解析可选 `capture_trace`
   - `false` 时沿用 `run_rule(...)`
   - `true` 时调用 `run_rule_with_trace(...)`
   - 在 `result.trace.rule_run_id` 返回 handle
4. 增加 explain-specific not-found error 映射与 DTO 校验。
5. 更新 `service/docs/03_runtime_queries_views.md`。
6. 增加最小 service/runtime 测试或现有 contract test 覆盖。

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- 如有必要，`src/factpy_kernel/core/docs/01_architecture.md`
- 如有必要，`src/factpy_kernel/core/docs/01_architecture.en.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `runtime_v1.py` 新增 `explain_runtime_support(...)` 与 `explain_runtime_rule_trace(...)`
  - `app_v1.py` 新增两个 `POST /queries/...` route
  - `/rules/run` 新增可选 `capture_trace`，开启时返回 `result.trace.rule_run_id`
  - explain artifact miss 统一返回 `runtime_explain_not_found`
  - `service/docs/03_runtime_queries_views.md` 已同步新增 endpoints 与响应 shape
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已补 service explain contract test
- 与 blueprint 不同的地方：
  - 无实质偏移；实现基本按蓝图原样落地
- 为什么会有这些调整：
  - 不适用
- 归档说明：
  - 本轮 service explain readback 已实现并完成验证；后续 durable storage / generic explain 如需引用，可直接引用 archive 中的已完成记录，无需继续留在 active 目录
