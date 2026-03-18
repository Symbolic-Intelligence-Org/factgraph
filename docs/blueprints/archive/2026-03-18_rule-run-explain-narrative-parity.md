# Task Blueprint: Rule-Run Explain Narrative Parity

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/rules/_trace_narrative.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_runtime-rule-run-explain-summary-api.md](../archive/2026-03-18_runtime-rule-run-explain-summary-api.md)
  - [2026-03-18_audit-rule-run-explain-summary-export.md](../archive/2026-03-18_audit-rule-run-explain-summary-export.md)
  - [2026-03-18_rule-run-explain-narrative.md](../archive/2026-03-18_rule-run-explain-narrative.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_rule-run-explain-narrative-parity.audit.md](./2026-03-18_rule-run-explain-narrative-parity.audit.md)

## 1. Problem

`rule_run` explain 的 delivery 现在已经有：

- raw contract
- summary contract
- shared deterministic narrative renderer
- static proof-entry page 中的 narrative block

但 narrative 仍然只是一层 **presentation behavior**，还不是一个正式的 consumer-facing contract。

这会产生一个不对称状态：

- runtime 侧：
  - raw explain 有 public surface
  - summary 有 public surface
  - narrative 没有 public surface
- audit 侧：
  - raw trace row 有读取面
  - summary 有 query/dto surface
  - narrative 只存在于 static HTML page 内部

因此，当前还缺一条很窄的 parity 切片：

- 把 narrative 从“shared rendering capability”提升为“runtime + audit 都可机器消费的同构 DTO”
- 让 static UI 也改为消费这条 DTO，而不是直接把 renderer 当作内部实现细节

## 2. Goals

- 为 `rule_run` narrative 提供 runtime + audit 同构的 consumer-facing surface。
- narrative contract 必须继续是 deterministic pure derivation。
- static proof-entry page 改为消费 audit narrative DTO，而不是直接调用 renderer。
- 第一轮只做 `rule_run` narrative，不扩到其他 explain object。

## 3. Non-goals

- 不修改 raw `rule_run` explain contract。
- 不修改 `rule_run_summary` 的 7 字段 contract。
- 不修改 shared narrative renderer 的 5 字段 output shape。
- 不引入 LLM 或自由文本生成。
- 不扩到 `candidate` / `assertion` narrative。
- 不把 static HTML 页面当作 narrative 的唯一 canonical surface。

## 4. Current Context

- `runtime-structured-json-explain-api` 已冻结 raw `rule_run` contract。
- `runtime-rule-run-explain-summary-api` 已冻结 runtime `rule_run_summary` surface。
- `audit-rule-run-explain-summary-export` 已让 audit 侧获得同构 summary surface。
- `rule-run-explain-narrative` 已实现：
  - `core.rules._trace_narrative.render_rule_run_narrative(summary, *, locale="en")`
  - static proof-entry page 顶部 narrative block
- 当前 narrative 是 shared helper + static page behavior，但还没有：
  - runtime narrative endpoint
  - audit narrative query/dto surface
- 由于 renderer 已位于 `core`，runtime 和 audit 都能以低成本接入同一个 deterministic DTO。

## 5. Proposed Shape

### 5.1 Positioning

这条蓝图是一个 **narrative contract parity** 切片，不是新的 carrier、不是新的 summary、也不是新的 HTML 设计切片。

它的核心任务只有一个：

- 让现有 narrative renderer 的输出，成为 runtime + audit 都显式承诺的 public consumer contract

### 5.2 Runtime Surface Direction

第一轮 runtime 侧建议新增一个独立 endpoint，而不是复用 `explain` / `explain-summary`：

