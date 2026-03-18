# Task Blueprint: Native Candidate Evidence Tree V1

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/queries.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [docs/blueprints/active/2026-03-17_durable-artifact-storage.md](./2026-03-17_durable-artifact-storage.md)
  - [docs/blueprints/archive/2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [docs/blueprints/archive/2026-03-17_explain-ref-service-unification.md](../archive/2026-03-17_explain-ref-service-unification.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-18_native-candidate-evidence-tree-v1.audit.md](./2026-03-18_native-candidate-evidence-tree-v1.audit.md)

## 1. Problem

当前 traceability / explainability 主线已经完成了：

- candidate explain handle
- support artifact capture / readback
- `rule_run` raw / summary / narrative / NL / static
- audit package explain artifact export

但它仍然主要是：

- `candidate` 侧的 flat explain handle
- `rule_run` 侧的 flat trace + derived views
- assertion detail 下钻

换句话说，系统已经有了 evidence tree 的底座，却还没有一个 **result-centric、tree-oriented、可递归消费的证据链对象**。

对照 [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)，当前最缺的不是再加一层 narrative，而是把已有：

- `candidate_id`
- `support_digest`
- `SupportArtifact.pred_witnesses`
- `SupportArtifact.non_fact_steps`
- assertion detail / source refs

提升成一个真正的 candidate evidence tree surface。

## 2. Goals

- 为 `native` candidate 定义第一版 evidence tree DTO。
- 让现有 `candidate_id` 成为 result-centric evidence tree 的入口，而不是只返回 `support_digest` 指针。
- 在 runtime 提供 machine-readable evidence tree surface。
- 在 audit/package 侧提供同构的 evidence tree surface。
- 第一轮若可行，提供最小 static HTML tree page，证明它不只是内部 carrier。

## 3. Non-goals

- 不做 `souffle` / `problog` true-witness parity。
- 不把 `rule_run` trace 重写成 evidence tree；`rule_run` 继续保持现有 surface。
- 不做 salience chart / impact breakdown。
- 不做 certainty/probability 语义扩张。
- 不做 snippet/span provenance。
- 不做 first-class case/package object。
- 不做 conflict resolution / judgment contract。
- 不做 graph-based UI；第一轮只允许 tree/list 形态。

## 4. Current Context

- 当前 `candidate` explain 已存在统一入口：
  - `POST /queries/explain`
  - `kind="candidate"`
  - 但响应只到 `support_digest/support.kind`
- 当前 native candidate 已有真实 `support_kind="native_binding_v1"`，并可继续解引用 `SupportArtifact`
- 当前 `audit` package 已导出：
  - `support_artifacts.jsonl`
  - `candidate_ledger`
- 当前 static proof-entry 只覆盖：
  - `rule_run_id`
  - 不覆盖 candidate evidence tree
- 当前多轮 walkthrough 已验证：
  - assertion detail surfaces 足以表达 source-family distinguishability
  - conflicting evidence 的 non-witnessed side 也能被单独取回
  - mixed-source same-case 仍不需要 first-class case/linkage contract

## 5. Proposed Shape

### 5.1 Positioning

第一轮 evidence tree 明确收窄为：

- `native`
- `candidate`
- `SupportArtifact` 驱动

也就是先把 derivation candidate explain 从“flat pointer”提升成“tree DTO”，而不是同时处理：

- `rule_run`
- engine parity
- annotation/value-semantics
- graph visualization

### 5.2 Entry Point

adopt 现有 `candidate_id` 作为 tree entry handle，不新增 `proof_entry_id`。

第一轮建议新增独立 surface，而不是修改既有 `POST /queries/explain` payload：

- runtime：
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-tree`
  - request: `{ "kind": "candidate", "id": "cand_v2:..." }`
- audit：
  - `AuditQuery.get_candidate_evidence_tree(candidate_id)`
  - 对应 DTO builder

理由：

- 现有 `explain(kind="candidate")` 已冻结为窄 entry DTO
- evidence tree 是新的 consumer object，不应挤进旧 `explain` payload

### 5.3 Tree Shape

第一轮 evidence tree DTO 应该是 **recursive schema, shallow semantics**：

- schema 上允许 `children[]` 递归
- 但第一轮只要求展开到：
  - candidate root
  - support atom/check nodes
  - assertion fact leaves

建议的最小 shape：

```json
{
  "kind": "candidate_evidence_tree",
  "candidate_id": "cand_v2:...",
  "support_digest": "sha256:...",
  "support_kind": "native_binding_v1",
  "root": {
    "node_id": "cand:...",
    "node_kind": "candidate_result",
    "title": "...",
    "children": [
      {
        "node_id": "atom:b0.a0",
        "node_kind": "predicate_witness_group",
        "pred_atom_key": "b0.a0:aml:high_risk_outflow_signal",
        "children": [
          {
            "node_id": "asrt:A123",
            "node_kind": "assertion_fact",
            "asrt_id": "A123",
            "pred_id": "aml:high_risk_outflow_signal",
            "e_ref": "idref_v1:...",
            "claim_args": [...],
            "children": []
          }
        ]
      },
      {
        "node_id": "step:b0.a9",
        "node_kind": "non_fact_check",
        "step_key": "b0.a9",
        "status": "evaluated",
        "details": {
          "binding": {...}
        },
        "children": []
      }
    ]
  }
}
```

V1 的 `assertion_fact` leaf 边界也需要显式收窄：

- 携带：
  - `asrt_id`
  - `pred_id`
  - `e_ref`
  - `claim_args`
- 不携带：
  - `meta`
  - `revoked_by`
  - `revokes`
  - `is_revoked`

这些字段继续留在既有 assertion detail drill-down surface。若 consumer 需要 revocation 或 meta 信息，应继续按 `asrt_id` 回跳 assertion detail，而不是要求 evidence tree leaf 直接内嵌完整 assertion dump。

### 5.4 What Counts As “Tree” In V1

第一轮不追求 Rainbird 那种完整的 recursive rule-chain tree。

V1 的 tree 含义是：

- 一个 candidate 结论节点
- 下面挂其 support atoms / checks
- predicate atoms 再挂 assertion leaves

也就是说，它先把当前 flat `SupportArtifact` 重新组织成：

- consumer-oriented recursive DTO
- 可直接渲染为 nested tree page

而不是继续要求用户自己拼：

- `candidate_id`
- `support_digest`
- `SupportArtifact`
- assertion detail

### 5.5 Native Candidate Facts vs. Non-witnessed Context

第一轮 evidence tree 只承诺表达：

- **为什么这个 candidate 成立**

不承诺表达：

- 当前 ledger 中所有与它有关但未被 witness 的事实
- conflicting but non-witnessed alternatives

这些仍然继续留在：

- assertion detail
- existing audit/query surfaces

这条边界很重要。否则第一轮 evidence tree 会立刻滑向：

- conflict-resolution UI
- source-linkage graph
- case package object

### 5.6 Audit / Static Position

若做 audit/static parity，第一轮建议同样收得很窄：

- `AuditQuery.get_candidate_evidence_tree(candidate_id)`
- `build_candidate_evidence_tree_dto(...)`
- static 仅新增最小 tree page：
  - `candidate_evidence/{candidate_id}.html`

它不需要：

- graph layout
- expand/collapse JS tree engine
- package-wide candidate tree index redesign

只需要证明：

- audit package 已足够离线重建 candidate evidence tree
- tree page 可分享、可 drill-down 到 assertion detail

### 5.7 Relationship To Deferred Gaps

本轮 evidence tree 默认不重新打开这些 deferred gaps：

- `T2`
- judgment/obligation
- `U2`
- snippet/span provenance
- extraction uncertainty
- source-linkage

只有当第一轮 candidate evidence tree 在 **native + current SupportArtifact** 边界内都无法诚实表达时，才允许把其中某一项升级为 blocker。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 现有 `candidate` explain DTO 不破坏
  - `rule_run` explain spine 不破坏
  - `SupportArtifact` 仍是第一轮唯一的 candidate proof substrate
  - audit/static 若扩展，只做 tree page，不做 graph UI
- 明确不做的内容：
  - engine parity
  - salience / impact breakdown
  - snippet/span
  - uncertainty scoring for extraction
  - first-class source-linkage graph
- 兼容性约束：
  - runtime 与 audit evidence tree DTO 应保持同构
  - source-family 区分继续只依赖现有 assertion/detail surfaces，不引入新的 source contract

## 7. Acceptance

- [ ] 已定义 candidate evidence tree DTO，且它是 recursive schema
- [ ] runtime 已能按 `candidate_id` 返回 native candidate evidence tree
- [ ] audit 已能按 `candidate_id` 返回同构 evidence tree DTO
- [ ] 若实现 static page，tree page 可 drill-down 到既有 assertion detail
- [ ] 第一轮没有引入新的 case/linkage/snippet/uncertainty contract

## 8. Implementation Plan

1. 先冻结 tree DTO shape 与 entry surface
2. runtime 侧用现有 `candidate_id -> support_digest -> SupportArtifact` 组装 tree
3. audit 侧用 `candidate_ledger + support_artifacts + assertion index` 组装同构 tree
4. 若第一轮仍然足够窄，再补 static tree page

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增了 native-only candidate evidence tree v1：
    - runtime：`POST /v1/runtime/sessions/{session_id}/queries/explain-tree`
    - audit：`AuditQuery.get_candidate_evidence_tree(candidate_id)` + `build_candidate_evidence_tree_dto(...)`
    - static：`candidate_evidence/{candidate_id}.html` + `candidate_evidence.html`
  - tree DTO 已按 blueprint 收窄为：
    - root：`candidate_result`
    - middle：`predicate_witness_group` / `non_fact_check`
    - leaf：`assertion_fact`
  - `assertion_fact` leaf 只携带：
    - `asrt_id`
    - `pred_id`
    - `e_ref`
    - `claim_args`
  - runtime / audit / static 三侧都复用了同一个 shared builder，没有把 full assertion detail 内嵌进 tree
  - `support_artifacts.jsonl` 现在被 audit reader/query/static 正式消费，用于离线重建 candidate evidence tree
- 与 blueprint 不同的地方：
  - static 第一轮除了 per-candidate tree page，还补了一个很小的 `candidate_evidence.html` index，便于在 static site 中发现 candidate tree pages
- 为什么会有这些调整：
  - 没有 index 的情况下，candidate tree page 只能依赖 `site_manifest.json` 手工发现；补一个最小 index 不改变 contract，但能让 static surface 可用
- 归档说明：
  - 本任务已按 scoped blueprint 完成实现、模块 docs 更新与全量 phase-3 contract 验证，可归档到 `docs/blueprints/archive/`
