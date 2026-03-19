# Task Blueprint: Native Candidate Evidence Tree Winning-Branch Semantics

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_support_capture.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)
  - [2026-03-19_native-where-ruleref-execution-substrate.md](./2026-03-19_native-where-ruleref-execution-substrate.md)
  - [2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.audit.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.audit.md)

## 1. Problem

本蓝图创建时，`recursive proof semantics` first-round 已经落地，但它仍保留了一个刻意 defer 的约束：

- native support capture 仍按 OR-of-AND 的 **全分支遍历** 工作
- `rule_ref_edges` 与 `pred_witnesses` 因而仍可能反映“所有匹配/可 ground 的 branch occurrence”
- 这是一种保守 capture，不等于“candidate proof 真正采用了哪个 branch”

当时的代码锚点很直接：

- `_support_capture.build_support_artifact_for_binding(...)` 对 `_normalize_where_branches(where)` 的所有 branch 做遍历
- `_support_capture.derive_rule_ref_edges_for_binding(...)` 也对所有 branch 扫描 `ruleref`
- `_builders.py` 继续维持单-support candidate 合并策略，只保留一个 `candidate_key -> support_digest`

这意味着当时的系统已经有：

- recursive child proof edge
- explicit tree terminal semantics

但还没有：

- **winning-branch semantics**

因此需要单独开一条 capability decision，回答：

- candidate proof 在 OR-of-AND 下是否应该收口到一个“winning branch”
- 若应该，winning branch 在哪一层被选定
- 这个选择如何与单-support candidate contract、support digest 稳定性、以及 recursive proof tree 保持一致

## 2. Goals

- 明确 `winning-branch semantics` 是否应成为 native candidate proof 的正式 contract。
- 冻结 winning branch 应该在哪一层被选定：
  - where evaluation
  - support capture
  - candidate selection
  - tree rendering
- 明确 winning branch 的 first-round identity shape：
  - branch index
  - branch-local atom namespace
  - 或其他更稳定的 handle
- 明确其与当前单-support candidate contract 的关系，避免把此话题扩成 multi-support 或 branch-set semantics。
- 为后续实现型切片提供清晰边界，但当前不直接进入编码。

## 3. Non-goals

- 不重开 `RuleRef` execution substrate。
- 不改 `rule_ref_edges` / `NativeWhereEvaluation.rule_ref_resolutions` 的基础 DTO 形状。
- 不引入 multi-support candidate、multi-proof ranking、或 branch-set carrier。
- 不把本轮扩成 graph UI、salience、certainty、engine parity。
- 不讨论 `artifact_missing / cycle / depth_limit` 的 richer taxonomy；这些不属于 branch 选择本身。
- 不把 winning-branch 问题扩成 query general optimization 或 planner redesign。

## 4. Current Context

- 当前 recursive proof 已实现：
  - `SupportArtifact.rule_ref_edges`
  - widened `NativeWhereEvaluation.rule_ref_resolutions`
  - `candidate_evidence_tree` 递归 child support expansion
- 当前 capture contract 已冻结并落地：
  - exact tuple match
  - `unresolved_reason="child_support_unavailable"`
  - legacy `rule_refs` compatibility summary
- 当前 winning-branch semantics 已通过子实现蓝图落地：
  - `_support_capture.find_winning_branch_index(...)` 先对 OR-of-AND branch 做 capture-local re-computation
  - `build_support_artifact_for_binding(...)` 只为 selected branch 生成 `pred_witnesses` / `non_fact_steps`
  - `derive_rule_ref_edges_for_binding(...)` 只为 selected branch derive edge
  - 若多个 branch 都 satisfy 同一 final binding，first-round 采用 `source-order wins`
- 当前 candidate contract 仍是单-support：
  - `_builders._support_is_better(...)` 只保留一个 `candidate_key -> support_digest`
  - 当前没有并行保留“多个 branch proof”
- 当前 tree / runtime / audit / static consumer 已统一读到 narrowed artifact：
  - selected branch identity 继续通过 `b{branch}.a{atom}:...` key namespace recover
  - 没有新增 top-level `branch_index`
  - non-winning branch 不再作为 shadow metadata 保留在 artifact 中

## 5. Proposed Shape