- provisional endpoint:
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-narrative`
- request shape:
  - `{"kind":"rule_run","id":"..."}`

这条方向与 raw / summary 的分层保持一致：

- raw:
  - `POST /queries/explain`
- summary:
  - `POST /queries/explain-summary`
- narrative:
  - `POST /queries/explain-narrative`

第一轮 runtime endpoint 只支持 `kind="rule_run"`。

本轮明确 **不** 采用 `POST /queries/explain-summary` + `include_narrative=true` 的 bundled 形态。原因是：

- `rule_run_summary` contract 刚刚冻结，第一轮不应立即把它变成带 optional `narrative` payload 的条件化 surface
- runtime/audit parity 在“独立 narrative surface”下更清晰：
  - runtime：`explain-narrative`
  - audit：`get_rule_trace_narrative(...)` / DTO
- static UI 也更适合消费“独立 narrative DTO”，而不是“summary + optional narrative” bundle

若后续确认 consumer 高频需要一次请求同时拿到 summary + narrative，再单独评估 bundled delivery 是否值得进入下一轮优化。

### 5.3 Audit Surface Direction

第一轮 audit 侧 surface 建议落在 `AuditQuery` + `audit.dto`：

- `AuditQuery.get_rule_trace_narrative(rule_run_id)`
- `build_rule_trace_narrative_dto(query, rule_run_id)`

是否需要 `list_rule_trace_narratives(...)`，第一轮不必默认纳入；当前 narrative 的主要消费面是 per-rule-run proof-entry，而不是 narrative index。

这样做的结果是：

- runtime narrative 有正式 machine-readable surface
- audit narrative 也有正式 machine-readable surface
- static UI 再消费 audit dto，而不是自己直接碰 renderer

### 5.4 Contract Boundary

narrative contract 必须保持两条边界：

1. **pure derivation from summary**
   - runtime narrative 先拿 `rule_run_summary`，再调用 shared renderer
   - audit narrative 也先拿 `rule_run_summary`，再调用 shared renderer
   - narrative surface 不直接下探 raw trace

2. **shape freeze**
   - first-round narrative DTO 固定为 5 个字段：
     - `headline`
     - `overview_lines`
     - `predicate_lines`
     - `non_fact_check_lines`
     - `drilldown_lines`
   - runtime / audit / static 三处都不得擅自加字段或弱化字段语义

这意味着 parity 由两层共同保证：

- 共享同一个 renderer
- 共享同一个 5 字段 public DTO shape

### 5.5 Locale / Delivery Direction

第一轮 narrative parity 继续保留 `locale="en"` 作为 renderer 签名预留，但不在 runtime/audit surface 上引入复杂的 locale negotiation。

当前建议：

- shared renderer 继续保留：
  - `render_rule_run_narrative(summary, *, locale="en")`
- runtime / audit 第一轮都直接调用 `locale="en"`
- 若后续真的需要多语言 surface，再单独开 locale 交付切片

static UI 在这一轮中的角色应收紧为：

- 消费 audit narrative DTO
- 负责 HTML 呈现
- 不再作为 narrative contract 的 owner

## 6. Boundaries And Invariants

- 必须保持的边界：
  - raw contract 不变
  - summary contract 不变
  - shared renderer output shape 不变
- 明确不做的内容：
  - 不做 LLM
  - 不做 narrative artifact 文件
  - 不扩 narrative index/list delivery，除非实现证明确有必要
- 兼容性约束：
  - static proof-entry page 继续保留 narrative block
  - runtime/audit narrative 必须保持完全同构

## 7. Acceptance

- [x] runtime narrative endpoint 已提供 `rule_run` surface
- [x] audit query/dto 已提供同构 `rule_run_narrative`
- [x] static UI 已消费 audit narrative DTO，而不是直接调用 renderer
- [x] runtime/audit narrative parity 已由测试锁定
- [x] raw / summary / narrative 三层 contract 边界都保持清晰

## 8. Implementation Plan

1. 收敛 runtime narrative endpoint 和 audit narrative query/dto 的最小 surface。
2. 若切到 `scoped`，接入 shared renderer，并让 static UI 改为消费 audit narrative DTO。
3. 补 runtime/audit/static 三侧 narrative parity tests，并同步 docs。

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - runtime 新增独立 `POST /v1/runtime/sessions/{session_id}/queries/explain-narrative`，只支持 `kind="rule_run"`，并沿 `raw explain -> summary -> narrative renderer` 链路返回 5 字段 narrative DTO。
  - audit 新增 `AuditQuery.get_rule_trace_narrative(rule_run_id)` 与 `build_rule_trace_narrative_dto(...)`，与 runtime narrative 输出保持同构。
  - static proof-entry page 改为消费 audit narrative DTO，再将 narrative block 渲染到 `rule_traces/{rule_run_id}.html` 顶部。
  - narrative parity 已由 runtime route/shape、runtime↔audit parity、static page narrative block 测试共同锁定。
- 与 blueprint 不同的地方：
  - 除计划中的 service / audit docs 外，还同步更新了 `src/factpy_kernel/core/docs/01_architecture.md`，说明 shared narrative renderer 的 owner 与 deterministic presentation boundary。
- 为什么会有这些调整：
  - renderer owner 位于 `core.rules`，若只更新 service / audit docs，会让 owner 边界停留在代码里而未进入模块文档。
- 归档说明：
  - Blueprint 与 audit log 在代码和文档对齐后归档到 `docs/blueprints/archive/`。
