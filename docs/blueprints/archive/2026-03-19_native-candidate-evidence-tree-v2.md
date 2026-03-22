# Task Blueprint: Native Candidate Evidence Tree V2

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/blueprints/archive/2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [docs/blueprints/archive/2026-03-18_runtime-traceability-evidence-tree-realignment.md](../archive/2026-03-18_runtime-traceability-evidence-tree-realignment.md)
  - [docs/blueprints/archive/2026-03-18_native-candidate-evidence-tree-v1.md](../archive/2026-03-18_native-candidate-evidence-tree-v1.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-19_native-candidate-evidence-tree-v2.audit.md](./2026-03-19_native-candidate-evidence-tree-v2.audit.md)

## 1. Problem

`native candidate evidence tree v1` 已经把 candidate explain 从 flat pointer 推进成了 first-class tree DTO，并且覆盖了：

- runtime `explain-tree`
- audit 同构 DTO
- static nested tree page

但当前 v1 仍然明显是 **tree carrier 的第一版**，而不是更完整的 evidence tree：

- node taxonomy 仍然偏薄
- root 下仍然是 flat support groups
- `rule_refs` 仍然只停留在 root metadata，不进入 tree
- nested rendering 仍然更像 “payload dump + children”，不是 evidence-card 风格 tree

如果继续沿 Rainbird-style evidence chain 这条线推进，最自然的下一步不是 graph、engine parity 或 salience，而是把 **tree 本体** 做得更像真正的 evidence tree，同时保持当前母蓝图边界不扩散。

## 2. Goals

- 在不改变 `native + candidate` 入口边界的前提下，深化 candidate evidence tree 的 node taxonomy。
- 让 tree 不再只是 `candidate -> support atom/check -> assertion leaf` 的薄包装，而是更清晰地表达 support structure。
- 允许有限递归展开，使 `rule_refs` / support grouping 可以进入 tree，而不是只停在 root metadata。
- 改善 runtime/audit/static 的 nested tree rendering，使其更接近 result-centric evidence tree，而不是 payload dump。
- 保持 v1 已验证的 leaf ownership boundary：assertion leaf 仍然只保留最小字段，深 detail 继续下钻 assertion detail。

## 3. Non-goals

- 不做 engine witness parity。
- 不做 graph layout / graph UI。
- 不做 salience / impact / annotation-value semantics。
- 不做 snippet/span provenance。
- 不做 uncertainty scoring / extraction confidence contract。
- 不做 first-class case/package object。
- 不把 tree 扩成 full conflict-resolution 或 judgment UI。

## 4. Current Context

- 当前 runtime/audit/static 已有 `candidate evidence tree v1`：
  - runtime `POST /queries/explain-tree`
  - audit `get_candidate_evidence_tree(candidate_id)`
  - static `candidate_evidence/{candidate_id}.html`
- 当前 tree 是 recursive schema，但实际语义仍然偏浅：
  - root：`candidate_result`
  - middle：`predicate_witness_group` / `non_fact_check`
  - leaf：`assertion_fact`
- 当前 `SupportArtifact` 仍然是唯一 proof substrate。
- 当前 `rule_run` trace / summary / narrative / NL / static 主线已经独立存在，不应被这轮 candidate tree 深化破坏。

## 5. Proposed Shape

### 5.1 Positioning

V2 不是新的 capability axis，而是 **candidate evidence tree v1 的结构深化**：

- 保持：
  - `native`
  - `candidate`
  - `SupportArtifact`
  - tree, not graph
- 深化：
  - node taxonomy
  - recursive grouping
  - nested rendering

也就是说，这一轮的目标是把 v1 的 tree carrier 做得更像真正 evidence tree，而不是再打开其他 deferred gaps。

### 5.2 Entry Surface And Compatibility

V2 默认继续复用既有 entry surface：

