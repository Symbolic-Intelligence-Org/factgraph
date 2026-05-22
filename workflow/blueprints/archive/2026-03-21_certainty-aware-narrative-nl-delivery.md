# Task Blueprint: Certainty-Aware Narrative/NL Delivery

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_nl.py`
  - `src/factpy_kernel/service/runtime_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [docs/blueprints/archive/2026-03-20_candidate-evidence-tree-salience-impact.md](../archive/2026-03-20_candidate-evidence-tree-salience-impact.md)
  - [docs/blueprints/archive/2026-03-21_certainty-summary-explain-delivery.md](../archive/2026-03-21_certainty-summary-explain-delivery.md)
- Audit Log:
  - [2026-03-21_certainty-aware-narrative-nl-delivery.audit.md](./2026-03-21_certainty-aware-narrative-nl-delivery.audit.md)

## 1. Problem

`CertaintySummary` 的 per-condition impact breakdown 和 `aggregate_certainty` 已在 runtime `explain-summary` 端点交付（`certainty_summary` response-level sibling）。但 narrative 和 NL 两层完全不知道这个信息：

- `render_candidate_evidence_tree_narrative(summary)` 只消费 12-field core summary
- `render_candidate_evidence_tree_nl_explain(summary, narrative)` 同理
- `explain_runtime_narrative` 和 `explain_runtime_nl` 端点从不计算 `certainty_summary`

结果是：用户通过 explain-summary 能看到 `certainty_summary`，但切到 narrative/NL 视图时这些信息消失了。

**这一轮的目标不是新增计算语义，而是扩展 `certainty_summary` 的消费面到 narrative + NL 两层。**
impact 计算已存在，不新增 ranking / scoring / aggregation 语义。

## 2. Goals

- `confidence_kind="certainty"` 且有 `certainty_summary` 时，runtime narrative 增加 `certainty_lines` section
- `confidence_kind="certainty"` 且有 `certainty_summary` 时，runtime NL 增加 certainty 段落
- 无 `certainty_summary` 时，narrative/NL 输出与当前完全一致（backward compatible）

## 3. Non-goals

- 不触碰 audit package、static site delivery
- 不实现 probability lane（`confidence_kind="probability"` 继续无 certainty_summary）
- 不引入 salience ranking / 排序语义（conditions 保持 atom position order）
- 不修改 12-field core summary set
- 不修改 `CertaintySummary` / `ConditionImpact` dataclass
- 不修改 `derive_certainty_summary()` 逻辑
- 不改现有 narrative/NL 的已有 section 内容

## 4. Current Context

### 4.1 Narrative 函数签名

```python
# _candidate_evidence_tree_narrative.py L21-25
def render_candidate_evidence_tree_narrative(
    summary: dict[str, Any],
    *,
    locale: str = "en",
) -> dict[str, Any]:
```

返回：`{headline, overview_lines, evidence_lines, rule_chain_lines, terminal_lines, drilldown_lines}`

### 4.2 NL 函数签名

```python
# _candidate_evidence_tree_nl.py L11-16
def render_candidate_evidence_tree_nl_explain(
    summary: dict[str, Any],
    narrative: dict[str, Any],
    *,
    locale: str = "en",
) -> dict[str, Any]:
```

返回：`{headline, paragraphs}` — 4 段（overview + evidence + rules + terminals）

### 4.3 Runtime 调用链

```
explain_runtime_narrative(kind="candidate")
  → _get_candidate_tree_narrative(session, id_)
    → _render_candidate_tree_narrative_from_summary(summary)
      → render_candidate_evidence_tree_narrative(summary, locale="en")

explain_runtime_nl(kind="candidate")
  → summary = _get_candidate_tree_summary(session, id_)
  → narrative = _render_candidate_tree_narrative_from_summary(summary)
  → render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
```

当前这两条路径都不计算 `certainty_summary`。计算只发生在 `explain_runtime_summary`。

### 4.4 certainty_summary dict shape（已冻结）

```json
{
  "confidence_kind": "certainty",
  "condition_count": 2,
  "weighted_condition_count": 2,
  "conditions": [
    {"atom_key": "b0.a0", "node_kind": "predicate_witness_group", "weight": 0.8, "impact": 0.64},
    {"atom_key": "b0.a1", "node_kind": "non_fact_check", "weight": 0.5, "impact": 0.5}
  ],
  "aggregate_certainty": 0.5
}
```

- 已有约束：eligibility guard（单 structured rule_ref_edge + 无 nested referenced_support）
- 三态 lookup：`None`（ineligible）→ skip；`{}`（无 weights）→ all-unweighted；`{k:v}`→ weighted

