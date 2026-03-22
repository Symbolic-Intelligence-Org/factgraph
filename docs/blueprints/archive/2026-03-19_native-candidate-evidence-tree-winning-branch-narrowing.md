# Task Blueprint: Native Candidate Evidence Tree Winning-Branch Narrowing

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_support_capture.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md)
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.audit.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.audit.md)

## 1. Problem

`winning-branch semantics` 已经在上一份 scoped blueprint 中冻结完成：

- winning branch 是 native candidate proof 的正式 contract
- narrowing 发生在 capture time，而不是 tree readback
- selected branch identity 只要求 recoverable，不强制新增 top-level field
- tie 规则是 `source-order wins`
- 不保留 non-winning shadow metadata
- provenance route 采用 capture-local re-computation，并且 atom-kind satisfaction 规则已对齐 `where_eval.py`

当前 implementation 已落地：

- `_support_capture.find_winning_branch_index(...)` 负责 capture-local re-computation
- `_support_capture.build_support_artifact_for_binding(...)` 现在只为 selected branch 生成 `pred_witnesses` / `non_fact_steps`
- `_support_capture.derive_rule_ref_edges_for_binding(...)` 现在只为 selected branch derive edges
- `single-support candidate` 的 `support_digest` 已建立在 narrowed artifact 上

这份 implementation blueprint 的任务不是再讨论语义，而是把 scoped 的 winning-branch contract 真正落到 support-capture narrowing 逻辑中。

## 2. Goals

- 在 support capture 层实现 winning-branch narrowing。
- 保持 `SupportArtifact`、`NativeWhereEvaluation.rule_ref_resolutions`、以及 recursive tree taxonomy 的既有 contract 不变。
- 让 single-support candidate 的 `support_digest` 建立在单 branch、语义干净的 artifact 上。
- 用针对性测试把 source-order、atom-kind satisfaction、legacy fallback、digest stability 一次钉住。

## 3. Non-goals

- 不重开 `winning-branch semantics` 的 capability decision。
- 不扩宽 `NativeWhereEvaluation` / `ruleref_substrate` DTO。
- 不引入 multi-support candidate、proof-set ranking、或 shadow metadata。
- 不修改 tree node taxonomy，`referenced_support` / `unresolved_support` / `recursion_boundary` 保持不变。
- 不改变 legacy artifact readback 形状。
- 不把这轮扩成 query planner、execution substrate、或 graph work。

## 4. Current Context

- 当前 branch identity 已经对 consumer 可恢复：
  - `pred_atom_key = b{branch}.a{atom}:pred_id`
  - `step_key = b{branch}.a{atom}:kind`
  - `ruleref_atom_key = b{branch}.a{atom}:ruleref`
- 当前单-support candidate 约束仍成立：
  - `_builders._support_is_better(...)` 只保留一个 `candidate_key -> support_digest`
- 当前 capture-local re-computation route 已被上游 scoped blueprint 采纳：
  - `pred` 通过 `witness_facts` 做 grounded match
  - `ruleref` 通过 `rule_ref_resolutions.row_supports` 做 exact tuple match
  - `eq` / `ne` / `in` / cmp 做 final-binding boolean re-check
  - arith 做 compute-and-check
  - `not` 重跑 negated body zero-match 语义，是唯一明确需要 `view_facts` / `witness_facts` 的 non-fact atom
- 当前 recursive proof 已经依赖 `rule_ref_edges`：
  - narrowing 实现若不在 capture 层完成，tree consumer 仍会继续读到 mixed-branch artifact

## 5. Proposed Shape

### 5.1 Implementation Owner

first-round implementation owner 应明确落在：

- `core.store._support_capture`

理由：

- winning-branch contract 是 support-artifact contract
- `_evaluate.py` 负责 orchestration，不应再承载 branch semantics 本体
- `_candidate_evidence_tree.py` 是 consumer，不应承担 narrowing 逻辑

### 5.2 Narrowing Entry Point

更合理的 first-round 形状是：

