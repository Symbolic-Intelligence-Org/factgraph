# Blueprint: Evidence Explain Depth（事实溯源 + 逐步路径解释）

- Status: implemented
- Created: 2026-03-31
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_nl.py`
  - `src/factpy_kernel/core/store/_candidate_provenance_timeline.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
- Audit Log:
  - [2026-03-31_evidence-explain-depth.audit.md](./2026-03-31_evidence-explain-depth.audit.md)

---

## 1. 问题

当前 Evidence Tree 的解释管线（narrative → NL → HTML）只在**聚合层**产出：

- NL 的 `explain-nl` 输出 "发现 3 个 witnesses"，而不是 "Alice 的 name=Alice 满足了条件 X"
- Narrative 从 `summary.witness_assertion_count` 读取总数，不遍历单个 `assertion_fact` 节点
- HTML 渲染每个节点的树形结构，但没有步骤序号、没有 "为什么这个事实重要" 的说明
- `assertion_fact` 节点不携带该事实的来源元数据（source / approved_by / trace_id）

这对于需要向用户解释 "结论为什么成立、经过了哪些步骤、每个事实从哪里来" 的场景（尤其是 LLM agent 生成事实后的可审计性需求）存在明显的解释深度不足。

---

## 2. 目标

### Phase 1 — 事实来源嵌入（Fact Provenance Embedding）

在 `assertion_fact` 节点中内联 AnnotationStore meta 里的来源字段，使解释链可以追溯到 "这个事实从哪里来"。

- `assertion_fact` 节点加 `fact_meta` 字段（可选，只在 meta 有对应字段时填充）
- NL 输出在有 source 时追加来源段落
- HTML 节点在有 source 时显示来源 tooltip

### Phase 2 — 逐步路径解释（Step-by-step Path Explain）

新增 `explain-steps` 端点，返回从证据叶子到结论的有序步骤列表。三个引擎各自按推理结构的自然形态生成步骤，不强行统一格式：

- **Native/Souffle/ProbLog**：bottom-up 树遍历（事实满足 → 规则触发 → 结论）
- **PyReason**：时间线本身已有序，直接映射为步骤

同步交付：
- 步骤 NL 文本（`steps[].description`）
- 步骤 HTML 视图（`render_evidence_steps_html()`）

### Phase 3 — Why-this-fact 反向查询（显式 Defer）

给定 `asrt_id` 查询它参与的所有推理链。依赖 dialog agent 实际落地后 AnnotationStore meta 有足够数据，**此 Phase 不在本 blueprint 范围内**，待 dialog agent 实施后另立蓝图。

---

## 3. Non-Goals

- **树 schema 不变**：不修改现有 tree/timeline 的顶层结构或已有字段
- **Summary dict 不变**：聚合指标层不受影响
- **不新增引擎能力**：不修改各引擎的 adapter 或 provenance capture 逻辑
- **不改变现有端点行为**：`explain-tree`、`explain-summary`、`explain-narrative`、`explain-nl` 的现有输出保持向后兼容
- **不捕获 LLM 内部推理**：`fact_meta.source` 记录的是 AnnotationStore 里的来源字段，不是 LLM 内部推理过程
- **Why-this-fact 反向查询**：Phase 3，defer

---

## 4. 当前状态

### 4.1 assertion_fact 节点结构（`_candidate_evidence_tree.py` `_build_assertion_leaf()` L210-233）

```python
{
  "node_id":    f"asrt:{asrt_id}",
  "node_kind":  "assertion_fact",
  "title":      f"Assertion {asrt_id}",
  "asrt_id":    str,
  "pred_id":    str,
  "e_ref":      str,
  "claim_args": list[dict],   # [{idx, tag, val}, ...]
  "confidence": float | None,
  "children":   []
}
```

`assertion_lookup()` callback 已读取 detail dict（L211-219），但 meta 字段（source、approved_by、trace_id）未被提取进节点。

### 4.2 Narrative 层（`_candidate_evidence_tree_narrative.py` L24-171）

`render_candidate_evidence_tree_narrative()` 只读取 `summary` dict 中的聚合指标（`witness_assertion_count` 等），**不遍历树节点**。assertion_fact 级别的信息无法进入 narrative。

### 4.3 NL 层（`_candidate_evidence_tree_nl.py` L11-71）