### 5.1 Positioning

本蓝图是一条独立 capability decision：

- 它承接 `recursive proof semantics`
- 但不再讨论 child-proof handle 是否存在
- 只讨论 **proof path 在 OR-of-AND 下的 branch choice semantics**

### 5.2 First-Round Questions To Freeze

若本蓝图继续推进，至少需要先回答：

1. winning branch 到底要不要成为正式 contract？
   - 继续接受“保守全分支 capture”
   - 还是要求每个 native support artifact 只表达一个 adopted branch
2. winning branch 在哪一层选定最合理？
   - `where_eval` / substrate
   - `_support_capture`
   - `_builders` candidate merge
   - tree readback
3. winning branch 的 identity 最小需要什么？
   - 是否必须新增 top-level `branch_index`
   - 还是只要求 selected branch identity 对 consumer **可恢复**
   - branch-local atom key namespace 是否已经足够
4. 当多个 branch 都满足同一 final binding 时，first-round 怎么处理？
   - deterministic source-order tie-break 选 1 个
   - contract violation
   - 或继续 deferred
5. non-winning branch 的 capture 是否保留在 artifact 中作为 shadow metadata，还是 first-round 直接不写入？
6. `_support_capture` 到底如何知道 winning branch？
   - capture-local re-computation
   - 还是再次扩宽 substrate output 带回 provenance
   - 这条 provenance route 必须在进入 `scoped` 前先冻结

### 5.3 Likely Decision Boundary

当前最可能需要冻结的不是“如何显示 winning branch”，而是：

- **winning branch 是否属于 support artifact contract**

更具体地说，若系统决定要有 winning-branch semantics，那么更合理的落点通常应是：

- 在 support capture 进入 `SupportArtifact` 之前完成 narrowing

而不是：

- 在 tree builder 里事后筛掉 non-winning branch

原因很直接：

- `SupportArtifact` 是 runtime / audit / static 共用的 proof substrate
- 若 narrowing 只发生在 tree 层，不同 consumer 仍然可能看到不同的 proof path 解释
- candidate 的 `support_digest` 也会继续建立在“全分支混合 artifact”上，语义不干净

同时，`support capture` 虽然是当前最自然的 narrowing 层级，但这里还有一个必须显式冻结的前置 gate：

- `_support_capture` 如何取得 winning-branch provenance

current first-round 更偏向：

- **capture-local re-computation**

而不是：

- 再次扩宽 `NativeWhereEvaluation` / execution substrate DTO

原因是：

- `build_support_artifact_for_binding(...)` 当前已经拿到：
  - `binding`
  - `witness_facts`
  - `rule_ref_resolutions`
- 这三者已经足以在 capture 层重算 branch satisfaction
- 这样可以避免重开上游 `ruleref_substrate` 的 output contract

因此，进入 `scoped` 前应先确认：

- first-round provenance route 默认是 capture-local re-computation
- 若这条路线被证明不成立，再另开 scope，而不是在本蓝图里隐式扩大 substrate DTO

但这里还需要一个更精确的 freeze gate：

- **branch satisfaction 必须按 atom kind 定义**

current code 的不对称点很明确：

- `pred` atom
  - satisfaction 可直接落在 grounded terms 是否能从 `witness_facts` 找到至少一个匹配 assertion
- `ruleref` atom
  - satisfaction 可直接落在 grounded terms 是否能在对应 `rule_ref_resolution.row_supports` 中 exact-match 到 child row
  - 若 terms 不能 ground，则该 branch 不应被视为对当前 binding satisfying
- 其他 non-fact atom（`eq` / `in` / `ne` / cmp / arith / `not`）
  - 不能仅凭“当前 binding 已存在”就推断该 branch satisfying
  - first-round 必须先明确这些 atom 在 capture-local re-computation 中如何做布尔重检

因此，在进入 `scoped` 前，除了确认 provenance route 之外，还必须确认：

- capture-local re-computation 对 `pred` / `ruleref` / 其他 non-fact atom 的 satisfaction 判定都已有明确规则
- 不能把这件事留到实现时再临场决定

first-round 当前更合适的 atom-kind satisfaction 规则是：

