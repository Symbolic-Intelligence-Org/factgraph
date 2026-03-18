# Task Blueprint: Runtime Structured JSON Explain API

- Status: scoped
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_explain_rule_trace.py`
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_scenario-a-composite-reference-check.md](../archive/2026-03-18_scenario-a-composite-reference-check.md)
  - [2026-03-18_scenario-a-audit-delivery-shape.md](../archive/2026-03-18_scenario-a-audit-delivery-shape.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_runtime-structured-json-explain-api.audit.md](./2026-03-18_runtime-structured-json-explain-api.audit.md)

## 1. Problem

当前仓库已经具备完整的 live explain substrate，但它还没有被单独收口为一条明确的 **public structured JSON contract**。

现状是：

- `Store.explain_rule_trace(rule_run_id)` 已经能返回 JSON-friendly dict；
- service 已经有：
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`
  - `POST /v1/runtime/sessions/{session_id}/queries/explain` with `kind="rule_run"`
- `Scenario A` 与 static audit delivery 已经证明：
  - `rule_run_id` 可以作为真实 proof entry；
  - `RuleTraceArtifact` 的当前 carrier 足以支撑 first-round explain / evidence delivery。

但仍缺一个任务级蓝图，专门回答下面这些 contract 问题：

- 哪个 endpoint 是这条 explain API 的 **canonical public surface**；
- 哪些 JSON 字段进入 **stable contract**；
- 哪些字段只承诺 **opaque passthrough**；
- legacy wrapper 与 unified `explain_ref` 的关系是什么；
- 第一轮 public contract 是否只冻结 `rule_run`，还是连 `candidate` / `assertion` 一并冻结。

如果这条线不单独收口，后续继续加 `NL explain`、structured consumers、甚至外部集成时，都会建立在一个“能跑但边界没冻结”的 explain surface 上。

## 2. Goals

- 为 live runtime explain 冻结一条 first-round **structured JSON API** 方向。
- 第一轮只聚焦 `rule_run` explain object。
- 明确：
  - canonical endpoint
  - legacy compatibility story
  - stable vs opaque field boundary
  - versioning / docs / test 落点
- 为后续 `NL explain` 提供清晰输入面，而不是直接从 runtime internals 取数。

## 3. Non-goals

- 不新增新的 proof carrier、support graph 或 trace schema。
- 不修改 `RuleTraceArtifact` 的 core capture contract。
- 不在本切片中优先冻结 `candidate` / `assertion` 的完整 structured contract。
- 不做 `NL explain`。
- 不新增新的 static UI、graph UI 或 audit delivery shape。
- 不引入新的 temporal / uncertainty 专用 explain 字段。

## 4. Current Context

- `core` 当前已经有：
  - `RuleTraceArtifact`
  - `rule_trace_artifact_to_dict(...)`
  - `render_rule_trace_artifact(...)`
  - `Store.explain_rule_trace(...)`
