# Audit Log: S6a — Souffle adapter → paths-model

Paired with [2026-06-09_explain-layer-s6a-souffle.md](./2026-06-09_explain-layer-s6a-souffle.md).

---

## A. Preflight (2026-06-09)

- `souffle_proof_tree_to_evidence_graph`(provenance.py:48)现 build nodes/edges(flat-DAG);import 自 `factgraph.audit.evidence_graph`(:11)。
- SDK `_row_support_artifacts_for_candidates`(store.py:2840)→ `Mapping[str, ProofReceipt]`;注入 :2790;S5 `_row_graph_builder`(:2785)仅 native。
- 目标:application/explain 的 EvidenceGraph/Tree/Rule/Atom/Source。

## B. S6 拆法(Codex + Claude 一致,2026-06-09)

S6a Souffle(tree,最简,验证 dispatch 模式)→ S6b ProbLog(多 proof→多 tree)→ S6c PyReason(timeline)→ S6d audit facade re-export + 旧 flat-DAG 终清。
顺序理由:adapter 各自先改 import 到 `application.explain` 独立收口;audit re-export 最后做(确保旧 flat-DAG 无 active producer 再动公共 namespace,避免半迁移)。

## C. Locked decisions

- souffle converter → paths-model;不再 import audit.evidence_graph。
- dispatch via `_row_support_artifacts`(ProofReceipt → SouffleProofTreeV0);engine==souffle 注入专门 builder。
- Q-S6-A fallback:converter 失败 → minimal paths(保 `{passed,failed}↔evidence`,不返 unsupported)。
- scope 限 souffle;不碰 problog/pyreason/audit。

## D. Open items for Codex

- ProofReceipt → SouffleProofTreeV0 提取路径(`_row_support_artifacts` 存 ProofReceipt,converter 要 SouffleProofTreeV0)—— 确认 ProofReceipt 是否携 souffle proof tree dict。
- souffle proof tree node→EvidenceRule 映射(root=head;rule node=body;axiom=atom/Source);多分支 proof 是否产多 tree(souffle 通常单 proof)。
- repr_text 本片给最小(atom_text);schema 烘焙非重点。

## E. Gate result / Deviations

impl + gate 后填写。
