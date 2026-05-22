# Audit Log: ProbLog CandidateEvidenceTree

## 2026-03-30 — Draft

- Blueprint created.
- Design direction: ProbLog trace is tree-shaped → naturally maps to CandidateEvidenceTree (same contract as native/souffle), no new contract needed.
- Key decisions frozen: D-PB1 through D-PB10.
- Builder location: `adapters/problog/provenance.py` (same file as existing helpers, no public API changes needed).
- Scope deliberately thin: most architecture decisions already frozen in parent and sibling blueprints.

## 2026-03-30 — Review Round 1

Findings addressed:
- [P1] D-PB2 重写：撤回"使用现有 taxonomy 不扩展"。新增 `proof_goal` + `proof_leaf` node_kind，避免 witness 语义错位。ProbLog proof frame 不是 witness，不能复用 `predicate_witness_group` / `assertion_fact`。
- [P1] D-PB4 重写：probability 从 `engine_meta` 改为 response-level sibling（类似 `certainty_summary`），确保 summary/narrative 可消费。
- [P1] D-PB8 降级：撤回"自动兼容"。summary/narrative 需要适配新 `proof` role，不再是纯 additive。
- [P2] D-PB3 废弃：`proof_leaf` 不携带 `asrt_id`，从根源避免 static UI 死链接。
- Implementation steps 从 4 步扩展到 8 步，包含 summary/narrative/static UI 适配。

Status: 仍在 draft，等第二轮 review。

## 2026-03-30 — Review Round 2

Findings addressed:
- [P1] D-PB4 重写（第二次）：probability 从 response-level sibling 改为 summary → narrative → NL 全链路传播。原因：`explain_runtime_nl` 内部走 `tree → summary → narrative → NL`，不经过 HTTP response，response sibling 会被 NL 跳过。修改后与 `certainty_lines` 完全对称。
- [P1] D-PB8 补充 NL 改动：`_candidate_evidence_tree_nl.py` 适配 `probability_lines`。
- [P2] 新增 D-PB10：显式声明 design fork——本蓝图修订 `01_architecture.md` 的 node_kind taxonomy 和 summary core set。
- Implementation steps 从 8 步扩展到 9 步，新增 Step 4 (NL) 和 Step 9 (architecture docs)。
- Acceptance criteria 更新：移除 response sibling 相关，新增 NL + architecture docs 条目。

Status: 推 walkthrough。

## 2026-03-30 — Review Round 3

Findings addressed:
- [P2] D-PB10 补齐：从"taxonomy + summary"扩展到"taxonomy + summary + narrative shape + NL shape"，覆盖全部 4 个冻结 contract 变更。
- Audit log 首段 D-PB 范围修正：D-PB1 through D-PB9 → D-PB1 through D-PB10。

无新阻塞。Status: draft → scoped。可开始实现。

## 2026-03-30 — Implementation Complete

- `adapters/problog/provenance.py` 新增 `problog_trace_to_candidate_evidence_tree()`，将 ProbLog call frame tree 投影为 `CandidateEvidenceTree`。
- `proof_goal` / `proof_leaf` node kinds 已接入 summary / narrative / NL / static UI。
- runtime `explain-tree` / `explain-summary` / `explain-narrative` / `explain-nl` 现在支持 accepted ProbLog candidate；pre-accept candidate 仍因 payload 不可回溯而返回 `explain_not_supported`。
- `01_architecture.md`、`02_problog_adapter.md`、`03_runtime_queries_views.md`、`examples/06_problog_probabilistic.ipynb` 已同步到当前实现真相。
- Regression coverage:
  - targeted unittest slice通过：`test_engine_provenance_surface`、`test_problog_candidate_evidence_tree`
  - implementation phase full suite已达 626+ green；本轮仅补文档/example，无额外代码回归

Status: implemented.
