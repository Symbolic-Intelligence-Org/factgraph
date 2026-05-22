# Task Blueprint: Rule-Run Explain Narrative

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/core/rules/_trace_narrative.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_runtime-rule-run-explain-summary-api.md](../archive/2026-03-18_runtime-rule-run-explain-summary-api.md)
  - [2026-03-18_audit-rule-run-explain-summary-export.md](../archive/2026-03-18_audit-rule-run-explain-summary-export.md)
  - [2026-03-18_scenario-a-audit-delivery-shape.md](../archive/2026-03-18_scenario-a-audit-delivery-shape.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_rule-run-explain-narrative.audit.md](./2026-03-18_rule-run-explain-narrative.audit.md)

## 1. Problem

当前 `rule_run` explain 已经有三层稳定面：

- raw contract
- `rule_run_summary`
- static proof-entry page：`rule_traces/{rule_run_id}.html`

但 proof-entry page 仍然主要展示结构化字段、列表和 drill-down link，缺少一个 **人可以第一眼读懂的 narrative layer**。

结果是：

- 机器消费可以直接走 raw / summary
- 人类消费仍需要自己把：
  - root rule
  - root row count
  - predicate witness groups
  - non-fact checks
  - assertion drill-down
  手工拼成“这次 rule run 说明了什么”

在 substrate 已冻结的前提下，当前最自然的增量价值不是再扩 carrier，而是补一层 **deterministic narrative**：

- 只从现有 summary/raw 派生
- 不引入 LLM
- 可测试、可 diff、可版本化
- 先服务 audit/static proof-entry page

## 2. Goals

- 为 `rule_run` 提供 deterministic narrative renderer。
- first-round 只在 audit/static proof-entry page 落地 narrative block。
- narrative 的每一句都能追溯回现有 `rule_run_summary` 字段。
- narrative renderer 由 shared helper 拥有，避免 runtime/audit/static 各自拼文案。

## 3. Non-goals

- 不引入 LLM 或任何非确定性生成。
- 不修改 raw `rule_run` contract 或 `rule_run_summary` 的 7 字段 contract。
- 不先做 runtime narrative API。
- 不把 `candidate` / `assertion` narrative 一起拉进来。
- 不把 narrative 反向定义成新的 explain carrier。
- 不重做 static rule trace 页面整体布局。

## 4. Current Context

- `runtime-structured-json-explain-api` 已冻结 raw `rule_run` explain contract。
- `runtime-rule-run-explain-summary-api` 已冻结 `rule_run_summary` 的 7 字段 consumer DTO。
- `audit-rule-run-explain-summary-export` 已让 audit 侧获得与 runtime 同构的 summary surface。
- `scenario-a-audit-delivery-shape` 已把 `rule_traces/{rule_run_id}.html` 变成 static proof-entry page。
- 当前 static page 已具备：
  - raw trace detail
  - witness assertion drill-down
  - shareable rule trace URL
  但没有 first-pass narrative block。
- Rainbird 参考在这一轮最相关的不是 certainty，而是：
  - proof entry point 之后要有“人能直接读懂”的第一层 evidence narrative

## 5. Proposed Shape

### 5.1 Positioning

这条蓝图是一个 **derived presentation layer** 切片。

它不改变：

- raw `rule_run` explain
- `rule_run_summary`
- static proof-entry page 的 drill-down structure

它只新增一层 deterministic narrative，用来回答：

- 这次 rule run 的核心结论是什么
- 主要涉及了哪些 predicate witnesses
- 主要涉及了哪些 non-fact checks
- 用户下一步应从哪里 drill down

### 5.2 First-round Surface

first-round surface 只选 **audit/static**：

- narrative block 嵌入 `rule_traces/{rule_run_id}.html`
- 不新增 runtime endpoint
- 不新增新的 durable artifact

这条方向的好处是：

- proof-entry page 已经存在，是最短路径
- 离线 consumer 拿到 audit package 后就能直接看到 narrative
- narrative block 可以建立在已完成的 runtime/audit summary parity 之上，而不必重新定义 live session contract

### 5.3 Input Contract Direction

first-round narrative renderer 应该 **只依赖 `rule_run_summary`**，不直接消费 raw trace。

理由：

1. `rule_run_summary` 已经是冻结过的 consumer-facing contract。
2. 若 narrative 需要回头依赖 raw trace，说明当前 summary 还不够；这应先在 summary 层解决，而不是让 narrative 偷偷下探 carrier。
3. 这让 narrative renderer 后续更容易被 runtime/audit 共同复用。

因此，第一轮 narrative block 的所有句子都应只从以下 7 个字段派生：

- `rule_run_id`
- `root_rule`
- `root_row_count`
- `invocation_count`
- `witness_assertion_ids`
- `predicate_witness_groups`
- `non_fact_step_groups`

