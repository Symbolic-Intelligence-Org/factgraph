# Audit Log: S6b — ProbLog adapter → paths-model

Paired with [2026-06-09_explain-layer-s6b-problog.md](./2026-06-09_explain-layer-s6b-problog.md).

---

## A. Preflight (2026-06-09)

- `problog_trace_to_evidence_graph`(provenance.py:187,794 行)现 build call frames → nodes/edges(flat-DAG);import 自 `audit.evidence_graph`(:10/16-18)。
- `ProbLogTraceV0.answers`(:59)= 多 proof。
- SDK:`_row_graph_builder_for_engine`(store.py:2815,S6a 建)+ `_row_provenance_envelopes`(:2808;`PROBLOG_PROVENANCE_KIND`:94)。

## B. Locked decisions(复用 S6a pattern)

- problog converter → paths-model;每 answer 一棵 EvidenceTree;`tree.certainty=Certainty(p,p,"probabilistic")`;聚合 → `EvidenceGraph.certainty`(design §6:433/457)。
- dispatch via `_row_provenance_envelopes`(per-engine builder,S6a 的 `_row_graph_builder_for_engine` 加 problog 分支)。
- Q-S6-A fallback:失败 → minimal(保不变式)。
- scope 限 problog;不碰 pyreason/souffle/audit。

## C. Open items for Codex

- envelope → ProbLogTraceV0 提取(`problog_trace_from_dict`);answer→EvidenceTree 的 head/body 映射(结构同 souffle/native)。
- 聚合概率 → `EvidenceGraph.certainty` 的算法(多 answer 时取何值;design §6 "聚合存 EvidenceGraph.certainty",具体聚合你定/记录)。
- repr_text 最小(schema 烘焙非重点)。

## D. Gate result (Claude 独立验证 2026-06-09)

impl `0d48de22`(parent = S6b 蓝图 `3e28bcf3`,线性栈)。**PASS**:
- scope:5 文件(problog provenance + sdk/store + docs + 2 tests);**pyreason/souffle/audit 未碰**。
- converter → paths:`paths=trees`(:239)、per-answer tree、`Certainty(probabilistic)`(:385/398);不再 import audit。
- dispatch:`_problog_row_graph_builder`(store:2865)engine==problog via `_row_provenance_envelopes`。
- `test_converter_maps_multiple_answers_to_multiple_trees`:`len(paths)==2`;probabilistic certainty(:72/77)。
- cohort 49 OK(独立)/ Codex 41 + 105。

裁决:**PASS**。

## E. S6c 复用

per-engine dispatch + Q-S6-A fallback pattern 已经 souffle + problog 双验证;S6c PyReason(timeline)复用同 pattern,经 `_row_provenance_envelopes`(PYREASON_PROVENANCE_KIND）。