- runtime：
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-tree`
- audit：
  - `AuditQuery.get_candidate_evidence_tree(candidate_id)`

draft 倾向是：

- **不新开 `explain-tree-v2` endpoint**
- 而是在保持 top-level handle 不变的前提下，做 **尽量收敛的 shape enrichment**

兼容边界：

- 现有 top-level fields 继续保留：
  - `kind`
  - `candidate_id`
  - `support_digest`
  - `support_kind`
  - `root`
- `assertion_fact` leaf 的窄边界继续保持
- 允许新增 node kinds / grouping nodes / display-oriented fields，但不移除 v1 stable fields

需要明确的一点是：V2 引入 `support_section` 后，`root.children` 的直接子节点类型会从 v1 的 `predicate_witness_group/non_fact_check`，变成 `support_section`（以及可选的 `rule_ref_section`）。这不是 pure additive enrichment，而是一个 **可接受的、范围受控的 shape change**。当前判断它可接受，是因为：

- v1 刚完成交付，还没有外部 consumer 稳定依赖旧的 `root.children[*].node_kind`
- top-level entry handle、leaf ownership boundary、runtime/audit/static 三侧同构都保持不变
- 这次 change 明确只服务于 evidence tree 本体深化，不打开新的 capability axis

### 5.3 Tree Shape: From Flat Groups To Evidence Structure

V2 的目标不是无限递归，而是把当前 v1 的 shallow tree 提升成 **structured recursive tree**。

draft 倾向的 shape：

- root：`candidate_result`
  - children:
    - `support_section`
      - children:
        - `predicate_witness_group`
          - children:
            - `assertion_fact`
        - `non_fact_check`
    - `rule_ref_section`（若存在）
      - children:
        - `rule_ref`
          - children: first-round 允许为空，或只挂 minimal referenced-support placeholder

也就是把当前 root 下的 flat mixed children 拆成更明确的 sectioned tree。

section emit 规则也应在 V2 冻结：

- `support_section` 始终存在，因为它是当前 native candidate support 的主 evidence body
- `rule_ref_section` **只在 `SupportArtifact.rule_refs` 非空时 emit**
- 不允许为了“结构统一”而输出空的 `rule_ref_section` 占位节点

这条约束的目的有两个：

- 避免 tree 出现语义空节点
- 让绝大多数 no-rule-ref candidate 的 tree 变化保持最小，只额外引入一层 `support_section` wrapper

这样做的价值是：

- consumer 更容易理解 “facts / checks / rule refs” 分属哪个 evidence section
- static nested rendering 不再需要把 heterogeneous child list 硬塞进一个层级
- 后续若继续向更强 recursive tree 演进，section node 已经是稳定中介层

### 5.4 RuleRef Position

当前 v1 把 `rule_refs` 留在 root metadata。

V2 draft 倾向：

- 把 `rule_refs` 从 metadata-only 提升成 first-class nodes
- 但第一轮只做 **minimal rule_ref nodes**
  - `node_kind="rule_ref"`
  - 携带 `rule_ref_id`
  - 允许 `children=[]`

也就是：

- 先让 tree 能表达 “this candidate also depends on referenced rule context”
- 但暂时不要求把整个 rule-chain fully inline 展开

这一步的目标是树形语义前进，而不是一次性重做 rule trace。

### 5.5 Assertion Leaf Boundary

V1 的 leaf boundary 继续保持，不在 V2 扩张：

- `assertion_fact` 只携带：
  - `asrt_id`
  - `pred_id`
  - `e_ref`
  - `claim_args`
- 继续不携带：
  - `meta`
  - `revoked_by`
  - `revokes`
  - `is_revoked`

如果 consumer 需要更深 assertion state，仍然按 `asrt_id` 回跳 assertion detail surface。

V2 不允许因为 tree 更复杂，就把 leaf 退化成 full assertion dump。

### 5.6 Static Rendering Position

V2 的 static 重点不在 graph，而在 **nested evidence rendering quality**。

draft 倾向：

- 继续保留 `candidate_evidence/{candidate_id}.html`
- 但不再用 “payload + raw children dump” 作为主阅读体验
- 改成：
  - section-oriented nested tree blocks
  - node-kind-specific rendering
  - assertion leaves 继续链接到 existing assertion detail pages

第一轮仍然不做：

- client-side graph
- expand/collapse JS engine
- package-wide redesign

### 5.7 What Remains Deferred

即使 V2 完成，以下仍继续 deferred：

- engine parity
- proof graph
- annotation / value semantics / salience
- snippet/span provenance
- extraction uncertainty
- source-linkage graph
- judgment / conflict resolution UI

只有当 V2 的 tree 深化明确暴露某个 blocker，才允许把其中某项升级为下一条 capability line。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 现有 `candidate` flat explain DTO 不破坏
  - 现有 `explain-tree` entry handle 不破坏
  - `SupportArtifact` 仍是 candidate tree 的唯一 proof substrate
  - assertion leaf 仍然保持窄边界
- 明确不做的内容：
  - graph
  - engine parity
  - salience / impact
  - snippet/span
  - judgment / conflict resolution
- 兼容性约束：
  - runtime 与 audit tree DTO 继续保持同构
  - v2 应优先采用 backward-compatible enrichment，而不是 shape replacement

## 7. Acceptance

- [ ] candidate evidence tree DTO 已从 v1 的 flat support grouping 提升到更清晰的 structured recursive tree
- [ ] runtime `explain-tree` 保持原入口，但返回 enriched tree DTO
- [ ] audit `get_candidate_evidence_tree(...)` 返回同构 enriched tree DTO
- [ ] static candidate tree page 改为 node-kind-aware nested rendering，而不是 payload dump 为主
- [ ] assertion leaf 仍保持 `asrt_id/pred_id/e_ref/claim_args` 窄边界
- [ ] `rule_ref_section` 只在 `rule_refs` 非空时 emit，不输出空 section 占位节点
- [ ] 没有引入新的 graph / engine / provenance / salience contract

## 8. Implementation Plan

1. 冻结 v2 node taxonomy 与 backward-compatible DTO enrichment 边界
2. 重构 shared tree builder，把 section nodes / rule_ref nodes 纳入 builder 输出
3. runtime / audit 继续复用同一个 builder 输出 enriched tree
4. static page 改成 node-kind-aware nested rendering
5. 补 tests，锁定 v2 tree shape、compatibility 和 leaf boundary

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - candidate evidence tree 已从 v1 的 flat mixed children 深化为 sectioned tree：
    - root：`candidate_result`
    - `support_section`
    - optional `rule_ref_section`
    - support children：`predicate_witness_group` / `non_fact_check`
    - optional minimal `rule_ref`
  - runtime/audit 继续复用同一个 shared builder，三层 surface 仍保持同构
  - static candidate tree page 已从 payload-dump-first 调整为 node-kind-aware nested rendering，raw payload 退到 secondary details block
  - `rule_ref_section` 按 blueprint 只在 `rule_refs` 非空时 emit
  - assertion leaf 继续保持 `asrt_id/pred_id/e_ref/claim_args` 窄边界，没有回退成 full assertion dump
- 与 blueprint 不同的地方：
  - 无实质偏离；实现按 blueprint 收敛完成
- 为什么会有这些调整：
  - 不适用
- 归档说明：
  - 本任务已完成代码、测试与模块 docs 同步，并通过全量 phase-3 contract suite，可归档到 `docs/blueprints/archive/`