`render_candidate_evidence_tree_nl_explain()` 消费 narrative dict，输出：
```python
{"headline": str, "paragraphs": list[str]}
```
当前段落全部来自聚合 narrative，无 per-fact 叙述。

### 4.4 HTML 层（`static_ui.py` `_render_candidate_evidence_node()` L1094-1193）

assertion_fact 节点渲染 `asrt_id`、`pred_id`、`confidence`、`claim_args.val`，有 detail 链接。无步骤序号、无 source 注释。

### 4.5 assertion_detail 的两条路径（关键约束）

`assertion_lookup()` callback 在两条路径下返回不同形状的 detail dict：

| 路径 | 来源 | meta 字段 |
|---|---|---|
| **Runtime** | `_runtime_assertion_detail_for_tree()` (runtime_v1.py L1932-1960) | **无 meta 字段**，只有 `{asrt_id, claim, claim_args, confidence}` |
| **Audit** | `AuditAssertionIndex.get_assertion_detail()` (assertions.py L26-49) | meta 按 kind 分组：`{"str": [{key, value, ...}], "int": [...], ...}` |

两条路径的 meta 形状不同，`_build_assertion_leaf()` 不能直接假设 `detail["meta"]["source"]` 可用。必须有统一的归一化入口（见 §5.1 的设计解法）。

### 4.6 PyReason Timeline Narrative（`_candidate_provenance_timeline.py` L242-292）

`render_candidate_provenance_timeline_narrative()` 输出：
```python
{
  "headline": str,
  "propagation_lines": list[str],  # 每行 "t={time}: ... updated to {bound} by {trigger}"
  "seed_summary": str,
  "convergence": str
}
```
事件已按 time 排序，天然有序，但没有 step_num 字段。

---

## 4.6 冻结设计决策

| ID | 决策 | 理由 |
|---|---|---|
| D-EED1 | `render_candidate_evidence_tree_narrative()` 加可选 keyword-only 参数 `tree: dict[str, Any] \| None = None` 和 `locale: str = "en"`，保持现有调用兼容 | 从树里抽取更深解释素材是 narrative 层自己的职责，不应散落到 runtime_v1 预处理 |
| D-EED2 | 步骤描述语言 v1 固定英文；`locale` 参数保留但 v1 只产出英文文本 | 与现有 NL surface 一致，避免本轮 scope 被 i18n 扩大 |
| D-EED3 | `explain-steps` 采用 flat list；`detail` 字段携带 `depth: int` 和 `parent_node_ref: str \| None` 作为层级提示 | 树形层已有 evidence tree 表达层级；explain-steps 的价值是线性化；PyReason timeline 本身线性，flat DTO 跨引擎对齐更容易；depth/parent_node_ref 保留未来 UI 缩进空间，不改合同 |

---

## 5. 设计

### 5.0 合同变更声明（Contract Fork）

**D-EED1 是架构合同变更，必须与文档同步更新。**

当前 `01_architecture.md`（L317-318）和 `03_runtime_queries_views.md` 明确声明：

> `candidate_evidence_tree_narrative` 由 `store._candidate_evidence_tree_narrative` **从 summary 纯派生**

D-EED1 将这一合同改为：

> `candidate_evidence_tree_narrative` 由 `summary` 派生，**可选接受 `tree` 参数以输出更深解释素材（source_lines）**；不传 `tree` 时行为与之前完全一致

此变更必须在 Phase 1 实施过程中同步更新这两份文档，否则"代码真相"与"文档真相"分裂。文档更新计入 §6 实施步骤（P1-6）。

---

### 5.1 Phase 1：assertion_fact 加 fact_meta

#### 5.1.1 fact_meta 归一化策略

由于 runtime/audit 两条路径的 detail 形状不同（§4.5），必须在 tree builder 层做归一化，而不是直接读 `detail["meta"]`。

**步骤一：扩展 runtime 路径，让它携带扁平 meta**

`_runtime_assertion_detail_for_tree()` (runtime_v1.py L1932-1960) 目前不返回 meta。需要扩展：从 ledger 的 AnnotationRow 里读取 `source`、`source_loc`、`approved_by`、`trace_id`、`note`，以扁平 dict 形式加进返回值。

```python
# 扩展后增加字段
"flat_meta": {
    "source":       str | None,
    "source_loc":   str | None,
    "approved_by":  str | None,
    "trace_id":     str | None,
    "note":         str | None,
}  # 全为 None 时整个字段可省略或置 None
```

