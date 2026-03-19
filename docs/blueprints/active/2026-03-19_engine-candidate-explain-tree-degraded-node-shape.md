# Task Blueprint: Engine Candidate Explain-Tree Degraded Node Shape

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
  - [2026-03-18_engine-witness-parity.md](../archive/2026-03-18_engine-witness-parity.md)
- Audit Log:
  - [2026-03-19_engine-candidate-explain-tree-degraded-node-shape.audit.md](./2026-03-19_engine-candidate-explain-tree-degraded-node-shape.audit.md)

## 1. Problem

当前 engine candidate 的 flat explain 语义已经冻结为：

- `support_kind="engine_no_witness_v1"`
- legacy `"none"` 继续视为 degraded kind
- `explain(kind="candidate")` 返回：
  - `ok=true`
  - `witness_status="degraded"`

也就是说，engine candidate 已经不再被表述成 `not_found`，而是明确的 **degraded / no-witness** 结果。

但在 `candidate_evidence_tree` 这条 surface 上，三侧现在仍停在 native-only：

- runtime
  - `_explain_tree_candidate(...)` 对非 `native_binding_v1` 直接抛 `runtime_explain_not_supported`
- audit
  - `AuditQuery.get_candidate_evidence_tree(...)` 对非 native `support_kind` 直接抛 `AuditQueryError`
- static
  - `build_candidate_evidence_tree_dto(...)` / candidate evidence page 生成链路因此也天然是 native-only

这造成了一个明确的 live surface gap：

- engine candidate 在 flat explain 上已经有正式 degraded contract
- 但在 tree explain 上仍然没有合法 node shape，只能返回 unsupported / error

本蓝图的任务不是去做完整 engine witness parity，而是回答一个更窄的问题：

- **engine candidate 在 `explain-tree` 上应该产出什么 degraded tree shape？**

## 2. Goals

- 冻结 engine candidate 在 `candidate_evidence_tree` surface 上的 first-round degraded shape。
- 明确 runtime / audit / static 是否应对 engine degraded candidate 返回有效 tree，而不是 unsupported / exception。
- 冻结 degraded state 挂在哪个 node kind，而不是误复用 native recursive proof 的 `unresolved_support`。
- 冻结 degraded tree node 的最小字段集合。
- 在不要求 engine 产出 witness artifact 的前提下，补齐 explain-tree 的最小 consumer contract。

## 3. Non-goals

- 不做完整 engine witness parity。
- 不要求 `souffle` / `problog` 开始产出 native `SupportArtifact`。
- 不修改 adapter 内部求值或 provenance 输出。
- 不把 engine degraded candidate 伪装成 native recursive proof。
- 不复用 `unresolved_support` / `recursion_boundary` 来表达 engine no-witness。
- 不扩成 graph、salience、source taxonomy、或 multi-engine abstraction redesign。

## 4. Current Context

- 当前已实现的 engine degraded contract：
  - `ENGINE_NO_WITNESS_KIND = "engine_no_witness_v1"`
  - `_DEGRADED_SUPPORT_KINDS = {"none", "engine_no_witness_v1"}`
  - runtime `explain(kind="candidate")` 对 degraded kind 返回 `witness_status="degraded"`
- 当前 tree surface 仍是 native-only：
  - runtime `_explain_tree_candidate(...)` 直接 reject 非 native `support_kind`
  - audit `get_candidate_evidence_tree(...)` 也直接 reject 非 native `support_kind`
  - static candidate evidence page 因为 DTO builder 依赖 audit query，同样继承 native-only 限制
- 当前 native tree contract 已冻结并持续有效：
  - `candidate_result`
  - `support_section`
  - optional `rule_ref_section`
  - recursive proof node：
    - `referenced_support`
    - `unresolved_support`
    - `recursion_boundary`
- 当前 unresolved taxonomy 已单独冻结：
  - `unresolved_support`
    - `child_support_unavailable`
    - `artifact_missing`
  - `recursion_boundary`
    - `cycle`
    - `depth_limit`
