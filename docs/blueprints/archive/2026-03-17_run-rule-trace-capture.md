# Task Blueprint: Run Rule Trace Capture

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/rules/rule_ir.py`
  - `src/factpy_kernel/core/view/projector.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/authoring/preflight.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_support-artifact-native-capture.md](./2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_support-artifact-readback.md](./2026-03-17_support-artifact-readback.md)
- Audit Log:
  - [2026-03-17_run-rule-trace-capture.audit.md](./2026-03-17_run-rule-trace-capture.audit.md)

## 1. Problem

`Store.evaluate(...)` 这条 derivation 路径现在已经具备：

- evaluate-time support capture
- `support_digest` 写入
- in-process readback（`Store.explain_support(...)`）

但 rule runtime 仍然是 explainability 的明显断层。

当前 `run_rule(...)` / `RuleRef` 调用链的现状是：

- `run_rule(...)` 返回的只有 `list[tuple[Any, ...]]`
- `_evaluate_rule(...)` 内部只有 `memo_rows`（子规则结果行缓存）和 `stack`（cycle detection）
- 不保留 root rule 执行 id
- 不保留 per-rule invocation bindings
- 不保留 per-layer `pred` witness / rewritten where / output rows 的结构化 trace

因此，不论是 SDK `run(...)`、runtime service `/rules/run`，还是 authoring preflight，调用方都只能拿到最终 rows，而无法回答：

- 这次 `run_rule(...)` 是如何展开 `RuleRef` 的？
- 哪一层子规则产生了哪批 rows？
- 顶层 rows 是由哪些 bindings / claims 支撑的？

## 2. Goals

- 为 `run_rule(...)` 路径定义一个独立于 `SupportArtifact` 的 `RuleTraceArtifact` carrier。
- 在 core rule runtime 中捕获：
- root rule invocation
- `RuleRef` 调用关系（第一轮允许 DAG，而非强制严格树）
  - 每层 rewritten where
  - 每层 bindings
  - 每层 output rows
  - 第一轮可行范围内的 `pred` witness summary
- 保持现有 `run_rule(...) -> list[tuple]` 兼容调用面，避免立即破坏 SDK / service / preflight。
- 为后续的 in-process readback、service explain surface、durable trace storage 提供稳定根对象和 root handle。

## 3. Non-goals

- 不把 `run_rule trace` 并入当前 `SupportArtifact` / `_support_artifacts` registry。
- 不在本轮处理 service / HTTP explain 暴露。
- 不处理 durable cross-process trace storage。
- 不把 `run_rule` 强行改造成 `Store.evaluate(...)` 风格的 candidate pipeline。
- 不引入 certainty / probability semantics，或 Rainbird-style salience/weight 语义。

## 4. Current Context

- 当前实现入口：
  - SDK：[`src/factpy_kernel/sdk/store.py`](../../../src/factpy_kernel/sdk/store.py) 的 `_run_rule(...)`
  - service：[`src/factpy_kernel/service/runtime_v1.py`](../../../src/factpy_kernel/service/runtime_v1.py) 的 `run_runtime_rule(...)`
  - authoring/preflight：[`src/factpy_kernel/authoring/preflight.py`](../../../src/factpy_kernel/authoring/preflight.py)
  - 核心执行：[`src/factpy_kernel/core/rules/rule_ir.py`](../../../src/factpy_kernel/core/rules/rule_ir.py) 的 `run_rule(...)` / `_evaluate_rule(...)`
- 当前已知约束：
  - `run_rule(...)` 当前直接返回 rows，多个调用方依赖这一形状。
  - `memo_rows` 目前只缓存 `list[tuple]`，不是 trace carrier。
  - 当前没有 rule-run 级别的 trace id、trace registry、trace readback helper。
  - derivation support 已采用独立 `SupportArtifact` 路线；rule runtime 不应强行塞进同一 carrier。
- 当前相关历史蓝图：
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_support-artifact-native-capture.md](./2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_support-artifact-readback.md](./2026-03-17_support-artifact-readback.md)

## 5. Proposed Shape

### 5.1 Separate Carrier: `RuleTraceArtifact`

第一轮不复用 `SupportArtifact`。

原因是 `SupportArtifact` 当前表达的是“单个 derivation binding 的 support summary”，而 rule runtime 需要表达的是“一个 `run_rule(...)` 调用的递归执行树”。两者根对象、粒度、消费方式都不同。

因此建议新增独立 carrier，例如：

```text
RuleTraceArtifact
- rule_run_id
- root_rule: {rule_id, version}
- select_vars
- invocations: [RuleTraceInvocation, ...]
- root_rows
```

其中 `RuleTraceInvocation` 第一轮至少应包含：

```text
RuleTraceInvocation
- invocation_id
- parent_invocation_id | None
- rule_id
- version
- memo_hit
- memo_source_invocation_id | None
- original_where
- rewritten_where
- bindings
- output_rows
- pred_witnesses
```

