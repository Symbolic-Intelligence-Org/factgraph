# Task Blueprint: Candidate Evidence Tree Provenance / Source Taxonomy

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/static_ui.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
- Audit Log:
  - [2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.audit.md](./2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.audit.md)

## 1. Problem

`candidate_evidence_tree` 现在已经有稳定的 node taxonomy、recursive proof contract、winning-branch narrowing、unresolved/boundary taxonomy，以及 engine degraded tree shape，但它仍缺一个正式的 provenance/source taxonomy。

当前 tree surface 上只有零散的 `support_kind`、`witness_status` 和 node-kind 自身，consumer 可以看出“这是 native recursive proof 还是 engine degraded”，却没有一套正式字段来表达“这个 node 的来源/承载类型是什么”。这会让 native recursive nodes、engine degraded nodes、legacy fallback nodes 的来源语义继续散落在说明文档和推断逻辑里，而不是成为显式 contract。

## 2. Goals

- 冻结 `candidate_evidence_tree` 是否需要正式的 `source_kind` / `provenance_kind` 类字段。
- 确定 first-round provenance/source taxonomy 适用于哪些 node kinds。
- 明确 native recursive proof 与 engine degraded tree 是否共享同一套 vocabulary。
- 明确 provenance/source 是 carrier contract 还是 display-only contract。

## 3. Non-goals

- 不重开 recursive proof DTO、winning-branch narrowing、或 unresolved taxonomy。
- 不直接展开 snippet/span 级 finer provenance。
- 不直接展开 source-linkage graph 或 proof graph。
- 不把 engine degraded tree 提升成 full witness parity。
- 不修改 engine adapter、native evaluator 或 SupportArtifact capture 语义。

## 4. Current Context

- 当前 tree surface 已有：
  - native recursive proof nodes
  - unresolved/boundary terminals
  - engine degraded `degraded_support`
- runtime / audit / static 共享同一 tree carrier，但没有正式的 provenance/source enum。
- engine degraded surface 当前主要依赖：
  - `support_kind in {"engine_no_witness_v1", "none"}`
  - `witness_status="degraded"`
- native recursive nodes 当前主要依赖 node kind 自身和 support-side carrier，而不是显式 source taxonomy。
- 外部参照：
  - [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md) 明确指出当前体系还缺 `fact source taxonomy`，这是可借鉴的设计输入，但不是当前 contract。

## 5. Freeze Decisions

### 5.1 Scope Narrowing

本蓝图冻结的是 **`node_kind → provenance role` contract**，不是完整的 Rainbird 式 **source taxonomy**。

区分：
- **provenance role**（本轮冻结）：树节点在证明结构中扮演的角色——"这是事实见证、约束检查、递归证明、还是降级占位"。当前 `node_kind` 已经编码了这层语义。
- **assertion-origin taxonomy**（本轮不做）：更深的事实生命周期来源——"这条 assertion 来自 direct write、derivation accept、还是 import"。这需要 `assertion_lookup` 回调返回 provenance metadata，超出当前 tree builder 的输入契约。

### 5.2 Q1: `source_kind` / `provenance_kind` — 一个字段还是两个？

**冻结决定：零新字段。`node_kind` 本身即为 provenance-role taxonomy 的载体。**

理由：
- 当前 12 种 `node_kind` 已形成完整、非重叠的证明角色分类。
- 新增 `source_kind` 会产生 ~95% 的冗余——对绝大多数 node kinds，它只是 `node_kind` 的同义词。
- 唯一的歧义点是 `rule_ref`（legacy flat 和 structured edge 共享 `node_kind`），但 consumer 已可通过 `ruleref_atom_key` 字段的有无区分。
- 真正缺失的不是运行时字段，而是文档化的 `node_kind → provenance role category` 映射。

**例外预留**：未来若需表达 assertion-level lifecycle provenance（direct write / derivation accept / import），应在 `assertion_fact` 节点上新增字段（如 `assertion_source`），但这超出 first-round 范围。

### 5.3 Q2: 哪些 node kinds first-round 必须带它？

**冻结决定：无需 per-node 新字段。交付物是模块文档中的正式映射表。**

`node_kind → provenance role category` 映射如下（冻结）：

| Provenance Role Category | Node Kinds | 语义 |
|---|---|---|
| **witness** | `predicate_witness_group`, `assertion_fact` | 直接见证 ledger 中的事实 |
| **constraint** | `non_fact_check` | 非事实约束检查（eq/ne/gt/not/ruleref/...） |
| **rule_chain** | `rule_ref`, `referenced_support` | 规则引用及递归证明展开 |
| **terminal** | `unresolved_support`, `recursion_boundary` | 遍历终止或证据不可用 |
| **degraded** | `degraded_support` | Engine 路径无 witness artifact |
| **structural** | `candidate_result`, `support_section`, `rule_ref_section` | 纯结构容器，不自身承载来源语义 |

### 5.4 Q3: Native recursive 和 engine degraded 是否共享同一 taxonomy？

