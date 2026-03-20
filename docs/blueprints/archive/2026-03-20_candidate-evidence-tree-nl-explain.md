# Task Blueprint: Candidate Evidence Tree NL Explain

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/rules/_trace_narrative.py`
  - `src/factpy_kernel/core/rules/_trace_nl.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
- Related Docs:
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-20_candidate-evidence-tree-nl-explain.audit.md](./2026-03-20_candidate-evidence-tree-nl-explain.audit.md)

## 1. Problem

`candidate_evidence_tree` 已有完整的 recursive tree carrier（native + engine degraded），provenance-role taxonomy 也已冻结，但 tree surface 还没有自己的 NL explain 层。

当前状态：
- `rule_run` 有完整的 4 层 explain surface：raw → summary → narrative → NL explain
- `candidate_evidence_tree` 只有 raw tree（`explain-tree` endpoint），没有 summary、narrative、NL
- consumer 若想向非技术受众解释"为什么这个 candidate 成立"，必须自行遍历 tree 节点并组装文本

## 2. Goals

- 为 `candidate_evidence_tree` 补齐 summary → narrative → NL explain 三层消费面
- 复用已验证的 `rule_run` 分层模式：每层只从上一层纯派生，不直接下探 raw carrier
- 三通道交付：runtime 交付 summary + narrative + NL；audit 交付 summary + narrative；static 交付 narrative block
- native tree 和 engine degraded tree 都需要有 NL output

## 3. Non-goals

- 不修改 `candidate_evidence_tree` 的 raw tree carrier（已冻结）
- 不把 NL explain 做成 LLM-generated（保持 deterministic prose）
- 不为 tree NL 新增 certainty/weight/salience 语义（这些依赖尚不存在的基础设施）
- 不新增 `assertion` 或 `rule_run` 的 NL 层（已有）
- 不在本轮引入 i18n 框架（继续 `locale="en"` 硬编码）

## 4. Current Context

### 4.1 已有 rule_run NL 分层模式

```
raw RuleTraceArtifact
  → summarize_rule_trace_artifact_dict()    → rule_run_summary
  → render_rule_run_narrative(summary)       → rule_run_narrative
  → render_rule_run_nl_explain(summary, narrative) → rule_run_nl_explain
```

每层特征：
- **summary**：结构化聚合（计数、分组、去重），纯 dict
- **narrative**：结构化文本段（headline + section lines），纯 dict
- **NL explain**：散文段落（headline + paragraphs），纯 dict

### 4.2 candidate_evidence_tree 的 raw 结构

当前 tree 的 provenance-role 分组（冻结 contract）：

| Category | Node Kinds |
|---|---|
| structural | `candidate_result`, `support_section`, `rule_ref_section` |
| witness | `predicate_witness_group`, `assertion_fact` |
| constraint | `non_fact_check` |
| rule_chain | `rule_ref`, `referenced_support` |
| terminal | `unresolved_support`, `recursion_boundary` |
| degraded | `degraded_support` |

### 4.3 已有三通道交付

- runtime：`POST /queries/explain-tree` + `kind="candidate"`
- audit：`AuditQuery.get_candidate_evidence_tree(candidate_id)`
- static：`candidate_evidence/{candidate_id}.html`

## 5. Proposed Shape

### 5.1 Tree Summary

`candidate_evidence_tree_summary`：从 raw tree 纯派生的结构化聚合。

First-round 采用 role-first 最小字段集。summary 的组织原则是 provenance-role category，不重复 raw tree 的 per-node-kind 细节。

**核心稳定字段（first-round 冻结）：**

```
candidate_evidence_tree_summary:
  candidate_id: str
  support_kind: str                    # "native_binding_v1" | "engine_no_witness_v1" | "none"
  is_degraded: bool
  root_result_kind: str | null         # "fact" | "entity" | "row" | null (degraded)
  node_count_by_role: dict[str, int]   # 按 provenance-role category 计数（structural/witness/constraint/rule_chain/terminal/degraded）
  witness_assertion_count: int         # assertion_fact 叶节点计数
  rule_ref_count: int                  # rule_ref 节点计数（legacy + structured）
  recursive_depth: int                 # 实际递归深度（0 = no recursion）
  has_unresolved: bool                 # 是否存在 unresolved_support
  has_boundary: bool                   # 是否存在 recursion_boundary
  unresolved_reasons: list[str]        # 去重后的 unresolved reason 列表
  boundary_reasons: list[str]          # 去重后的 boundary reason 列表
```

**可延后字段（不在 first-round 冻结，后续按需追加）：**

```
  node_count_by_kind: dict[str, int]   # 按 node_kind 细分计数——重复 raw tree 分类细节
  witness_predicate_ids: list[str]     # 去重后的 pred_id 列表——增强型摘要
  constraint_check_kinds: list[str]    # 去重后的 check_kind 列表——增强型摘要
```

延后理由：`node_count_by_kind` 基本是 raw tree 的分类冗余；`witness_predicate_ids` 和 `constraint_check_kinds` 不是 narrative / NL 的最低依赖。

### 5.2 Tree Narrative

`candidate_evidence_tree_narrative`：从 summary 纯派生的结构化文本段。