- 因此 engine degraded candidate 不应简单复用 native recursive terminal taxonomy：
  - 它不是 “proof edge 断了”
  - 而是 “这个 candidate 本身没有 witness carrier”

## 5. Proposed Shape

### 5.1 Positioning

本蓝图是一条窄 capability decision：

- 它承接旧的 `engine degraded explain` flat contract
- 只讨论 tree surface 上的 degraded node shape
- 不承诺 engine 进入 native proof carrier

### 5.2 First-Round Questions To Freeze

若本蓝图继续推进到 `scoped`，至少需要先回答：

1. engine degraded candidate 在 `explain-tree` 上是否必须返回有效 tree，而不是 `not_supported` / exception？
2. degraded state 应挂在哪个 node kind？
   - root 直接降级
   - `support_section` 下的新专用 node
   - 或其他 shape
3. degraded node 的最小字段集合是什么？
   - `support_kind`
   - `witness_status`
   - `support_digest`
   - 是否需要单独的 degraded reason
4. runtime / audit / static 三侧是否必须共享同一个 degraded tree contract？
5. legacy degraded kind `"none"` 是否与 `engine_no_witness_v1` 在 tree surface 上完全同构？

### 5.3 Decision Boundary

当前更需要冻结的不是“engine 未来能否给出真 witness”，而是：

- **在没有 witness artifact 的前提下，engine candidate 是否仍然应有合法 tree surface**

当前更自然的 first-round 方向是：

- `candidate_evidence_tree` envelope 保持不变
- root 继续保持 `candidate_result`
- 仍保留 `support_section`
- 但 `support_section` 下不再要求 native support body，而是允许一个专门的 degraded node

这样做的好处是：

- 不破坏现有 `explain-tree` entry handle
- 不把 engine candidate 表述成 unsupported
- 不要求 engine 伪装成 native recursive proof

first-round 当前更合适的 freeze position 是：

- engine degraded candidate 在 `explain-tree` 上必须返回有效 tree
- runtime / audit / static 都不应继续把 degraded kind 表述成 unsupported / exception
- 顶层 envelope 继续保持：
  - `kind="candidate_evidence_tree"`
  - root `candidate_result`
  - `support_section`

### 5.4 Taxonomy Boundary

当前更合理的 first-round判断是：

- engine degraded node **不应复用** `unresolved_support`
- 也不应复用 `recursion_boundary`

原因很直接：

- `unresolved_support`
  - 当前已冻结为“想继续沿 child proof edge 走，但 child support unavailable / artifact missing”
- `recursion_boundary`
  - 当前已冻结为 traversal 主动停止
- engine degraded candidate
  - 则是“这个 candidate 自身没有 witness carrier”

因此，若 first-round 要在 tree surface 上表达 engine degraded candidate，更像需要：

- 一个新的专用 degraded node kind

而不是：

- 把 no-witness 混写进 native recursive taxonomy

first-round 当前更合适的 taxonomy freeze 是：

- degraded state 挂在 `support_section` 下
- 专用 node kind 采用：
  - `degraded_support`
- engine degraded tree first-round 不产出 native proof body：
  - 不产出 `rule_ref_section`
  - 不产出 `referenced_support`
  - 不产出 `unresolved_support`
  - 不产出 `recursion_boundary`

### 5.5 Compatibility Direction

当前更稳的 first-round方向是：

- native candidate tree contract 保持不变
- engine degraded candidate 返回与 native 同一个 envelope：
  - `kind="candidate_evidence_tree"`
  - root `candidate_result`
  - `support_section`
- 但 `support_section` 的 children 允许为一个 engine degraded node

这样可以保持：

- runtime / audit / static 的 candidate tree surface 仍是同一种顶层 DTO
- consumer 不需要先判断“native 才能看 tree”

同时应继续保持：

- legacy `"none"` 与 `engine_no_witness_v1` 在 tree surface 上同构
- 没有 witness artifact 时，不要求 `support_digest -> SupportArtifact` readback 成功