**步骤二：audit 路径归一化**

`AuditAssertionIndex.get_assertion_detail()` 返回 `meta[kind][rows]`。需要在 tree builder 里加归一化 helper，将 kind-grouped rows 转为扁平 dict。

**步骤三：tree builder 统一消费**

新增私有 helper：

```python
def _extract_fact_meta(detail: dict) -> dict | None:
    """
    归一化两条路径的 meta：
    - 若 detail 有 flat_meta（runtime 路径）→ 直接用
    - 若 detail 有 meta（audit 路径，kind-grouped）→ 从 str rows 提取 key/value
    - 若两者都没有 → 返回 None
    """
```

`_build_assertion_leaf()` 只调用 `_extract_fact_meta(detail)`，不直接访问 detail["meta"]。

节点新增字段：
```python
"fact_meta": fact_meta   # dict | None
```

**只读取，不修改任何 meta 写入逻辑。**

#### 5.1.2 Narrative 扩展

冻结后的函数签名（D-EED1）：

```python
def render_candidate_evidence_tree_narrative(
    summary: dict[str, Any],
    *,
    tree: dict[str, Any] | None = None,
    certainty_summary: dict[str, Any] | None = None,
    locale: str = "en",          # v1 只产出英文，参数保留供未来扩展（D-EED2）
) -> dict[str, Any]:
```

当 `tree` 不为 None 时，可选地扫描 assertion_fact 节点，收集有 `fact_meta.source` 的事实，生成：

```python
"source_lines": [
    "credit_score(李四) — from '2026年Q1报告' (approved by agent-session-xyz)",
    ...
]
```

当 `tree` 为 None 时，`source_lines` 不出现在 narrative dict 中（向后兼容，不影响现有调用）。

#### 5.1.3 NL 扩展

消费 `narrative.source_lines`（与现有 certainty_lines / probability_lines 对称）：

```python
if source_lines:
    paragraphs.append(f"Fact sources: {_join_sentences(source_lines)}")
```

#### 5.1.4 HTML 扩展

assertion_fact 节点在有 `fact_meta.source` 时，在 props 列表中追加：

```html
<span class="prop-label">Source</span>
<span class="prop-value" title="{source_loc}">{source}</span>
```

---

### 5.2 Phase 2：explain-steps 端点

#### 5.2.1 输出契约（冻结 DTO）

```python
# DTO 名称：candidate_evidence_steps
{
  "kind":         "candidate_evidence_steps",
  "candidate_id": str,
  "engine":       "native" | "souffle" | "problog" | "pyreason",
  "steps": [
    {
      "step_num":    int,           # 1-indexed
      "step_kind":   str,           # 见下方引擎枚举
      "description": str,           # 人类可读，英文（D-EED2）
      "node_ref":    str | None,    # asrt_id 或 node_id，可用于 detail 链接
      "detail": {
        "depth":           int,           # 0=结论层，数字越大越靠近叶子（D-EED3）
        "parent_node_ref": str | None,    # 父步骤的 node_ref，用于 UI 缩进（D-EED3）
        # ... 引擎自定义字段
      }
    }
  ]
}
```

flat list，通过 `detail.depth` 和 `detail.parent_node_ref` 携带层级信息，UI 可据此缩进展示（D-EED3）。

#### 5.2.2 引擎 step_kind 枚举

| 引擎 | step_kind 取值 | 含义 |
|---|---|---|
| native/souffle | `fact_check` | 某 assertion_fact 满足条件 |
| native/souffle | `rule_apply` | 某规则所有条件均已满足 |
| native/souffle | `conclusion` | 最终结论节点 |
| problog | `proof_leaf_check` | 基础概率事实被使用 |
| problog | `proof_goal_derive` | 中间 proof_goal 导出 |
| problog | `conclusion` | 最终概率结论 |
| pyreason | `bound_seed` | T=0 初始化 bound |
| pyreason | `bound_update` | T>0 规则传播更新 bound |
| pyreason | `convergence` | 收敛事件（最终 bound） |

#### 5.2.3 Native/Souffle/ProbLog 树遍历

新函数：`build_candidate_evidence_steps(tree: dict) -> list[dict]`

位置：`src/factpy_kernel/core/store/_candidate_evidence_tree_steps.py`（新建）

遍历策略（bottom-up，DFS 后序）：

