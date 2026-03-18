# Task Blueprint: Audit Rule-Run Explain Summary Export

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/__init__.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_runtime-rule-run-explain-summary-api.md](../archive/2026-03-18_runtime-rule-run-explain-summary-api.md)
  - [2026-03-18_scenario-a-audit-delivery-shape.md](../archive/2026-03-18_scenario-a-audit-delivery-shape.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_audit-rule-run-explain-summary-export.audit.md](./2026-03-18_audit-rule-run-explain-summary-export.audit.md)

## 1. Problem

runtime 侧已经有 `rule_run_summary` JSON DTO，但 audit 侧当前仍只有两种消费面：

- raw `audit/rule_trace_artifacts.jsonl`
- static HTML rule trace pages

这意味着离线 consumer 如果想拿到与 runtime 等价的 summary 形态，只能：

- 自己重新实现一遍 `rule_run_summary` 的 grouping / dedupe 逻辑
- 或退回 HTML / detail page drill-down

这两条都不合适。

当前更合理的目标是把 audit 侧也补齐为一个 **derived summary surface**：

- 不改 raw audit package contract
- 不把 HTML 变成唯一消费面
- 让 runtime 和 audit 共享同一个 `rule_run_summary` contract

## 2. Goals

- 为 audit package / query 层提供与 runtime `rule_run_summary` 同构的 derived DTO。
- 保证 audit summary 与 runtime summary 在字段集和语义上保持一致。
- 保持 audit summary 为 raw `rule_trace_artifacts` 的纯派生。
- 为离线 consumer 提供 machine-readable summary，而不是只剩 HTML drill-down。

## 3. Non-goals

- 不修改 `rule_trace_artifacts.jsonl` 的 raw shape。
- 不新增 `rule_trace_summaries.jsonl` 或其他新的 audit artifact 文件。
- 不修改 runtime `rule_run_summary` 的 7 字段 contract。
- 不把 `candidate` / `assertion` summary 一起拉进来。
- 不把 static UI 的 HTML 页面重构成新的 primary contract。
- 不做 NL explain。

## 4. Current Context

- `runtime-rule-run-explain-summary-api` 已归档：
  - `POST /queries/explain-summary` 已提供 `rule_run_summary`
  - summary 为纯派生，字段固定为 7 个
  - grouping 已冻结：
    - `predicate_witness_groups` 按 `pred_id`
    - `non_fact_step_groups` 按 `kind`
- `audit.reader` 已把 `rule_trace_artifacts.jsonl` 纳入正式读取面。
- `AuditQuery` 当前已提供：
  - `list_rule_traces(...)`
  - `get_rule_trace(...)`
  但返回的仍是 raw trace row。
- `audit.dto` / static UI 当前能消费 raw trace/detail，但还没有与 runtime 同构的 `rule_run_summary` 机器消费面。
- 现有 `service.runtime_v1._summarize_rule_run_explain(...)` 已经是 `dict -> dict` 的纯函数，不依赖 session 或 runtime state；这意味着 runtime/audit parity 可以通过 shared summarizer 或严格同构逻辑实现。

## 5. Proposed Shape

### 5.1 Positioning

这条蓝图是 **runtime/audit summary parity** 切片，不是新的 carrier 或新的 delivery shape 切片。

第一轮目标很窄：

- runtime raw explain contract 不变
- audit raw package contract 不变
- 在 audit 侧补一个与 runtime 同构的 `rule_run_summary` 派生面

### 5.2 Export Direction

第一轮不新增新的 audit artifact 文件，而是在 read/query 层从现有 `rule_trace_artifacts.jsonl` 派生 summary。

adopted direction 倾向应是：

- raw source of truth:
  - `audit/rule_trace_artifacts.jsonl`
- derived summary surface:
  - `AuditQuery` / `audit.dto` 层

这样做的好处是：

- audit package manifest 不需要扩容新的 summary 文件
- runtime summary 和 audit summary 都依赖同一类 raw trace payload
- 避免出现 raw trace / summary artifact 双份 durable contract

### 5.3 Parity Contract

audit `rule_run_summary` 应与 runtime `rule_run_summary` 完全同构：

- `rule_run_id`
- `root_rule`
- `root_row_count`
- `invocation_count`
- `witness_assertion_ids`
- `predicate_witness_groups`
- `non_fact_step_groups`

这里的关键约束是：

- audit summary 不能新增 runtime summary 没有的字段
- audit summary 也不能弱化 runtime summary 的字段语义
- runtime/audit 两侧都必须能把每个 summary 字段追溯回 raw trace payload

换句话说，第一轮不是“做一个 audit 风格 summary”，而是“在 audit 侧导出 runtime 已冻结的 summary contract”。