- `pred`
  - 在当前 final binding 下 ground terms
  - 若 `witness_facts` 中至少存在一个 matching assertion，则该 atom satisfied
- `ruleref`
  - 在当前 final binding 下 ground terms
  - 若对应 `rule_ref_resolution.row_supports` 中存在 exact tuple match，则该 atom satisfied
  - 若 terms 无法 ground，则该 atom 对当前 binding 不 satisfied
- `eq`
  - 在 final binding 下重放相等判断
  - 只做布尔过滤，不再允许绑定新变量
- `ne`
  - 在 final binding 下重放不等判断
  - 只做布尔过滤
- `in`
  - 在 final binding 下重放 membership 判断
  - 只做布尔过滤
- `gt` / `ge` / `lt` / `le`
  - 复用 `where_eval` 当前的 coercion + compare 语义
  - 在 final binding 下只做布尔过滤
- arith (`add` / `sub` / `neg` / `addc` / `mulc`)
  - 复用 `where_eval` 当前的 result 计算语义
  - 但 capture-local re-computation 只做一致性检查，不做 rebinding
  - 也就是：若输出位已在 final binding 中绑定，则必须 `existing == computed_result`
- `not`
  - 复用 `where_eval` 的 negation 语义
  - 只有在 negated body 对当前 final binding 产生 **zero matches** 时，该 atom 才 satisfied
  - 这也是当前 non-fact atom 中唯一明确需要 `view_facts` / `witness_facts` 的 re-check，因为它必须重新评估 negated body，而不只是读取 binding

这条规则带来的一个重要简化是：

- capture re-check 面对的总是 **final binding**
- 因此 first-round 不需要在 re-computation 中重跑“绑定模式”
- 所有 atom kind 都应被视为布尔一致性检查，而不是再次参与变量求解

### 5.4 Single-Support Constraint

本蓝图必须显式继承当前单-support candidate 边界：

- 不把 winning branch 设计成“一个 candidate 同时保留多个 branch proofs”
- 不把 candidate merge 改成 multi-support ranking
- 不要求 `_builders` 在 first-round 同时保留所有满足该 candidate 的 support digests

这意味着 first-round 若采纳 winning-branch semantics，更像是：

- **对单个 support artifact 做 branch narrowing**

而不是：

- 把 candidate model 扩成 proof-set model

### 5.5 Likely First-Round Shape

当前更可能的 first-round 方向是：

1. `SupportArtifact` 只表达一个 adopted branch 的 proof body
   - `pred_witnesses`
   - `non_fact_steps`
   - `rule_ref_edges`
2. branch choice 发生在 capture 阶段，而不是 tree 阶段
3. current exact tuple match / recursive edge DTO 继续保持不变
4. tie handling 保持 deterministic 且极窄
   - first-round 更偏向 `source-order wins`
   - 也就是对同一 final binding，最低 `branch_index` 的 satisfying branch 获胜
5. selected branch identity 必须对 consumer **可恢复**
   - 但 first-round 不强制新增 top-level `branch_index`
   - 当前 `b{branch}.a{atom}:kind` key namespace 已经让 selected branch 可从 artifact 中恢复
6. non-winning branch 不保留 shadow metadata
   - first-round artifact 只承载 adopted branch 的 proof body
7. winning-branch provenance 首选 capture-local re-computation
   - 先在 `_support_capture` 内部基于 `binding + witness_facts + rule_ref_resolutions` 做 narrowing
   - 不默认把这个问题升级成 substrate DTO widening
8. atom-kind satisfaction 复用 `where_eval` 既有语义
   - 但在 capture 时统一收口成 final-binding 下的布尔一致性检查
   - `not` 是唯一需要重新访问 `view_facts` / `witness_facts` 的 non-fact atom

本轮不应默认的路线：

- 继续 ship “全分支 + 树上再猜哪条是 winning”
- 或引入 `winning=true/false` 的 mixed artifact，把 adopted / non-adopted branch 一起塞进同一个 support carrier
- 或为了 branch provenance 直接重开 execution substrate output contract

### 5.6 Compatibility Surface

无论是否收口成 winning branch，本蓝图都应保持：