**冻结决定：共享。**

它们已共享同一 tree carrier 和 `node_kind` 集合。`degraded_support` 是一个独立的 node_kind，有自己的 provenance role category（`degraded`），不与 native 的 node kinds 混淆。不需要建立两套平行 vocabulary。

### 5.5 Q4: Carrier contract 还是 display-only contract？

**冻结决定：Carrier contract。**

实现方式是将 **已有的 `node_kind` 字段** 正式化为 provenance-role taxonomy 的载体：
- `node_kind` 的值集合是冻结的 contract，runtime / audit / static 共享
- `node_kind → provenance role category` 映射是冻结的 contract，写入 module docs
- Consumer 基于 `node_kind` 做渲染/分类决策，不需要维护自己的推断逻辑
- 这不是 display-only，因为 `node_kind` 已经在 carrier（tree dict）上

### 5.6 Deferred Items

以下明确不属于本轮冻结，留给后续子蓝图：

1. **Assertion-origin taxonomy** — `assertion_fact` 节点上的 `assertion_source` 字段（direct write / derivation accept / import），需要 assertion_lookup 回调扩展
2. **Finer snippet/span provenance** — 树节点指向具体源代码或规则片段
3. **Source-linkage graph** — 从 tree 升级为 graph-oriented provenance surface
4. **Salience / impact** — 条件贡献度标注，依赖 certainty/weight 基础设施

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不让 `source/provenance taxonomy` 偷偷演变成 graph、snippet/span、或 full source-linkage contract。
  - 不让这条线重新定义 `support_kind` 或 `witness_status` 的现有语义。
  - 不把 `unresolved_support` / `recursion_boundary` 的 reason taxonomy 和 source taxonomy 混成一个字段。
- 明确不做的内容：
  - 不在 first-round 讨论 UI 配色、icon、或 presentation wording。
  - 不把 ingest/provenance validation 的 assertion-meta 语义直接搬到 tree node 上。
- 兼容性约束：
  - runtime / audit / static 若采纳 taxonomy，应共享同一底层 contract。
  - legacy tree readback 不能因为 taxonomy 讨论而失效。

## 7. Acceptance

- [x] 已明确是否需要正式 `source_kind` / `provenance_kind` contract → **不新增字段；`node_kind` 提升为正式 provenance-role carrier**
- [x] 已冻结 first-round taxonomy 覆盖的 node 范围与非目标范围 → **全部 12 种 node_kind 覆盖，assertion-origin taxonomy deferred**
- [x] 已明确 native recursive proof、engine degraded、legacy fallback 的 vocabulary 关系 → **共享同一 vocabulary**
- [x] 已明确 provenance/source 是 carrier contract 还是 display-only contract → **carrier contract**
- [x] 若采用外部参考结论，blueprint audit 已记录”采纳了什么、没有采纳什么” → **audit log 2026-03-20 条目已记录 Rainbird 采纳边界**
- [x] `node_kind → provenance role category` 映射表已写入 module docs → **core/docs, service/docs, audit/docs 三处已同步**

## 8. Implementation Plan

1. ~~盘点当前 tree surface 已有的来源暗示字段和 node kinds。~~ ✅ done
2. ~~结合 Rainbird source taxonomy 参考，提出 first-round freeze options。~~ ✅ done
3. ~~冻结 owner / scope / compatibility 边界，推进到 `scoped`。~~ ✅ done
4. ~~将 `node_kind → provenance role category` 映射表写入以下 module docs：~~ ✅ done
   - `src/factpy_kernel/core/docs/01_architecture.md`（node_kind provenance-role contract）
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（consumer 消费指引）
   - `src/factpy_kernel/audit/docs/01_overview.md`（audit/static 消费同一 taxonomy）
5. ~~更新 provenance audit log 记录 Rainbird 参考的采纳/不采纳边界。~~ ✅ done
6. 归档。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（若 taxonomy 成为正式 contract）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若 runtime tree surface 新增 provenance/source 语义）
- `src/factpy_kernel/audit/docs/01_overview.md`（若 audit/static 消费同一 taxonomy）

## 10. Outcome / Deviations

- 最终落地结果：doc-and-contract promotion。零代码变更。`node_kind` 正式提升为 carrier-level provenance-role taxonomy，映射表写入 core/service/audit 三份 module docs。
- 与 blueprint 不同的地方：
  - Draft §5 原列 5 个 freeze questions，scoping 时收敛为 4 个（Q5 "legacy fallback 是否进入" 合并到 Q2/Q3）
  - 原预期可能新增 `source_kind` 字段，最终决定零新字段
  - 原 §9 只列 core 和 service docs，实际追加了 audit docs
- 为什么会有这些调整：inventorying 代码后发现 `node_kind` 已经 1:1 映射 provenance role，新增字段会产生 ~95% 冗余；scope 从 "source taxonomy" 收窄为 "provenance-role taxonomy"，更精确地反映当前能力边界
- 归档说明：待归档到 `docs/blueprints/archive/`
