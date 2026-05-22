# Task Blueprint: Runtime Rule-Run Explain Summary API

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_runtime-structured-json-explain-api.md](../archive/2026-03-18_runtime-structured-json-explain-api.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_runtime-rule-run-explain-summary-api.audit.md](./2026-03-18_runtime-rule-run-explain-summary-api.audit.md)

## 1. Problem

`rule_run` 的 raw structured JSON explain contract 已经冻结，但它仍然更像 carrier-level payload，而不是 consumer-facing summary DTO。

当前 consumer 若只想回答下面这类问题：

- 这次 rule run 的根规则是什么？
- 命中了多少 root rows？
- 涉及哪些 assertion witnesses？
- 哪些 predicate witnesses / non-fact checks 参与了这次结论？
- 从 summary 如何回跳到 raw explain 或 assertion detail？

就必须直接消费完整 raw `rule_run` payload，包括：

- `invocations` flat list
- per-invocation `pred_witnesses`
- per-invocation `non_fact_steps`
- opaque `original_where` / `rewritten_where`

这对 first-round consumer 来说过重，也会让消费方过早依赖 raw carrier 的内部细节。

因此，需要一条更窄的、纯派生的 summary API：

- 不修改 raw explain contract
- 不在 raw endpoint 上叠加 `format=summary`
- 只提供一个更易消费的 `rule_run_summary` DTO

## 2. Goals

- 为 `rule_run` 提供独立的 consumer-facing summary endpoint。
- summary DTO 必须是 raw `rule_run` explain payload 的纯派生。
- 为 consumer 提供明确的回跳 handle：
  - `rule_run_id`
  - `asrt_ids`
- 第一轮只做 `rule_run`，不把 `candidate` / `assertion` 一起拉进来。

## 3. Non-goals

- 不修改现有 raw `rule_run` payload。
- 不在现有 `POST /queries/explain` 上新增 `format=summary` 参数。
- 不把 summary 反向定义成新的 proof carrier contract。
- 不统一 runtime summary DTO 与 audit summary DTO。
- 不做 `candidate` / `assertion` summary。
- 不做 `NL explain`。

## 4. Current Context

- `runtime-structured-json-explain-api` 已归档，当前真相已经明确：
  - canonical = `POST /queries/explain` + `kind="rule_run"`
  - legacy = `POST /queries/explain-rule-trace`
  - 两条路径 `explain` payload identical
  - `invocations` 是 stable flat list + id-linkage
  - `details.binding` stable，`details.atom` opaque
- 当前 runtime 实现已经能稳定返回 raw `rule_run` payload。
- 当前 static audit delivery 已经把 `rule_run_id` 变成 proof-entry page，但 live service 侧还没有单独的 summary DTO。
- Rainbird 参考在这一轮最相关的不是 certainty 机制，而是：
  - structured consumer API 的存在本身
  - result/proof entry 的更窄消费形态

## 5. Proposed Shape

### 5.1 Positioning

这条蓝图是一个 **consumer-facing derived DTO** 切片。

它不改变 raw `rule_run` contract，只在其上叠加一个更窄的派生层。

第一轮应保持两个面分离：

- raw explain API
  - carrier-facing
  - 完整 `rule_run` payload
- summary explain API
  - consumer-facing
  - 只暴露 first-round消费真正需要的聚合字段

### 5.2 Endpoint Direction

第一轮建议新增单独 summary endpoint，而不是在既有 raw endpoint 上增加 `format=summary`：