```
candidate_evidence_tree_narrative:
  headline: str
  overview_lines: list[str]
  evidence_lines: list[str]        # witness + constraint 摘要
  rule_chain_lines: list[str]      # rule_ref / recursive proof 摘要
  terminal_lines: list[str]        # unresolved + boundary 摘要
  drilldown_lines: list[str]       # 下钻指引
```

对 degraded tree，narrative 应生成一个简短的降级说明，而不是空段。

### 5.3 Tree NL Explain

`candidate_evidence_tree_nl_explain`：从 summary + narrative 纯派生的散文段落。

```
candidate_evidence_tree_nl_explain:
  headline: str
  paragraphs: list[str]
```

与 `rule_run_nl_explain` 保持同构 shape。

### 5.4 通道交付矩阵

三通道同步到 narrative；NL first-round 只要求 runtime。

| Channel | Summary | Narrative | NL |
|---|---|---|---|
| runtime | `POST /queries/explain-summary` + `kind="candidate"` | `POST /queries/explain-narrative` + `kind="candidate"` | `POST /queries/explain-nl` + `kind="candidate"` |
| audit | `AuditQuery.get_candidate_evidence_tree_summary(candidate_id)` | `AuditQuery.get_candidate_evidence_tree_narrative(candidate_id)` | not first-round |
| static | not first-round | narrative block on evidence tree page | not first-round |

注意：runtime 三个 endpoint 当前只支持 `kind="rule_run"`；本轮扩展它们以接受 `kind="candidate"`。audit/static NL 层收益小、scope 宽，留给后续按需追加。

### 5.5 实现分层

```
_candidate_evidence_tree.py (已有, 不修改)
  → _candidate_evidence_tree_summary.py (新增)
    → _candidate_evidence_tree_narrative.py (新增)
      → _candidate_evidence_tree_nl.py (新增)
```

所有新增模块放在 `src/factpy_kernel/core/store/` 下，与 `_candidate_evidence_tree.py` 同级。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不修改 `_candidate_evidence_tree.py` 现有代码
  - 不修改 `rule_run` 的 summary / narrative / NL 层
  - summary / narrative / NL 每层只从上一层纯派生
  - runtime / audit / static 共享同一底层 summary → narrative → NL 纯函数（各通道按交付矩阵选择消费到哪一层）
- 明确不做的内容：
  - 不引入 assertion-level provenance 到 summary（deferred）
  - 不引入 certainty/weight/salience 语义到 narrative
  - 不做 NL i18n
- 兼容性约束：
  - `explain-summary` / `explain-narrative` / `explain-nl` 现有 `kind="rule_run"` 行为不变
  - `kind="candidate"` 是 additive extension

## 7. Acceptance

- [x] `candidate_evidence_tree_summary` 函数存在并可从 raw tree 纯派生（role-first 核心字段集）
- [x] `candidate_evidence_tree_narrative` 函数存在并可从 summary 纯派生
- [x] `candidate_evidence_tree_nl_explain` 函数存在并可从 summary + narrative 纯派生
- [x] native tree 和 engine degraded tree 都能生成三层 output
- [x] runtime `explain-summary` / `explain-narrative` / `explain-nl` 已扩展支持 `kind="candidate"`
- [x] audit query 已扩展 candidate tree summary 和 narrative（NL 不要求 first-round）
- [x] static site candidate evidence page 已包含 narrative block
- [x] 已有针对 summary / narrative / NL 三层的单元测试（native + degraded）
- [x] 已有 runtime / audit / static 的 targeted integration tests
- [x] module docs 已更新

## 8. Implementation Plan

1. 实现 `_candidate_evidence_tree_summary.py`：tree → summary 纯派生（role-first 核心字段集）
2. 实现 `_candidate_evidence_tree_narrative.py`：summary → narrative 纯派生
3. 实现 `_candidate_evidence_tree_nl.py`：summary + narrative → NL 纯派生
4. 为三层分别编写单元测试（native + degraded cases）
5. 扩展 service `runtime_v1.py`：`explain-summary` / `explain-narrative` / `explain-nl` 接受 `kind="candidate"`
6. 扩展 audit `query.py` / `dto.py`：candidate tree summary + narrative（NL 不要求 first-round）
7. 扩展 audit `static_ui.py`：candidate evidence page 加 narrative block
8. 补 runtime / audit / static 的 targeted integration tests
9. 更新 module docs
10. 归档

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `store._candidate_evidence_tree_summary`、`store._candidate_evidence_tree_narrative`、`store._candidate_evidence_tree_nl` 三个纯派生 helper。
  - runtime `explain-summary` / `explain-narrative` / `explain-nl` 已扩展支持 `kind="candidate"`。
  - audit 已新增 candidate tree summary / narrative query 与 DTO；static candidate evidence page 已新增 narrative block。
  - native tree 与 engine degraded tree 均已覆盖 summary → narrative → NL（runtime）链路。
- 与 blueprint 不同的地方：
  - 无实质偏离；实现保持了 role-first summary、runtime-only candidate NL、以及 static 只渲染 narrative block 的收窄边界。
- 为什么会有这些调整：
  - n/a
- 归档说明：
  - 代码、模块 docs 与 acceptance 已对齐后归档。