first-round 当前更合适的 compatibility freeze 是：

- `degraded_support` 的最小字段只收：
  - `node_kind="degraded_support"`
  - `support_kind`
  - `witness_status="degraded"`
  - `children=[]`
- first-round 不要求单独的 `degraded_reason`
- first-round 不在 degraded node 本体暴露 `support_digest`
  - 当前 zero digest 只是兼容 placeholder，不代表可解引用 witness handle
  - 若 consumer 仍需要 raw digest，继续从顶层 envelope 兼容字段读取，而不是从 degraded node 推导 readback 语义
- legacy `"none"` 与 `engine_no_witness_v1` 在 tree surface 上完全同构
  - 唯一允许保留的差异是 raw `support_kind` 值本身

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 这条线只解决 engine candidate 在 tree surface 上的 degraded shape
  - native recursive proof contract 不被回退或污染
  - runtime / audit / static 最终应共享同一 degraded tree contract
- 明确不做的内容：
  - 不让 engine path 伪装成 `native_binding_v1`
  - 不把 no-witness 解释成 `artifact_missing`
  - 不在 first-round 引入 engine-specific proof graph 或 adapter provenance payload
- 兼容性约束：
  - 既有 flat `explain(kind="candidate")` degraded contract 保持不变
  - native candidate tree shape 保持不变
  - legacy `"none"` 继续作为 degraded kind 兼容输入

## 7. Acceptance

- [x] 已明确并实现 engine degraded candidate 在 `explain-tree` 上返回有效 tree
- [x] 已冻结并实现 degraded tree node 的挂载层级与 node kind（`support_section -> degraded_support`）
- [x] 已冻结并实现 degraded node 的最小字段集合，并明确不在 node 本体暴露 `support_digest`
- [x] 已明确并实现 runtime / audit / static 共享同一 degraded tree contract
- [x] 已明确并实现 legacy `"none"` 与 `engine_no_witness_v1` 的 tree-surface 兼容边界
- [x] 受影响模块 docs 已同步更新

## 8. Implementation Plan

1. 盘点当前 runtime / audit / static 三侧 engine degraded candidate 的现状：哪些地方返回 unsupported，哪些地方抛错。
2. 冻结 first-round tree shape：envelope、挂载层级、`degraded_support` node kind、最小字段集。
3. 明确 degraded tree contract 与 native recursive taxonomy 的边界，避免复用 `unresolved_support`，并确认 first-round 不产出 native recursive nodes。
4. 若 scope freeze 可成立，再决定是否需要新的 implementation blueprint。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md`
- `docs/blueprints/active/2026-03-19_engine-candidate-explain-tree-degraded-node-shape.audit.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若后续进入实现）
- `src/factpy_kernel/core/docs/01_architecture.md`（若后续进入实现）
- `src/factpy_kernel/audit/docs/01_overview.md`（若后续进入实现）

## 10. Outcome / Deviations

- 最终落地结果：
  - runtime `explain-tree` 对 degraded kind 不再返回 `runtime_explain_not_supported`
  - audit `get_candidate_evidence_tree(...)` 也不再拒绝 degraded kind
  - 新增专用 degraded tree builder，返回：
    - `candidate_result`
    - `support_section`
    - `degraded_support`
  - `degraded_support` 最小字段固定为：
    - `support_kind`
    - `witness_status="degraded"`
    - `children=[]`
  - static candidate evidence page 已可渲染 degraded tree
  - focused tests 已覆盖 runtime degraded tree、audit/static round-trip，以及 native tree 回归
- 与 blueprint 不同的地方：
  - 没有新增单独的 `degraded_reason` 字段
- 为什么会有这些调整：
  - first-round 只需要表达 “engine candidate has no witness carrier”；`support_kind + witness_status` 已足够，不需要再发明第二层 degraded enum
- 归档说明：
  - 本蓝图已进入 `implemented`
  - 归档副本保留在 `docs/blueprints/archive/`