`original_where` 与 `rewritten_where` 第一轮都应保留：

- `original_where`
  - 保留 authoring / registry 视角的原始 rule body
  - 保留 `ruleref` atom
- `rewritten_where`
  - 保留实际送进 `evaluate_where(...)` 的执行输入
  - 便于 debug / replay / 对照内部 `pred` 展开

两者表达的是不同层面的 truth，当前代码里都能低成本获得，因此不应在第一轮二选一丢弃信息。

另外，当前 `memo_rows` 以 `(rule_id, version)` 为 key 复用 exposed subrule 结果，因此 `RuleRef` 关系在运行时并不总是严格树。第一轮 trace 不应掩盖这一点；更稳的表达是：

- 每个 call site 都可以有自己的 `RuleTraceInvocation`
- 若某次调用命中 `memo_rows`，则：
  - `memo_hit = True`
  - `memo_source_invocation_id` 指向首次完整执行该 rule 的 invocation
- invocation 间关系因此更接近“带 memo reuse 的 call graph / DAG”，而不是强行简化成单父严格树

### 5.2 Root Handle And Compatibility Strategy

第一轮应避免破坏现有 `run_rule(...) -> list[tuple]` 调用面。

较稳的兼容策略是：

- 保留现有 `run_rule(...) -> list[tuple]`
- 新增 traced sibling helper，例如：

```python
def run_rule_with_trace(store, rule_spec, registry) -> RuleRunResult:
    ...
```

其中：

```text
RuleRunResult
- rule_run_id
- rows
```

现有 SDK / service / preflight 在这一轮不强制切换；它们可继续使用 `run_rule(...)`。trace capture/readback 先在 core 里站稳，再由后续子蓝图决定哪些入口要显式暴露 `rule_run_id`。

第一轮内部实现应优先收口到单一 core 路径，例如：

```python
def _run_rule_core(..., trace_ctx: RuleTraceCaptureContext | None = None) -> list[tuple[Any, ...]]:
    ...
```

然后：

- `run_rule(...)`
  - 调 `_run_rule_core(..., trace_ctx=None)`
- `run_rule_with_trace(...)`
  - 创建 `rule_run_id`
  - 创建 `RuleTraceCaptureContext`
  - 调 `_run_rule_core(..., trace_ctx=ctx)`
  - 从 context 组装 `RuleTraceArtifact`
  - 注册到 store-level trace registry
  - 返回 `RuleRunResult(rule_run_id, rows)`

这样可以避免复制两份 rule runtime 主体，也避免旧调用面被 trace 逻辑反向挟持。

### 5.3 Capture Hook Location

trace capture 的天然挂点已经存在于 [`rule_ir.py`](../../../src/factpy_kernel/core/rules/rule_ir.py)：

- `run_rule(...)`
  - 负责建立 root run 级上下文
- `_evaluate_rule(...)`
  - 负责递归展开 rule invocation
- `_rewrite_where_rule_refs(...)`
  - 负责记录 `RuleRef` 展开关系

第一轮 capture 应优先长在 `_evaluate_rule(...)` 层，而不是外侧 wrapper。因为只有在这里才能同时看到：

- 当前 rule invocation
- rewritten where
- recursive subrule call
- `evaluate_where(...)` 的 binding 结果
- rows 输出

与此配套，`trace_ctx` 应采用**显式参数传递**，而不是线程局部或隐式全局状态：

```python
def _evaluate_rule(..., trace_ctx: RuleTraceCaptureContext | None = None, parent_invocation_id: str | None = None) -> list[tuple[Any, ...]]:
    ...
```

`_rewrite_where_rule_refs(...)` 也应接收同一 `trace_ctx`，以便在 `RuleRef` 递归展开时记录父子 invocation 关系。

`RuleTraceCaptureContext` 第一轮建议采用 mutable accumulator，而不是 return-time list merge：

```text
RuleTraceCaptureContext
- rule_run_id
- invocations: list[RuleTraceInvocation]
- primary_invocation_by_rule_key: dict[(rule_id, version), invocation_id]
```

每次 `_evaluate_rule(...)` 完成一层 invocation capture 后，直接 append 到同一个 context；在 `run_rule_with_trace(...)` 返回前再统一冻结成 `RuleTraceArtifact.invocations` 的 tuple/list。对于当前递归结构，这比多层返回 `(rows, invocations)` 更简单，也更不容易污染现有返回值路径。

### 5.4 Witness Strategy

若第一轮就要避免“只有 rows 没有 why”，trace 中需要引入最小 `pred_witnesses`。

这里建议复用 derivation 路径已经存在的思路：

- 通过 witness-capable projection 获取 `ProjectedFact`
- 对每层 rule invocation 的 bindings 做 grounded pred witness 回填

但为了控制 scope，第一轮可以接受以下限制：

