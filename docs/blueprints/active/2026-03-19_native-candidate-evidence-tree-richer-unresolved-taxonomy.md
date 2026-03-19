# Task Blueprint: Native Candidate Evidence Tree Richer Unresolved Taxonomy

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/rules/ruleref_substrate.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)
  - [2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md)
  - [2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.audit.md](./2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.audit.md)

## 1. Problem

`recursive proof semantics` 与 `winning-branch narrowing` 都已经落地，native candidate evidence tree 现在已经能稳定表达：

- `referenced_support`
- `unresolved_support`
- `recursion_boundary`

但当前 unresolved / boundary 语义仍然是 **可用但未冻结的混合状态**：

- capture-side `RuleRefEdge.unresolved_reason` 当前只正式使用：
  - `child_support_unavailable`
- tree traversal / readback 当前还会额外产出：
  - `artifact_missing`
  - `cycle`
  - `depth_limit`
- 这些 reason 现在已经会穿透到 runtime / audit / static consumer
  - 但还没有形成一份正式的 taxonomy contract

这导致当前系统已经有 terminal semantics，却还没有回答清楚：

- 哪些 reason 属于正式 unresolved taxonomy
- 哪些属于 `unresolved_support`
- 哪些属于 `recursion_boundary`
- 哪些 reason 应由 capture 负责，哪些应由 tree traversal / readback 负责
- runtime / audit / static 是否必须看到同一组 reason enum

因此，这一轮不再讨论 child-proof handle、winning branch、或 execution substrate，而是单独收口：

- **recursive proof tree 的 richer unresolved / boundary taxonomy**

## 2. Goals

- 冻结 native candidate evidence tree 的 unresolved / boundary taxonomy 范围。
- 明确现有 reason 中哪些进入正式 contract，哪些继续保持实现细节。
- 明确 `unresolved_support` 与 `recursion_boundary` 的职责边界，不把两类 terminal 混成一个 generic error node。
- 冻结 reason 的 owner layer：
  - capture
  - tree traversal
  - artifact readback / lookup
- 明确 runtime / audit / static 三侧是否必须共享同一组 reason enum 与 node semantics。

## 3. Non-goals

- 不重开 `winning-branch semantics` 或 `winning-branch narrowing`。
- 不重开 `RuleRef` execution substrate。
- 不把 `WhereValidationError("no satisfying branch")`、duplicate row-support match、或其他 fail-fast capture violation 混进 unresolved taxonomy。
- 不扩成 graph、salience、certainty、engine parity。
- 不重开 `SupportArtifact.rule_ref_edges` / `NativeWhereEvaluation.rule_ref_resolutions` 的基础 DTO 形状。
- 不顺手做新的 UI 文案体系或 static page 视觉 redesign。

## 4. Current Context

- 当前 recursive proof carrier 已稳定：
  - `SupportArtifact.rule_ref_edges`
  - tree `rule_ref -> referenced_support`
  - explicit terminal nodes `unresolved_support` / `recursion_boundary`
- 当前 capture-side unresolved surface 很窄：
  - `ruleref_substrate._build_rule_row_support(...)` 在无法生成 child support artifact 时写：
    - `unresolved_reason="child_support_unavailable"`
  - `RuleRefEdge` / `NativeRuleRefRowSupport` 都允许 `child_support_digest | unresolved_reason`
- 当前 tree-side terminal reason 已比 capture-side 更宽：
  - `_candidate_evidence_tree.py`
    - `artifact_missing` -> `unresolved_support`
    - `cycle` -> `recursion_boundary`
    - `depth_limit` -> `recursion_boundary`
- 当前 consumer surface 已经直接暴露这些 reason：
  - runtime explain-tree 返回原始 node dict
  - audit DTO / query 读取同一 tree shape
  - static UI 直接渲染 `unresolved_reason` / `boundary_reason`
- 当前模块文档已经记录了这个分裂状态：
  - capture-side first-round `unresolved_reason` 只有 `child_support_unavailable`
  - `artifact_missing / cycle / depth_limit` 属于 tree terminal reason