1. 先对 `where` 做 `_normalize_where_branches(...)`
2. 新增一个 `_find_winning_branch(...)` 或同等职责的内部 helper
3. 该 helper 接收最小上下文：
   - normalized branches
   - final `binding`
   - `witness_facts`
   - `rule_ref_resolutions`
4. 该 helper 返回：
   - selected `branch_index`
   - 或在无 satisfying branch 时 fail fast
5. `build_support_artifact_for_binding(...)` 和 `derive_rule_ref_edges_for_binding(...)` 都只消费 selected branch

first-round 不建议的路线：

- 在 tree builder 中二次筛 branch
- 在 `_evaluate.py` 里散落一层 branch-specific patch
- 先生成 mixed artifact，再事后剔除 non-winning rows

### 5.3 Branch Satisfaction Re-check

`_find_winning_branch(...)` 的 re-check 规则直接复用上游 scoped 语义：

- `pred`
  - grounded terms 至少命中一个 `witness_facts[pred_id]`
- `ruleref`
  - grounded terms 在对应 `rule_ref_resolution.row_supports` 中存在 exact tuple match
  - terms 不能 ground，则该 atom 不 satisfied
- `eq`
  - final-binding 下 `lhs == rhs`
- `ne`
  - final-binding 下 `lhs != rhs`
- `in`
  - final-binding 下 `binding[var] in allowed_values`
- `gt` / `ge` / `lt` / `le`
  - 复用 `where_eval` 的 coercion + compare 语义
- arith
  - 复用 `where_eval` 的计算逻辑
  - 但只做 compute-and-check，不做 rebinding
- `not`
  - 复用 `where_eval` 的 negated-body zero-match 语义
  - 这是唯一需要重新访问 `view_facts` / `witness_facts` 的 non-fact atom

### 5.4 Tie Rule

若多个 branch 都 satisfy 同一个 final binding，first-round 固定采用：

- `source-order wins`

也就是：

- 最低 `branch_index` 的 satisfying branch 获胜

这条规则必须体现在实现中，而不是只存在于文档。

### 5.5 Artifact Emission Boundary

winning branch 一旦选定，artifact emission 应保持极窄：

- `pred_witnesses`
  - 只从 selected branch 生成
- `non_fact_steps`
  - 只从 selected branch 生成
- `rule_ref_edges`
  - 只从 selected branch derive
- `rule_refs`
  - 继续由 narrowed `rule_ref_edges` 派生

first-round 不引入：

- top-level `selected_branch_index`
- non-winning branch shadow metadata
- mixed-branch diagnostics surface

selected branch identity 继续通过现有 atom keys recoverable。

### 5.6 Failure Shape

这轮实现需要显式决定并保持一致：

- 若没有任何 branch satisfy 当前 final binding
  - 视为 capture contract violation
  - 应 fail fast，而不是退回 mixed capture 或 silent fallback
  - 这同样适用于 single-branch AND 规则：
    - `_normalize_where_branches(...)` 会把它归一成只含 1 个 branch 的列表
    - 若这个唯一 branch 在 re-check 中仍不 satisfy 当前 final binding，说明 evaluator 与 capture 之间存在一致性问题，而不是“正常无匹配”
- 若多个 branch satisfy
  - 不报错
  - 直接按 `source-order wins` 选第一个 satisfying branch

### 5.7 Test Shape

first-round 测试至少覆盖：

1. single-branch baseline
   - 只有一个 AND branch
   - narrowing 应退化为 no-op
2. multi-branch source-order wins
   - 两个 branch 都 satisfy 同一 binding
   - artifact 只含 lowest-index branch 的 atoms
3. non-satisfying branch excluded
   - 某 branch 的 `pred` atom 在 `witness_facts` 中无 match
   - 该 branch 不得进入 artifact
4. `not` atom re-check
   - negated body 有 match
   - 该 branch 不 satisfy
5. `ruleref` cannot ground
   - `ruleref` terms 不能 ground
   - 该 branch 不 satisfy
