# Implementation Blueprint: ProbLog CandidateEvidenceTree

- Status: implemented
- Created: 2026-03-30
- Last Updated: 2026-03-30
- Parent: [2026-03-28_evidence-graph-unified-explain.md](./2026-03-28_evidence-graph-unified-explain.md)
- Sibling: [2026-03-30_pyreason-runtime-explain-timeline.md](./2026-03-30_pyreason-runtime-explain-timeline.md)
- Audit Log: [2026-03-30_problog-candidate-evidence-tree.audit.md](./2026-03-30_problog-candidate-evidence-tree.audit.md)

## 1. Problem

ProbLog candidates (`support_kind="problog_provenance_v1"`) 调 `explain-tree` / `explain-summary` / `explain-narrative` / `explain-nl` 全部返回 `runtime_explain_not_supported`。这是三引擎中唯一没有 runtime explain surface 的引擎。

ProbLog 的 `ProbLogTraceV0` 本身是 tree 形（call frame tree），自然方向是接入 `CandidateEvidenceTree` contract（和 native/souffle 相同），不需要像 PyReason 那样新建独立合同。

## 2. Design Decisions

### D-PB1: 接入 CandidateEvidenceTree，不新建合同

ProbLog proof trace 是 tree 形，mapping 到 `kind="candidate_evidence_tree"` 是自然的。不需要像 PyReason 的 `CandidateProvenanceTimeline` 那样新建 contract。

### D-PB2: 新增 2 个 proof-specific node_kind，不复用 witness 语义

现有 `predicate_witness_group` / `assertion_fact` 表示"直接见证 ledger 事实"。ProbLog proof frame 是递归证明步骤，不是 witness。强行复用会导致 summary 把深层 proof 错报为"很多 witness facts、无 rule-chain、递归深度 0"。

新增：
- **`proof_goal`** — 中间证明步骤（有 child goals）。Role: `proof`。
- **`proof_leaf`** — 终端事实（无 children，succeeded）。Role: `proof`。

不复用 `predicate_witness_group`（避免 witness 语义污染），不复用 `assertion_fact`（避免 synthetic asrt_id 死链接）。

完整 mapping：

| ProbLog call frame 类别 | → node_kind | role |
|---|---|---|
| Root frame (candidate anchor) | `candidate_result` | structural |
| Structural wrapper | `support_section` | structural |
| Non-leaf frame (有 child goals) | `proof_goal` | **proof** (新) |
| Leaf frame (succeeded) | `proof_leaf` | **proof** (新) |
| Leaf frame (failed) | `non_fact_check` status="fail" | constraint |
| Synthetic frames (query/answer/rule_body_*) | 剪枝 | — |

`proof_goal` 字段：`node_id`, `node_kind`, `pred_id`, `goal`, `goal_args`, `children`
`proof_leaf` 字段：`node_id`, `node_kind`, `pred_id`, `goal`, `goal_args`, `children=[]`
**不携带 `asrt_id`**——从根源避免 assertion detail 死链接。

### D-PB3: `_ROLE_BY_NODE_KIND` 扩展

在 `_candidate_evidence_tree_summary.py` 的 `_ROLE_BY_NODE_KIND` dict 中新增：
```python
"proof_goal": "proof",
"proof_leaf": "proof",
```

Summary walker 遇到 `proof` role 时：
- `proof_goal` 计入 `proof_goal_count`（新 summary 字段）
- `proof_leaf` 计入 `proof_leaf_count`（新 summary 字段）
- `proof_goal` 递归深度贡献到 `recursive_depth`（和 `referenced_support` 行为类似）

### D-PB4: probability 进入 summary → narrative → NL 全链路

probability 不作为 response-level sibling。`explain-nl` 内部走 `tree → summary → narrative → NL`，不经过 HTTP response，sibling 会被跳过。正确路径是让 probability 流过完整管线，与 `certainty_lines` 对称。

**数据源**：builder 在 root `candidate_result` 写入 `engine_meta: {"engine": "problog", "probability": 0.42}`。

**Summary**（`_candidate_evidence_tree_summary.py`）：
walker 从 root 的 `engine_meta.probability` 读取，写入 summary dict：
```json
{ "problog_probability": 0.42 }
```
当 `support_kind` 不是 ProbLog 时，字段不存在。

**Narrative**（`_candidate_evidence_tree_narrative.py`）：
当 `summary.problog_probability` 存在时，narrative dict 新增：
```json
{ "probability_lines": ["ProbLog probability: 0.42."] }
```
当不存在时，字段不存在。

