# Task Blueprint: Native Candidate Evidence Tree Recursive Proof Semantics

- Status: implemented
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
- recursive proof first-round 已落地：
  - native `SupportArtifact` 现在同时携带 legacy `rule_refs` 与 structured `rule_ref_edges`
  - widened `NativeWhereEvaluation` 已可带回 occurrence-scoped `rule_ref_resolutions`
  - `_evaluate.py` 已按 exact tuple match 把 `rule_ref_resolutions` 压缩成 binding-scoped `rule_ref_edges`
  - runtime / audit / static `candidate_evidence_tree` 已可沿 `child_support_digest` 继续展开 `referenced_support`
  - `unresolved_support` / `recursion_boundary` 已成为显式 terminal node
- 仍然 deferred 的边界：
  - multi-branch winning semantics
  - richer `unresolved_reason` enum
  - engine witness parity
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

当前 first-round 的最低可用门槛不应再表述为裸的：

- `rule_ref_id + child_support_digest`

而应冻结成 **per-occurrence structured edge**。更合理的最小 resolved edge handle 是：

- `ruleref_atom_key`
- `rule_ref_id`
- `rule_ref_version`
- `child_support_digest`

其中：

- `ruleref_atom_key` 必须复用现有 `rule_ir` / trace 已采用的 `b{branch}.a{atom}:ruleref` 命名空间
- 不能只靠 `rule_ref_id` 区分 edge，因为同一个 rule 在同一 where 中可能出现多次
- `rule_ref_version` 也不能丢，否则 capture contract 不能稳定指向 registry 中的具体 target version

如果 capture 侧在 first-round 仍然只能交出 bare `rule_ref_id`，而不能稳定交出 per-occurrence child proof handle，那么 recursive tree contract 不应先被冻结成一个依赖 child proof readback 的 shape。此时更合理的动作是：

- 先补 capture gap
- 然后再冻结 recursive expansion contract

而不是先交付一版只有 placeholder terminal nodes、但没有真实 child proof handle 的“递归” tree。

### 5.4 Current Likely Direction

基于当前代码与文档，first-round 更像需要先收口一个 **可递归但仍然保守的 tree contract**，而不是直接承诺任意深度 proof expansion。

更可能的第一轮形状是：

- root 继续保持 `candidate_result`
- `support_section` 继续作为主 evidence body
- `rule_ref_section` 继续保留，但其底层 carrier 不再只靠 flat `rule_refs`
- 新增 `rule_ref_edges` 作为 structured recursive carrier，`rule_ref` 节点按 edge occurrence 展开第一层 referenced-support expansion
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
3. 只有当 native capture 可稳定交出 per-occurrence structured child-proof edge 时，本蓝图才有资格推进到 `scoped`

这里的依赖关系需要显式保持：

- `recursive proof tree contract` 不能假设 capture 侧已经有 child proof handle
- `capture contract` 也不能只交 `rule_ref_id`，却要求 tree builder 凭空构造递归 proof edge
- `NativeWhereEvaluation` 的输出形状也不能保持不变；若要进入 recursive proof，shared substrate 必须能把 per-occurrence child edge 信息带回 capture 层

因此，若后续 scope freeze 想采用 `rule_ref -> child proof` 这条递归路径，就必须先证明 native capture 可稳定交出这条 edge 的最小 handle，至少达到：

- `ruleref_atom_key + rule_ref_id + rule_ref_version + child_support_digest`

并且 first-round 的 carrier 形状更适合明确冻结为：

- `SupportArtifact.rule_ref_edges`
  - 新增 structured field，按 occurrence 承载 recursive child-proof edges
  - resolved edge 最少包含上面的四字段
  - unresolved edge 可允许 `child_support_digest=None`，以显式表达 `unresolved_support`
- `SupportArtifact.rule_refs`
  - 继续保留为 legacy compatibility summary
  - 只作为 flat rule-id 列表，不再承担 recursive proof contract

否则，这条递归路径应继续保持 deferred，而不是把当前 direct `rule_refs` 误当成可递归 child proof shipped。