- 当前更高层约束已经冻结：
  - recursive proof DTO 已 implemented
  - winning-branch 已 implemented
  - 这条线现在不应再回头修改 capture contract 或 branch semantics

## 5. Proposed Shape

### 5.1 Positioning

本蓝图是一条独立 capability decision：

- 它承接已实现的 recursive proof tree
- 只讨论 terminal semantics 的 taxonomy contract
- 不再讨论 proof edge 是否存在，也不讨论 branch choice

### 5.2 First-Round Questions To Freeze

若本蓝图继续推进到 `scoped`，至少需要先回答：

1. 哪些 reason 应进入正式 unresolved / boundary taxonomy？
   - 仅保留当前四个：
     - `child_support_unavailable`
     - `artifact_missing`
     - `cycle`
     - `depth_limit`
   - 还是 first-round 还要补更多枚举
2. 哪些 reason 属于 `unresolved_support`，哪些属于 `recursion_boundary`？
3. 每个 reason 的 owner 在哪一层？
   - capture
   - tree traversal
   - artifact lookup / readback
4. runtime / audit / static 三侧是否必须共享同一组 raw reason enum？
5. legacy artifact 与旧 terminal shape 如何兼容？

### 5.3 Decision Boundary

当前更需要冻结的不是“如何给这些 reason 起更漂亮的名字”，而是：

- **reason taxonomy 是否属于 shared tree contract**

更具体地说，当前系统已经通过 `candidate_evidence_tree` 把这些 reason 暴露给了三侧 consumer，因此 first-round 更合理的方向应是：

- runtime / audit / static 共享同一组 terminal node kinds
- 共享同一组 reason enum
- 不允许每个 consumer 自己再翻译成另一套局部状态机

否则即使底层 proof tree 已经同构，不同 consumer 仍可能对同一个 terminal 给出不一致解释。

first-round freeze position 是：

- runtime / audit / static 必须共享同一组 raw terminal reason enum
- 不引入 consumer-specific 翻译层
- 文档可以解释 reason 的 operator-facing 含义，但底层 carrier 不再派生第二套局部状态名

### 5.4 Owner Split

当前最自然的 first-round owner split 看起来是：

- capture-owned unresolved reason
  - `child_support_unavailable`
- tree readback / traversal-owned unresolved reason
  - `artifact_missing`
- tree traversal-owned boundary reason
  - `cycle`
  - `depth_limit`

也就是说，first-round 更像应保持：

- `unresolved_support`
  - 表示“想继续走 proof edge，但 child support 无法得到或无法解引用”
- `recursion_boundary`
  - 表示“proof traversal 主动停止，而不是数据缺失”

这条边界如果成立，就不应把：

- `artifact_missing`
- `cycle`
- `depth_limit`

全部塞回 capture-side `unresolved_reason`，也不应把它们压平成一个 generic terminal reason。

first-round owner freeze 是：

- `child_support_unavailable`
  - capture-owned
  - 更准确地说，是 child support capture / substrate 无法产出 child artifact 时的 unresolved reason
- `artifact_missing`
  - lookup / readback-owned
  - capture 只负责产出 digest 引用；真正知道“这个 digest 现在解不开”的是 tree readback / support lookup 层
- `cycle`
  - traversal-owned
- `depth_limit`
  - traversal-owned

这意味着 first-round 不应把 `artifact_missing` 重新叙述成 capture 当场已知的事实。

### 5.5 Compatibility Direction

当前更稳的 first-round 方向是：

- 保持现有 node taxonomy 不变：
  - `unresolved_support`
  - `recursion_boundary`
- 在这两个 node kind 内冻结 richer reason taxonomy
- legacy artifact 继续通过现有 fallback 路径工作
  - 没有 `rule_ref_edges` 的旧 artifact 不必为了 taxonomy 升级而迁移

first-round compatibility freeze 是：