## 5. Proposed Shape

### 5.1 Narrative 扩展

```python
def render_candidate_evidence_tree_narrative(
    summary: dict[str, Any],
    *,
    certainty_summary: dict[str, Any] | None = None,  # NEW keyword-only
    locale: str = "en",
) -> dict[str, Any]:
```

**当 `certainty_summary is not None`**，返回值增加 `certainty_lines` key：

```python
return {
    "headline": ...,
    "overview_lines": ...,
    "evidence_lines": ...,
    "rule_chain_lines": ...,
    "terminal_lines": ...,
    "drilldown_lines": ...,
    "certainty_lines": [...],  # NEW — only present when certainty_summary provided
}
```

**当 `certainty_summary is None`**（默认），返回值无 `certainty_lines` key，完全等价于当前行为。

`certainty_lines` 内容示例：

```python
[
    "Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.5.",
    "Condition b0.a0 (predicate_witness_group): weight=0.8, impact=0.64.",
    "Condition b0.a1 (non_fact_check): weight=0.5, impact=0.5.",
]
```

规则：
- 第一行显式标注 scope 为 "eligible child-proof subtree"（当前 `certainty_summary` 的真实语义是单 eligible referenced_support subtree 的派生，不是 full candidate tree 的 certainty）
- 第一行总是有 aggregate（可能是 None → "...aggregate certainty (bottleneck): -."）
- 每个 condition 一行，保持 atom position order（不排序）
- unweighted condition（weight=None）→ "Condition b0.a2 (predicate_witness_group): unweighted."

### 5.2 NL 扩展

NL 函数签名 **不变**。不新增 `certainty_summary` 参数。
NL 只消费 narrative 输出，通过检查 `narrative.get("certainty_lines")` 决定是否追加第 5 段。
这消除了双输入面的静默漂移风险。

```python
def render_candidate_evidence_tree_nl_explain(
    summary: dict[str, Any],
    narrative: dict[str, Any],
    *,
    locale: str = "en",  # 签名不变
) -> dict[str, Any]:
```

**当 narrative 包含 `certainty_lines`**，`paragraphs` 数组增加第 5 段：

```python
paragraphs = [
    "... overview ...",
    "Evidence summary: ...",
    "Rule-chain summary: ...",
    "Terminal and drill-down summary: ...",
    "Certainty summary: Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.5. Condition b0.a0 ...",  # NEW
]
```

无 `certainty_lines` 时保持 4 段，完全等价于当前行为。

### 5.3 Runtime 调用链变更

`explain_runtime_narrative` 和 `explain_runtime_nl` 在 `kind="candidate"` 分支里需要计算 `certainty_summary`：

```python
# explain_runtime_narrative, kind="candidate"
if kind == "candidate":
    registry_root = _resolve_rule_registry_root(session, dto)
    tree = _get_candidate_tree(session, id_)
    summary = summarize_candidate_evidence_tree_dict(tree)
    certainty_summary_dict = _compute_certainty_summary_from_tree(
        session, id_, tree, registry_root=registry_root,
    )
    narrative = render_candidate_evidence_tree_narrative(
        summary, certainty_summary=certainty_summary_dict, locale="en",
    )
    return ok_response(...)
```

```python
# explain_runtime_nl, kind="candidate"
if kind == "candidate":
    registry_root = _resolve_rule_registry_root(session, dto)
    tree = _get_candidate_tree(session, id_)
    summary = summarize_candidate_evidence_tree_dict(tree)
    certainty_summary_dict = _compute_certainty_summary_from_tree(
        session, id_, tree, registry_root=registry_root,
    )
    narrative = render_candidate_evidence_tree_narrative(
        summary, certainty_summary=certainty_summary_dict, locale="en",
    )
    return ok_response(
        ...,
        explain_nl=render_candidate_evidence_tree_nl_explain(
            summary, narrative, locale="en",
        ),
    )
```

**提取共享 helper**：`_compute_certainty_summary_from_tree(session, candidate_id, tree_dict, *, registry_root)` → `dict | None`。
接收预先构建好的 `tree_dict`，避免重复构建 candidate tree。每个端点先调 `_get_candidate_tree(...)` 一次，然后把 tree 同时传给 `summarize_candidate_evidence_tree_dict(tree)` 和 `_compute_certainty_summary_from_tree(session, id_, tree, ...)`。

## 6. Boundaries And Invariants