**NL**（`_candidate_evidence_tree_nl.py`）：
与 `certainty_lines` 对称。当 `narrative.probability_lines` 存在时：
```python
if probability_lines:
    paragraphs.append(f"Probability assessment: {_join_sentences(probability_lines)}")
```
无 `probability_lines` 时无变化——native/souffle 路径零影响。

### D-PB5: 候选锚定复用现有 best-effort 逻辑

`problog_trace_to_evidence_graph()` 中的 `_select_root_frame()` 已实现 best-effort candidate anchoring。新 builder 复用同一逻辑。若锚定失败，`explain-tree` 返回 `runtime_explain_not_found`（而非 `not_supported`）。

### D-PB6: Builder 放在 adapter 内，不移动 private helpers

`problog_trace_to_candidate_evidence_tree()` 放在 `adapters/problog/provenance.py`（和 `problog_trace_to_evidence_graph()` 同文件）。直接调用同文件的 `_build_call_frames`、`_select_root_frame` 等 private helpers，不需要公开化。

### D-PB7: runtime_v1.py dispatch 加分支，不改现有路径

在 `_get_candidate_tree()` 的 `raise _runtime_explain_not_supported` 之前加 `PROBLOG_PROVENANCE_KIND` 分支。Native/souffle/pyreason 路径零变更。

### D-PB8: Summary/narrative 需要适配 proof role

**撤回"自动兼容"。** 新增 `proof_goal` / `proof_leaf` node_kind 后，summary 和 narrative 都需要改动：

**Summary 改动**（`_candidate_evidence_tree_summary.py`）：
- `_ROLE_BY_NODE_KIND` 新增 `"proof_goal": "proof"`, `"proof_leaf": "proof"`
- `_ROLE_ORDER` 新增 `"proof"` role
- Walk 逻辑：`proof_goal` 贡献 `recursive_depth`（每层 +1），`proof_leaf` 不贡献
- Summary dict 新增 `proof_goal_count` 和 `proof_leaf_count` 字段

**Narrative 改动**（`_candidate_evidence_tree_narrative.py`）：
- 识别 proof role 并生成描述行：
  - `"ProbLog proof tree: {proof_goal_count} intermediate goals, {proof_leaf_count} leaf facts"`
  - `"Proof depth: {recursive_depth}"`

**NL 改动**（`_candidate_evidence_tree_nl.py`）：
- 读取 `narrative.probability_lines`（optional，与 `certainty_lines` 对称）
- 存在时追加 paragraph：`"Probability assessment: {_join_sentences(probability_lines)}"`
- 不存在时无变化——native/souffle 路径零影响

**Static UI 改动**（`static_ui.py`）：
- `proof_goal` / `proof_leaf` 节点渲染为 proof 结构展示，不生成 assertion detail 链接

### D-PB9: 已 accept candidate 限制

与 PyReason timeline 相同的结构性限制：candidate_payload 从 ledger claim 反推。Live explain 目前只对已 accept 的 ProbLog candidate 可用。

### D-PB10: Design Fork — 修订 architecture truth

本蓝图修改了 `01_architecture.md` 中的四个冻结 contract：

1. **node_kind taxonomy**：新增 `proof_goal` / `proof_leaf`。之前 taxonomy 只覆盖 witness-bearing 语义。
2. **summary core set**：新增 `proof_goal_count` / `proof_leaf_count` / `problog_probability`。之前 summary 是 12 字段固定集。
3. **narrative shape**：新增可选 `probability_lines`。之前只允许基础 6 字段 + 可选 `certainty_lines`。
4. **NL shape**：probability 存在时追加 paragraph。之前只在 certainty 存在时追加第 5 段。

这不是 additive extension——是对冻结文档的显式修订。Step 9 会同步更新 `01_architecture.md`，使代码和文档保持单一真相。

## 3. Non-Goals

- 不做 ProbLog 特定的 certainty propagation（ProbLog 的置信度是 probability，不是 condition_weights）
- 不改 `_WITNESS_BEARING_SUPPORT_KINDS`（ProbLog 不产生 SupportArtifact）
- 不改 `explain-timeline` 端点（ProbLog 不是 event-log 形态）
- 不改 EvidenceGraph converter（audit 层已可用，保持不变）

## 4. Implementation Steps