**节点信息约束（来自 §4.5 代码勘查）**：
- `support_section` 节点无 rule label，只有 `node_id`
- `candidate_result` 节点无 `pred_id` / entity，只有 `root_result_kind` 和 `binding`
- `rule_ref` 节点有 `rule_ref_id`（可用于命名）
- 因此 `rule_apply` 和 `conclusion` 的文案必须退化处理，不能假设命名信息存在

```
1. assertion_fact 叶节点 → step_kind=fact_check
   description: "Fact {pred_id}({e_ref}) = {val} ✓"
   node_ref: asrt_id
   detail: {depth, parent_node_ref, pred_id, e_ref, claim_args, confidence, fact_meta}

2. predicate_witness_group → 不单独生成步骤，只作为分组语义

3. support_section → step_kind=rule_apply
   description:
     - 若 children 中含 rule_ref 且有 rule_ref_id：
       "Rule '{rule_ref_id}' support group satisfied: {N} condition(s) met"
     - 否则（无命名信息）：
       "Support group satisfied: {N} condition(s) met"
   node_ref: node_id
   detail: {depth, parent_node_ref, rule_ref_id | None, witness_count}

4. referenced_support（递归规则链）→ 子树步骤先展开（depth+1），再生成 parent rule_apply

5. candidate_result → step_kind=conclusion
   description:
     - 若 binding 非空：
       "Candidate {candidate_id} established ({root_result_kind})"
     - 否则：
       "Candidate {candidate_id} established"
   node_ref: node_id（candidate_result 的 node_id）
   detail: {depth: 0, parent_node_ref: None, root_result_kind, binding}
```

ProbLog 的 proof_goal/proof_leaf 使用同样的 DFS 后序，step_kind 不同：
- `proof_leaf` → `proof_leaf_check`，description: "Proof leaf: {goal} (p={probability})"
- `proof_goal` → `proof_goal_derive`，description: "Proof goal: {goal} derived"

#### 5.2.4 PyReason Timeline → Steps

新函数：`build_candidate_provenance_steps(timeline: dict) -> list[dict]`

位置：`src/factpy_kernel/core/store/_candidate_provenance_timeline.py`（追加）

直接将 `chain.events` 的时间序列映射为步骤，无需遍历算法。

#### 5.2.5 新端点

路径遵循现有 explain family 约定（全部为 POST + `/v1/runtime/sessions/{session_id}/queries/` 前缀）：

```
POST /v1/runtime/sessions/{session_id}/queries/explain-steps
```

Payload（与现有 `explain-tree`、`explain-nl` 一致）：
```python
{
  "kind": "candidate",
  "id":   "<candidate_id>",
  # 可选：
  "certainty_aggregation": "bottleneck" | "additive"
}
```

位置：`src/factpy_kernel/service/app_v1.py` + `src/factpy_kernel/service/runtime_v1.py`

Runtime 函数：`explain_runtime_steps(session_id: str, payload: dict) -> dict`

分发逻辑与现有 `_get_candidate_tree()` 对称：
- `support_kind == PYREASON_PROVENANCE_KIND` → `build_candidate_provenance_steps()`
- 其他 → `build_candidate_evidence_steps()`

#### 5.2.6 Steps HTML 渲染（helper 交付，不承诺独立页面）

新函数：`render_evidence_steps_html(steps: list[dict]) -> str`

位置：`src/factpy_kernel/audit/static_ui.py`（追加，不修改现有函数）

输出：有序列表（`<ol>`），每个步骤：

```html
<li class="step step-{step_kind}">
  <span class="step-num">{step_num}</span>
  <span class="step-desc">{description}</span>
  [<a href="/evidence/{node_ref}">detail</a>]  ← 仅当 node_ref 非空时
</li>
```

**交付边界**：本 Phase 只交付 `render_evidence_steps_html()` helper 函数和对应测试。将 steps HTML 接入 candidate detail page 或独立路由，属于后续 UI 集成工作，**不在本 blueprint 范围内**。

---

## 6. 实施计划

### Phase 1（事实来源嵌入）