### 5.5A First-Round Capture Contract Shape

基于当前代码现实，first-round 更合理的 capture contract 应明确收口为：

1. `SupportArtifact` 保持向后兼容
   - 继续保留 `rule_refs: list[str]`
   - 新增 `rule_ref_edges: list[edge]`
2. `edge` 采用 per-occurrence shape
   - `ruleref_atom_key`
   - `rule_ref_id`
   - `rule_ref_version`
   - `child_support_digest | None`
   - `unresolved_reason | None`
3. `ruleref_atom_key` 复用现有命名空间
   - 与 `pred_atom_key` / `non_fact_step_key` 保持同一风格
   - 不发明第三套 tree-only key scheme
4. `NativeWhereEvaluation` 也必须同步扩宽
   - 当前只返回 `bindings + rule_refs`
   - 若要支持 recursive proof，必须能把 per-occurrence child edge 信息带回 `_evaluate.py`
   - 不能只冻结 `SupportArtifact` 侧 contract，而假设 substrate 输出不变

更具体地说，`SupportArtifact.rule_ref_edges` 的 first-round DTO 应冻结为：

- `RuleRefEdge`
  - `ruleref_atom_key: str`
  - `rule_ref_id: str`
  - `rule_ref_version: str`
  - `child_support_digest: str | None`
  - `unresolved_reason: str | None`

建议的不变量：

- resolved edge
  - `child_support_digest` 为 `sha256:...`
  - `unresolved_reason is None`
- unresolved edge
  - `child_support_digest is None`
  - `unresolved_reason` 为非空字符串
- `SupportArtifact.rule_ref_edges` 按稳定顺序排序
  - `ruleref_atom_key`
  - `rule_ref_id`
  - `rule_ref_version`
  - `child_support_digest or ""`

这里 `rule_ref_edges` 是 **binding-scoped** 的：

- 一个 `SupportArtifact` 只描述一个最终 binding
- 因此 `rule_ref_edges` 不再需要重复携带 parent binding 本身
- `row_terms` 这类“如何从 child rows 匹配到该 binding”的信息，应该留在 widened substrate 输出，而不是写进最终 support carrier

### 5.5B Widened NativeWhereEvaluation Shape

为了让 `_evaluate.py` 真正生成上面的 binding-scoped `rule_ref_edges`，`NativeWhereEvaluation` 不能继续只返回：

- `bindings`
- `rule_refs`

更合理的 first-round widened DTO 应冻结为：

- `NativeWhereEvaluation`
  - `bindings: list[dict[str, Any]]`
  - `rule_refs: tuple[str, ...]`
  - `rule_ref_resolutions: tuple[NativeRuleRefResolution, ...]`

其中：

- `rule_refs`
  - 继续保留为 legacy summary
  - 可由 `rule_ref_resolutions` 派生
- `rule_ref_resolutions`
  - 是 occurrence-scoped，不是 binding-scoped
  - 负责把 parent capture 所需的 child row support handles 带回 `_evaluate.py`

`NativeRuleRefResolution` 的 first-round 形状应至少为：

- `ruleref_atom_key: str`
- `rule_ref_id: str`
- `rule_ref_version: str`
- `row_supports: tuple[NativeRuleRefRowSupport, ...]`

`NativeRuleRefRowSupport` 的 first-round 形状应至少为：

- `row_terms: tuple[Any, ...]`
- `child_support_digest: str | None`
- `unresolved_reason: str | None`

建议的不变量：

- `rule_ref_resolutions` 按 `ruleref_atom_key` 排序
- `row_supports` 按 row tuple 的稳定顺序排序
- resolved row support
  - `child_support_digest` 非空
  - `unresolved_reason is None`
- unresolved row support
  - `child_support_digest is None`
  - `unresolved_reason` 非空

这层 DTO 的职责是：