| Step | 描述 | 文件 |
|------|------|------|
| 1 | `problog_trace_to_candidate_evidence_tree()` builder（使用 `proof_goal` / `proof_leaf` node kinds，root 写入 `engine_meta.probability`） | `adapters/problog/provenance.py` |
| 2 | `_ROLE_BY_NODE_KIND` + summary walker 适配 proof role + 读取 `problog_probability` | `core/store/_candidate_evidence_tree_summary.py` |
| 3 | Narrative 适配 proof role + 输出 `probability_lines` | `core/store/_candidate_evidence_tree_narrative.py` |
| 4 | NL 适配 `probability_lines`（与 `certainty_lines` 对称） | `core/store/_candidate_evidence_tree_nl.py` |
| 5 | `_get_candidate_tree()` 加 `PROBLOG_PROVENANCE_KIND` 分支 + helper | `service/runtime_v1.py` |
| 6 | Static UI 适配 `proof_goal` / `proof_leaf` 渲染 | `audit/static_ui.py` |
| 7 | 测试：builder + summary + narrative + NL + integration | `tests/test_problog_candidate_evidence_tree.py` |
| 8 | 更新 notebook 06 explain status | `examples/06_problog_probabilistic.ipynb` |
| 9 | 更新 `01_architecture.md` node_kind taxonomy + summary contract | `core/docs/01_architecture.md` |

## 5. CandidateEvidenceTree Output Shape (ProbLog)

```json
{
  "kind": "candidate_evidence_tree",
  "candidate_id": "cand_v2:abc123",
  "support_digest": "sha256:...",
  "support_kind": "problog_provenance_v1",
  "root": {
    "node_id": "cand:cand_v2:abc123",
    "node_kind": "candidate_result",
    "root_result_kind": "fact",
    "binding": {"arg_0": "vip", "arg_1": "idref_v1:User:user_id=Alice"},
    "rule_refs": [],
    "rule_ref_edges": [],
    "children": [
      {
        "node_id": "support:cand_v2:abc123",
        "node_kind": "support_section",
        "children": [
          {
            "node_id": "problog:cand_v2:abc123:frame:1",
            "node_kind": "proof_goal",
            "pred_id": "user__tag_seed",
            "goal": "user__tag_seed(\"vip\",\"idref_v1:User:user_id=Alice\")",
            "goal_args": ["vip", "idref_v1:User:user_id=Alice"],
            "children": [
              {
                "node_id": "problog:cand_v2:abc123:frame:2",
                "node_kind": "proof_leaf",
                "pred_id": "user__name",
                "goal": "user__name(\"Alice\",\"idref_v1:User:user_id=Alice\")",
                "goal_args": ["Alice", "idref_v1:User:user_id=Alice"],
                "children": []
              }
            ]
          }
        ]
      }
    ]
  }
}
```

## 6. Acceptance Criteria

- [x] `problog_trace_to_candidate_evidence_tree()` 从 ProbLogTraceV0 正确构建 tree
- [x] root node_kind = `candidate_result`
- [x] 中间 proof frame → `proof_goal`，有 `pred_id`, `goal`, `goal_args`, `children`
- [x] 叶子 proof frame → `proof_leaf`，有 `pred_id`, `goal`, `goal_args`, `children=[]`
- [x] `proof_leaf` 不携带 `asrt_id`（无死链接）
- [x] synthetic frames (query/answer/rule_body_*) 被剪枝
- [x] `explain-tree` 对 ProbLog candidate 返回 `kind="candidate_evidence_tree"`（而非 error）
- [x] `explain-summary` 对 ProbLog candidate 返回有效 summary（含 `proof_goal_count`, `proof_leaf_count`）
- [x] `explain-summary` summary dict 含 `problog_probability`
- [x] `explain-narrative` 对 ProbLog candidate 返回有效 narrative（含 proof 描述行 + `probability_lines`）
- [x] `explain-nl` 对 ProbLog candidate 返回 NL paragraph 含 probability 信息
- [x] static UI 渲染 `proof_goal` / `proof_leaf` 不生成 assertion detail 链接
- [x] `01_architecture.md` node_kind taxonomy 和 summary contract 已更新
- [x] native/souffle/pyreason 路径零回归
- [x] 626+ tests green

## 7. Outcome / Deviations

- Implemented as scoped: ProbLog now reuses `CandidateEvidenceTree` rather than introducing a new explain contract.
- Runtime tree family support is intentionally limited to accepted candidates whose payload can be reconstructed from ledger claims; pre-accept candidates still return `explain_not_supported`.
- Raw `explain(kind="candidate")` provenance delivery and audit `EvidenceGraph(tree)` delivery remain unchanged; the new tree family is an additive projected surface on top of the existing ProbLog provenance carrier.