| 步骤 | 文件 | 改动 |
|---|---|---|
| P1-1 | `service/runtime_v1.py` L1932-1960 | `_runtime_assertion_detail_for_tree()` 扩展：返回 `flat_meta` dict（source/source_loc/approved_by/trace_id/note）|
| P1-2 | `core/store/_candidate_evidence_tree.py` | 新增 `_extract_fact_meta(detail)` helper；`_build_assertion_leaf()` L210-233 调用它加 `fact_meta` 字段 |
| P1-3 | `_candidate_evidence_tree_narrative.py` L24 | 函数签名加 `tree: dict \| None = None` + `locale: str = "en"`（D-EED1）；扫描 assertion_fact 生成 `source_lines` |
| P1-4 | `_candidate_evidence_tree_nl.py` L11 | 消费 `source_lines` → 追加段落 |
| P1-5 | `audit/static_ui.py` L1156 | assertion_fact 节点渲染 `fact_meta.source` tooltip |
| P1-6 | 文档 | `core/docs/01_architecture.md` L317-318 + `service/docs/03_runtime_queries_views.md`：更新 narrative 合同声明（Contract Fork §5.0）|
| P1-7 | 测试 | `test_assertion_fact_meta_embedding.py` — runtime/audit 两路，有/无 meta 各一组 |

### Phase 2（逐步路径解释）

| 步骤 | 文件 | 改动 |
|---|---|---|
| P2-1 | `core/store/_candidate_evidence_tree_steps.py`（新建） | `build_candidate_evidence_steps(tree)` — native/souffle/problog DFS 后序遍历；放宽 rule_apply/conclusion 文案（§5.2.3）|
| P2-2 | `core/store/_candidate_provenance_timeline.py` | 追加 `build_candidate_provenance_steps(timeline)` — pyreason 时间线线性映射 |
| P2-3 | `service/runtime_v1.py` | 新增 `explain_runtime_steps(session_id, payload)` + 分发逻辑 |
| P2-4 | `service/app_v1.py` | 新增路由 `POST /v1/runtime/sessions/{session_id}/queries/explain-steps`（统一 POST 风格）|
| P2-5 | `audit/static_ui.py` | 追加 `render_evidence_steps_html(steps)` helper |
| P2-6 | 测试 | `test_candidate_evidence_steps.py` — native/problog/pyreason 各一组 |
| P2-7 | 文档 | `core/docs/01_architecture.md`：更新 explain 管线表格加 explain-steps 端点 |

---

## 7. 验收标准

### Phase 1

- [x] `_extract_fact_meta(detail)` 在 runtime 路径（含 `flat_meta`）和 audit 路径（含 kind-grouped `meta`）均能正确提取，无 meta 时返回 `None`
- [x] `assertion_fact` 节点在 meta 有 source 时包含 `fact_meta: {source: "...", ...}`；无相关字段时 `fact_meta` 为 `None`
- [x] `render_candidate_evidence_tree_narrative()` 不传 `tree` 时输出与当前完全一致（向后兼容）
- [x] `explain-nl` 在 `fact_meta` 有 source 时，`paragraphs` 含 "Fact sources: ..." 段落
- [x] HTML 中有 source 的 assertion_fact 节点渲染 source tooltip；无 source 时渲染与当前一致
- [x] `01_architecture.md` 和 `03_runtime_queries_views.md` narrative 合同描述已更新（Contract Fork §5.0）
- [x] 新增测试：`test_assertion_fact_meta_embedding.py` 全部通过

### Phase 2

- [x] `POST /v1/runtime/sessions/{session_id}/queries/explain-steps` 返回 `kind == "candidate_evidence_steps"` DTO
- [x] Native candidate 的 steps 顺序正确（fact_check 先于 rule_apply 先于 conclusion）；`rule_apply.description` 在无命名时退化为 "Support group satisfied: N condition(s) met"
- [x] ProbLog candidate 的 steps 包含 `proof_leaf_check` → `proof_goal_derive` → `conclusion`
- [x] PyReason candidate 的 steps 按时间排序，`bound_seed` 在前，`convergence` 在后
- [x] 所有 `fact_check` 步骤的 `node_ref` 等于对应 `asrt_id`
- [x] 所有步骤的 `detail.depth` 和 `detail.parent_node_ref` 已正确填写
- [x] `render_evidence_steps_html()` 输出有序列表，步骤顺序与 steps 列表一致
- [x] 现有 `explain-tree`、`explain-nl`、`explain-summary`、`explain-narrative`、`explain-timeline` 端点行为不变
- [x] 新增测试：`test_candidate_evidence_steps.py` 全部通过

---

## 8. 实现注记

