# Task Blueprint: Rule-Run NL Explain

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/rules/_trace_nl.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_runtime-structured-json-explain-api.md](../archive/2026-03-18_runtime-structured-json-explain-api.md)
  - [2026-03-18_runtime-rule-run-explain-summary-api.md](../archive/2026-03-18_runtime-rule-run-explain-summary-api.md)
  - [2026-03-18_rule-run-explain-narrative-parity.md](../archive/2026-03-18_rule-run-explain-narrative-parity.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_rule-run-nl-explain.audit.md](./2026-03-18_rule-run-nl-explain.audit.md)

## 1. Problem

`rule_run` explain delivery 现在已经形成四层闭环：

- raw explain
- summary
- narrative
- static proof-entry

但对“人直接阅读”的 live consumer 来说，当前最上层仍然是结构化 narrative DTO，而不是更接近最终 operator consumption 的自然语言说明。

这带来两个问题：

- narrative 虽然是 deterministic 的文本字段集合，但仍然偏向 UI section rendering，而不是一段可直接消费的 explain prose
- 若后续直接引入 LLM，没有先冻结 deterministic NL explain 层，LLM 输出就会反向模糊 explain contract 的边界

因此需要一个很窄的下一层：

- 以现有 `rule_run_summary` + `rule_run_narrative` 为输入
- 生成 deterministic 的 NL explain
- 先提供 runtime-first surface
- 明确它不是 canonical explain source

## 2. Goals

- 为 `rule_run` 提供 runtime-first 的 deterministic NL explain surface。
- NL explain 必须只依赖现有 `rule_run_summary` 和 `rule_run_narrative`。
- NL explain 必须是 pure derivation，不对 raw/summary/narrative contract 施加 back-pressure。
- 为后续可能的 LLM explain 留出清晰分层：LLM 只能消费 structured explain，不拥有 canonical truth。

## 3. Non-goals

- 不修改 raw `rule_run` explain contract。
- 不修改 `rule_run_summary` 的 7 字段 contract。
- 不修改 `rule_run_narrative` 的 5 字段 contract。
- 不引入 LLM、prompt orchestration 或 model selection。
- 第一轮不做 audit parity，不做 static UI 接入。
- 不扩到 `candidate` / `assertion` explain。

## 4. Current Context

- 当前实现入口：
  - runtime 已有 `POST /queries/explain`
  - runtime 已有 `POST /queries/explain-summary`
  - runtime 已有 `POST /queries/explain-narrative`
  - audit 已有 summary / narrative parity
- 当前已知约束：
  - summary 是 raw explain 的 pure derivation
  - narrative 是 summary 的 pure derivation
  - static proof-entry 已消费 narrative DTO
  - `rule_run` raw/summary/narrative contract 都已冻结
- 当前相关历史蓝图：
  - `runtime-structured-json-explain-api`
  - `runtime-rule-run-explain-summary-api`
  - `audit-rule-run-explain-summary-export`
  - `rule-run-explain-narrative`
  - `rule-run-explain-narrative-parity`

## 5. Proposed Shape

### 5.1 Positioning

这条蓝图不是新的 reasoning/carrying layer，而是 explain delivery 栈最上层的 **runtime-first natural-language view**。

层级关系应保持为：

- raw explain：canonical structured carrier
- summary：consumer-facing structural reduction
- narrative：deterministic presentation DTO
- NL explain：deterministic prose view

`NL explain` 不得反向定义或限制下面三层的 carrier/DTO contract。

### 5.2 Runtime Surface Direction

第一轮建议新增独立 runtime endpoint：

- `POST /v1/runtime/sessions/{session_id}/queries/explain-nl`

请求形状保持与前两层一致：

```json
{
  "kind": "rule_run",
  "id": "rt_trace_123"
}
```

第一轮只支持 `kind="rule_run"`。

保持独立 endpoint 的原因是：

- `NL explain` 是位于 `summary` / `narrative` 之上的新派生层，而不是对现有 endpoint 的 optional payload 扩展
- `summary` 和 `narrative` contract 刚刚冻结，第一轮不应把它们改成带 optional prose bundle 的条件化 surface
- runtime-first scope 更适合先把 `NL explain` 作为独立 consumer object 观察，而不是立刻和现有 surface 耦合

### 5.3 Derivation Boundary

NL explain 的 derivation boundary 应明确冻结为：

- 输入：
  - `rule_run_summary`
  - `rule_run_narrative`