### 5.4 Output Shape

第一轮 narrative renderer 不应返回单个 opaque string，而应返回 **结构化 narrative DTO**，再由 static UI 渲染。

第一轮 narrative DTO 收敛为 5 个字段：

- `headline`
- `overview_lines`
- `predicate_lines`
- `non_fact_check_lines`
- `drilldown_lines`

说明：

- narrative caller 已经持有 `rule_run_id`，因此 narrative DTO 自身不重复回传该 id
- 上述 5 个字段都是 presentation content：
  - `headline` 为单条 `str`
  - 其余 4 项为 `list[str]`

其中每一行都是 deterministic sentence，例如：

- `headline`
  - `Rule q.foo@1.0.0 produced 1 root row across 3 invocations.`
- `overview_lines`
  - witness assertion 总数
  - predicate group 总数
  - non-fact check group 总数
- `predicate_lines`
  - 每个 `pred_id` 各一行
- `non_fact_check_lines`
  - 每个 `kind` 各一行
- `drilldown_lines`
  - 指向 assertion detail / existing rule trace detail 的下一步阅读提示

这样做的目的不是把 narrative 复杂化，而是：

- 保持 deterministic
- 便于测试每一行
- 便于 static UI 选择如何排版
- 为未来 runtime API 暴露 narrative 保留复用空间

### 5.5 Shared Renderer Ownership

**Adopted direction：narrative renderer owner 放在 `factpy_kernel.core.rules._trace_narrative`。**

具体落点：

- 新增 `src/factpy_kernel/core/rules/_trace_narrative.py`
- owner function：
  - `render_rule_run_narrative(summary: dict[str, Any], *, locale: str = "en") -> dict[str, Any]`

理由：

- narrative 是从 `rule_run_summary` 派生的 shared deterministic layer，不应留在 `audit.static_ui`
- 但它又不同于 `_trace.py` 当前负责的 artifact serialization / summary derivation，可以单独收一个更清晰的 presentation helper
- 依赖方向仍然正确：
  - `core` ← `audit`
  - 后续若有 runtime narrative surface，也可以复用同一个 renderer

`locale` 在 first-round 中只作为签名预留：

- 默认值为 `"en"`
- 当前实现可以先忽略非英文值
- 这样后续若新增中文模板，不需要 break 函数签名

## 6. Boundaries And Invariants

- 必须保持的边界：
  - raw `rule_run` contract 不变
  - `rule_run_summary` 的 7 字段 contract 不变
  - narrative 只从 summary 派生
- 明确不做的内容：
  - 不做 LLM
  - 不新增 narrative artifact 文件
  - 不把 runtime API 拉进 first round
- 兼容性约束：
  - narrative block 不应破坏现有 static proof-entry page 的 raw trace / assertion drill-down

## 7. Acceptance

- [x] deterministic narrative renderer 已存在，且只依赖 `rule_run_summary`
- [x] `rule_traces/{rule_run_id}.html` 已嵌入 narrative block
- [x] 每条 narrative sentence 都可追溯回 summary fields
- [x] raw explain / summary contracts 都保持不变
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 在 `core.rules._trace_narrative` 中实现 deterministic renderer，并固定 5 字段 narrative DTO + `locale` 预留签名。
2. 让 audit/static proof-entry page 消费 narrative DTO，并把 block 嵌入 `rule_traces/{rule_run_id}.html`。
3. 补 narrative rendering tests，并同步 audit docs。

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/01_overview.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（若需要补 shared renderer owner）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - 新增 `src/factpy_kernel/core/rules/_trace_narrative.py`，由 `render_rule_run_narrative(summary, *, locale="en")` 统一拥有 deterministic narrative rendering。
  - narrative 只消费 `rule_run_summary` 的 7 个字段，输出固定 5 个 presentation 字段：`headline`、`overview_lines`、`predicate_lines`、`non_fact_check_lines`、`drilldown_lines`。
  - `src/factpy_kernel/audit/static_ui.py` 已在 `rule_traces/{rule_run_id}.html` 顶部嵌入 narrative block，放在现有 raw trace detail 之前。
  - `src/factpy_kernel/audit/docs/01_overview.md` 与 `src/factpy_kernel/core/docs/01_architecture.md` 已同步 narrative owner 与 static proof-entry behavior。
  - tests 已覆盖 deterministic renderer 输出和 static proof-entry page 中的 narrative block。
- 与 blueprint 不同的地方：
  - 无。
- 为什么会有这些调整：
  - 不适用。本轮实现与 scoped blueprint 一致。
- 归档说明：
  - blueprint 已在 code/docs/tests 对齐后归档到 `docs/blueprints/archive/2026-03-18_rule-run-explain-narrative.md`。