- 只捕获正向 `pred` atom 的 witness summary
- `not/cmp/in/arithmetic` 先只做 minimal step summary
- OR-of-AND 可暂时接受非 winning branch 的空 witness 记录，只要 deterministic

### 5.5 Registry And Readback Boundary

既然本轮不并入 `_support_artifacts`，则应给 rule trace 自己的 in-process registry：

- `Store._rule_trace_artifacts: dict[str, RuleTraceArtifact]`
- `Store._remember_rule_trace_artifact(...)`
- `Store._lookup_rule_trace_artifact(...)`

是否同时在本轮提供 `Store.explain_rule_trace(rule_run_id)`，可以作为实现切 scope 时的二级决策：

- 若需要形成 capture + readback 闭环，则提供最小 readback helper
- 若要再控一轮 scope，也可先只 capture + registry，readback 另拆子蓝图

本轮最终选择：**同轮完成 capture + in-process registry + readback**，但仍不触及 service / HTTP 暴露。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `run_rule(...)` 现有返回值形状不被破坏。
  - `SupportArtifact` 与 `RuleTraceArtifact` 保持分离；两者未来可以协议层对齐，但当前不强行统一。
  - 当前 SDK / service / preflight 调用链在第一轮不要求全面改造。
- 明确不做的内容：
  - 不为 `/rules/run` 立即增加 trace payload。
  - 不做 durable trace storage。
  - 不把 trace 直接写入 ledger/meta。
  - 不把 row-level trace handle 与 candidate/support 体系混成一个 id 空间。
- 兼容性约束：
  - `run_rule(...)` 现有调用点必须继续工作。
  - 若新增 `run_rule_with_trace(...)`，其存在不应迫使旧调用点同步迁移。

## 7. Acceptance

- [x] `run_rule` 路径有独立 carrier 设计，不再只有 rows 黑箱输出
- [x] `RuleRef` 调用关系可被 capture 为结构化 trace（第一轮允许 DAG / memo reuse）
- [x] 现有 `run_rule(...) -> list[tuple]` 兼容调用面未被破坏
- [x] 不与当前 `SupportArtifact` / `_support_artifacts` 机制混用
- [x] 本轮已提供最小 in-process readback 入口
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 在 `core/rules` 下定义 `RuleTraceArtifact` / `RuleTraceInvocation` / `RuleTraceCaptureContext` / `RuleRunResult` 等内部 carrier。
2. 在 `rule_ir.py` 中抽出 `_run_rule_core(..., trace_ctx=None)`，让 `run_rule(...)` 与 `run_rule_with_trace(...)` 共用同一执行主体。
3. 在 `rule_ir.py` 中为 `_evaluate_rule(...)` / `_rewrite_where_rule_refs(...)` 引入显式 `trace_ctx` 参数，先捕获 root invocation、subrule invocation、`original_where`、`rewritten_where`、bindings、rows。
4. 以 mutable accumulator 方式在 `RuleTraceCaptureContext.invocations` 中归集整张 invocation graph，并通过 `primary_invocation_by_rule_key` 记录首次完整执行节点，供后续 memo-hit invocation 回指。
5. 若 scope 允许，复用 witness-capable projection，为每层 invocation 增加最小 `pred_witnesses`。
6. 仅在 core 层建立 in-process registry / readback；service/HTTP 暴露另开后续子蓝图。

## 9. Docs To Update

- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`（若 traced entry 被 SDK 暴露）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（仅在 service 层后续暴露时）
- 相关模块 docs（`core/rules` / `core/store`）如需新增 carrier 说明
- `docs/README.md`（仅在新增持久 docs 入口时）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - 新增 `core/rules/_trace.py`，定义 `RuleTraceArtifact` / `RuleTraceInvocation` / `RuleRunResult` / `RuleTraceCaptureContext`
  - `rule_ir.py` 新增 `run_rule_with_trace(...)` 和共享内部路径 `_run_rule_core(...)`
  - `Store` 新增 `_rule_trace_artifacts` registry 与 `explain_rule_trace(rule_run_id)`
  - 第一轮 readback 已在同轮落地，返回 JSON-friendly trace dict
- 与 blueprint 不同的地方：
  - `RuleRef` capture 从“调用树”更准确收口为“允许 memo reuse 的 invocation graph / DAG”
  - 第一轮同轮落地了 in-process readback，而不是只停在 capture
- 为什么会有这些调整：
  - 当前 `memo_rows` 以 `(rule_id, version)` 复用 subrule 结果，严格树模型会丢失 call-site reuse
  - 既然 `Store` 已经为 support artifact 提供 readback，rule trace 若只 capture 不 readback，验证和消费价值都偏低
- 归档说明：
  - service explain readback 已作为后续子蓝图单独落地；本文件现在保留为已完成的 core rule-trace capture 记录，适合移入 archive，后续 durable storage 继续按归档文档引用即可
