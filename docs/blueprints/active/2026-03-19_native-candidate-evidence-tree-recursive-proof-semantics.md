# Task Blueprint: Native Candidate Evidence Tree Recursive Proof Semantics

- Status: draft
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-19_native-where-ruleref-execution-substrate.md](./2026-03-19_native-where-ruleref-execution-substrate.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_runtime-traceability-evidence-tree-realignment.md](../archive/2026-03-18_runtime-traceability-evidence-tree-realignment.md)
  - [2026-03-18_native-candidate-evidence-tree-v1.md](../archive/2026-03-18_native-candidate-evidence-tree-v1.md)
  - [2026-03-19_native-candidate-evidence-tree-v2.md](../archive/2026-03-19_native-candidate-evidence-tree-v2.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.audit.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.audit.md)

## 1. Problem

`native candidate evidence tree v2` 已经把 candidate explain 从 flat payload 提升成了稳定的 result-centric tree surface：

- runtime 有 `POST /queries/explain-tree`
- audit 有 `get_candidate_evidence_tree(candidate_id)`
- static 有 `candidate_evidence/{candidate_id}.html`
- root 下已经有 `support_section` 与按需出现的 `rule_ref_section`

但 v2 仍然停在 **tree carrier 的结构化底座**，还没有进入更强的 recursive proof semantics：

- `rule_ref` 已是 first-class node，但 `children` 仍为空
- current tree 仍主要表达 “candidate -> support groups / checks / minimal rule refs”
- 当前 native `SupportArtifact` 已可记录 direct `rule_refs`，但 `Store.evaluate(...)` 所走的 native support capture 仍只产出 bare rule ids，而不是 child proof handles
- 因此，现有 tree 已经像 evidence tree 的入口，却还不能真正沿 proof dependency 继续展开

与此同时，最新 handoff 已明确：

- `evidence tree v2` 已完成
- 下一步应该是新的 capability decision
- 更自然的候选方向之一是 `richer recursive proof semantics`

`docs/references/external/rainbird-evidence-chain-compare.md` 也提供了一个有价值的外部参照：

- result-centric proof entry
- recursive evidence tree
- structured API / shareable page / NL explain 共用同一底层 proof carrier

本蓝图的任务就是把这个方向收口成一个窄范围的下一阶段入口，而不是继续停留在“是否要做 tree”的讨论。

## 2. Goals

- 把 evidence-tree 之后的下一条 capability line 收口为：`native candidate evidence tree` 的 recursive proof semantics。
- 明确当前 v2 树形载体还缺哪些语义，才能从 sectioned tree 走到真正可递归消费的 proof tree。
- 比较并冻结 first-round recursive expansion 应该挂在哪些节点、依赖哪些底层 capture、以及如何停止递归。
- 明确哪些 Rainbird 设计理念被采纳为本轮参考，哪些继续 defer。
- 为后续实现型子切片提供清晰边界，但当前不预设已经可以直接编码。

## 3. Non-goals

- 不切到 graph UI / graph layout / graph API。
- 不打开 engine witness parity。
- 不把 salience / impact breakdown / annotation-value semantics 带进本轮。
- 不引入 certainty / probability / extraction uncertainty contract。
- 不做 snippet/span provenance、source-linkage graph、或更细 source taxonomy 全量方案。
- 不重写 `rule_run` trace carrier；它仍是独立 explain surface。
- 不把本轮扩成 case/package object 或 conflict-resolution UI。

## 4. Current Context

- 当前正式 truth 已明确：
  - `candidate evidence tree` 是稳定 consumer surface，不再只是实验草稿
  - runtime / audit / static 三侧同构
  - graph、engine parity、salience、finer provenance 仍然都在边界外
- 当前 v2 实现形状：
  - root：`candidate_result`
  - children：
    - `support_section`
    - `rule_ref_section`（仅当 `rule_refs` 非空）
  - leaf：
    - `assertion_fact`
    - `non_fact_check`
    - minimal `rule_ref`
- 当前直接实现中存在一个关键现实约束：
  - `_candidate_evidence_tree.py` 已能渲染 minimal `rule_ref` nodes
  - `_evaluate.py` 现在也能把 direct `rule_refs` 写进 `SupportArtifact`
  - 但 native derivation 主路径还没有稳定产出可递归追踪的 referenced support edges