- `service` 当前已经暴露两条 live 入口：
  - legacy wrapper：`/queries/explain-rule-trace`
  - unified ref：`/queries/explain` with `kind="rule_run"`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md` 已经记录了一版 first-round `rule_run` explain payload 边界，但它仍是 service docs 中的一节，不是单独蓝图收口后的 adopted contract。
- `Scenario A` 相关切片已经证明：
  - `T1 temporal` 与 `U1 uncertainty` 不需要专用 explain schema 扩展；
  - temporal / uncertainty anchors 都可通过现有：
    - `pred_witnesses`
    - `non_fact_steps.details.binding`
    传达；
  - static audit delivery 已经把 `rule_run_id` 变成 shareable proof entry page。
- `docs/references/external/rainbird-evidence-chain-compare.md` 的当前相关启示是：
  - 近期最应该补的是 structured evidence API / proof entry；
  - 不是先做 certainty 机制，也不是先做 NL explain。

## 5. Proposed Shape

### 5.1 Positioning

这条蓝图是一个 **runtime/service public contract freeze** 切片，不是新的 scenario 线，也不是 explainability substrate 重构。

它的目标是把已经存在的 live explain ability 变成一个对外可依赖的 structured JSON surface。

第一轮 contract 只讨论：

- runtime session 内的 live readback
- `rule_run` object
- JSON payload stability

不讨论：

- audit package format
- static page shape
- LLM/NL generation

### 5.2 First-round Object Narrowing

第一轮只冻结 `rule_run` explain object。

原因：

- `rule_run` 已经有最完整的 live substrate：
  - `/rules/run` with `capture_trace=true` 返回 `rule_run_id`
  - `Store.explain_rule_trace(rule_run_id)` 可直接 readback
  - service 和 static delivery 两端都已经验证过
- `candidate` / `assertion` 仍可继续通过现有 `explain_ref` 使用，但不在本轮优先冻结成单独 public contract 对象

这意味着第一轮的最小 public explain object 是：

- request handle: `rule_run_id`
- response object: `rule_run explain payload`

### 5.3 Endpoint Direction

建议的 first-round direction：

- **canonical public endpoint**：`POST /v1/runtime/sessions/{session_id}/queries/explain`
  - 请求：`{"kind":"rule_run","id":"..."}`
- **legacy compatibility wrapper**：`POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`
  - 保留，但只作为 legacy alias

**Adopted decision：canonical endpoint 与 legacy wrapper 共享同一个 `explain` payload shape。**

- 两条路径都复用同一个底层 `Store.explain_rule_trace(...)` dict payload。
- legacy wrapper 保持当前 envelope shape 不变，不新增顶层 `kind`。
- canonical endpoint 保持当前 envelope shape，在顶层增加 `kind="rule_run"` discriminator。
- 因此，两条路径唯一允许存在的响应差异是：
  - canonical：顶层有 `kind="rule_run"`
  - legacy：顶层没有 `kind`
  - `explain` payload 本身应保持 identical

这条方向的好处是：

- `explain_ref` 可以成为统一 explain surface；
- `rule_run` 是其中第一个被正式冻结的 structured object kind；
- legacy wrapper 不需要立刻移除，但其 payload 应与 canonical object shape 对齐。

### 5.4 Stable Contract Vs Opaque Contract

第一轮建议把 `rule_run` explain payload 分成三层：

1. **stable top-level fields**
   - `rule_run_id`
   - `root_rule.rule_id`
   - `root_rule.version`
   - `select_vars`
   - `root_rows`

2. **stable invocation-level fields**
   - `invocations` 本身是 stable flat list shape
     - consumer 通过 `parent_invocation_id` 与 `ruleref_links.child_invocation_id` 重建 tree
     - 这个 flat-list + id-linkage traversal pattern 本身属于 stable contract
   - `invocation_id`
   - `parent_invocation_id`
   - `rule.rule_id`
   - `rule.version`
   - `memo_hit`
   - `memo_source_invocation_id`
   - `bindings`
   - `output_rows`
   - `pred_witnesses[]`
     - `binding_index`
     - `pred_atom_key`
     - `asrt_ids`
   - `ruleref_links[]`
     - `ruleref_atom_key`
     - `child_invocation_id`
   - `non_fact_steps[]`
     - `binding_index`
     - `step_key`
     - `kind`
     - `status`

3. **opaque or partially-stable payloads**
   - `original_where`
   - `rewritten_where`
     - 只承诺 JSON-native payload，不承诺 typed inner schema
   - `non_fact_steps.details`
     - `details.binding` 建议进入 stable contract
     - `details.atom` 保持 opaque passthrough
     - 其他未来 `details.*` key 默认不承诺 typed schema，除非后续单独冻结

这条边界的直接含义是：

- temporal / uncertainty checks 继续复用同一 contract；
- client 可以稳定消费 witness ids、binding values、rule/ref linkage；
- client 不能假设 where AST 或 `details.atom` 的内部结构在 service v1 中固定不变。

### 5.5 Versioning And Test Direction

第一轮实现若启动，建议同步做三件事：

1. **service docs 冻结**
   - 把 `rule_run` structured JSON explain object 从“已有说明”提升为明确 adopted contract

2. **tests 锁 shape**
   - runtime service tests 直接断言：
     - canonical endpoint shape
     - legacy wrapper parity
     - stable vs opaque fields

3. **version boundary 显式化**
   - 继续使用 service v1 envelope
   - `rule_run` object 本身不额外引入 payload-internal version tag 或 discriminator

**Adopted decision：第一轮不引入 `explain.kind` 或 `rule_run_v1` 这类 object-level discriminator。**

- `kind` 已经存在于 canonical endpoint 的 envelope 顶层。
- `explain` payload 的结构由 envelope 顶层 `kind="rule_run"` 隐含决定，不需要在 payload 内部重复一次。
- 若未来需要 breaking change，应优先通过：
  - service version 演进
  - 或 envelope 层新的 `kind` 值
  来处理，而不是在 payload 内部叠加 version/discriminator 字段。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不修改 `RuleTraceArtifact` capture schema
  - 不引入 scenario-specific explain fields
  - 不把 static audit delivery 与 live runtime contract 混成一个 surface
- 明确不做的内容：
  - NL explain
  - graph UI
  - proof-tree recursion schema redesign
  - candidate/assertion full-contract freeze
- 兼容性约束：
  - 不能破坏既有 `explain-rule-trace` 客户端
  - service docs 与 tests 必须对齐同一 stable/opaque 边界

## 7. Acceptance

- [ ] `rule_run` structured JSON explain object 的 canonical endpoint 已明确
- [ ] legacy wrapper 与 canonical endpoint 的关系已明确
- [ ] stable vs opaque fields 边界已明确
- [ ] 若进入实现，service tests 能锁定上述边界
- [ ] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 收敛 canonical endpoint 与 legacy wrapper 的 adopted relationship。
2. 收敛 `rule_run` explain payload 的 stable vs opaque field boundary。
3. 若 scope freeze 后进入实现，再更新 runtime/service tests 与 docs。

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（如 contract 边界需要同步）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `service/docs/03_runtime_queries_views.md` 已把 `rule_run` structured JSON explain object 冻结为 adopted contract。
  - canonical / legacy 关系已明确写成当前真相：
    - canonical = `POST /queries/explain` + `kind="rule_run"`
    - legacy = `POST /queries/explain-rule-trace`
    - 两条路径 `explain` payload identical，唯一 envelope 差异是 canonical 顶层 `kind="rule_run"`
  - service-level tests 已新增并锁定：
    - canonical endpoint shape
    - legacy wrapper parity
    - `invocations` stable flat list shape
    - `details.binding` stable vs `details.atom` opaque boundary
- 与 blueprint 不同的地方：
  - runtime/service 代码本身没有修改；当前实现已满足 adopted contract，实际改动集中在 docs freeze 与 tests。
- 为什么会有这些调整：
  - 这条切片的目标是 contract freeze，不是新功能开发；现有 runtime implementation 已经与 adopted direction 对齐。
- 归档说明：
  - 该蓝图完成后应归档；后续若继续向前推进，新的自然入口是 structured consumer API 扩展或 NL explain，而不是继续修改 `rule_run` payload contract。