- 不允许的输入：
  - raw trace payload
  - `RuleTraceArtifact` 实例
  - runtime session 中的其他隐式状态

这条边界保证：

- NL explain 不会因为 raw carrier 的细节变化而变成隐式 contract owner
- 如果后续要接入 LLM，也必须通过同一 structured input 边界进入

### 5.4 Output Shape Direction

第一轮 `rule_run_nl_explain` 应尽量窄，并且直接面向人类阅读而不是 UI section 组装。

当前 adopted 输出形状为：

- `headline`
- `paragraphs`

约束：

- `headline` 为单句总结
- `paragraphs` 为 deterministic prose 段落列表，负责把 overview、predicate evidence、non-fact checks 与必要的 drill-down guidance 串成完整说明

这里的 `paragraphs` 与 narrative 的 `overview_lines` / `predicate_lines` / `non_fact_check_lines` / `drilldown_lines` 都不是一一透传关系，而是上层 prose composition。

本轮明确不保留独立 `drilldown_lines` 字段。若 consumer 需要结构化 drill-down affordance，应继续消费 `explain-narrative`；`explain-nl` 只承诺可直接自上而下阅读的 prose view。

### 5.5 Owner / Future Direction

第一轮建议新增 shared renderer owner：

- `src/factpy_kernel/core/rules/_trace_nl.py`

预期入口形状：

- `render_rule_run_nl_explain(summary: dict[str, Any], narrative: dict[str, Any], *, locale: str = "en") -> dict[str, Any]`

owner 放在 `core.rules` 的原因是：

- runtime 侧第一轮消费它
- audit/static 若后续需要 parity，也应能直接复用
- 它位于 `_trace.py` / `_trace_narrative.py` 的上层 presentation ring，但仍属于 shared explain delivery logic

关于未来方向，第一轮明确：

- `locale="en"` 只作为签名预留
- 不做 locale negotiation
- 不做 LLM
- 如果后续要做 model-backed NL explain，应把 deterministic NL explain 视为 baseline/control，而不是替换 canonical source

## 6. Boundaries And Invariants

- 必须保持的边界：
  - raw / summary / narrative contract 不变
  - NL explain 只从 summary + narrative 派生
  - runtime 第一轮保持独立 endpoint
- 明确不做的内容：
  - 不把 NL explain 反写回 static proof-entry page
  - 不在 audit/query/dto 第一轮接入 narrative parity 的再上一层
  - 不新增 durable artifact
- 兼容性约束：
  - 现有 runtime explain / explain-summary / explain-narrative 行为不应改变
  - NL explain 必须保持 deterministic，可测试、可 diff

## 7. Acceptance

- [x] runtime 已提供 `rule_run` 的 NL explain surface
- [x] NL explain 输出只依赖 summary + narrative
- [x] raw / summary / narrative contract 未因 NL explain 发生变化
- [x] 受影响模块 docs 已同步
- [x] 没有越过 runtime-first scope

## 8. Implementation Plan

1. 收敛 `rule_run_nl_explain` 的 runtime surface、input boundary 和最小 output shape。
2. 若切到 `scoped`，新增 shared NL renderer，并在 runtime service 接入独立 `explain-nl` endpoint。
3. 补 service-level shape tests 和 module docs，确认 NL explain 不对下层 contract 施加 back-pressure。

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/core/docs/01_architecture.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 shared deterministic NL renderer `core.rules._trace_nl.render_rule_run_nl_explain(...)`，输入严格限定为 `rule_run_summary + rule_run_narrative`，输出冻结为 `headline + paragraphs`。
  - runtime 新增独立 `POST /v1/runtime/sessions/{session_id}/queries/explain-nl`，只支持 `kind="rule_run"`，返回 `rule_run_nl_explain` DTO。
  - `test_phase3_contracts_v1` 补充了 deterministic renderer 单测、runtime explain surface/shape 测试，并确认 `explain-nl` 不改变既有 raw/summary/narrative contract。
  - `service/docs/03_runtime_queries_views.md` 与 `core/docs/01_architecture.md` 已同步记录 owner、boundary 与 DTO shape。
- 与 blueprint 不同的地方：
  - 无实质偏离；第一轮仍严格停在 runtime-first，没有接入 audit/static parity。
- 为什么会有这些调整：
  - 不适用。
- 归档说明：
  - Blueprint 与 audit log 在代码、测试、文档对齐后归档到 `docs/blueprints/archive/`。