- 当前 upstream execution-side blocker 已经被单独实现切片收口：
  - native `query + derivation` 现在通过 `rules.ruleref_substrate.evaluate_native_where(...)` 执行 `RuleRef`
  - `Store.evaluate(..., registry=RuleRegistry | None)` 已具备显式 registry-backed native `RuleRef` 执行入口
  - service/runtime derivation evaluate 也已复用 `override_registry_root` / `registry_root` / `session.registry_root` 进入同一 substrate
- 但当前 capture-side blocker 仍然存在，而且仍然阻止本蓝图进入 `scoped`：
  - native `SupportArtifact.rule_refs` 现在只能稳定交出 direct `rule_ref_id`
  - 当前还没有 `rule_ref_id + child_support_digest` 级别的 child-proof edge handle
  - 多分支 `RuleRef` child-proof capture 也仍然 deferred，尚未定义 winning-branch semantics
- 当前相邻 explain substrate：
  - candidate tree 依赖 `SupportArtifact`
  - rule-run explain 依赖 `RuleTraceArtifact`
  - `RuleTraceArtifact` 已有 `ruleref_links` 和 invocation tree，但它不是 candidate tree 的 current carrier
- 外部参考的采用边界：
  - Rainbird 只作为设计比较与 consumer-shape 提示
  - 不作为当前 contract 或实现真相

## 5. Proposed Shape

### 5.1 Positioning

本蓝图默认把 `richer recursive proof semantics` 视为 evidence tree v2 之后最自然的一条主线：

- 延续现有 `native + candidate + tree` 主轴
- 优先深化 proof carrier 本体
- 不改成 graph-first，也不切去 engine parity-first

### 5.2 Design Principles To Borrow From Rainbird

本轮优先吸收这些理念：

1. `result-centric proof entry`
   - 每个 candidate 应继续作为稳定入口，而不是退回到 flat explain payload。
2. `recursive evidence tree first`
   - 在 graph 之前，先把 tree 的递归语义做实。
3. `multi-surface delivery on one carrier`
   - runtime JSON、audit DTO、static page 继续共用同一底层 proof carrier。
4. `consumer-facing shape matters`
   - 要先回答 tree 节点如何被人和程序理解，而不是只追加内部 metadata。

本轮明确不采纳这些更宽的部分：

- salience chart
- certainty 语义
- 完整 interaction log
- graph-style dependency canvas

### 5.3 First-Round Questions To Freeze

若本蓝图继续推进到 `scoped`，至少需要先回答这些问题：

1. 递归到底挂在哪个节点上？
   - `rule_ref`
   - `rule_ref -> referenced_support`
   - 还是新的 intermediate node kind
2. 递归边是由什么 handle 驱动？
   - 仅有 `rule_ref_id`
   - `rule_ref_id + child support handle`
   - 还是其他 proof edge identity
3. 停止递归的条件是什么？
   - 无 child support
   - degraded / no-witness support
   - depth guard
   - cycle hit
4. unresolved referenced support 是省略，还是显式节点？
5. runtime / audit / static 三侧是否允许看到同一个 recursion boundary reason？

这些问题不是独立冻结的。它们都受 §5.5 capture gap 的约束，尤其是：

- Q2 `递归边是由什么 handle 驱动`
- 以及由此反向约束的 Q1 / Q3 / Q4

因此，在从 `draft` 推进到 `scoped` 之前，必须先确认 native capture 侧能够交出的最小 proof-edge handle 是什么。

当前 first-round 的最低可用门槛应至少是：

- `rule_ref_id + child_support_digest`

如果 capture 侧在 first-round 仍然只能交出 `rule_ref_id`，而不能稳定交出 child support handle，那么 recursive tree contract 不应先被冻结成一个依赖 child proof readback 的 shape。此时更合理的动作是：

- 先补 capture gap
- 然后再冻结 recursive expansion contract

而不是先交付一版只有 placeholder terminal nodes、但没有真实 child proof handle 的“递归” tree。

### 5.4 Current Likely Direction

基于当前代码与文档，first-round 更像需要先收口一个 **可递归但仍然保守的 tree contract**，而不是直接承诺任意深度 proof expansion。

更可能的第一轮形状是：