- richer taxonomy 只适用于 structured `rule_ref_edges` path
- 没有 `rule_ref_edges` 的旧 artifact 继续走 legacy `rule_refs` fallback
  - 产出 `rule_ref_section`
  - 产出 flat `rule_ref` node
  - 不产出 `referenced_support`
  - 不产出 `unresolved_support`
  - 不产出 `recursion_boundary`

这意味着 first-round 更像是在冻结：

- tree terminal reason 的正式语义边界

而不是：

- 再开一轮 carrier migration

## 6. Boundaries And Invariants

- 必须保持的边界：
  - unresolved / boundary taxonomy 属于 shared candidate proof tree contract
  - runtime / audit / static 继续消费同一底层 tree shape
  - `unresolved_support` 与 `recursion_boundary` 的 node-kind split 不能被静默抹平
- 明确不做的内容：
  - 不把 fail-fast capture / evaluation violation 包装成 terminal node
  - 不把 taxonomy 设计成 multi-engine parity layer
  - 不把此话题扩成新的 carrier schema migration
- 兼容性约束：
  - 旧 artifact readback / static fallback 继续成立
  - 现有 `child_support_unavailable / artifact_missing / cycle / depth_limit` 不能在没有 scope freeze 的情况下被随意重命名
  - 若 first-round 不决定新增枚举，应优先保持 taxonomy 窄，而不是提前扩一套没有 owner 的 reason set

## 7. Acceptance

- [x] 已冻结 first-round unresolved / boundary taxonomy 的正式 reason 集合
- [x] 已明确 `unresolved_support` 与 `recursion_boundary` 的职责边界
- [x] 已冻结每个 reason 的 owner layer，不把 capture / traversal / lookup 混在一起
- [x] 已明确 runtime / audit / static 是否共享同一组 raw reason enum
- [x] 已明确 richer taxonomy 只适用于 structured `rule_ref_edges` path，legacy fallback 不进入 recursive terminal 语义面
- [x] 受影响模块 docs 已同步更新

## 8. Implementation Plan

1. 盘点当前 capture-side、tree traversal、artifact readback 三层已经存在的 reason 与 node-kind 映射。
2. 冻结 first-round taxonomy scope：reason 集合、node-kind mapping、owner split、consumer visibility。
3. 明确 legacy fallback 的边界：没有 structured child-proof contract 的旧 artifact 不进入 recursive terminal taxonomy。
4. 若 scope freeze 可成立，再决定是否需要新的 implementation blueprint，而不是直接在当前蓝图中写代码。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md`
- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.audit.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（若后续进入实现）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若后续进入实现）
- `src/factpy_kernel/audit/docs/01_overview.md`（若后续进入实现）

## 10. Outcome / Deviations

- 最终落地结果：
  - native candidate proof tree 的 richer unresolved / boundary taxonomy 已被冻结为正式 contract
  - first-round 正式 reason 集合保持为当前 live surface：
    - `child_support_unavailable`
    - `artifact_missing`
    - `cycle`
    - `depth_limit`
  - `unresolved_support` / `recursion_boundary` 的 node-kind split 被确认为正式语义边界
  - owner split 被确认为：
    - `child_support_unavailable` = capture / substrate-owned
    - `artifact_missing` = lookup / readback-owned
    - `cycle` / `depth_limit` = traversal-owned
  - runtime / audit / static 继续共享同一组 raw terminal reason enum
  - richer taxonomy 被明确限制在 structured `rule_ref_edges` path；legacy `rule_refs` fallback 不进入 recursive terminal taxonomy
- 与 blueprint 不同的地方：
  - 没有单开 implementation blueprint
- 为什么会有这些调整：
  - 这条线冻结的是已存在 live behavior 的正式 contract，而不是尚未落地的新机制
  - 代码已经满足 freeze 结论，剩余工作只是在模块 docs 中把实现细节提升为正式边界
- 归档说明：
  - 本蓝图已进入 `implemented`
  - 无新增代码实现切片；本轮属于 doc-and-contract promotion
  - 归档副本保留在 `docs/blueprints/archive/`