- substrate 负责“这个 `ruleref` atom 产生了哪些 child rows，以及每个 row 是否已有 child support digest”
- `_evaluate.py` 负责“对当前 final binding，选中哪个 row_support，并把它压缩成 binding-scoped `RuleRefEdge`”

这样可以避免把 binding-specific selection 逻辑提前塞进 substrate，也避免让 tree builder 重新发明 row matching。

### 5.5C Row-Support Matching Rule

`_evaluate.py` 从 occurrence-scoped `rule_ref_resolutions` 生成 binding-scoped `rule_ref_edges` 时，matching 规则也需要显式冻结。

first-round 更合理的 deterministic 规则是：

1. 对当前 parent binding 和某个 `ruleref_atom_key`：
   - 按该 occurrence 在 original where 中的 terms 顺序做 grounding
   - 得到一个 `grounded_row_terms: tuple[Any, ...]`
2. 在对应 `NativeRuleRefResolution.row_supports` 中做 **exact tuple match**
   - `row_support.row_terms == grounded_row_terms`
3. match 结果按以下规则处理：
   - 恰好 1 个 match：为当前 binding emit 1 条 `RuleRefEdge`
   - 0 个 match：当前 binding 不为该 occurrence emit edge
   - 多于 1 个 match：视为 substrate contract violation，应 fail fast，而不是静默选第一条

这里有两个明确边界：

- `row_terms` 必须与 `ruleref` atom 的 terms 顺序一一对齐
- matching 只做 tuple equality，不做子集匹配、类型宽松匹配、或 tree-side heuristic

这条规则的含义是：

- `SupportArtifact.rule_ref_edges` 只记录“当前 binding 与哪个 child row 精确对上了”
- 对于 OR-of-AND 中未命中当前 binding 的 occurrence，不会因为“没匹配到 row_support”就被写成 unresolved edge

这有意保持一个窄边界：

- 它减少了 non-winning branch 噪音
- 但它还不等于完整的 winning-branch semantics
- 多分支 proof path 的更强语义仍然继续 deferred

### 5.5D Generation Boundary

`child_support_digest` 必须在 native capture 层生成，而不是由 tree builder 事后推断。

更自然的边界是：

- shared substrate 在 child rule rows 已经成立的地方，同时产出 child support handle
- `_evaluate.py` 在 parent binding support capture 时，把这些 handles 写进 `SupportArtifact.rule_ref_edges`
- tree builder 只消费 `rule_ref_edges` 并复用现有 `support_digest -> SupportArtifact` readback

不应采用的路线：

- tree builder 只拿到 `rule_ref_id`，再反向推断 child support
- service / audit 各自另做一套 child support resolution

补充一个边界：

- recursive proof 不需要再发明第二种 child handle 系统
- `child_support_digest` 继续复用现有 `support_digest -> SupportArtifact` readback
- 这也是为什么 first-round DTO 应围绕 digest 冻结，而不是围绕 tree-only object pointer

### 5.5E `unresolved_reason` Enum

`unresolved_reason` 的 first-round 枚举也应保持极窄，不要把 capture-side unresolved 和 tree traversal terminal reasons 混成一个字段。

对 `NativeRuleRefRowSupport.unresolved_reason` / `SupportArtifact.RuleRefEdge.unresolved_reason`，first-round 只建议允许：

- `child_support_unavailable`

它的含义是：

- 当前 matched child row 已知存在
- 但 native capture 没能为该 row 产出 `child_support_digest`

first-round 不应把这些值塞进 `unresolved_reason`：

- `artifact_missing`
  - 这是 tree readback 阶段的 unresolved terminal reason
  - 不是 capture-side unresolved reason
- `cycle`
  - 这是 recursion boundary
  - 不属于 edge unresolved reason
- `depth_limit`
  - 同样属于 recursion boundary
  - 不属于 edge unresolved reason
- `no_matching_row`
  - 0-match 情况按上节规则应直接“不 emit edge”
  - 不是 unresolved edge

因此 first-round 的责任边界是：

- edge-level `unresolved_reason`
  - 只表达 capture 已知 row，但没有 child support digest