- root 继续保持 `candidate_result`
- `support_section` 继续作为主 evidence body
- `rule_ref_section` 中的 `rule_ref` 节点允许进入第一层 referenced-support expansion
- 当 referenced support 不可解析时，保持显式 terminal node，而不是静默丢失
- cycle / depth / degraded-support 都需要有清楚的停止语义

也就是说，下一步更像：

- **先把 recursion contract 立起来**

而不是：

- 一口气做 fully expanded proof graph

### 5.5 Likely Capture/Carrier Gap

当前最需要正视的现实是：v2 已经有 tree 形状，但 native capture substrate 还没有把 recursive edge 真正交出来。

因此，本蓝图后续很可能需要把问题拆成两层：

1. `recursive proof tree contract`
   - node taxonomy
   - recursion boundary
   - unresolved/degraded/cycle semantics
2. `native support capture gap`
   - 需要什么额外信息，才能让 candidate tree 顺着 `rule_ref` 继续走到 child proof

如果第二层没有先收口，tree 侧单独深化很容易退化为更多 placeholder 节点，而不是真正的 proof semantics。

上游 `execution gap` 已经被单独切片解决，因此本蓝图当前不应再被解读为 execution-plus-capture 双重阻塞。更准确的当前判断是：

1. shared native where `RuleRef` execution substrate 已成立
2. 当前剩余 blocker 已收口为 capture/carrier gap
3. 只有当 native capture 可稳定交出 `rule_ref_id + child_support_digest` 这类 child-proof handle 时，本蓝图才有资格推进到 `scoped`

这里的依赖关系需要显式保持：

- `recursive proof tree contract` 不能假设 capture 侧已经有 child proof handle
- `capture contract` 也不能只交 `rule_ref_id`，却要求 tree builder 凭空构造递归 proof edge

因此，若后续 scope freeze 想采用 `rule_ref -> child proof` 这条递归路径，就必须先证明 native capture 可稳定交出这条 edge 的最小 handle，至少达到：

- `rule_ref_id + child_support_digest`

否则，这条递归路径应继续保持 deferred，而不是把当前 direct `rule_refs` 误当成可递归 child proof shipped。

### 5.6 Delivery Invariants

无论后续是否实现，本蓝图默认保持这些不变：

- canonical entry 仍是 `candidate_id`
- runtime `explain-tree` 不被 graph surface 替换
- audit DTO 与 runtime shape 继续同构
- static page 继续是 nested evidence page，不跳成 graph app
- assertion leaf 继续保持窄边界，不退化为 full assertion dump

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 这条主线仍属于 `runtime-traceability-explainability` 母蓝图内的 evidence-tree 延续
  - `native + candidate + tree` 仍是 first-round 边界
  - Rainbird 只作为外部参照，不升级为系统真相
- 明确不做的内容：
  - 不把 rule-run trace 与 candidate tree 强行并成一个 carrier
  - 不因为递归需求，就提前打开 certainty、salience、snippet/span 或 graph
  - 不承诺 current code 已具备直接递归展开所需的全部 substrate
- 兼容性约束：
  - 现有 `explain` / `explain-tree` entry handle 不破坏
  - v2 已存在的 root / section / leaf 边界不应被随意打散
  - 若后续发现 runtime substrate 不足，应先补 capture contract，再扩 tree rendering

## 7. Acceptance

- [ ] 已明确 evidence tree v2 之后的下一条 capability line 是 `recursive proof semantics`，而不是 graph 或 engine parity
- [ ] 已冻结 first-round recursive tree 的边界问题、停止条件与 carrier 依赖问题
- [ ] 已明确记录本轮采纳的 Rainbird 设计理念与继续 deferred 的部分
- [ ] 后续若进入实现，受影响模块 docs 将同步更新

## 8. Implementation Plan

1. 用本蓝图先收口 next-stage 目标、边界和外部参照，不直接跳到实现。
2. 识别 current `SupportArtifact` / candidate-tree substrate 对递归 proof expansion 的最小缺口。
3. 若缺口可被压成一轮窄实现，再把本蓝图推进到 `scoped`，并拆成实现动作。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md`
- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.audit.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（若后续进入实现）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若后续进入实现）
- `src/factpy_kernel/audit/docs/01_overview.md`（若后续进入实现）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