- `candidate_id -> support_digest -> SupportArtifact` 主路径不变
- `rule_ref_edges` 继续是 recursive proof 的正式 carrier
- tree node taxonomy 不因本轮被推翻
- old artifacts 仍可通过 legacy fallback 被 readback
- selected branch identity 应对 consumer 可恢复，但 first-round 不要求新增 top-level branch handle

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 这条线属于 `candidate evidence tree` 的 proof semantics，不是 planner 重写
  - runtime / audit / static 必须继续共用同一底层 support artifact contract
  - 单-support candidate contract 保持不变，除非未来另开 capability 线
- 明确不做的内容：
  - 不把 branch-winning 扩成多 proof ranking
  - 不引入新的 graph carrier 或 trace-carrier 合并
  - 不重开 recursive proof DTO 基础形状
- 兼容性约束：
  - 当前已落地的 recursive proof tree 不能回退成 flat explain
  - 旧 artifact readback / static site fallback 继续成立
  - 若 first-round 不能稳定定义 tie semantics，应优先保持 `draft`，而不是仓促实现半隐式规则

## 7. Acceptance

- [x] 已明确 winning-branch semantics 成为 native candidate proof 的正式 contract
- [x] 已冻结并实现 winning branch 的选定层级、tie 规则、以及 recoverable identity 边界
- [x] 已冻结并实现 winning-branch provenance 的 first-round 路线，未隐式重开 substrate DTO
- [x] 已确认并实现 capture-local re-computation 对 `pred` / `ruleref` / 其他 non-fact atom 都有明确的 branch satisfaction 规则
- [x] 已明确并落地其与单-support candidate contract 的关系
- [x] 受影响模块 docs 已同步更新

## 8. Implementation Plan

1. 盘点当前 OR-of-AND conservative capture 在 `pred_witnesses`、`non_fact_steps`、`rule_ref_edges` 三侧的具体暴露形状。
2. 收口 winning branch 的 freeze 问题：选定层级、recoverable identity、source-order tie 行为、artifact contract 边界。
3. 先定义 branch satisfaction 的 atom-kind 规则，至少覆盖 `pred`、`ruleref`、以及其他 non-fact atom。
4. 再判断 capture-local re-computation 能否稳定给出 winning-branch provenance；若不能，再决定是否要升级成新的 substrate scope。
5. 若 freeze 可成立，再决定是否需要新的 implementation blueprint，而不是直接在当前蓝图中写代码。
6. 已选择拆成独立 implementation blueprint：
   - [2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md)
   - 由该蓝图承接 narrowing logic + tests 的具体实现

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md`
- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.audit.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（若后续进入实现）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若后续进入实现）

## 10. Outcome / Deviations

- 最终落地结果：
  - winning-branch semantics 已成为 native candidate proof 的正式 contract
  - narrowing 在 `core.store._support_capture` 落地，而不是在 tree readback 层做二次筛选
  - selected branch identity 继续通过 `b{branch}.a{atom}:...` key namespace recover，没有新增 top-level `branch_index`
  - tie 规则按 `source-order wins` 实现
  - non-winning branch 不保留 shadow metadata
  - capture-local re-computation 已按 atom kind 落地，覆盖 `pred` / `ruleref` / `eq` / `ne` / `in` / cmp / arith / `not`
  - 具体实现由子蓝图 [2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md) 完成
- 与 blueprint 不同的地方：
  - 没有新增 top-level branch field；recoverable identity 的更窄 contract 已足够支撑 runtime / audit / static proof readback
  - selected branch 下的 `ruleref` 若无法 ground 或缺少 row-support match，会直接视为 contract violation 并 fail fast，而不再保留 pre-narrowing 的宽松 `skip` 行为
- 为什么会有这些调整：
  - `b{branch}.a{atom}:...` key namespace 已足以恢复 branch identity，新增 top-level field 只会重复状态并扰动 digest
  - winning-branch narrowing 一旦成为正式 proof contract，selected branch 中再出现 ungroundable / no-match `ruleref`，更合理的解释是 capture/evaluation 一致性被破坏，而不是“正常缺边”
- 归档说明：
  - 本蓝图已进入 `implemented`
  - 具体实现与测试位于子蓝图 `2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing`
  - 归档副本保留在 `docs/blueprints/archive/`
