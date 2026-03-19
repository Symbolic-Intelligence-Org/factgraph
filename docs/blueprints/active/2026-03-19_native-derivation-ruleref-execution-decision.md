# Task Blueprint: Native Derivation RuleRef Execution Decision

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/rules/where_eval.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/authoring/derivation_compile.py`
  - `src/factpy_kernel/authoring/docs/01_overview.md`
  - `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)
  - [2026-03-19_native-where-ruleref-execution-substrate.md](./2026-03-19_native-where-ruleref-execution-substrate.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/core/docs/04_public_contract_v1.md](../../../src/factpy_kernel/core/docs/04_public_contract_v1.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](../../../src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
  - [src/factpy_kernel/authoring/docs/01_overview.md](../../../src/factpy_kernel/authoring/docs/01_overview.md)
  - [docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
- Audit Log:
  - [2026-03-19_native-derivation-ruleref-execution-decision.audit.md](./2026-03-19_native-derivation-ruleref-execution-decision.audit.md)

## 1. Problem

`native candidate evidence tree recursive proof semantics` 蓝图在 review 中暴露了一个更前置的 blocker：

- 当前 native derivation path 不只是 capture 不足
- 而是正式 `Store.evaluate(...)` 执行路径本身还不支持 `RuleRef`

因此，在继续讨论 candidate tree 如何递归之前，必须先单独回答一个 capability decision：

- `native derivation` 是否应该正式支持 `RuleRef` 执行语义？

如果答案是：

- `否`
  - 那么 recursive proof blueprint 需要换方向，不应再默认沿 `rule_ref -> child proof` 前进。
- `是`
  - 那么这应成为一条独立 capability line，先补 execution substrate，再谈 capture 与 recursive tree。

## 2. Goals

- 明确判断 `native derivation` 是否应支持 `RuleRef` 执行语义。
- 区分“当前实现没有做”与“系统有意不做”。
- 给 `recursive proof semantics` 蓝图一个清楚的上游结论。
- 若结论为支持，明确这是一条独立 capability line，而不是 `recursive proof` 蓝图的附属补丁。

## 3. Non-goals

- 不在本蓝图中实现 `RuleRef` in derivation。
- 不在本蓝图中直接修改 runtime/service/core contract。
- 不在本蓝图中冻结 child proof capture schema。
- 不把 derivation path 与 `run_rule` trace 合并成同一个 carrier。
- 不在本轮扩成 graph、salience、engine parity 或 temporal 全栈实现。

## 4. Current Context

- 当前 formal native derivation path：
  - `evaluate_runtime_derivation(...)` 调 `session.store.evaluate(...)`
  - `Store.evaluate(...)` native path 调 `rules.where_eval.evaluate_where(...)`
  - `where_eval` 当前显式 `allow_ruleref=False`
  - 即使关闭 AST gate，`_validate_atom(...)` 仍把 `ruleref` 视为 unsupported
- 当前 rule runtime path：
  - `run_rule(...) / run_rule_with_trace(...)` 通过 `RuleRegistry` 解析 `RuleRef`
  - `rule_ir` 已能把 `ruleref` rewrite 成 internal predicate overlay，并记录 child invocation link
- 当前文档与设计信号并不支持把 `RuleRef` 永久限定在 rule-only world：
  - SDK 文档把 `RuleRef(...)(...)` 列为通用 where 支持语法
  - Derivation DSL 继续复用同一套 where contract
  - authoring 文档明确写到 `service.runtime_v1` 可读取 registry 中的 schema/rule，以支持 runtime session 与 `RuleRef` 解析
  - `SupportArtifact` 母蓝图和 native capture 子蓝图都已预留 `rule_refs` 槽位
  - `Scenario A / T1 temporal semantics` 的归档蓝图也把 helper rule + `RuleRef` 作为 first-round validation pattern
- 当前更准确的现实是：
  - 公开 DSL / authoring intent / future explain direction 倾向于“允许 derivation 使用 RuleRef”
  - 但 formal runtime evaluate path 还没有兑现这件事

## 5. Proposed Shape

### 5.1 Adopted Position

本蓝图的结论是：

- **`native derivation` 应该支持 `RuleRef` 执行语义**

但这不是 `recursive proof` 蓝图里的一个小修，而是一条独立 capability line。

### 5.2 Why The Answer Is Yes

#### A. Public/authoring intent already points in this direction

- `RuleRef` 当前被写进通用 where 语法，而不是只写成 rule-only 特例。
- Derivation DSL 继续复用该 where contract。
- authoring 文档已经把 runtime session + registry + `RuleRef` 解析联系起来。

如果在 capability decision 上选择“native derivation 不支持 `RuleRef`”，就意味着要把这些已有文档与 DSL 口径整体回收，而不仅仅是接受一个实现缺口。

#### B. Recursive proof line depends on it, but should not own it

- current candidate tree 若要沿 `rule_ref -> child proof` 前进，必须先有 derivation-side referenced child execution substrate。
- 这个 substrate 不属于 tree rendering，也不属于 capture payload 小修。
- 因此它应先被当作独立 capability line 处理。

#### C. Existing architecture already has a nearby execution substrate

- `rule_ir` 已经实现了 `RuleRef` 解析、registry lookup、overlay rewrite 和 child invocation capture。
- 这说明问题不是“系统完全没有 RuleRef runtime semantics”，而是“这些语义还没有进入 formal derivation evaluate path”。

因此，选择“支持”是扩展既有能力边界；选择“不支持”反而意味着要把当前 DSL / authoring / future explain framing 明确收紧回 rule-only。

### 5.3 What The Answer Does Not Mean

这条结论不等于：

- derivation 要返回 `RuleTraceArtifact`
- derivation 要复制 `run_rule_with_trace(...)` 的整个 trace surface
- recursive proof blueprint 现在就可以推进到 `scoped`

它只意味着：

- 系统应打开一条新的 implementation line，让 native derivation 正式获得 `RuleRef` execution semantics

### 5.4 First-Round Capability Boundary

如果后续要实现，这条 capability line 的 first-round 边界应保持很窄：

1. 让 `Store.evaluate(..., mode="native")` 在正式 path 中能处理 `RuleRef`
2. derivation/runtime path 需要能拿到 registry-backed resolution substrate
3. derivation support capture 至少能产出：
   - `rule_ref_id + child_support_digest`
4. 继续保持：
   - derivation candidate support 与 `rule_run` trace 分离
   - candidate tree 仍由 `SupportArtifact` 驱动

### 5.5 Rejected Alternative

本轮明确不采纳下面这条路线：

- “把 `RuleRef` 永久限定在 `run_rule` / rule trace 世界；derivation 一律不支持”

拒绝理由：

- 与现有 SDK / authoring 文档口径不一致
- 会把 `recursive proof` 方向直接锁死在 current placeholder level
- 也会让 helper-rule style capability（已在 temporal 讨论中出现）持续停留在语义漂移状态

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 这是一个 capability decision，不是实现蓝图
  - `recursive proof semantics` 蓝图继续保持 `draft`，不因本决定自动推进到 `scoped`
  - `run_rule` trace 与 derivation support 继续保持两条 explain substrate
- 明确不做的内容：
  - 不在本蓝图中决定具体 API 参数、DTO 字段或 registry injection 方案
  - 不在本蓝图中决定是否复用 `rule_ir` 全部内部结构
- 兼容性约束：
  - 如果后续实现开启，必须同步修正文档和 runtime contract，消除当前 DSL / authoring / core runtime 之间的漂移

## 7. Acceptance

- [x] 已明确回答 `native derivation` 是否应支持 `RuleRef` 执行语义
- [x] 已明确这是独立 capability line，而不是 `recursive proof` 蓝图的尾部补丁
- [x] 已明确当前 blocker 是 implementation drift，而不是已冻结的长期边界
- [x] 已给出后续 implementation line 的最小边界

## 8. Implementation Plan

1. 用本蓝图完成 capability decision，先不进入实现。
2. 后续若继续推进，单独开启一个 implementation-facing blueprint，处理 native derivation 的 `RuleRef` execution substrate。
3. 只有在该 implementation line 收口之后，`recursive proof semantics` 蓝图才有资格从 `draft` 推进到 `scoped`。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_native-derivation-ruleref-execution-decision.md`
- `docs/blueprints/active/2026-03-19_native-derivation-ruleref-execution-decision.audit.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 已完成 doc-only capability decision：`native derivation` 应支持 `RuleRef` 执行语义。
  - 已明确这是一条独立 capability line，位于 `recursive proof semantics` 之前。
  - 已明确当前 formal runtime evaluate path 与 SDK/authoring intent 之间存在 contract drift。
  - 后续实现讨论已下沉到独立草案 `native where RuleRef execution substrate`，并把 owner 提升为 `query + derivation`。
- 与 blueprint 不同的地方：
  - 无。
- 为什么会有这些调整：
  - 不适用；本切片为 doc-only capability decision。
- 归档说明：
  - 当前先保留在 `active/` 作为近期 implementation line 的直接上游依据；待后续实现型蓝图开启并收口后再归档。