6. arith compute-and-check
   - binding 中输出值与重算结果不一致
   - 该 branch 不 satisfy
7. legacy fallback no regression
   - 旧 artifact（无 `rule_ref_edges`，只有 flat `rule_refs`）
   - readback / tree fallback 行为不受影响
8. digest stability
   - narrowed artifact 对相同输入保持确定性

## 6. Boundaries And Invariants

- 必须保持的边界：
  - narrowing 只影响 support-capture emission，不重开 execution substrate
  - single-support candidate model 保持不变
  - recursive proof carrier 仍是 `rule_ref_edges + legacy rule_refs`
- 明确不做的内容：
  - 不保留 non-winning branch diagnostics
  - 不改变 `SupportArtifact` public DTO shape
  - 不把 legacy artifact 自动迁移成带 branch metadata 的新格式
- 兼容性约束：
  - old `support_digest -> SupportArtifact` readback 继续可用
  - static / runtime / audit tree consumer 无需感知新的 top-level branch field
  - 若 narrowing 失败，应显式报错，而不是 silently 退回 pre-winning behavior

## 7. Acceptance

- [x] support capture 已实现 winning-branch narrowing，而不是继续全分支混合 capture
- [x] narrowing 只发生在 `core.store._support_capture`，没有扩散成 tree-readback patch
- [x] `source-order wins` 已在实现和测试中被明确验证
- [x] atom-kind satisfaction re-check 已覆盖 `pred` / `ruleref` / `eq` / `ne` / `in` / cmp / arith / `not`
- [x] single-branch baseline、multi-branch overlap、non-satisfying branch exclusion、`not`、`ruleref` ungroundable、arith mismatch、legacy fallback、digest stability 都有针对性测试
- [x] 受影响模块 docs 已同步更新

## 8. Implementation Plan

1. 在 `_support_capture.py` 中提炼 atom-kind boolean re-check helpers，避免直接复用现有“先构建 DTO 再观察副作用”的代码路径。
2. 实现 `_find_winning_branch(...)`，用 capture-local re-computation 选择 selected branch，并固定 `source-order wins`。
3. 改写 `build_support_artifact_for_binding(...)`，只为 selected branch 生成 `pred_witnesses` / `non_fact_steps`。
4. 改写 `derive_rule_ref_edges_for_binding(...)`，只为 selected branch derive edges。
5. 补 targeted tests，覆盖本蓝图 §5.7 的 8 类场景。
6. 更新 core / service docs，记录 native candidate proof 已从 conservative all-branch capture 收口到 winning-branch contract。
7. 完成 outcome / audit，并在实现完成后归档。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md`
- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.audit.md`
- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `_support_capture` 新增 `find_winning_branch_index(...)`，并以 capture-local re-computation 实现 winning-branch narrowing
  - `build_support_artifact_for_binding(...)` / `derive_rule_ref_edges_for_binding(...)` 现在都只消费 selected branch
  - `_evaluate.py` 与 `ruleref_substrate.py` 在 capture 前统一先求 winning branch，再生成 narrowed artifact
  - targeted tests 已覆盖 single-branch no-op、source-order overlap、pred exclusion、`not`、ungroundable `ruleref`、arith mismatch、legacy fallback、digest stability，以及 single-branch no-satisfying-branch fail-fast
- 与 blueprint 不同的地方：
  - first-round 实现把“selected branch lacks row_support match”也视为 contract violation，并在 `derive_rule_ref_edges_for_binding(...)` 中 fail fast，而不再保留 pre-narrowing 的 `0-match => skip` 宽松语义
- 为什么会有这些调整：
  - narrowing 后 `derive_rule_ref_edges_for_binding(...)` 只面向 selected branch；若 selected branch 仍然没有 matching row_support，说明 branch selection 与 edge derivation 之间存在一致性问题，应尽早暴露
- 归档说明：
  - active blueprint 已标记 `implemented`；归档副本保留在 `docs/blueprints/archive/`