### 5.4 Surface Direction

第一轮更合适的 surface 应该在 `AuditQuery` 和 `audit.dto`，而不是先改 static UI：

- query layer
  - `get_rule_trace_summary(rule_run_id)`
  - 可选：`list_rule_trace_summaries(root_rule_id=...)`
- dto layer
  - 为离线 consumer 提供 machine-readable summary payload
  - 保持与现有 raw trace/detail DTO 并存，不互相替代

这条方向意味着：

- static HTML rule trace pages 可以暂时不改
- 现有 `build_rule_trace_list_dto(...)` / `build_rule_trace_detail_dto(...)` 不必被 summary 取代
- summary 是新的消费面，不是对现有 audit UI contract 的破坏性替换

### 5.5 Shared Summarizer Ownership

**Adopted direction：shared summarizer owner 放在 `factpy_kernel.core.rules._trace`。**

具体落点：

- 在现有 `src/factpy_kernel/core/rules/_trace.py` 中新增：
  - `summarize_rule_trace_artifact_dict(explain: dict[str, Any]) -> dict[str, Any]`
- 相关的 `pred_atom_key -> pred_id` 提取 helper 也一并迁入 `core.rules._trace`

理由：

- `_trace.py` 已经拥有 `RuleTraceArtifact` 和 `rule_trace_artifact_to_dict()`，summary 本身就是该 dict payload 的纯派生。
- 依赖方向正确：
  - `core` ← `service`
  - `core` ← `audit`
- 不需要新建额外顶层模块，也不需要让 `audit` 反向 import `service.runtime_v1`。
- 避免 runtime/audit 各自复制 grouping / dedupe 逻辑后再靠 parity tests 兜底。

第一轮迁移方向因此固定为：

- `service.runtime_v1`
  - 不再拥有 canonical summarizer，只调用 `core.rules._trace` 的 shared helper
- `audit.query` / `audit.dto`
  - 直接调用同一个 shared helper

这也意味着：

- runtime/audit summary parity 主要由共享同一个 summarizer 在源码层保证
- audit 侧仍需要正常的功能测试，但不再需要“复制两份逻辑后靠 parity test 校准”的设计

## 6. Boundaries And Invariants

- 必须保持的边界：
  - raw runtime explain contract 不变
  - raw audit package contract 不变
  - audit summary 只来自 raw `rule_trace_artifacts`
- 明确不做的内容：
  - 不新增 durable summary artifact
  - 不把 static HTML 页面定义成 canonical summary contract
  - 不扩展到 `candidate` / `assertion`
- 兼容性约束：
  - runtime summary 的 7 字段 contract 不能被这条蓝图改写
  - 现有 audit trace list/detail DTO 和 static pages 不应被破坏

## 7. Acceptance

- [x] audit 侧已能提供与 runtime 同构的 `rule_run_summary`
- [x] audit summary 不依赖新的 durable artifact 文件
- [x] runtime/audit summary parity 已由测试锁定
- [x] raw runtime/audit contracts 都保持不变
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 把 `rule_run_summary` 的 canonical 派生逻辑迁到 `src/factpy_kernel/core/rules/_trace.py`，并让 runtime summary 改为消费 shared helper。
2. 在 `AuditQuery` / `audit.dto` 上暴露 audit-side `rule_run_summary`，输入继续只来自现有 `rule_trace_artifacts.jsonl`。
3. 补功能测试并同步 audit docs，明确 summary 是 derived surface，不是新的 package artifact。

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/01_overview.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若需要补 cross-reference）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `rule_run_summary` 的 canonical 派生逻辑已迁入 `src/factpy_kernel/core/rules/_trace.py`，由 `summarize_rule_trace_artifact_dict(...)` 统一拥有。
  - `src/factpy_kernel/service/runtime_v1.py` 已改为消费 shared summarizer；raw runtime explain contract 没有变化。
  - `AuditQuery` 新增：
    - `get_rule_trace_summary(rule_run_id)`
    - `list_rule_trace_summaries(...)`
  - `audit.dto` 新增：
    - `build_rule_trace_summary_dto(...)`
    - `build_rule_trace_summary_list_dto(...)`
  - audit docs 已明确：summary 只从现有 `rule_trace_artifacts.jsonl` 派生，不新增 durable summary artifact。
  - tests 已覆盖 shared helper、runtime summary、audit summary、dto builder 的同构输出。
- 与 blueprint 不同的地方：
  - 无。
- 为什么会有这些调整：
  - 不适用。本轮实现与 scoped blueprint 一致。
- 归档说明：
  - blueprint 已在 code/docs/tests 对齐后归档到 `docs/blueprints/archive/2026-03-18_audit-rule-run-explain-summary-export.md`。
