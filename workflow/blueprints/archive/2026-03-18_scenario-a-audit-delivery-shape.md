# Task Blueprint: Scenario A Audit Delivery Shape

- Status: scoped
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/audit/reader.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
  - `tools/benchmarks/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_ecss-scenario-anchoring.md](./2026-03-18_ecss-scenario-anchoring.md)
  - [2026-03-18_scenario-a-composite-reference-check.md](../archive/2026-03-18_scenario-a-composite-reference-check.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_scenario-a-audit-delivery-shape.audit.md](./2026-03-18_scenario-a-audit-delivery-shape.audit.md)

## 1. Problem

`Scenario A` 当前已经证明 kernel substrate 足够表达 first-round composite reference check：

- `T1 temporal` + `U1 uncertainty` 可以在单条 rule 里组合；
- live trace 可以给出 fact-backed witnesses + binding values；
- audit package 中的 `rule_trace_artifacts.jsonl` 与 live readback 保持一致。

但 delivery 侧还缺一个稳定、可分享的 proof entry：

- static audit site 还没有 `rule_run_id` 对应的 trace 页面；
- `load_audit_package(...)` 还没有把 rule trace artifacts 纳入统一读取；
- static UI 还不能从一个 exported composite check 直接跳进 evidence path。

这会让 `Scenario A` 虽然“技术上可解释”，但仍缺少一个用户真正能消费的交付面。

## 2. Goals

- 为 exported audit package 提供稳定的 `rule_run_id` proof entry point。
- 在 static audit site 中新增 trace drill-down 页面，并把 witness assertion 下钻链接接通。
- 让 audit reader/query/static UI 对 `rule_trace_artifacts.jsonl` 形成统一消费路径，而不是测试里手工读 JSONL。
- 补一组轻量 baseline benchmark，观察 composite check 的 live/export/render 路径在 `1 / 100 / 1000` assessments 下是否有明显退化。

## 3. Non-goals

- 不新增 runtime/service live endpoint。
- 不修改 `RuleTraceArtifact` schema。
- 不引入新的 temporal / uncertainty semantics，也不进入 `T2 state propagation`。
- 不把 delivery shape 扩成完整 graph UI、NL explain 或新的 proof-tree carrier。
- 不把 benchmark 扩成独立性能工程或优化任务。

## 4. Current Context

- `Scenario A` 的 temporal / uncertainty / composite 子蓝图都已归档，结论是当前 substrate 足够支撑 first-round reference check。
- audit package 已导出：
  - `audit/rule_trace_artifacts.jsonl`
  - `audit/support_artifacts.jsonl`
- 当前 `audit.static_ui` 已支持：
  - run pages
  - decision pages
  - assertion pages
  - authoring apply pages
  - `compliance_matrix.html`
- 当前 `audit.reader` 仍只加载 ledger / decision / mapping / authoring apply 数据，没有统一加载 rule trace artifacts。
- `docs/references/external/rainbird-evidence-chain-compare.md` 的 adopted reference only 结论是：
  - 近期最值得借鉴的是层 2 的 proof entry 和层 5 的对外交付形态；
  - 不应把 Rainbird 的 certainty 机制或更重 evidence tree 直接照搬进当前切片。

## 5. Proposed Shape

### 5.1 Adopted Narrowing

本切片只做一个窄的 delivery closure：

- **proof entry point = `rule_run_id`**
- **shareable static delivery = `rule_traces/{rule_run_id}.html`**

第一轮不引入 candidate-level stable proof id，也不为每个 assertion/support 再造新的入口标识。

### 5.2 Reader / Query / DTO Shape

- `load_audit_package(...)` 增加对 `rule_trace_artifacts.jsonl` 的统一读取。
- `AuditPackageData` 增加 `rule_trace_artifacts` 容器。
- `AuditQuery` 增加最小 trace 查询入口：
  - `list_rule_traces()`
  - `get_rule_trace(rule_run_id)`
- `dto.py` 增加最小 trace DTO：
  - trace list summary
  - trace detail payload

这里的目标是让 static UI 和后续 consumer 不再手工解析 raw JSONL。

### 5.3 Static Delivery Shape

static audit site 第一轮新增：

- `rule_traces.html`
  - 作为 trace proof-entry index
- `rule_traces/{rule_run_id}.html`
  - 作为单条 composite / rule trace 的 shareable page

trace detail page 至少展示：

- `rule_run_id`
- root rule
- select vars / root rows
- invocation summaries
- `pred_witnesses`
- `non_fact_steps`
- 从 witness `asrt_id` 到 assertion detail page 的链接

这是当前 `Scenario A` 的最小 evidence path：

`rule_run_id page -> pred_witnesses.asrt_ids -> assertions/{asrt_id}.html`

### 5.4 UI Index / Search Shape

- `ui_index.json` 增加 `rule_trace_pages` lookup 和 trace count。
- search 页面增加 `rule_trace` 维度，允许通过 `rule_run_id` 搜索进入 proof entry。
- `index.html` 增加 trace index 入口。

### 5.5 Benchmark Baseline

同一切片内补一个轻量 benchmark 脚本，测三段路径：

1. live
   - composite rule 执行时间
   - trace readback 时间
2. export
   - audit package 导出时间
   - `rule_trace_artifacts.jsonl` 文件大小
3. delivery
   - static site render 时间
   - trace pages / assertion pages 数量

第一轮只测三档：

- `1` assessment
- `100` assessments
- `1000` assessments

benchmark 的职责是给出 baseline，不要求本切片内做性能优化。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `audit` 仍是离线 package 消费层，不新增 live service contract。
  - `RuleTraceArtifact` payload 保持原样，static UI 只消费现有字段。
  - assertion detail 仍是 witness 下钻页，不把 support artifact 路径混入 rule trace 页面。
- 明确不做的内容：
  - 不新增 graph UI、NL explain、candidate proof id。
  - 不要求 static UI 实现递归 evidence tree。
- 兼容性约束：
  - `load_audit_package(...)` 对没有 trace artifact 的旧 package 需要保持可读，不把 trace artifact 变成强制存在项。
  - static site 新增页面不能破坏现有 run / decision / assertion / compliance matrix 页面路径。

## 7. Acceptance

- [ ] audit reader 已统一读取 `rule_trace_artifacts.jsonl`，旧 package 仍可正常加载
- [ ] static audit site 新增 `rule_traces.html` 和 `rule_traces/{rule_run_id}.html`
- [ ] trace detail page 能从 `pred_witnesses.asrt_ids` 下钻到 assertion detail pages
- [ ] `ui_index.json` / search / index.html 已暴露 trace proof-entry
- [ ] baseline benchmark 已提供 `1 / 100 / 1000` assessments 的 live/export/render 指标
- [ ] 代码行为满足任务目标
- [ ] 没有越过 blueprint 明示的边界
- [ ] 受影响模块 docs 已同步

## 8. Implementation Plan

1. [audit reader/query/dto] 把 rule trace artifacts 纳入统一读取和最小查询/DTO surface。
2. [audit static UI] 新增 trace index/detail pages，并把 proof-entry 暴露到 index/search/ui_index。
3. [tests + benchmark] 用 composite scenario 验证 static delivery path，再补 baseline benchmark 脚本和文档同步。

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `audit.reader` 已统一读取 `rule_trace_artifacts.jsonl`，且对旧 package 保持 optional 兼容。
  - `AuditQuery` / `dto.py` 新增最小 trace list/detail 查询与 DTO surface。
  - static audit site 新增：
    - `rule_traces.html`
    - `rule_traces/{rule_run_id}.html`
  - `ui_index.json`、search、`index.html` 已暴露 `rule_run_id` proof-entry。
  - baseline benchmark 工具落在 `tools/benchmarks/bench_scenario_a_audit_delivery_shape.py`，并已测得：
    - `1 assessment`: run `0.000416s`, export `0.002734s`, render `0.004637s`
    - `100 assessments`: run `0.02078s`, export `0.016275s`, render `0.178697s`
    - `1000 assessments`: run `0.672223s`, export `0.168369s`, render `1.987274s`
- 与 blueprint 不同的地方：
  - 没有新增独立的 requirement/check summary page。
- 为什么会有这些调整：
  - 当前最关键缺口是稳定 proof-entry 和 trace-to-assertion delivery；独立 summary page 不影响这一轮结论，先保持最小闭环。
- 归档说明：
  - 本切片确认当前 `Scenario A` 的下一阶段价值主要在 delivery shape，而不是新的 kernel semantics；蓝图完成后归档。