- provisional endpoint:
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-summary`
- request shape:
  - `{"kind":"rule_run","id":"..."}`

这条方向的目标是保持 raw contract 的纯净性：

- raw endpoint 继续只承载 raw `rule_run` explain object
- summary endpoint 明确承载 derived DTO
- summary endpoint 内部直接复用 canonical raw explain path，不重复实现 explain carrier lookup

### 5.3 Derivation Boundary

summary DTO 必须满足下面三条边界：

1. **pure derivation**
   - 每个 summary 字段都必须能从 canonical raw `rule_run` payload 直接计算出来
   - 不允许新增需要额外 runtime semantics 的字段

2. **no back-pressure on carrier**
   - summary 不能反向要求 raw payload 改 shape
   - 若某个 summary 字段需要 raw payload 新增字段，这通常意味着该字段不应进入第一轮 summary

3. **drill-down handles stay explicit**
   - summary 不是 explain 终点
   - consumer 必须能从 summary 回跳到：
     - raw `rule_run_id`
     - witness `asrt_ids`

### 5.4 First-round DTO Shape

第一轮 `rule_run_summary` 至少应考虑包含：

- `rule_run_id`
- `root_rule`
- `root_row_count`
- `invocation_count`
- `witness_assertion_ids`
- `predicate_witness_groups`
- `non_fact_step_groups`

这里的核心约束是：

- `witness_assertion_ids` 应是去重后的 flat set/list
- `predicate_witness_groups` / `non_fact_step_groups` 应只使用 stable raw fields 派生
- 不把 `original_where` / `rewritten_where` 或 `details.atom` 变成 summary 的核心字段
- `rule_run_id` 本身就是充分的 raw explain 回跳 handle，不再额外包装成 `raw_ref`
- consumer 可直接使用 `witness_assertion_ids` 调用 `explain_ref(kind="assertion", id=...)`，不再单独提供 `assertion_refs`

### 5.5 Grouping Question To Resolve

**Adopted direction：summary groups 使用 flat semantic key + back-links，不按 `invocation_id` 作为主聚合维度。**

理由：

1. summary 的消费问题是“这次 rule run 涉及了哪些 predicates 和哪些 checks”，不是“每个 invocation 内部发生了什么”。
2. 按 `invocation_id` 聚合本质上仍然贴着 raw carrier shape，不能显著降低消费复杂度。
3. `pred_atom_key`（例如 `b0.a0:...`）对 consumer 来说过于底层；summary 更适合按从 `pred_atom_key` 提取出来的 `pred_id` 聚合。

第一轮采用的 summary grouping shape：

- `predicate_witness_groups`
  - grouping key：`pred_id`
  - group fields：
    - `pred_id`
    - `asrt_ids`
    - `invocation_ids`
- `non_fact_step_groups`
  - grouping key：`kind`
  - group fields：
    - `kind`
    - `count`
    - `invocation_ids`

这条 adopted direction 也意味着：

- `binding_index` 不进入 first-round summary groups；它属于 raw payload 的消费粒度。
- `step_key` 不作为 first-round `non_fact_step_groups` 的主 grouping key；它仍保留在 raw payload 中供更深消费方使用。
- summary 的 group 只保留最小 back-links：
  - `predicate_witness_groups[*].invocation_ids`
  - `non_fact_step_groups[*].invocation_ids`

第一轮 `rule_run_summary` 因此收敛为 7 个字段：

- `rule_run_id`
- `root_rule`
- `root_row_count`
- `invocation_count`
- `witness_assertion_ids`
- `predicate_witness_groups`
- `non_fact_step_groups`

## 6. Boundaries And Invariants

- 必须保持的边界：
  - raw `rule_run` contract 完全不变
  - summary 只依赖 canonical raw explain path
  - summary 字段只能来自 stable raw fields 或 allowed opaque passthrough 的安全子集
- 明确不做的内容：
  - 不为 summary 增加新的 carrier semantics
  - 不把 audit static delivery 一起并入
  - 不做 NL generation
- 兼容性约束：
  - summary endpoint 不应影响既有 raw endpoint、legacy alias 或 tests

## 7. Acceptance

- [x] summary endpoint 与 raw endpoint 已明确分离
- [x] `rule_run_summary` 每个字段都能追溯回 raw payload
- [x] raw `rule_run` contract 保持不变
- [x] tests 能锁定 raw→summary parity
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 收敛 summary endpoint 形态和 request shape。
2. 收敛 `rule_run_summary` 的字段集与 grouping 维度。
3. 若切到 `scoped`，再实现 endpoint、docs、tests。

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - 新增 `POST /v1/runtime/sessions/{session_id}/queries/explain-summary`，仅接受 `{"kind":"rule_run","id":"..."}`。
  - summary endpoint 内部直接复用 canonical `explain_ref(kind="rule_run")`，并以纯派生方式生成 `rule_run_summary`。
  - 第一轮 `rule_run_summary` 按 blueprint 收敛为 7 个字段：`rule_run_id`、`root_rule`、`root_row_count`、`invocation_count`、`witness_assertion_ids`、`predicate_witness_groups`、`non_fact_step_groups`。
  - `predicate_witness_groups` 按从 `pred_atom_key` 提取的 `pred_id` 聚合；`non_fact_step_groups` 按 `kind` 聚合；两者都只保留最小 back-links。
  - service docs 已同步把 summary endpoint 及其 stable 派生规则写成当前真相；service-level tests 已锁定 raw→summary parity 和 HTTP route shape。
- 与 blueprint 不同的地方：
  - 无。
- 为什么会有这些调整：
  - 不适用。本轮实现与 scoped blueprint 一致。
- 归档说明：
  - blueprint 已在 code/docs/tests 对齐后归档到 `docs/blueprints/archive/2026-03-18_runtime-rule-run-explain-summary-api.md`。