### N-EED1：steps traversal 与文案生成解耦

`build_candidate_evidence_steps(tree)` 内部最好拆成两阶段：

1. **Traversal 阶段**：DFS 后序，产出中间 `StepRecord`（dataclass 或 TypedDict），只包含结构信息（node_kind、node_id、depth 等），不含文案
2. **Render 阶段**：遍历 `StepRecord` 列表，统一生成 `description` 字符串

原因：native 和 problog 的节点信息不完全对称，后续修改文案模板时不应牵动 DFS 逻辑；两阶段分离让单测也更容易（可分别测 traversal 输出和 render 输出）。

### N-EED2：Runtime dispatch helper 轻量抽象

`runtime_v1.py` 里 summary/narrative/nl/steps 等 explain family 函数各自重复判断 candidate kind（是 tree path、timeline path 还是 degraded）。建议在 Phase 2 实施时引入一个轻量共用 helper（如 `_resolve_candidate_explain_source(session, candidate_id)`）返回统一的 explain source enum，供各 explain 函数复用，避免 kind 分发逻辑散落多处。此为实现建议，不是 blocker。

## 9. 开放问题

所有开放问题已在 2026-03-31 scoping 阶段关闭，决策冻结为 D-EED1 / D-EED2 / D-EED3（见 §4.6）。

---

## 10. Outcome

- **最终落地结果**：Phase 1 和 Phase 2 全部完成，709 tests green。
  - Phase 1：`_extract_fact_meta()` 归一化两条路径（runtime `flat_meta` + audit kind-grouped `meta`）；`assertion_fact` 节点在有 source 时携带 `fact_meta` 字段；narrative 增加可选 `source_lines`（D-EED1 Contract Fork）；NL 追加 "Fact sources:" 段落；HTML assertion_fact 节点渲染 source tooltip；`_runtime_assertion_detail_for_tree()` 读取 AnnotationStore str-kind meta；audit/query.py 接线；23 新测试。
  - Phase 2：新建 `_candidate_evidence_tree_steps.py`（N-EED1 两阶段设计：`_StepRecord` traversal + `_describe_step` render）；`build_candidate_provenance_steps()` 追加到 `_candidate_provenance_timeline.py`；`explain_runtime_steps()` + dispatch 分支加入 `runtime_v1.py`；`POST .../queries/explain-steps` 路由加入 `app_v1.py`；`render_evidence_steps_html()` helper 加入 `static_ui.py`；`01_architecture.md` 补 explain-steps 区段；50 新测试。

- **与 blueprint 不同的地方**：
  1. **`engine` 字段值为 `support_kind` 字符串**（如 `native_binding_v1`），而非 blueprint §5.2.1 DTO 示意中的抽象名（`"native"`）。实际响应中 `support_kind` 直接透传，消费方可从中推断引擎。
  2. **`render_evidence_steps_html()` detail link href 无对应 live route**：`href='/evidence/{node_ref}'` 是预留占位符，当前无独立页面接收。blueprint §5.2.6 已明确标注"不在本范围内"，与边界一致。
  3. **N-EED2 dispatch helper 未提取**：`explain_runtime_steps()` 内部仍自行判断 `support_kind`，未抽取共用 `_resolve_candidate_explain_source()` helper。N-EED2 是实施建议而非 blocker，后续 explain family 增长时可统一提取。
  4. **`render_evidence_steps_html()` 测试未覆盖 HTML 输出细节**：Phase 2 测试集中于 builder 层（steps list），HTML render 逻辑在 Phase 1 的 `static_ui` 测试体系之外，属于非阻塞延迟。

- **为什么会有这些调整**：
  - `engine` 字段选 `support_kind` 是在实现时发现 runtime 层已有 `support_kind` 直通，避免重复映射维护两套语义命名表；blueprint 示意值为说明性占位，不是冻结合同。
  - `render_evidence_steps_html()` 的 href 问题是 blueprint 已预见的 Phase 2 边界：Steps HTML helper 交付，UI 集成 defer。
  - N-EED2 属于提醒性建议，当前 explain family 函数尚在接受范围内，不需要提前重构。

- **归档说明**：Phase 3（Why-this-fact 反向查询）显式 defer，待 dialog agent 实施后另立蓝图。`render_evidence_steps_html()` 接入 candidate detail page 属于后续 UI 集成，不在本 blueprint 范围内。