- tree terminal reason
  - 单独表达 `artifact_missing`
  - 单独表达 `cycle` / `depth_limit`

### 5.5F Terminal Node Semantics

first-round 若进入 recursive tree contract，terminal node 语义也必须显式冻结。

至少应区分两类：

1. `unresolved_support`
   - capture 没有拿到 `child_support_digest`
   - 或拿到 digest 但 artifact readback miss
   - 这属于 proof data 缺失，不是 traversal 主动停止
2. `recursion_boundary`
   - `cycle`
   - `depth_limit`
   - 这属于 traversal 主动停止，不是 proof data 缺失

这两类不能合并成同一个 generic terminal reason，否则 consumer 无法区分：

- “没有 child proof data”
- “系统故意在这里停住了”

### 5.5G Branch-Winning Constraint

branch-winning 仍然是 current first-round 的显式约束。

当前 native support capture 仍遍历所有 OR branches，因此在 winning-branch semantics 没冻结前：

- multi-branch `RuleRef` child edges 只能被视为保守 capture
- 不能宣称它们已经代表了最终 winning proof path

因此 first-round 若继续推进 recursive capture，更稳的路线仍然是：

- 先支持单分支 / 无歧义场景下的 child-proof edge
- 多分支 `RuleRef` child-proof semantics 继续 deferred
- blueprint 必须把这个约束显式保留，而不是默认“所有 capture edge 都等于 winning path”

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

- [x] 已明确 evidence tree v2 之后的下一条 capability line 是 `recursive proof semantics`，而不是 graph 或 engine parity
- [x] 已冻结 first-round recursive tree 的边界问题、停止条件与 carrier 依赖问题
- [x] 已明确记录本轮采纳的 Rainbird 设计理念与继续 deferred 的部分
- [x] 受影响模块 docs 已同步更新

## 8. Implementation Plan

1. 扩宽 `NativeWhereEvaluation`，引入 `rule_ref_resolutions` / `row_supports` 的 first-round DTO。
2. 扩宽 `SupportArtifact`，新增 binding-scoped `rule_ref_edges`，同时保留 legacy `rule_refs`。
3. 在 `_evaluate.py` 中按已冻结的 exact tuple match 规则，把 occurrence-scoped resolution 压缩成 binding-scoped edges。
4. 更新 candidate tree builder / runtime / audit / static consumer，使其优先消费 `rule_ref_edges`，并为 `unresolved_support` / `recursion_boundary` 保留显式 terminal node 语义。
5. 补 targeted tests，覆盖 resolved edge、`child_support_unavailable`、0-match no-edge、以及 contract-violation fast-fail。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md`
- `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.audit.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（若后续进入实现）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若后续进入实现）
- `src/factpy_kernel/audit/docs/01_overview.md`（若后续进入实现）

## 10. Outcome / Deviations

- 最终落地结果：
  - `NativeWhereEvaluation` 已扩宽为 `bindings + rule_refs + rule_ref_resolutions`
  - `SupportArtifact` 已新增 `rule_ref_edges`，同时保留 legacy `rule_refs`
  - native support capture 已按 exact tuple match 生成 binding-scoped child-proof edge
  - runtime / audit / static candidate evidence tree 已优先消费 `rule_ref_edges`，并支持 `referenced_support`、`unresolved_support`、`recursion_boundary`
  - targeted tests 已覆盖 recursive proof resolved path、unresolved terminal、0-match no-edge、以及 duplicate row-support fast-fail
- 与 blueprint 不同的地方：
  - first-round tree builder 同时实现了 `artifact_missing` / `cycle` / `depth_limit` terminal node 语义，虽然 capture-side `unresolved_reason` 仍保持最窄枚举
- 为什么会有这些调整：
  - tree traversal 本身必须区分“artifact readback miss”和“主动 recursion stop”，否则 runtime / audit / static 三侧无法共享同一个 terminal semantics
- 归档说明：
  - active blueprint 已标记 `implemented`；归档副本保留在 `docs/blueprints/archive/`