- **Additive only**：`certainty_lines` 是新增 key，不改已有 6 个 section 的内容
- **Backward compatible**：`certainty_summary=None`（默认）时输出完全不变
- **不改 12-field core summary**：certainty_summary 是 response-level sibling，不嵌入 summary
- **不改 CertaintySummary dataclass**：消费已有结构
- **不改 derive_certainty_summary()**：消费已有函数
- **Conditions 不排序**：保持 atom position order
- **只影响 runtime delivery**：narrative/NL 函数本身是 delivery-agnostic，但本轮只在 runtime 端点传入 certainty_summary
- **override_registry_root 语义一致**：narrative/NL 端点也支持 `override_registry_root`，和 explain-summary 端点行为一致

## 7. Acceptance

- [x] `confidence_kind="certainty"` 且有 `certainty_summary` 时，runtime narrative 输出包含 `certainty_lines` section
- [x] `confidence_kind="certainty"` 且有 `certainty_summary` 时，runtime NL 输出包含第 5 段 certainty 段落
- [x] 无 `certainty_summary` 时（`confidence_kind="none"` / `"probability"` / ineligible），narrative/NL 输出与当前完全一致
- [x] 不触碰 audit package、static site、probability lane、排序语义
- [x] `_compute_certainty_summary_from_tree` 共享 helper 存在，接收预建 tree_dict，explain-summary 也改为调用它
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

### Phase 1：提取共享 helper

1. **[service/runtime_v1.py]** 提取 `_compute_certainty_summary_from_tree(session, candidate_id, tree_dict, *, registry_root) -> dict[str, Any] | None`：
   - 接收预先构建的 `tree_dict`，封装 `_extract_single_referenced_support_tree` → `_lookup_condition_weights_for_candidate` → `derive_certainty_summary` → `_certainty_summary_to_dict` 链路
   - `explain_runtime_summary` 的 `kind="candidate"` 分支改为：先 `_get_candidate_tree`，再分别调 `summarize_candidate_evidence_tree_dict(tree)` 和 `_compute_certainty_summary_from_tree(session, id_, tree, ...)`
   - 验证全量 green（行为不变）

### Phase 2：Narrative 扩展

2. **[core/store/_candidate_evidence_tree_narrative.py]** 扩展 `render_candidate_evidence_tree_narrative`：
   - 新增 keyword-only `certainty_summary: dict[str, Any] | None = None`
   - `certainty_summary is not None` 时生成 `certainty_lines` section
   - `certainty_summary is None` 时返回值不含 `certainty_lines`
3. **[service/runtime_v1.py]** `explain_runtime_narrative` 的 `kind="candidate"` 分支传入 `certainty_summary`
4. **[tests/test_certainty_explain_contracts.py]** 新增 narrative certainty 测试

### Phase 3：NL 扩展

5. **[core/store/_candidate_evidence_tree_nl.py]** 扩展 `render_candidate_evidence_tree_nl_explain`：
   - 签名不变（不新增 `certainty_summary` 参数）
   - 检查 `narrative.get("certainty_lines")`，有值时追加第 5 段
6. **[service/runtime_v1.py]** `explain_runtime_nl` 的 `kind="candidate"` 分支：narrative 已携带 `certainty_lines`，NL 自动消费，无需额外传参
7. **[tests/test_certainty_explain_contracts.py]** 新增 NL certainty 测试

### Phase 4：Backward compatibility + docs

8. **[tests/test_evidence_tree_explain_contracts.py]** 确认现有 narrative/NL tests 不受影响（无 `certainty_lines` / 无第 5 段）
9. **[docs]** 同步模块文档：`03_runtime_queries_views.md`、`core/annotation/docs/README.md`

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/core/annotation/docs/README.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（如有变更）

## 10. Outcome / Deviations

- 最终落地结果：
  - `runtime_v1.py` 新增 `_compute_certainty_summary_from_tree(...)`，并让 `explain-summary` / `explain-narrative` / `explain-nl` 共用同一条 certainty 派生链路
  - `render_candidate_evidence_tree_narrative(...)` 新增 keyword-only `certainty_summary=None`，certainty lane 时附加 `certainty_lines`
  - `render_candidate_evidence_tree_nl_explain(...)` 保持签名不变；当 narrative 含 `certainty_lines` 时追加第 5 段 certainty paragraph
  - 新增 direct render + runtime integration tests；全量回归 `209` tests green
- 与 blueprint 不同的地方：
  - 无实质偏差
- 为什么会有这些调整：
  - 不适用
- 归档说明：
  - blueprint 已完成，可归档到 `docs/blueprints/archive/`
